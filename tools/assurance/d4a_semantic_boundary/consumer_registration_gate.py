from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Protocol


class TopicRegistrar(Protocol):
    def register(self, *, consumer_contract: str, topic: str) -> None: ...


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
    if kafka.get("idempotent_producer") or kafka.get("transactions"):
        # These features are permitted as transport optimizations only. They never
        # substitute for the inbox/effect requirements above.
        if errors:
            errors.append("kafka idempotence/transactions cannot bypass inbox/effect rejection")
    return errors


def register_consumer(manifest: dict, registrar: TopicRegistrar) -> None:
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("; ".join(errors))
    registrar.register(
        consumer_contract=manifest["consumer_contract"],
        topic=manifest["topic"],
    )


class RecordingRegistrar:
    def __init__(self) -> None:
        self.registrations: list[tuple[str, str]] = []

    def register(self, *, consumer_contract: str, topic: str) -> None:
        self.registrations.append((consumer_contract, topic))


def validate_registry(registry: Path) -> None:
    manifests = sorted(registry.glob("*.json"))
    if not manifests:
        raise SystemExit("consumer registry is empty")
    registrar = RecordingRegistrar()
    for path in manifests:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        register_consumer(manifest, registrar)
    print(f"consumer_registration_gate=PASS manifests={len(manifests)} registrations={len(registrar.registrations)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="D4-A actual CI consumer-registration gate")
    parser.add_argument("--registry", required=True, type=Path)
    args = parser.parse_args()
    validate_registry(args.registry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
