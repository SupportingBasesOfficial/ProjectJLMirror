from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from typing import Iterable

from jlmirror_authority import TenantContext

from .model import (
    BrokerPublicationReceipt,
    ComparisonEvidence,
    InvalidTransition,
    LogicalMessage,
    MessageClass,
    MessageScope,
    MessageSubject,
    OutboxDispatchState,
    aware,
    identifier,
)


@dataclass(frozen=True)
class OutboxClaim:
    record_id: int
    owner_id: str
    claim_generation: int
    message: LogicalMessage


@dataclass
class _OutboxEntry:
    record_id: int
    message: LogicalMessage
    state: OutboxDispatchState = OutboxDispatchState.PENDING
    claim_owner: str | None = None
    claim_generation: int = 0
    attempt_count: int = 0
    last_error_class: str | None = None
    publication_receipt: BrokerPublicationReceipt | None = None


def tenant_message_from_context(
    context: TenantContext,
    *,
    message_id: str,
    producer_message_scope: str,
    message_class: MessageClass,
    contract_name: str,
    contract_version: str,
    producer: str,
    occurred_at: datetime,
    correlation_id: str,
    data_classification: str,
    serialization_profile_id: str,
    encoded_payload: bytes,
    comparison_evidence: ComparisonEvidence,
    producer_generation: str | None = None,
    causation_id: str | None = None,
    subject: MessageSubject | None = None,
) -> LogicalMessage:
    """Construct tenant publication only from the trusted Wave 1 TenantContext.

    The caller cannot provide a separate tenant id to this helper. Whether the
    context is *current* remains the owning use-case/current-authority boundary's
    responsibility; this helper prevents payload/request tenant substitution.
    """

    if not isinstance(context, TenantContext):
        raise ValueError("trusted TenantContext is required for tenant publication")
    return LogicalMessage(
        message_id=message_id,
        producer_message_scope=producer_message_scope,
        message_class=message_class,
        contract_name=contract_name,
        contract_version=contract_version,
        producer=producer,
        producer_generation=producer_generation,
        scope=MessageScope.TENANT,
        tenant_id=context.tenant_id,
        subject=subject,
        occurred_at=occurred_at,
        correlation_id=correlation_id,
        causation_id=causation_id,
        data_classification=data_classification,
        serialization_profile_id=serialization_profile_id,
        encoded_payload=encoded_payload,
        comparison_evidence=comparison_evidence,
    )


class InMemoryOutboxLedger:
    """Thread-safe reference model for immutable outbox + mutable dispatch state.

    This is a falsification oracle, not a production durability claim. Production
    code must bind domain mutation, audit intent and outbox append in one accepted
    PostgreSQL transaction and use a reviewed durable claim implementation.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._next_id = 1
        self._by_id: dict[int, _OutboxEntry] = {}
        self._by_message: dict[tuple[str, str], int] = {}

    def append_committed(self, message: LogicalMessage) -> int:
        if not isinstance(message, LogicalMessage):
            raise ValueError("outbox append requires LogicalMessage")
        with self._lock:
            existing = self._by_message.get(message.outbox_identity)
            if existing is not None:
                original = self._by_id[existing].message
                relation = original.comparison_evidence.relation_to(message.comparison_evidence)
                if relation.value != "equivalent" or original != message:
                    raise InvalidTransition(
                        "outbox message identity cannot be reused for different immutable meaning"
                    )
                return existing
            record_id = self._next_id
            self._next_id += 1
            self._by_id[record_id] = _OutboxEntry(record_id=record_id, message=message)
            self._by_message[message.outbox_identity] = record_id
            return record_id

    def claim_next(self, owner_id: str) -> OutboxClaim | None:
        identifier(owner_id, "owner_id")
        with self._lock:
            for record_id in sorted(self._by_id):
                entry = self._by_id[record_id]
                if entry.state is not OutboxDispatchState.PENDING:
                    continue
                entry.state = OutboxDispatchState.CLAIMED
                entry.claim_owner = owner_id
                entry.claim_generation += 1
                entry.attempt_count += 1
                return OutboxClaim(
                    record_id=record_id,
                    owner_id=owner_id,
                    claim_generation=entry.claim_generation,
                    message=entry.message,
                )
            return None

    def mark_published(
        self,
        claim: OutboxClaim,
        receipt: BrokerPublicationReceipt,
    ) -> None:
        if not isinstance(receipt, BrokerPublicationReceipt):
            raise ValueError("broker publication receipt is required")
        with self._lock:
            entry = self._require_current_claim(claim)
            entry.state = OutboxDispatchState.PUBLISHED
            entry.publication_receipt = receipt
            entry.claim_owner = None
            entry.last_error_class = None

    def mark_publication_ambiguous(self, claim: OutboxClaim) -> None:
        """Return the same logical message to pending after ambiguous publication.

        A subsequent dispatcher retries the *same* message identity. It must not
        fabricate another semantic event merely because acknowledgement was lost.
        """

        with self._lock:
            entry = self._require_current_claim(claim)
            entry.state = OutboxDispatchState.PENDING
            entry.claim_owner = None
            entry.last_error_class = "publication_outcome_ambiguous"

    def quarantine(self, claim: OutboxClaim, error_class: str) -> None:
        identifier(error_class, "error_class")
        with self._lock:
            entry = self._require_current_claim(claim)
            entry.state = OutboxDispatchState.QUARANTINED
            entry.claim_owner = None
            entry.last_error_class = error_class

    def release_claim(self, claim: OutboxClaim, error_class: str) -> None:
        identifier(error_class, "error_class")
        with self._lock:
            entry = self._require_current_claim(claim)
            entry.state = OutboxDispatchState.PENDING
            entry.claim_owner = None
            entry.last_error_class = error_class

    def message(self, record_id: int) -> LogicalMessage:
        with self._lock:
            return self._by_id[record_id].message

    def state(self, record_id: int) -> OutboxDispatchState:
        with self._lock:
            return self._by_id[record_id].state

    def attempt_count(self, record_id: int) -> int:
        with self._lock:
            return self._by_id[record_id].attempt_count

    def pending_messages(self) -> Iterable[LogicalMessage]:
        with self._lock:
            return tuple(
                entry.message
                for entry in self._by_id.values()
                if entry.state is OutboxDispatchState.PENDING
            )

    def _require_current_claim(self, claim: OutboxClaim) -> _OutboxEntry:
        if not isinstance(claim, OutboxClaim):
            raise InvalidTransition("current OutboxClaim is required")
        entry = self._by_id.get(claim.record_id)
        if entry is None:
            raise InvalidTransition("unknown outbox record")
        if (
            entry.state is not OutboxDispatchState.CLAIMED
            or entry.claim_owner != claim.owner_id
            or entry.claim_generation != claim.claim_generation
        ):
            raise InvalidTransition("stale/non-owner outbox claim cannot mutate dispatch state")
        return entry
