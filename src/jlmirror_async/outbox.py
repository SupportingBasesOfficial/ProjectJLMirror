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
    claim_expires_at: datetime
    message: LogicalMessage


@dataclass
class _OutboxEntry:
    record_id: int
    message: LogicalMessage
    state: OutboxDispatchState = OutboxDispatchState.PENDING
    claim_owner: str | None = None
    claim_generation: int = 0
    claim_expires_at: datetime | None = None
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
    correlation_id: str,
    data_classification: str,
    serialization_profile_id: str,
    encoded_payload: bytes,
    comparison_evidence: ComparisonEvidence,
    producer_generation: str | None = None,
    causation_id: str | None = None,
    subject: MessageSubject | None = None,
    occurred_at: datetime | None = None,
    created_at: datetime | None = None,
    operation_id: str | None = None,
    not_before: datetime | None = None,
    deadline: datetime | None = None,
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
        created_at=created_at,
        operation_id=operation_id,
        not_before=not_before,
        deadline=deadline,
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

    Claim expiry recovers dispatcher liveness only. It never proves that a broker
    publish did not happen. Reclaim therefore republishes the same immutable
    logical message identity under the accepted at-least-once contract.
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

    def claim_next(
        self,
        owner_id: str,
        *,
        observed_at: datetime,
        claim_expires_at: datetime,
    ) -> OutboxClaim | None:
        identifier(owner_id, "owner_id")
        now = aware(observed_at, "observed_at")
        expires = aware(claim_expires_at, "claim_expires_at")
        if expires <= now:
            raise ValueError("claim_expires_at must be later than observed_at")
        with self._lock:
            self._expire_claims_locked(now)
            for record_id in sorted(self._by_id):
                entry = self._by_id[record_id]
                if entry.state is not OutboxDispatchState.PENDING:
                    continue
                entry.state = OutboxDispatchState.CLAIMED
                entry.claim_owner = owner_id
                entry.claim_generation += 1
                entry.claim_expires_at = expires
                entry.attempt_count += 1
                return OutboxClaim(
                    record_id=record_id,
                    owner_id=owner_id,
                    claim_generation=entry.claim_generation,
                    claim_expires_at=expires,
                    message=entry.message,
                )
            return None

    def mark_published(
        self,
        claim: OutboxClaim,
        receipt: BrokerPublicationReceipt,
        *,
        observed_at: datetime,
    ) -> None:
        if not isinstance(receipt, BrokerPublicationReceipt):
            raise ValueError("broker publication receipt is required")
        now = aware(observed_at, "observed_at")
        with self._lock:
            entry = self._require_current_claim(claim, now)
            entry.state = OutboxDispatchState.PUBLISHED
            entry.publication_receipt = receipt
            entry.claim_owner = None
            entry.claim_expires_at = None
            entry.last_error_class = None

    def mark_publication_ambiguous(
        self,
        claim: OutboxClaim,
        *,
        observed_at: datetime,
    ) -> None:
        """Return the same logical message to pending after ambiguous publication.

        A subsequent dispatcher retries the *same* message identity. It must not
        fabricate another semantic event merely because acknowledgement was lost.
        """

        now = aware(observed_at, "observed_at")
        with self._lock:
            entry = self._require_current_claim(claim, now)
            entry.state = OutboxDispatchState.PENDING
            entry.claim_owner = None
            entry.claim_expires_at = None
            entry.last_error_class = "publication_outcome_ambiguous"

    def quarantine(
        self,
        claim: OutboxClaim,
        error_class: str,
        *,
        observed_at: datetime,
    ) -> None:
        identifier(error_class, "error_class")
        now = aware(observed_at, "observed_at")
        with self._lock:
            entry = self._require_current_claim(claim, now)
            entry.state = OutboxDispatchState.QUARANTINED
            entry.claim_owner = None
            entry.claim_expires_at = None
            entry.last_error_class = error_class

    def release_claim(
        self,
        claim: OutboxClaim,
        error_class: str,
        *,
        observed_at: datetime,
    ) -> None:
        identifier(error_class, "error_class")
        now = aware(observed_at, "observed_at")
        with self._lock:
            entry = self._require_current_claim(claim, now)
            entry.state = OutboxDispatchState.PENDING
            entry.claim_owner = None
            entry.claim_expires_at = None
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

    def pending_messages(self, *, observed_at: datetime | None = None) -> Iterable[LogicalMessage]:
        with self._lock:
            if observed_at is not None:
                self._expire_claims_locked(aware(observed_at, "observed_at"))
            return tuple(
                entry.message
                for entry in self._by_id.values()
                if entry.state is OutboxDispatchState.PENDING
            )

    def _expire_claims_locked(self, now: datetime) -> None:
        for entry in self._by_id.values():
            if (
                entry.state is OutboxDispatchState.CLAIMED
                and entry.claim_expires_at is not None
                and entry.claim_expires_at <= now
            ):
                entry.state = OutboxDispatchState.PENDING
                entry.claim_owner = None
                entry.claim_expires_at = None
                entry.last_error_class = "dispatcher_claim_expired_outcome_not_proven_absent"

    def _require_current_claim(self, claim: OutboxClaim, now: datetime) -> _OutboxEntry:
        if not isinstance(claim, OutboxClaim):
            raise InvalidTransition("current OutboxClaim is required")
        self._expire_claims_locked(now)
        entry = self._by_id.get(claim.record_id)
        if entry is None:
            raise InvalidTransition("unknown outbox record")
        if (
            entry.state is not OutboxDispatchState.CLAIMED
            or entry.claim_owner != claim.owner_id
            or entry.claim_generation != claim.claim_generation
            or entry.claim_expires_at != claim.claim_expires_at
        ):
            raise InvalidTransition("stale/non-owner/expired outbox claim cannot mutate dispatch state")
        return entry
