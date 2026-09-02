from __future__ import annotations

from copy import deepcopy
import json
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
    RegistrationPermit,
    discover_consumer_manifests,
    register_consumer,
    validate_discovered_consumers,
)
from effect_protection import DurableResponsibilityReceipt, SQLiteAtomicInboxEffectGuard
from validate_repository_boundary import (
    KAFKA_TEXT_MARKERS,
    dependency_calls,
    discover_broker_path_declarations,
    scan_nonpython_for_direct_kafka,
)


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
            contract_version=message.contract_version,
            message_id=message.message_id,
            tenant_scope=message.tenant_scope,
            payload='{"device":"canonical-device-1","state":"CORRUPTED"}',
        )
        return super().publish(corrupted)


class VersionCorruptingKafkaAdapter(KafkaCandidateAdapter):
    @staticmethod
    def _decode(record: dict[str, object]) -> LogicalMessage:
        decoded = KafkaCandidateAdapter._decode(record)
        return LogicalMessage(
            contract_name=decoded.contract_name,
            contract_version="v-corrupted",
            message_id=decoded.message_id,
            tenant_scope=decoded.tenant_scope,
            payload=decoded.payload,
        )


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
    semantics = dict(kafka_semantics)
    assert semantics["published_accepted"] is True
    assert semantics["replay_accepted"] is True
    assert semantics["delivered_contract"] == "evidence.device-state.changed"
    assert semantics["delivered_contract_version"] == "v1"
    assert semantics["replayed_contract_version"] == "v1"
    assert semantics["durable_effect_apply_count"] == 1
    assert semantics["durable_effect_scope"] == "tenant-evidence-a"
    assert semantics["durable_responsibility_receipt"] == semantics["replay_durable_responsibility_receipt"]

    corrupting = CorruptingAlternateTransport()
    assert semantic_transcript(corrupting) != kafka_semantics, "payload corruption escaped semantic transcript"

    version_corrupting = VersionCorruptingKafkaAdapter()
    assert semantic_transcript(version_corrupting) != alternate_semantics, "contract-version corruption escaped semantic transcript"

    reconstruction_probe = KafkaCandidateAdapter()
    probe_message = LogicalMessage("probe.contract", "v7", "probe-id", "tenant-probe", "probe-payload")
    reconstruction_probe.publish(probe_message)
    reconstructed = reconstruction_probe.receive("probe.consumer")
    assert reconstructed == probe_message
    assert reconstructed is not probe_message, "Kafka-shaped boundary returned original logical object instead of reconstruction"

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
        raise AssertionError("registrar accepted registration without typed permit")

    forged_typed_permit = RegistrationPermit(
        consumer_contract="bypass",
        topic="topic",
        effect_profile="atomic_local",
        effect_contract="sqlite_atomic_inbox_effect_v1",
        issuance_id="forged-not-issued",
    )
    try:
        valid_registrar.register_validated(forged_typed_permit)
    except PermissionError:
        pass
    else:
        raise AssertionError("registrar accepted typed permit not issued by validation")

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

    malformed_contract = deepcopy(VALID)
    malformed_contract["consumer_contract"] = ["not", "a", "string"]
    expect_registration_failure(malformed_contract)
    malformed_topic = deepcopy(VALID)
    malformed_topic["topic"] = {"not": "a string"}
    expect_registration_failure(malformed_topic)
    whitespace_topic = deepcopy(VALID)
    whitespace_topic["topic"] = "bad topic"
    expect_registration_failure(whitespace_topic)

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        nested = root / "alternate/location"
        nested.mkdir(parents=True)
        valid_path = nested / "consumer.json"
        valid_path.write_text(json.dumps(VALID), encoding="utf-8")
        assert discover_consumer_manifests(root) == [valid_path]

        partial = {
            "transport_candidate": "kafka",
            "topic": "partial.kafka.topic",
            "inbox": {"durable": True},
        }
        partial_path = nested / "partial-consumer.json"
        partial_path.write_text(json.dumps(partial), encoding="utf-8")
        discovered_manifests = discover_consumer_manifests(root)
        assert partial_path in discovered_manifests, "partial Kafka consumer declaration escaped discovery"
        try:
            validate_discovered_consumers(root)
        except ValueError as exc:
            assert "consumer_contract must be a stable nonempty string identifier" in str(exc)
        else:
            raise AssertionError("partial consumer declaration escaped validation")

        external_path = root / "external_broker_path.py"
        external_path.write_text(
            "from broker_boundary import BrokerFacingPath as BFP\n"
            "class EscapingPath(BFP):\n"
            "    def run(self):\n"
            "        return self._port.publish('x')\n",
            encoding="utf-8",
        )
        external = discover_broker_path_declarations([external_path])
        assert list(external.values()) == ["EscapingPath"], "external BrokerFacingPath subclass escaped static discovery"

        csharp = root / "DirectKafka.cs"
        csharp.write_text("using Confluent.Kafka;", encoding="utf-8")
        assert "confluent.kafka" in scan_nonpython_for_direct_kafka(csharp)
        node = root / "direct.js"
        node.write_text("require('node-rdkafka')", encoding="utf-8")
        assert "node-rdkafka" in scan_nonpython_for_direct_kafka(node)
        rust = root / "direct.rs"
        rust.write_text("use rdkafka::consumer::Consumer;", encoding="utf-8")
        assert "rdkafka" in scan_nonpython_for_direct_kafka(rust)
        assert all(marker in KAFKA_TEXT_MARKERS for marker in ("confluent.kafka", "node-rdkafka", "rdkafka"))

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
        adapter.publish(LogicalMessage("c", "v1", "forged-msg", "tenant-a", "payload"))
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

        scoped_adapter = AlternateStubTransport()
        scoped_ack = InboxAcknowledgePath(scoped_adapter, guard)
        scoped_adapter.publish(LogicalMessage("c", "v1", "same-id", "tenant-b", "payload-b"))
        try:
            scoped_ack.acknowledge_after_durable_responsibility(first)
        except ValueError:
            pass
        else:
            raise AssertionError("cross-scope durable receipt acknowledged another scope's message")
        remaining = scoped_adapter.receive("evidence.consumer.v1")
        assert (remaining.tenant_scope, remaining.message_id) == ("tenant-b", "same-id")

    print("d4a_broker_path_discovery=PASS paths=4 external_subclass=detected constructors=checked")
    print("d4a_kafka_sdk_marker_negative_controls=PASS csharp+node+rust")
    print("d4a_semantic_payload_corruption_negative_control=PASS")
    print("d4a_contract_version_boundary=PASS version=separate corruption=detected")
    print("d4a_kafka_record_reconstruction=PASS logical_object=reconstructed")
    print("d4a_effect_protection_binding=PASS fake_label=blocked kafka_eos_only=blocked")
    print("d4a_inbox_identity_scope=PASS cross_scope_same_message_id=independent")
    print("d4a_scoped_ack_identity=PASS cross_scope_receipt=blocked message_preserved=true")
    print("d4a_durable_ack_boundary=PASS forged_receipt=blocked message_preserved=true")
    print("d4a_registration_permit_provenance=PASS forged_typed_permit=blocked")
    print("d4a_registration_identifiers=PASS nonstring+invalid_topic=blocked")
    print("d4a_consumer_manifest_discovery=PASS nested+partial_declarations_detected=true")
    print("d4a_transport_swap=PASS adapters=2 durable_effect_observed=true replay_apply_count=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
