from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from broker_boundary import (
    AlternateStubTransport,
    KafkaCandidateAdapter,
    LogicalMessage,
    assert_discovered_paths_do_not_leak_kafka_primitives,
    discover_broker_facing_paths,
    forbidden_kafka_tokens,
    semantic_transcript,
)
from consumer_registration_gate import (
    RecordingRegistrar,
    RegistrationPermit,
    discover_consumer_manifests,
    register_consumer,
)


VALID = {
    "consumer_contract": "evidence.consumer.protected.v1",
    "transport_candidate": "kafka",
    "topic": "evidence.protected.v1",
    "inbox": {
        "durable": True,
        "dedup_identity": "consumer_contract+message_identity_scope+message_id",
        "effect_protection": "atomic_local",
    },
    "kafka_features": {"idempotent_producer": True, "transactions": True},
}


class CorruptingAlternateTransport(AlternateStubTransport):
    def publish(self, message: LogicalMessage):
        corrupted = LogicalMessage(
            contract_name=message.contract_name,
            message_id=message.message_id,
            tenant_scope=message.tenant_scope,
            payload='{"device":"canonical-device-1","state":"CORRUPTED"}',
        )
        return super().publish(corrupted)


def expect_registration_failure(manifest: dict) -> None:
    registrar = RecordingRegistrar()
    try:
        register_consumer(manifest, registrar)
    except ValueError:
        assert registrar.registrations == [], "invalid consumer reached topic registration"
        return
    raise AssertionError("invalid consumer registration unexpectedly passed")


def main() -> int:
    discovered = discover_broker_facing_paths()
    assert set(discovered) == {
        "OutboxDispatchPath",
        "ConsumerReceivePath",
        "InboxAcknowledgePath",
        "ReplayDispatchPath",
    }
    assert_discovered_paths_do_not_leak_kafka_primitives()
    assert forbidden_kafka_tokens("class BadPath: offset = broker.offset") == ["offset"]
    assert forbidden_kafka_tokens("class BadPath: consumer_group = 'x'") == ["consumer_group"]

    kafka = KafkaCandidateAdapter()
    alternate = AlternateStubTransport()
    kafka_semantics = semantic_transcript(kafka)
    alternate_semantics = semantic_transcript(alternate)
    assert kafka_semantics == alternate_semantics, "logical semantics changed across transport swap"
    assert kafka.physical_trace != alternate.physical_trace, "test did not exercise distinct physical adapters"

    corrupting = CorruptingAlternateTransport()
    assert semantic_transcript(corrupting) != kafka_semantics, "payload corruption escaped semantic transcript"

    valid_registrar = RecordingRegistrar()
    register_consumer(deepcopy(VALID), valid_registrar)
    assert valid_registrar.registrations == [
        ("evidence.consumer.protected.v1", "evidence.protected.v1", "d4a-inbox-effect-v1")
    ]

    try:
        valid_registrar.register_validated({"consumer_contract": "bypass"})  # type: ignore[arg-type]
    except TypeError:
        pass
    else:
        raise AssertionError("registrar accepted registration without validated permit")

    no_inbox = deepcopy(VALID)
    no_inbox["inbox"]["durable"] = False
    expect_registration_failure(no_inbox)

    no_effect = deepcopy(VALID)
    no_effect["inbox"]["effect_protection"] = "none"
    expect_registration_failure(no_effect)

    kafka_eos_only = deepcopy(VALID)
    kafka_eos_only["inbox"] = {
        "durable": False,
        "dedup_identity": "none",
        "effect_protection": "none",
    }
    kafka_eos_only["kafka_features"] = {"idempotent_producer": True, "transactions": True}
    expect_registration_failure(kafka_eos_only)

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        nested = root / "alternate/location"
        nested.mkdir(parents=True)
        (nested / "consumer.json").write_text(__import__("json").dumps(VALID), encoding="utf-8")
        assert discover_consumer_manifests(root) == [nested / "consumer.json"]

    print("d4a_broker_path_discovery=PASS paths=4")
    print("d4a_broker_primitive_leak_negative_controls=PASS cases=2")
    print("d4a_semantic_payload_corruption_negative_control=PASS")
    print("d4a_semantic_boundary_negative_controls=PASS registration_cases=4")
    print("d4a_consumer_manifest_discovery=PASS nested_location_detected=true")
    print("d4a_transport_swap=PASS adapters=2 logical_transcript_equal=true payload_included=true")
    print("d4a_consumer_registration=PASS protected=accepted unprotected=blocked permit_bypass=blocked kafka_eos_bypass=blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
