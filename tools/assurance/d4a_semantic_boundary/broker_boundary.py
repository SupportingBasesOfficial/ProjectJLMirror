from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol
import inspect

from effect_protection import DurableResponsibilityReceipt, SQLiteAtomicInboxEffectGuard


@dataclass(frozen=True)
class LogicalMessage:
    contract_name: str
    contract_version: str
    message_id: str
    tenant_scope: str
    payload: str


@dataclass(frozen=True)
class LogicalReceipt:
    message_id: str
    accepted: bool


class BrokerPort(Protocol):
    def publish(self, message: LogicalMessage) -> LogicalReceipt: ...
    def receive(self, consumer_contract: str) -> LogicalMessage: ...
    def acknowledge(self, consumer_contract: str, message_identity_scope: str, message_id: str) -> None: ...


class DurableResponsibilityVerifier(Protocol):
    def assert_durable(self, receipt: DurableResponsibilityReceipt) -> None: ...


class KafkaCandidateAdapter:
    """Evidence adapter whose logical boundary is reconstructed from a Kafka-shaped physical record."""

    def __init__(self) -> None:
        self._queue: list[dict[str, object]] = []
        self._delivery_consumer: str | None = None
        self.physical_trace: list[dict[str, object]] = []

    @staticmethod
    def _encode(message: LogicalMessage) -> dict[str, object]:
        return {
            "topic": f"evidence.{message.contract_name}.{message.contract_version}",
            "partition": 0,
            "offset": None,
            "headers": {
                "contract_name": message.contract_name,
                "contract_version": message.contract_version,
                "message_id": message.message_id,
                "tenant_scope": message.tenant_scope,
            },
            "value": message.payload,
        }

    @staticmethod
    def _decode(record: dict[str, object]) -> LogicalMessage:
        headers = record.get("headers")
        if not isinstance(headers, dict):
            raise ValueError("physical record headers are required")
        required = ("contract_name", "contract_version", "message_id", "tenant_scope")
        if any(not isinstance(headers.get(key), str) or not headers[key] for key in required):
            raise ValueError("physical record lost canonical logical headers")
        payload = record.get("value")
        if not isinstance(payload, str):
            raise ValueError("physical record payload must reconstruct as string")
        return LogicalMessage(
            contract_name=headers["contract_name"],
            contract_version=headers["contract_version"],
            message_id=headers["message_id"],
            tenant_scope=headers["tenant_scope"],
            payload=payload,
        )

    def publish(self, message: LogicalMessage) -> LogicalReceipt:
        record = self._encode(message)
        record["offset"] = len(self._queue)
        self._queue.append(record)
        self.physical_trace.append(
            {
                "topic": record["topic"],
                "partition": record["partition"],
                "offset": record["offset"],
                "transactional": False,
            }
        )
        return LogicalReceipt(message_id=message.message_id, accepted=True)

    def receive(self, consumer_contract: str) -> LogicalMessage:
        if not self._queue:
            raise LookupError("no logical message available")
        if self._delivery_consumer is None:
            self._delivery_consumer = consumer_contract
        elif self._delivery_consumer != consumer_contract:
            raise PermissionError("current delivery is already bound to another consumer contract")
        self.physical_trace.append({"consumer_group": f"evidence.{consumer_contract}"})
        return self._decode(self._queue[0])

    def acknowledge(self, consumer_contract: str, message_identity_scope: str, message_id: str) -> None:
        if not self._queue:
            raise ValueError("acknowledgement has no current logical message")
        if self._delivery_consumer != consumer_contract:
            raise ValueError("acknowledgement consumer contract does not match current delivery")
        current = self._decode(self._queue[0])
        if (current.tenant_scope, current.message_id) != (message_identity_scope, message_id):
            raise ValueError("acknowledgement does not match current scoped logical message")
        self._queue.pop(0)
        self._delivery_consumer = None
        self.physical_trace.append({"consumer_group": f"evidence.{consumer_contract}", "ack": True})


class AlternateStubTransport:
    def __init__(self) -> None:
        self._queue: list[LogicalMessage] = []
        self._delivery_consumer: str | None = None
        self.physical_trace: list[dict[str, object]] = []

    def publish(self, message: LogicalMessage) -> LogicalReceipt:
        self._queue.append(message)
        self.physical_trace.append({"mailbox": f"{message.contract_name}:{message.contract_version}"})
        return LogicalReceipt(message_id=message.message_id, accepted=True)

    def receive(self, consumer_contract: str) -> LogicalMessage:
        if not self._queue:
            raise LookupError("no logical message available")
        if self._delivery_consumer is None:
            self._delivery_consumer = consumer_contract
        elif self._delivery_consumer != consumer_contract:
            raise PermissionError("current delivery is already bound to another consumer contract")
        self.physical_trace.append({"subscription": consumer_contract})
        return self._queue[0]

    def acknowledge(self, consumer_contract: str, message_identity_scope: str, message_id: str) -> None:
        if not self._queue:
            raise ValueError("acknowledgement has no current logical message")
        if self._delivery_consumer != consumer_contract:
            raise ValueError("acknowledgement consumer contract does not match current delivery")
        current = self._queue[0]
        if (current.tenant_scope, current.message_id) != (message_identity_scope, message_id):
            raise ValueError("acknowledgement does not match current scoped logical message")
        self._queue.pop(0)
        self._delivery_consumer = None
        self.physical_trace.append({"subscription": consumer_contract, "ack": True})


class BrokerFacingPath:
    """Marker base used for mechanical discovery of every governed logical broker path."""


class OutboxDispatchPath(BrokerFacingPath):
    def __init__(self, broker: BrokerPort) -> None:
        self._broker = broker

    def dispatch(self, message: LogicalMessage) -> LogicalReceipt:
        return self._broker.publish(message)


class ConsumerReceivePath(BrokerFacingPath):
    def __init__(self, broker: BrokerPort) -> None:
        self._broker = broker

    def receive(self, consumer_contract: str) -> LogicalMessage:
        return self._broker.receive(consumer_contract)


class InboxAcknowledgePath(BrokerFacingPath):
    def __init__(self, broker: BrokerPort, verifier: DurableResponsibilityVerifier) -> None:
        self._broker = broker
        self._verifier = verifier

    def acknowledge_after_durable_responsibility(self, receipt: DurableResponsibilityReceipt) -> None:
        self._verifier.assert_durable(receipt)
        self._broker.acknowledge(receipt.consumer_contract, receipt.message_identity_scope, receipt.message_id)


class ReplayDispatchPath(BrokerFacingPath):
    def __init__(self, broker: BrokerPort) -> None:
        self._broker = broker

    def dispatch_original_identity(self, message: LogicalMessage) -> LogicalReceipt:
        return self._broker.publish(message)


FORBIDDEN_KAFKA_PRIMITIVES = ("topic", "partition", "offset", "consumer_group", "rebalance", "transactional", "kafka")


def discover_broker_facing_paths() -> dict[str, type[BrokerFacingPath]]:
    discovered: dict[str, type[BrokerFacingPath]] = {}
    for name, value in globals().items():
        if inspect.isclass(value) and value is not BrokerFacingPath and issubclass(value, BrokerFacingPath):
            discovered[name] = value
    return discovered


def forbidden_kafka_tokens(source: str) -> list[str]:
    lowered = source.lower()
    return sorted(token for token in FORBIDDEN_KAFKA_PRIMITIVES if token in lowered)


def assert_discovered_paths_do_not_leak_kafka_primitives() -> None:
    for path_type in discover_broker_facing_paths().values():
        leaks = forbidden_kafka_tokens(inspect.getsource(path_type))
        if leaks:
            raise AssertionError(f"{path_type.__name__} leaks Kafka primitives: {leaks}")


def semantic_transcript(port: BrokerPort) -> list[tuple[str, object]]:
    original = LogicalMessage(
        contract_name="evidence.device-state.changed",
        contract_version="v1",
        message_id="msg-evidence-0001",
        tenant_scope="tenant-evidence-a",
        payload='{"device":"canonical-device-1","state":"up"}',
    )
    with TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "effect.db"
        guard = SQLiteAtomicInboxEffectGuard(db_path)
        outbox = OutboxDispatchPath(port)
        consumer = ConsumerReceivePath(port)
        inbox = InboxAcknowledgePath(port, guard)
        replay = ReplayDispatchPath(port)

        first_receipt = outbox.dispatch(original)
        delivered = consumer.receive("evidence.consumer.v1")
        durable = guard.record_and_apply(
            consumer_contract="evidence.consumer.v1",
            message_identity_scope=delivered.tenant_scope,
            message_id=delivered.message_id,
            contract_name=delivered.contract_name,
            contract_version=delivered.contract_version,
            payload=delivered.payload,
        )
        reopened_guard = SQLiteAtomicInboxEffectGuard(db_path)
        inbox = InboxAcknowledgePath(port, reopened_guard)
        inbox.acknowledge_after_durable_responsibility(durable)

        replay_receipt = replay.dispatch_original_identity(original)
        replayed = consumer.receive("evidence.consumer.v1")
        replay_durable = reopened_guard.record_and_apply(
            consumer_contract="evidence.consumer.v1",
            message_identity_scope=replayed.tenant_scope,
            message_id=replayed.message_id,
            contract_name=replayed.contract_name,
            contract_version=replayed.contract_version,
            payload=replayed.payload,
        )
        inbox.acknowledge_after_durable_responsibility(replay_durable)
        observed_effect = reopened_guard.observe_effect(durable.effect_key)

        return [
            ("published_id", first_receipt.message_id),
            ("published_accepted", first_receipt.accepted),
            ("delivered_contract", delivered.contract_name),
            ("delivered_contract_version", delivered.contract_version),
            ("delivered_id", delivered.message_id),
            ("delivered_scope", delivered.tenant_scope),
            ("delivered_payload", delivered.payload),
            ("replay_id", replay_receipt.message_id),
            ("replay_accepted", replay_receipt.accepted),
            ("replayed_contract", replayed.contract_name),
            ("replayed_contract_version", replayed.contract_version),
            ("replayed_id", replayed.message_id),
            ("replayed_scope", replayed.tenant_scope),
            ("replayed_payload", replayed.payload),
            ("durable_effect_contract", observed_effect["contract_name"]),
            ("durable_effect_contract_version", observed_effect["contract_version"]),
            ("durable_effect_scope", observed_effect["message_identity_scope"]),
            ("durable_effect_message_id", observed_effect["message_id"]),
            ("durable_effect_payload", observed_effect["payload"]),
            ("durable_effect_semantic_digest", observed_effect["semantic_digest"]),
            ("durable_effect_apply_count", observed_effect["apply_count"]),
            ("durable_responsibility_receipt", durable.receipt_id),
            ("replay_durable_responsibility_receipt", replay_durable.receipt_id),
        ]
