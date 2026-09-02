from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class TopicRegistrar(Protocol):
    def register_validated(self, permit: "RegistrationPermit") -> None: ...


@dataclass(frozen=True)
class RegistrationPermit:
    consumer_contract: str
    topic: str
    validation_profile: str = "d4a-inbox-effect-v1"


REQUIRED_EFFECT_PROFILES = {"atomic_local", "reconcile_external"}


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
    if inbox.get("effect_protection") not in REQUIRED_EFFECT_PROFILES:
        errors.append("real effect protection profile is required")

    kafka = manifest.get("kafka_features", {})
    if (kafka.get("idempotent_producer") or kafka.get("transactions")) and errors:
        errors.append("kafka idempotence/transactions cannot bypass inbox/effect rejection")
    return errors


def issue_registration_permit(manifest: dict) -> RegistrationPermit:
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("; ".join(errors))
    return RegistrationPermit(
        consumer_contract=manifest["consumer_contract"],
        topic=manifest["topic"],
    )


def register_consumer(manifest: dict, registrar: TopicRegistrar) -> None:
    """Only governed entrypoint from a discovered consumer manifest to topic registration."""
    registrar.register_validated(issue_registration_permit(manifest))


class RecordingRegistrar:
    """Evidence sink for the governed registration boundary; accepts permits only."""

    def __init__(self) -> None:
        self.registrations: list[tuple[str, str, str]] = []

    def register_validated(self, permit: RegistrationPermit) -> None:
        if not isinstance(permit, RegistrationPermit):
            raise TypeError("topic registration requires a validated RegistrationPermit")
        self.registrations.append(
            (permit.consumer_contract, permit.topic, permit.validation_profile)
        )


def discover_consumer_manifests(implementation_root: Path) -> list[Path]:
    """Discover every JSON consumer declaration in the governed D4 namespace."""
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
        manifest = json.loads(path.read_text(encoding="utf-8"))
        register_consumer(manifest, registrar)
    print(
        "consumer_registration_gate=PASS "
        f"discovered={len(manifests)} registrations={len(registrar.registrations)}"
    )
    return registrar


def main() -> int:
    parser = argparse.ArgumentParser(description="D4-A governed consumer-registration CI gate")
    parser.add_argument("--implementation-root", required=True, type=Path)
    args = parser.parse_args()
    validate_discovered_consumers(args.implementation_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
