from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
import inspect


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


class KafkaCandidateAdapter:
    """Evidence adapter with Kafka-specific physical metadata contained here only.

    This adapter is intentionally evidence-only. It proves logical/physical separation;
    it does not claim a live Kafka broker, capacity, ordering, or recovery evidence run.
    """

    def __init__(self) -> None:
        self._queue: list[LogicalMessage] = []
        self.physical_trace: list[dict[str, object]] = []

    def publish(self, message: LogicalMessage) -> LogicalReceipt:
        self._queue.append(message)
        self.physical_trace.append({
            "topic": f"evidence.{message.contract_name}",
            "partition": 0,
            "offset": len(self._queue) - 1,
            "transactional": False,
        })
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


class OutboxDispatchPath:
    def __init__(self, broker: BrokerPort) -> None:
        self._broker = broker

    def dispatch(self, message: LogicalMessage) -> LogicalReceipt:
        return self._broker.publish(message)


class ConsumerReceivePath:
    def __init__(self, broker: BrokerPort) -> None:
        self._broker = broker

    def receive(self, consumer_contract: str) -> LogicalMessage:
        return self._broker.receive(consumer_contract)


class InboxAcknowledgePath:
    def __init__(self, broker: BrokerPort) -> None:
        self._broker = broker

    def acknowledge_after_durable_responsibility(
        self, consumer_contract: str, message_id: str, *, durable_responsibility: bool
    ) -> None:
        if not durable_responsibility:
            raise PermissionError("broker ack prohibited before durable responsibility")
        self._broker.acknowledge(consumer_contract, message_id)


class ReplayDispatchPath:
    def __init__(self, broker: BrokerPort) -> None:
        self._broker = broker

    def dispatch_original_identity(self, message: LogicalMessage) -> LogicalReceipt:
        return self._broker.publish(message)


BROKER_FACING_PATHS = {
    "outbox_dispatch": OutboxDispatchPath,
    "consumer_receive": ConsumerReceivePath,
    "inbox_acknowledge": InboxAcknowledgePath,
    "replay_dispatch": ReplayDispatchPath,
}

FORBIDDEN_KAFKA_PRIMITIVES = (
    "topic",
    "partition",
    "offset",
    "consumer_group",
    "rebalance",
    "transactional",
    "kafka",
)


def forbidden_kafka_tokens(source: str) -> list[str]:
    lowered = source.lower()
    return sorted(token for token in FORBIDDEN_KAFKA_PRIMITIVES if token in lowered)


def assert_broker_facing_paths_do_not_leak_kafka_primitives() -> None:
    """Mechanically reject physical Kafka coupling in every registered logical path."""
    for path_name, path_type in BROKER_FACING_PATHS.items():
        leaks = forbidden_kafka_tokens(inspect.getsource(path_type))
        if leaks:
            raise AssertionError(f"{path_name} leaks Kafka primitives: {leaks}")


def semantic_transcript(port: BrokerPort) -> list[tuple[str, object]]:
    original = LogicalMessage(
        contract_name="evidence.device-state.changed.v1",
        message_id="msg-evidence-0001",
        tenant_scope="tenant-evidence-a",
        payload='{"device":"canonical-device-1","state":"up"}',
    )
    outbox = OutboxDispatchPath(port)
    consumer = ConsumerReceivePath(port)
    inbox = InboxAcknowledgePath(port)
    replay = ReplayDispatchPath(port)

    first_receipt = outbox.dispatch(original)
    delivered = consumer.receive("evidence.consumer.v1")
    inbox.acknowledge_after_durable_responsibility(
        "evidence.consumer.v1", delivered.message_id, durable_responsibility=True
    )
    replay_receipt = replay.dispatch_original_identity(original)
    replayed = consumer.receive("evidence.consumer.v1")

    return [
        ("published_id", first_receipt.message_id),
        ("delivered_contract", delivered.contract_name),
        ("delivered_id", delivered.message_id),
        ("delivered_scope", delivered.tenant_scope),
        ("replay_id", replay_receipt.message_id),
        ("replayed_id", replayed.message_id),
        ("business_effect_authority", "consumer_inbox_effect_guard"),
    ]
