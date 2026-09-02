from __future__ import annotations

from copy import deepcopy

from broker_boundary import (
    AlternateStubTransport,
    KafkaCandidateAdapter,
    assert_broker_facing_paths_do_not_leak_kafka_primitives,
    forbidden_kafka_tokens,
    semantic_transcript,
)
from consumer_registration_gate import RecordingRegistrar, register_consumer


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


def expect_registration_failure(manifest: dict) -> None:
    registrar = RecordingRegistrar()
    try:
        register_consumer(manifest, registrar)
    except ValueError:
        assert registrar.registrations == [], "invalid consumer reached topic registration"
        return
    raise AssertionError("invalid consumer registration unexpectedly passed")


def main() -> int:
    assert_broker_facing_paths_do_not_leak_kafka_primitives()
    assert forbidden_kafka_tokens("class BadPath: offset = broker.offset") == ["offset"]
    assert forbidden_kafka_tokens("class BadPath: consumer_group = 'x'") == ["consumer_group"]

    kafka = KafkaCandidateAdapter()
    alternate = AlternateStubTransport()
    kafka_semantics = semantic_transcript(kafka)
    alternate_semantics = semantic_transcript(alternate)
    assert kafka_semantics == alternate_semantics, "logical semantics changed across transport swap"
    assert kafka.physical_trace != alternate.physical_trace, "test did not exercise distinct physical adapters"

    valid_registrar = RecordingRegistrar()
    register_consumer(deepcopy(VALID), valid_registrar)
    assert valid_registrar.registrations == [("evidence.consumer.protected.v1", "evidence.protected.v1")]

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

    print("d4a_broker_primitive_leak_negative_controls=PASS cases=2")
    print("d4a_semantic_boundary_negative_controls=PASS registration_cases=3")
    print("d4a_transport_swap=PASS adapters=2 logical_transcript_equal=true")
    print("d4a_consumer_registration=PASS protected=accepted unprotected=blocked kafka_eos_bypass=blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
