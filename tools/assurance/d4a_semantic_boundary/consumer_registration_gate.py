from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from effect_protection import EffectProtectionGuard, SQLiteAtomicInboxEffectGuard


class TopicRegistrar(Protocol):
    def register_validated(self, permit: "RegistrationPermit") -> None: ...


@dataclass(frozen=True)
class RegistrationPermit:
    consumer_contract: str
    topic: str
    effect_profile: str
    effect_contract: str
    validation_profile: str = "d4a-inbox-effect-v2"


SUPPORTED_EFFECT_BINDINGS = {
    (
        SQLiteAtomicInboxEffectGuard.profile,
        SQLiteAtomicInboxEffectGuard.__name__,
        SQLiteAtomicInboxEffectGuard.contract_id,
    ): SQLiteAtomicInboxEffectGuard
}


def _effect_binding(manifest: dict) -> tuple[str | None, str | None, str | None]:
    value = manifest.get("inbox", {}).get("effect_protection")
    if not isinstance(value, dict):
        return None, None, None
    return value.get("profile"), value.get("implementation"), value.get("contract")


def validate_manifest(manifest: dict) -> list[str]:
    errors: list[str] = []
    if manifest.get("transport_candidate") != "kafka":
        errors.append("transport_candidate must be kafka for this D4-A source gate")
    if not manifest.get("consumer_contract"):
        errors.append("consumer_contract is required")
    if not manifest.get("topic"):
        errors.append("topic is required")

    inbox = manifest.get("inbox", {})
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
    if (kafka.get("idempotent_producer") or kafka.get("transactions")) and errors:
        errors.append("kafka idempotence/transactions cannot bypass inbox/effect rejection")
    return errors


def issue_registration_permit(manifest: dict) -> RegistrationPermit:
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("; ".join(errors))
    profile, _, contract = _effect_binding(manifest)
    assert profile is not None and contract is not None
    return RegistrationPermit(
        consumer_contract=manifest["consumer_contract"],
        topic=manifest["topic"],
        effect_profile=profile,
        effect_contract=contract,
    )


def register_consumer(manifest: dict, registrar: TopicRegistrar) -> None:
    registrar.register_validated(issue_registration_permit(manifest))


class RecordingRegistrar:
    """Evidence sink for the governed registration boundary; accepts permits only."""

    def __init__(self) -> None:
        self.registrations: list[tuple[str, str, str, str, str]] = []

    def register_validated(self, permit: RegistrationPermit) -> None:
        if not isinstance(permit, RegistrationPermit):
            raise TypeError("topic registration requires a validated RegistrationPermit")
        self.registrations.append(
            (
                permit.consumer_contract,
                permit.topic,
                permit.effect_profile,
                permit.effect_contract,
                permit.validation_profile,
            )
        )


def discover_consumer_manifests(implementation_root: Path) -> list[Path]:
    discovered: list[Path] = []
    for path in sorted(implementation_root.rglob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(value, dict) and "consumer_contract" in value:
            discovered.append(path)
    return discovered


def validate_discovered_consumers(implementation_root: Path) -> RecordingRegistrar:
    manifests = discover_consumer_manifests(implementation_root)
    if not manifests:
        raise SystemExit("no consumer manifests discovered in governed D4 namespace")
    registrar = RecordingRegistrar()
    for path in manifests:
        register_consumer(json.loads(path.read_text(encoding="utf-8")), registrar)
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
