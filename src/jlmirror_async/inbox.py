from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import RLock

from .model import (
    ComparisonEvidence,
    EffectResultLink,
    EquivalenceRelation,
    InboxState,
    IntegrityConflict,
    InvalidTransition,
    ReconciliationBlocked,
    ScopedMessageIdentity,
    identifier,
)


class InboxAdmission(str, Enum):
    NEW = "new"
    DUPLICATE_COMPLETED = "duplicate_completed"
    OBSERVE_IN_PROGRESS = "observe_in_progress"
    RECONCILIATION_BLOCKED = "reconciliation_blocked"
    INTEGRITY_CONFLICT = "integrity_conflict"


@dataclass(frozen=True)
class InboxExecutorClaim:
    identity: ScopedMessageIdentity
    executor_id: str
    execution_generation: int


@dataclass
class _Receipt:
    identity: ScopedMessageIdentity
    comparison_evidence: ComparisonEvidence
    state: InboxState = InboxState.ADMITTED
    executor_id: str | None = None
    execution_generation: int = 0
    result_link: EffectResultLink | None = None
    operation_id: str | None = None
    terminal_reason: str | None = None


class InMemoryInboxLedger:
    """Thread-safe reference model for durable create-or-observe inbox semantics."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._receipts: dict[tuple[str, str, str], _Receipt] = {}

    def admit(
        self,
        identity: ScopedMessageIdentity,
        comparison_evidence: ComparisonEvidence,
    ) -> InboxAdmission:
        if not isinstance(identity, ScopedMessageIdentity):
            raise ValueError("trusted ScopedMessageIdentity is required")
        if not isinstance(comparison_evidence, ComparisonEvidence):
            raise ValueError("comparison evidence is required")
        with self._lock:
            receipt = self._receipts.get(identity.key)
            if receipt is None:
                self._receipts[identity.key] = _Receipt(
                    identity=identity,
                    comparison_evidence=comparison_evidence,
                )
                return InboxAdmission.NEW

            relation = receipt.comparison_evidence.relation_to(comparison_evidence)
            if relation is EquivalenceRelation.MISMATCH:
                receipt.state = InboxState.QUARANTINED
                receipt.executor_id = None
                receipt.terminal_reason = "same_scoped_identity_conflicting_immutable_content"
                return InboxAdmission.INTEGRITY_CONFLICT
            if relation is EquivalenceRelation.UNKNOWN:
                receipt.state = InboxState.RECONCILIATION_REQUIRED
                receipt.executor_id = None
                receipt.terminal_reason = "message_equivalence_authority_unknown"
                return InboxAdmission.RECONCILIATION_BLOCKED

            if receipt.state is InboxState.COMPLETED:
                return InboxAdmission.DUPLICATE_COMPLETED
            if receipt.state in {
                InboxState.RECONCILIATION_REQUIRED,
                InboxState.QUARANTINED,
                InboxState.FAILED_TERMINAL,
            }:
                return InboxAdmission.RECONCILIATION_BLOCKED
            return InboxAdmission.OBSERVE_IN_PROGRESS

    def claim_effect(
        self,
        identity: ScopedMessageIdentity,
        executor_id: str,
    ) -> InboxExecutorClaim:
        identifier(executor_id, "executor_id")
        with self._lock:
            receipt = self._require(identity)
            if receipt.state is not InboxState.ADMITTED:
                if receipt.state in {
                    InboxState.RECONCILIATION_REQUIRED,
                    InboxState.QUARANTINED,
                }:
                    raise ReconciliationBlocked("receipt is not effect-eligible")
                raise InvalidTransition("receipt does not admit another logical executor")
            receipt.state = InboxState.PROCESSING
            receipt.executor_id = executor_id
            receipt.execution_generation += 1
            return InboxExecutorClaim(
                identity=identity,
                executor_id=executor_id,
                execution_generation=receipt.execution_generation,
            )

    def complete_local_effect(
        self,
        claim: InboxExecutorClaim,
        result_link: EffectResultLink,
    ) -> None:
        if not isinstance(result_link, EffectResultLink):
            raise ValueError("completed duplicate-sensitive receipt requires a durable result link")
        with self._lock:
            receipt = self._require_current_claim(claim)
            receipt.state = InboxState.COMPLETED
            receipt.result_link = result_link
            receipt.executor_id = None
            receipt.terminal_reason = None

    def bind_cross_authority_operation(
        self,
        claim: InboxExecutorClaim,
        operation_id: str,
    ) -> None:
        identifier(operation_id, "operation_id")
        with self._lock:
            receipt = self._require_current_claim(claim)
            receipt.operation_id = operation_id

    def require_reconciliation(
        self,
        claim: InboxExecutorClaim,
        reason: str,
    ) -> None:
        identifier(reason, "reason")
        with self._lock:
            receipt = self._require_current_claim(claim)
            receipt.state = InboxState.RECONCILIATION_REQUIRED
            receipt.executor_id = None
            receipt.terminal_reason = reason

    def fail_terminal(self, claim: InboxExecutorClaim, reason: str) -> None:
        identifier(reason, "reason")
        with self._lock:
            receipt = self._require_current_claim(claim)
            receipt.state = InboxState.FAILED_TERMINAL
            receipt.executor_id = None
            receipt.terminal_reason = reason

    def reconcile_completed(
        self,
        identity: ScopedMessageIdentity,
        result_link: EffectResultLink,
    ) -> None:
        if not isinstance(result_link, EffectResultLink):
            raise ValueError("reconciliation completion requires durable result link")
        with self._lock:
            receipt = self._require(identity)
            if receipt.state is not InboxState.RECONCILIATION_REQUIRED:
                raise InvalidTransition("only reconciliation-blocked receipt can be reconciled")
            receipt.state = InboxState.COMPLETED
            receipt.result_link = result_link
            receipt.terminal_reason = None

    def state(self, identity: ScopedMessageIdentity) -> InboxState:
        with self._lock:
            return self._require(identity).state

    def result_link(self, identity: ScopedMessageIdentity) -> EffectResultLink | None:
        with self._lock:
            return self._require(identity).result_link

    def operation_id(self, identity: ScopedMessageIdentity) -> str | None:
        with self._lock:
            return self._require(identity).operation_id

    def _require(self, identity: ScopedMessageIdentity) -> _Receipt:
        if not isinstance(identity, ScopedMessageIdentity):
            raise ValueError("ScopedMessageIdentity is required")
        receipt = self._receipts.get(identity.key)
        if receipt is None:
            raise InvalidTransition("unknown inbox identity")
        return receipt

    def _require_current_claim(self, claim: InboxExecutorClaim) -> _Receipt:
        if not isinstance(claim, InboxExecutorClaim):
            raise InvalidTransition("current InboxExecutorClaim is required")
        receipt = self._require(claim.identity)
        if (
            receipt.state is not InboxState.PROCESSING
            or receipt.executor_id != claim.executor_id
            or receipt.execution_generation != claim.execution_generation
        ):
            raise InvalidTransition("stale/non-owner inbox executor cannot mutate receipt")
        return receipt
