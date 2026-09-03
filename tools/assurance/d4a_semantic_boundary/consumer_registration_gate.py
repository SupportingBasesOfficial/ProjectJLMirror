from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from jlmirror_async.model import contract_name as canonical_contract_name
from effect_protection import EffectProtectionGuard, SQLiteAtomicInboxEffectGuard


class TopicRegistrar(Protocol):
    def register_validated(self, permit: "RegistrationPermit") -> None: ...


@dataclass(frozen=True)
class RegistrationPermit:
    consumer_contract: str
    topic: str
    effect_profile: str
    effect_contract: str
    issuance_id: str
    validation_profile: str = "d4a-inbox-effect-v2"


_ISSUED_PERMITS: set[RegistrationPermit] = set()

SUPPORTED_EFFECT_BINDINGS = {
    (
        SQLiteAtomicInboxEffectGuard.profile,
        SQLiteAtomicInboxEffectGuard.__name__,
        SQLiteAtomicInboxEffectGuard.contract_id,
    ): SQLiteAtomicInboxEffectGuard
}

CONSUMER_DECLARATION_MARKERS = {
    "consumer_contract",
    "topic",
    "transport_candidate",
    "inbox",
    "kafka_features",
}
GOVERNED_CONSUMER_REGISTRY_DIR_NAMES = {"consumer-registry", "consumer_registry"}

TOPIC_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,248}[A-Za-z0-9]$|^[A-Za-z0-9]$")


def _valid_topic_identifier(value: object) -> bool:
    return isinstance(value, str) and bool(value) and TOPIC_IDENTIFIER_RE.fullmatch(value) is not None


def _valid_consumer_contract(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        canonical_contract_name(value, "consumer_contract")
    except ValueError:
        return False
    return True


def _effect_binding(manifest: dict) -> tuple[str | None, str | None, str | None]:
    inbox = manifest.get("inbox")
    if not isinstance(inbox, dict):
        return None, None, None
    value = inbox.get("effect_protection")
    if not isinstance(value, dict):
        return None, None, None
    return value.get("profile"), value.get("implementation"), value.get("contract")


def validate_manifest(manifest: dict) -> list[str]:
    errors: list[str] = []
    if manifest.get("transport_candidate") != "kafka":
        errors.append("transport_candidate must be kafka for this D4-A source gate")
    if not _valid_consumer_contract(manifest.get("consumer_contract")):
        errors.append("consumer_contract must satisfy canonical async contract-name rules")
    if not _valid_topic_identifier(manifest.get("topic")):
        errors.append("topic must be a stable nonempty Kafka-compatible identifier")

    inbox = manifest.get("inbox", {})
    if not isinstance(inbox, dict):
        errors.append("inbox must be an object")
        inbox = {}
    if inbox.get("durable") is not True:
        errors.append("durable inbox is required")
    if inbox.get("dedup_identity") != "consumer_contract+message_identity_scope+message_id":
        errors.append("trusted inbox dedup identity is required")

    binding = _effect_binding(manifest)
    implementation = SUPPORTED_EFFECT_BINDINGS.get(binding)
    if implementation is None:
        errors.append("effect protection must bind to an executable supported guard contract")
    elif not issubclass(implementation, EffectProtectionGuard):
        errors.append("effect protection implementation must satisfy EffectProtectionGuard")
    elif implementation.binding_descriptor() != {
        "profile": binding[0],
        "implementation": binding[1],
        "contract": binding[2],
    }:
        errors.append("effect protection binding descriptor mismatch")

    kafka = manifest.get("kafka_features", {})
    if not isinstance(kafka, dict):
        errors.append("kafka_features must be an object")
        kafka = {}
    if (kafka.get("idempotent_producer") or kafka.get("transactions")) and errors:
        errors.append("kafka idempotence/transactions cannot bypass inbox/effect rejection")
    return errors


def issue_registration_permit(manifest: dict) -> RegistrationPermit:
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("; ".join(errors))
    profile, _, contract = _effect_binding(manifest)
    assert profile is not None and contract is not None
    permit = RegistrationPermit(
        consumer_contract=manifest["consumer_contract"],
        topic=manifest["topic"],
        effect_profile=profile,
        effect_contract=contract,
        issuance_id=uuid4().hex,
    )
    _ISSUED_PERMITS.add(permit)
    return permit


def register_consumer(manifest: dict, registrar: TopicRegistrar) -> None:
    registrar.register_validated(issue_registration_permit(manifest))


class RecordingRegistrar:
    """Evidence sink for the governed registration boundary; accepts validation-issued permits only."""

    def __init__(self) -> None:
        self.registrations: list[tuple[str, str, str, str, str]] = []

    def register_validated(self, permit: RegistrationPermit) -> None:
        if not isinstance(permit, RegistrationPermit):
            raise TypeError("topic registration requires a validated RegistrationPermit")
        if permit not in _ISSUED_PERMITS:
            raise PermissionError("topic registration permit was not issued by manifest validation")
        _ISSUED_PERMITS.remove(permit)
        self.registrations.append(
            (
                permit.consumer_contract,
                permit.topic,
                permit.effect_profile,
                permit.effect_contract,
                permit.validation_profile,
            )
        )


def _looks_like_consumer_declaration(value: dict) -> bool:
    keys = set(value)
    if value.get("transport_candidate") == "kafka":
        return True
    if "consumer_contract" in keys:
        return True
    if "topic" in keys and ("inbox" in keys or "kafka_features" in keys):
        return True
    return len(keys & CONSUMER_DECLARATION_MARKERS) >= 3


def _is_governed_consumer_registry_path(path: Path, implementation_root: Path) -> bool:
    try:
        relative = path.relative_to(implementation_root)
    except ValueError:
        return False
    return any(part in GOVERNED_CONSUMER_REGISTRY_DIR_NAMES for part in relative.parts[:-1])


def _read_governed_json(path: Path) -> object:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"governed JSON is not valid UTF-8: {path}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"governed JSON is malformed: {path}: {exc.msg}") from exc


def discover_consumer_manifests(implementation_root: Path) -> list[Path]:
    discovered: list[Path] = []
    for path in sorted(implementation_root.rglob("*.json")):
        value = _read_governed_json(path)
        if _is_governed_consumer_registry_path(path, implementation_root):
            discovered.append(path)
            continue
        if isinstance(value, dict) and _looks_like_consumer_declaration(value):
            discovered.append(path)
    return discovered


def validate_discovered_consumers(implementation_root: Path) -> RecordingRegistrar:
    manifests = discover_consumer_manifests(implementation_root)
    if not manifests:
        raise SystemExit("no consumer manifests discovered in governed implementation namespace")
    registrar = RecordingRegistrar()
    for path in manifests:
        value = _read_governed_json(path)
        if not isinstance(value, dict):
            raise ValueError(f"discovered consumer manifest must be a JSON object: {path}")
        register_consumer(value, registrar)
    print(f"consumer_registration_gate=PASS discovered={len(manifests)} registrations={len(registrar.registrations)}")
    return registrar


def main() -> int:
    parser = argparse.ArgumentParser(description="D4-A governed consumer-registration CI gate")
    parser.add_argument("--implementation-root", required=True, type=Path)
    args = parser.parse_args()
    validate_discovered_consumers(args.implementation_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
