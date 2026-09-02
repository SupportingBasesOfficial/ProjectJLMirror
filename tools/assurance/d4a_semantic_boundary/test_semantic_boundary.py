from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from broker_boundary import (
    AlternateStubTransport,
    InboxAcknowledgePath,
    KafkaCandidateAdapter,
    LogicalMessage,
    assert_discovered_paths_do_not_leak_kafka_primitives,
    discover_broker_facing_paths,
    forbidden_kafka_tokens,
    semantic_transcript,
)
from consumer_registration_gate import (
    RecordingRegistrar,
    discover_consumer_manifests,
    register_consumer,
)
from effect_protection import DurableResponsibilityReceipt, SQLiteAtomicInboxEffectGuard
from validate_repository_boundary import dependency_calls


VALID = {
    "consumer_contract": "evidence.consumer.protected.v1",
    "transport_candidate": "kafka",
    "topic": "evidence.protected.v1",
    "inbox": {
        "durable": True,
        "dedup_identity": "consumer_contract+message_identity_scope+message_id",
        "effect_protection": {
            "profile": "atomic_local",
            "implementation": "SQLiteAtomicInboxEffectGuard",
            "contract": "sqlite_atomic_inbox_effect_v1",
        },
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
    assert set(discovered) == {"OutboxDispatchPath", "ConsumerReceivePath", "InboxAcknowledgePath", "ReplayDispatchPath"}
    assert_discovered_paths_do_not_leak_kafka_primitives()
    assert forbidden_kafka_tokens("class BadPath: offset = broker.offset") == ["offset"]
    assert forbidden_kafka_tokens("class BadPath: consumer_group = 'x'") == ["consumer_group"]

    constructor_bypass = """
class BadPath:
    def __init__(self, broker):
        helper(broker)
        self._broker = broker
    def run(self, message):
        return self._broker.publish(message)
"""
    assert dependency_calls(constructor_bypass) == {"helper", "_broker.publish"}

    kafka = KafkaCandidateAdapter()
    alternate = AlternateStubTransport()
    kafka_semantics = semantic_transcript(kafka)
    alternate_semantics = semantic_transcript(alternate)
    assert kafka_semantics == alternate_semantics, "logical semantics changed across transport swap"
    assert kafka.physical_trace != alternate.physical_trace, "test did not exercise distinct physical adapters"
    assert dict(kafka_semantics)["durable_effect_apply_count"] == 1
    assert dict(kafka_semantics)["durable_effect_scope"] == "tenant-evidence-a"
    assert dict(kafka_semantics)["durable_responsibility_receipt"] == dict(kafka_semantics)["replay_durable_responsibility_receipt"]

    corrupting = CorruptingAlternateTransport()
    assert semantic_transcript(corrupting) != kafka_semantics, "payload corruption escaped semantic transcript"

    valid_registrar = RecordingRegistrar()
    register_consumer(deepcopy(VALID), valid_registrar)
    assert valid_registrar.registrations == [
        (
            "evidence.consumer.protected.v1",
            "evidence.protected.v1",
            "atomic_local",
            "sqlite_atomic_inbox_effect_v1",
            "d4a-inbox-effect-v2",
        )
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

    fake_label = deepcopy(VALID)
    fake_label["inbox"]["effect_protection"] = {
        "profile": "atomic_local",
        "implementation": "FakeAtomicGuard",
        "contract": "sqlite_atomic_inbox_effect_v1",
    }
    expect_registration_failure(fake_label)

    kafka_eos_only = deepcopy(VALID)
    kafka_eos_only["inbox"]["effect_protection"] = {
        "profile": "atomic_local",
        "implementation": "KafkaTransactionOnly",
        "contract": "kafka-eos",
    }
    expect_registration_failure(kafka_eos_only)

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        nested = root / "alternate/location"
        nested.mkdir(parents=True)
        (nested / "consumer.json").write_text(__import__("json").dumps(VALID), encoding="utf-8")
        assert discover_consumer_manifests(root) == [nested / "consumer.json"]

        guard = SQLiteAtomicInboxEffectGuard(root / "durable.db")
        first = guard.record_and_apply(
            consumer_contract="evidence.consumer.v1",
            message_identity_scope="tenant-a",
            message_id="same-id",
            payload="payload-a",
        )
        second = guard.record_and_apply(
            consumer_contract="evidence.consumer.v1",
            message_identity_scope="tenant-b",
            message_id="same-id",
            payload="payload-b",
        )
        assert first.effect_key != second.effect_key
        assert first.receipt_id != second.receipt_id
        assert guard.observe_effect(first.effect_key)["message_identity_scope"] == "tenant-a"
        assert guard.observe_effect(second.effect_key)["message_identity_scope"] == "tenant-b"

        adapter = AlternateStubTransport()
        ack = InboxAcknowledgePath(adapter, guard)
        adapter.publish(LogicalMessage("c", "forged-msg", "tenant-a", "payload"))
        forged = DurableResponsibilityReceipt(
            "evidence.consumer.v1",
            "tenant-a",
            "forged-msg",
            "forged",
            "bad",
            "effect",
        )
        try:
            ack.acknowledge_after_durable_responsibility(forged)
        except PermissionError:
            pass
        else:
            raise AssertionError("broker acknowledgement accepted forged/non-durable responsibility")
        assert adapter.receive("evidence.consumer.v1").message_id == "forged-msg", "failed ack removed broker message"

    print("d4a_broker_path_discovery=PASS paths=4 constructors=checked")
    print("d4a_semantic_payload_corruption_negative_control=PASS")
    print("d4a_effect_protection_binding=PASS fake_label=blocked kafka_eos_only=blocked")
    print("d4a_inbox_identity_scope=PASS cross_scope_same_message_id=independent")
    print("d4a_durable_ack_boundary=PASS forged_receipt=blocked message_preserved=true")
    print("d4a_consumer_manifest_discovery=PASS nested_location_detected=true")
    print("d4a_transport_swap=PASS adapters=2 durable_effect_observed=true replay_apply_count=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
