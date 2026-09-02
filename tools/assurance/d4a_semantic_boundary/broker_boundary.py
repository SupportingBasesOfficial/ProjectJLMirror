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
    def acknowledge(self, consumer_contract: str, message_id: str) -> None: ...


class DurableResponsibilityVerifier(Protocol):
    def assert_durable(self, receipt: DurableResponsibilityReceipt) -> None: ...


class KafkaCandidateAdapter:
    """Evidence adapter with Kafka-specific physical metadata contained here only."""

    def __init__(self) -> None:
        self._queue: list[LogicalMessage] = []
        self.physical_trace: list[dict[str, object]] = []

    def publish(self, message: LogicalMessage) -> LogicalReceipt:
        self._queue.append(message)
        self.physical_trace.append({"topic": f"evidence.{message.contract_name}", "partition": 0, "offset": len(self._queue) - 1, "transactional": False})
        return LogicalReceipt(message_id=message.message_id, accepted=True)

    def receive(self, consumer_contract: str) -> LogicalMessage:
        if not self._queue:
            raise LookupError("no logical message available")
        self.physical_trace.append({"consumer_group": f"evidence.{consumer_contract}"})
        return self._queue[0]

    def acknowledge(self, consumer_contract: str, message_id: str) -> None:
        if not self._queue or self._queue[0].message_id != message_id:
            raise ValueError("acknowledgement does not match current logical message")
        self._queue.pop(0)
        self.physical_trace.append({"consumer_group": f"evidence.{consumer_contract}", "ack": True})


class AlternateStubTransport:
    def __init__(self) -> None:
        self._queue: list[LogicalMessage] = []
        self.physical_trace: list[dict[str, object]] = []

    def publish(self, message: LogicalMessage) -> LogicalReceipt:
        self._queue.append(message)
        self.physical_trace.append({"mailbox": message.contract_name})
        return LogicalReceipt(message_id=message.message_id, accepted=True)

    def receive(self, consumer_contract: str) -> LogicalMessage:
        if not self._queue:
            raise LookupError("no logical message available")
        self.physical_trace.append({"subscription": consumer_contract})
        return self._queue[0]

    def acknowledge(self, consumer_contract: str, message_id: str) -> None:
        if not self._queue or self._queue[0].message_id != message_id:
            raise ValueError("acknowledgement does not match current logical message")
        self._queue.pop(0)
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
        self._broker.acknowledge(receipt.consumer_contract, receipt.message_id)


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
        contract_name="evidence.device-state.changed.v1",
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
            message_id=delivered.message_id,
            payload=delivered.payload,
        )
        # Re-open durable authority before broker acknowledgement to prove committed state survives connection lifecycle.
        reopened_guard = SQLiteAtomicInboxEffectGuard(db_path)
        inbox = InboxAcknowledgePath(port, reopened_guard)
        inbox.acknowledge_after_durable_responsibility(durable)

        replay_receipt = replay.dispatch_original_identity(original)
        replayed = consumer.receive("evidence.consumer.v1")
        replay_durable = reopened_guard.record_and_apply(
            consumer_contract="evidence.consumer.v1",
            message_id=replayed.message_id,
            payload=replayed.payload,
        )
        inbox.acknowledge_after_durable_responsibility(replay_durable)
        observed_effect = reopened_guard.observe_effect(durable.effect_key)

        return [
            ("published_id", first_receipt.message_id),
            ("delivered_contract", delivered.contract_name),
            ("delivered_id", delivered.message_id),
            ("delivered_scope", delivered.tenant_scope),
            ("delivered_payload", delivered.payload),
            ("replay_id", replay_receipt.message_id),
            ("replayed_contract", replayed.contract_name),
            ("replayed_id", replayed.message_id),
            ("replayed_scope", replayed.tenant_scope),
            ("replayed_payload", replayed.payload),
            ("durable_effect_payload", observed_effect["payload"]),
            ("durable_effect_payload_digest", observed_effect["payload_digest"]),
            ("durable_effect_apply_count", observed_effect["apply_count"]),
            ("durable_responsibility_receipt", durable.receipt_id),
            ("replay_durable_responsibility_receipt", replay_durable.receipt_id),
        ]
