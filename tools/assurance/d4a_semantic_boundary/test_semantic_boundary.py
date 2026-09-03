from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from broker_boundary import (
    AlternateStubTransport, InboxAcknowledgePath, KafkaCandidateAdapter, LogicalMessage,
    assert_discovered_paths_do_not_leak_kafka_primitives, discover_broker_facing_paths,
    forbidden_kafka_tokens, semantic_transcript,
)
from consumer_registration_gate import (
    RecordingRegistrar, RegistrationPermit, discover_consumer_manifests,
    register_consumer, validate_discovered_consumers,
)
from effect_protection import DurableResponsibilityReceipt, SQLiteAtomicInboxEffectGuard
from validate_repository_boundary import (
    BOUNDARY_SOURCE, KAFKA_TEXT_MARKERS, dependency_calls, discover_assurance_dependency_sources,
    discover_broker_path_declarations, scan_nonpython_for_direct_kafka,
    scan_python_for_direct_kafka,
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
        return super().publish(LogicalMessage(
            message.contract_name, message.contract_version, message.message_id,
            message.tenant_scope, '{"device":"canonical-device-1","state":"CORRUPTED"}',
        ))


class VersionCorruptingKafkaAdapter(KafkaCandidateAdapter):
    @staticmethod
    def _decode(record: dict[str, object]) -> LogicalMessage:
        decoded = KafkaCandidateAdapter._decode(record)
        return LogicalMessage(decoded.contract_name, "v-corrupted", decoded.message_id, decoded.tenant_scope, decoded.payload)


def expect_registration_failure(manifest: dict) -> None:
    registrar = RecordingRegistrar()
    try:
        register_consumer(manifest, registrar)
    except ValueError:
        assert registrar.registrations == []
        return
    raise AssertionError("invalid consumer registration unexpectedly passed")


def main() -> int:
    discovered = discover_broker_facing_paths()
    assert set(discovered) == {"OutboxDispatchPath", "ConsumerReceivePath", "InboxAcknowledgePath", "ReplayDispatchPath"}
    assert_discovered_paths_do_not_leak_kafka_primitives()
    assert forbidden_kafka_tokens("class BadPath: offset = broker.offset") == ["offset"]

    constructor_bypass = """class BadPath:\n    def __init__(self, broker):\n        helper(broker)\n        self._broker = broker\n    def run(self, message):\n        return self._broker.publish(message)\n"""
    assert dependency_calls(constructor_bypass) == {"helper", "_broker.publish"}

    kafka = KafkaCandidateAdapter(); alternate = AlternateStubTransport()
    kafka_semantics = semantic_transcript(kafka); alternate_semantics = semantic_transcript(alternate)
    assert kafka_semantics == alternate_semantics
    assert kafka.physical_trace != alternate.physical_trace
    semantics = dict(kafka_semantics)
    assert semantics["published_accepted"] is True and semantics["replay_accepted"] is True
    assert semantics["delivered_contract"] == "evidence.device-state.changed"
    assert semantics["delivered_contract_version"] == "v1"
    assert semantics["replayed_contract_version"] == "v1"
    assert semantics["durable_effect_contract"] == "evidence.device-state.changed"
    assert semantics["durable_effect_contract_version"] == "v1"
    assert semantics["durable_effect_apply_count"] == 1
    assert semantics["durable_effect_scope"] == "tenant-evidence-a"
    assert semantics["durable_responsibility_receipt"] == semantics["replay_durable_responsibility_receipt"]

    assert semantic_transcript(CorruptingAlternateTransport()) != kafka_semantics
    assert semantic_transcript(VersionCorruptingKafkaAdapter()) != alternate_semantics

    reconstruction_probe = KafkaCandidateAdapter()
    probe_message = LogicalMessage("probe.contract", "v7", "probe-id", "tenant-probe", "probe-payload")
    reconstruction_probe.publish(probe_message)
    reconstructed = reconstruction_probe.receive("probe.consumer")
    assert reconstructed == probe_message and reconstructed is not probe_message

    valid_registrar = RecordingRegistrar(); register_consumer(deepcopy(VALID), valid_registrar)
    assert len(valid_registrar.registrations) == 1
    try:
        valid_registrar.register_validated({"consumer_contract": "bypass"})  # type: ignore[arg-type]
    except TypeError: pass
    else: raise AssertionError("registrar accepted untyped permit")
    forged = RegistrationPermit("bypass.contract", "topic", "atomic_local", "sqlite_atomic_inbox_effect_v1", "forged")
    try:
        valid_registrar.register_validated(forged)
    except PermissionError: pass
    else: raise AssertionError("registrar accepted non-issued typed permit")

    for bad in (
        {**deepcopy(VALID), "consumer_contract": ["not", "a", "string"]},
        {**deepcopy(VALID), "consumer_contract": "Not_A.Contract"},
        {**deepcopy(VALID), "consumer_contract": "single"},
        {**deepcopy(VALID), "topic": {"not": "a string"}},
        {**deepcopy(VALID), "topic": "bad topic"},
    ):
        expect_registration_failure(bad)

    no_inbox = deepcopy(VALID); no_inbox["inbox"]["durable"] = False; expect_registration_failure(no_inbox)
    fake_label = deepcopy(VALID); fake_label["inbox"]["effect_protection"] = {"profile":"atomic_local","implementation":"FakeAtomicGuard","contract":"sqlite_atomic_inbox_effect_v1"}; expect_registration_failure(fake_label)

    with TemporaryDirectory() as tmp:
        root = Path(tmp); nested = root / "alternate/location"; nested.mkdir(parents=True)
        valid_path = nested / "consumer.json"; valid_path.write_text(json.dumps(VALID), encoding="utf-8")
        assert discover_consumer_manifests(root) == [valid_path]
        partial = {"transport_candidate":"kafka","topic":"partial.kafka.topic","inbox":{"durable":True}}
        partial_path = nested / "partial.json"; partial_path.write_text(json.dumps(partial), encoding="utf-8")
        assert partial_path in discover_consumer_manifests(root)
        try: validate_discovered_consumers(root)
        except ValueError as exc: assert "canonical async contract-name rules" in str(exc)
        else: raise AssertionError("partial manifest escaped validation")

        malformed_root = root / "malformed"; malformed_root.mkdir()
        (malformed_root / "valid.json").write_text(json.dumps(VALID), encoding="utf-8")
        malformed = malformed_root / "consumer-broken.json"
        malformed.write_text('{"transport_candidate":"kafka",', encoding="utf-8")
        try:
            discover_consumer_manifests(malformed_root)
        except ValueError as exc:
            assert "governed JSON is malformed" in str(exc) and "consumer-broken.json" in str(exc)
        else:
            raise AssertionError("malformed governed consumer JSON was silently skipped")

        external_path = root / "external_broker_path.py"
        external_path.write_text("from broker_boundary import BrokerFacingPath as BFP\nclass EscapingPath(BFP):\n    def run(self):\n        return self._port.publish('x')\n", encoding="utf-8")
        assert list(discover_broker_path_declarations([external_path]).values()) == ["EscapingPath"]

        inheritance_root = root / "inheritance"; inheritance_root.mkdir()
        parent = inheritance_root / "parent.py"
        parent.write_text("from broker_boundary import BrokerFacingPath\nclass ParentPath(BrokerFacingPath):\n    pass\n", encoding="utf-8")
        child = inheritance_root / "child.py"
        child.write_text("from parent import ParentPath\nclass EscapingChild(ParentPath):\n    def dispatch(self, message):\n        return self._transport.send(message)\n", encoding="utf-8")
        descendants = set(discover_broker_path_declarations([parent, child]).values())
        assert descendants == {"ParentPath", "EscapingChild"}

        concrete_alias = inheritance_root / "concrete_alias.py"
        concrete_alias.write_text(
            "from broker_boundary import OutboxDispatchPath as Base\n"
            "class AliasEscapingPath(Base):\n"
            "    def dispatch(self, message):\n"
            "        return self._transport.send(message)\n",
            encoding="utf-8",
        )
        alias_descendants = set(discover_broker_path_declarations([BOUNDARY_SOURCE, concrete_alias]).values())
        assert "AliasEscapingPath" in alias_descendants

        assigned_alias = inheritance_root / "assigned_alias.py"
        assigned_alias.write_text(
            "from broker_boundary import OutboxDispatchPath\n"
            "Base = OutboxDispatchPath\n"
            "Alias2: object = Base\n"
            "class AssignmentEscapingPath(Alias2):\n"
            "    def dispatch(self, message):\n"
            "        return self._transport.send(message)\n",
            encoding="utf-8",
        )
        assignment_descendants = set(discover_broker_path_declarations([BOUNDARY_SOURCE, assigned_alias]).values())
        assert "AssignmentEscapingPath" in assignment_descendants

        conditional_path = inheritance_root / "conditional_path.py"
        conditional_path.write_text(
            "from broker_boundary import OutboxDispatchPath\n"
            "enabled = True\n"
            "if enabled:\n"
            "    Base = OutboxDispatchPath\n"
            "    Alias2: object = Base\n"
            "    class ConditionalEscapingPath(Alias2):\n"
            "        def dispatch(self, message):\n"
            "            return self._transport.send(message)\n",
            encoding="utf-8",
        )
        conditional_descendants = set(discover_broker_path_declarations([BOUNDARY_SOURCE, conditional_path]).values())
        assert "ConditionalEscapingPath" in conditional_descendants

        assurance_root = root / "assurance"; assurance_root.mkdir()
        helpers = assurance_root / "helpers"; helpers.mkdir()
        deeper = helpers / "deeper"; deeper.mkdir()
        entry = assurance_root / "entry.py"
        helpers_init = helpers / "__init__.py"
        deeper_init = deeper / "__init__.py"
        helper = helpers / "guard.py"
        nested_helper = deeper / "more.py"
        entry.write_text("from helpers.guard import run\n", encoding="utf-8")
        helpers_init.write_text("PACKAGE_GUARD = 'loaded'\n", encoding="utf-8")
        deeper_init.write_text("DEEP_PACKAGE_GUARD = 'loaded'\n", encoding="utf-8")
        helper.write_text("from helpers.deeper.more import execute\ndef run(): return execute()\n", encoding="utf-8")
        nested_helper.write_text("def execute(): return 'ok'\n", encoding="utf-8")
        closure = {path.relative_to(assurance_root).as_posix() for path in discover_assurance_dependency_sources([entry], assurance_root)}
        assert closure == {"entry.py", "helpers/__init__.py", "helpers/guard.py", "helpers/deeper/__init__.py", "helpers/deeper/more.py"}

        helpers_init.write_text("def load(client): return client.commit_transaction()\n", encoding="utf-8")
        closure_with_init = discover_assurance_dependency_sources([entry], assurance_root)
        assert helpers_init in closure_with_init
        assert "transaction_api:commit_transaction" in scan_python_for_direct_kafka(helpers_init)

        for name, source, expected in (
            ("commit.py", "def f(self): self.client.commit_transaction()\n", "transaction_api:commit_transaction"),
            ("abort.py", "def f(self): self.transport.abort_transaction()\n", "transaction_api:abort_transaction"),
            ("offsets.py", "def f(self): self.session.send_offsets_to_transaction({})\n", "transaction_api:send_offsets_to_transaction"),
            ("begin.py", "def f(self): self.transport.begin_transaction()\n", "transaction_api:begin_transaction"),
            ("commit_camel.py", "def f(self): self.client.commitTransaction()\n", "transaction_api:commit_transaction"),
            ("offsets_pascal.py", "def f(self): self.transport.SendOffsetsToTransaction({})\n", "transaction_api:send_offsets_to_transaction"),
        ):
            p = root / name; p.write_text(source, encoding="utf-8")
            assert expected in scan_python_for_direct_kafka(p)

        for name, text, marker in (
            ("DirectKafka.cs", "using Confluent.Kafka;", "marker:confluent.kafka"),
            ("SpringKafka.java", "import org.springframework.kafka.core.KafkaTemplate;", "marker:org.springframework.kafka"),
            ("direct.js", "require('node-rdkafka')", "marker:node-rdkafka"),
            ("direct.rs", "use rdkafka::consumer::Consumer;", "marker:rdkafka"),
        ):
            p = root / name; p.write_text(text, encoding="utf-8"); assert marker in scan_nonpython_for_direct_kafka(p)
        assert "org.springframework.kafka" in KAFKA_TEXT_MARKERS

        for name, text, expected in (
            ("tx.rs", "fn apply(client: &impl TransactionPort) { client.commit_transaction(); }", "transaction_api:commit_transaction"),
            ("tx.go", "func apply(client TransactionPort) { client.BeginTransaction() }", "transaction_api:begin_transaction"),
            ("tx.cs", "void Apply(ITransport client) { client.AbortTransaction(); }", "transaction_api:abort_transaction"),
            ("tx.ts", "client.sendOffsetsToTransaction({});", "transaction_api:send_offsets_to_transaction"),
            ("tx.java", "client.commitTransaction();", "transaction_api:commit_transaction"),
            ("tx.kt", "client.abortTransaction()", "transaction_api:abort_transaction"),
        ):
            p = root / name; p.write_text(text, encoding="utf-8")
            assert expected in scan_nonpython_for_direct_kafka(p)

        guard = SQLiteAtomicInboxEffectGuard(root / "durable.db")
        first = guard.record_and_apply(
            consumer_contract="evidence.consumer.v1", message_identity_scope="tenant-a", message_id="same-id",
            contract_name="evidence.contract", contract_version="v1", payload="payload-a",
        )
        second = guard.record_and_apply(
            consumer_contract="evidence.consumer.v1", message_identity_scope="tenant-b", message_id="same-id",
            contract_name="evidence.contract", contract_version="v1", payload="payload-b",
        )
        assert first.effect_key != second.effect_key and first.receipt_id != second.receipt_id

        try:
            guard.record_and_apply(
                consumer_contract="evidence.consumer.v1", message_identity_scope="tenant-a", message_id="same-id",
                contract_name="evidence.contract", contract_version="v2", payload="payload-a",
            )
        except ValueError as exc:
            assert "conflicting immutable semantics" in str(exc)
        else:
            raise AssertionError("same scoped identity accepted changed contract version")

        adapter = AlternateStubTransport(); ack = InboxAcknowledgePath(adapter, guard)
        adapter.publish(LogicalMessage("evidence.contract", "v1", "forged-msg", "tenant-a", "payload"))
        adapter.receive("evidence.consumer.v1")
        forged_receipt = DurableResponsibilityReceipt(
            "evidence.consumer.v1", "tenant-a", "forged-msg", "evidence.contract", "v1", "forged", "bad", "effect"
        )
        try: ack.acknowledge_after_durable_responsibility(forged_receipt)
        except PermissionError: pass
        else: raise AssertionError("forged durable receipt acknowledged message")

        consumer_bound = AlternateStubTransport(); consumer_bound_ack = InboxAcknowledgePath(consumer_bound, guard)
        consumer_bound.publish(LogicalMessage("evidence.contract", "v1", "same-id", "tenant-a", "payload-a"))
        consumer_bound.receive("evidence.consumer.other.v1")
        try: consumer_bound_ack.acknowledge_after_durable_responsibility(first)
        except ValueError: pass
        else: raise AssertionError("consumer A receipt acknowledged consumer B delivery")
        remaining = consumer_bound.receive("evidence.consumer.other.v1")
        assert remaining.message_id == "same-id"

        semantic_bound = AlternateStubTransport(); semantic_bound_ack = InboxAcknowledgePath(semantic_bound, guard)
        semantic_bound.publish(LogicalMessage("evidence.contract", "v2", "same-id", "tenant-a", "payload-a"))
        semantic_bound.receive("evidence.consumer.v1")
        try:
            semantic_bound_ack.acknowledge_after_durable_responsibility(first)
        except ValueError as exc:
            assert "contract semantics" in str(exc) or "semantic digest" in str(exc)
        else:
            raise AssertionError("old durable receipt acknowledged changed immutable delivery semantics")
        remaining_semantic = semantic_bound.receive("evidence.consumer.v1")
        assert remaining_semantic.contract_version == "v2"

    print("d4a_fresh_review_hardening=PASS nested_declarations+python_case_normalization+assignment_aliases+polyglot_case_normalization+package_initializers+nested_imports")
    print("d4a_transport_swap=PASS adapters=2 durable_effect_observed=true replay_apply_count=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())