from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from threading import RLock
from typing import Protocol

from .execution import (
    AsyncExecutionAdmission,
    AsyncExecutionRequest,
    CurrentAsyncExecutionAuthorityPort,
    require_current_execution,
)
from .model import (
    ComparisonEvidence,
    CrossAuthorityOperationSnapshot,
    EffectResultLink,
    EquivalenceRelation,
    InboxState,
    IntegrityConflict,
    InvalidTransition,
    OperationState,
    ReconciliationBlocked,
    ReconciliationResolution,
    ScopedMessageIdentity,
    aware,
    identifier,
)


class InboxAdmission(str, Enum):
    NEW = "new"
    DUPLICATE_COMPLETED = "duplicate_completed"
    OBSERVE_IN_PROGRESS = "observe_in_progress"
    RECONCILIATION_BLOCKED = "reconciliation_blocked"
    INTEGRITY_CONFLICT = "integrity_conflict"


class CrossAuthorityReconciliationPort(Protocol):
    def snapshot(self, operation_id: str) -> CrossAuthorityOperationSnapshot:
        """Return one coherent durable observation for the stable operation."""


@dataclass(frozen=True)
class InboxExecutorClaim:
    identity: ScopedMessageIdentity
    executor_id: str
    execution_generation: int
    claim_expires_at: datetime
    execution_admission: AsyncExecutionAdmission


@dataclass
class _Receipt:
    identity: ScopedMessageIdentity
    comparison_evidence: ComparisonEvidence
    state: InboxState = InboxState.ADMITTED
    executor_id: str | None = None
    execution_generation: int = 0
    claim_expires_at: datetime | None = None
    execution_admission: AsyncExecutionAdmission | None = None
    result_link: EffectResultLink | None = None
    operation_id: str | None = None
    terminal_reason: str | None = None
    reconciliation_revision: str | None = None


class InMemoryInboxLedger:
    """Thread-safe reference model for durable create-or-observe inbox semantics.

    Effect ownership requires two independent conditions: a single current inbox
    executor and a revision-bound current execution admission. Lease expiry never
    proves effect absence. An expired processing claim moves to reconciliation
    rather than becoming automatically executable again.
    """

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

            if receipt.identity != identity:
                receipt.state = InboxState.QUARANTINED
                receipt.executor_id = None
                receipt.claim_expires_at = None
                receipt.execution_admission = None
                receipt.terminal_reason = "same_scoped_identity_conflicting_trusted_binding"
                return InboxAdmission.INTEGRITY_CONFLICT

            relation = receipt.comparison_evidence.relation_to(comparison_evidence)
            if relation is EquivalenceRelation.MISMATCH:
                receipt.state = InboxState.QUARANTINED
                receipt.executor_id = None
                receipt.claim_expires_at = None
                receipt.execution_admission = None
                receipt.terminal_reason = "same_scoped_identity_conflicting_immutable_content"
                return InboxAdmission.INTEGRITY_CONFLICT
            if relation is EquivalenceRelation.UNKNOWN:
                receipt.state = InboxState.RECONCILIATION_REQUIRED
                receipt.executor_id = None
                receipt.claim_expires_at = None
                receipt.execution_admission = None
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
        *,
        execution_authority: CurrentAsyncExecutionAuthorityPort,
        claim_expires_at: datetime,
        runtime_profile_id: str = "runtime.worker@1",
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

            request = AsyncExecutionRequest(
                authority_contract=identity.consumer_contract,
                runtime_profile_id=runtime_profile_id,
                tenant_id=identity.tenant_id,
                message_identity=identity,
            )
            try:
                admission = require_current_execution(execution_authority, request)
            except ValueError as exc:
                raise ReconciliationBlocked(
                    "current placement/authorization/runtime authority cannot be established"
                ) from exc
            expires = aware(claim_expires_at, "claim_expires_at")
            admitted_at = aware(admission.observed_at, "execution_admission.observed_at")
            if expires <= admitted_at:
                raise ValueError("claim_expires_at must be later than current execution admission")

            receipt.state = InboxState.PROCESSING
            receipt.executor_id = executor_id
            receipt.execution_generation += 1
            receipt.claim_expires_at = expires
            receipt.execution_admission = admission
            receipt.reconciliation_revision = None
            return InboxExecutorClaim(
                identity=identity,
                executor_id=executor_id,
                execution_generation=receipt.execution_generation,
                claim_expires_at=expires,
                execution_admission=admission,
            )

    def expire_processing_claim(
        self,
        identity: ScopedMessageIdentity,
        *,
        observed_at: datetime,
    ) -> bool:
        now = aware(observed_at, "observed_at")
        with self._lock:
            receipt = self._require(identity)
            if receipt.state is not InboxState.PROCESSING:
                return False
            if receipt.claim_expires_at is None or receipt.claim_expires_at > now:
                return False
            receipt.state = InboxState.RECONCILIATION_REQUIRED
            receipt.executor_id = None
            receipt.claim_expires_at = None
            receipt.execution_admission = None
            receipt.terminal_reason = "processing_lease_expired_effect_absence_unproven"
            receipt.reconciliation_revision = None
            return True

    def complete_local_effect(
        self,
        claim: InboxExecutorClaim,
        result_link: EffectResultLink,
        *,
        observed_at: datetime,
    ) -> None:
        if not isinstance(result_link, EffectResultLink):
            raise ValueError("completed duplicate-sensitive receipt requires a durable result link")
        now = aware(observed_at, "observed_at")
        with self._lock:
            receipt = self._require_current_claim(claim, now)
            if receipt.operation_id is not None:
                raise InvalidTransition(
                    "operation-bound receipt requires cross-authority outcome authority"
                )
            receipt.state = InboxState.COMPLETED
            receipt.result_link = result_link
            receipt.executor_id = None
            receipt.claim_expires_at = None
            receipt.terminal_reason = None

    def complete_cross_authority_effect(
        self,
        claim: InboxExecutorClaim,
        result_link: EffectResultLink,
        *,
        operation_authority: CrossAuthorityReconciliationPort,
        observed_at: datetime,
    ) -> None:
        """Complete a processing receipt only from one coherent operation snapshot."""

        if not isinstance(result_link, EffectResultLink):
            raise ValueError("cross-authority completion requires durable result link")
        now = aware(observed_at, "observed_at")
        with self._lock:
            receipt = self._require_current_claim(claim, now)
            if receipt.operation_id is None:
                raise ReconciliationBlocked(
                    "cross-authority completion requires stable bound operation identity"
                )
            try:
                snapshot = operation_authority.snapshot(receipt.operation_id)
            except Exception as exc:
                raise ReconciliationBlocked("operation outcome authority failed closed") from exc
            if not isinstance(snapshot, CrossAuthorityOperationSnapshot):
                raise ReconciliationBlocked("operation authority did not return canonical atomic snapshot")
            if snapshot.operation_id != receipt.operation_id:
                raise ReconciliationBlocked("operation authority snapshot is bound to wrong operation")
            if snapshot.state is not OperationState.COMPLETED or snapshot.outcome != result_link:
                raise ReconciliationBlocked("bound operation has not durably completed with exact outcome")
            if snapshot.reconciliation_resolution is not None or snapshot.reconciliation_revision is not None:
                raise ReconciliationBlocked(
                    "reconciled operation completion must use reconciliation completion path"
                )
            receipt.state = InboxState.COMPLETED
            receipt.result_link = result_link
            receipt.executor_id = None
            receipt.claim_expires_at = None
            receipt.terminal_reason = None

    def bind_cross_authority_operation(
        self,
        claim: InboxExecutorClaim,
        operation_id: str,
        *,
        observed_at: datetime,
    ) -> None:
        identifier(operation_id, "operation_id")
        now = aware(observed_at, "observed_at")
        with self._lock:
            receipt = self._require_current_claim(claim, now)
            if receipt.operation_id is not None and receipt.operation_id != operation_id:
                raise InvalidTransition("inbox receipt cannot be rebound to another operation_id")
            receipt.operation_id = operation_id

    def require_reconciliation(
        self,
        claim: InboxExecutorClaim,
        reason: str,
        *,
        observed_at: datetime,
    ) -> None:
        identifier(reason, "reason")
        now = aware(observed_at, "observed_at")
        with self._lock:
            receipt = self._require_current_claim(claim, now)
            receipt.state = InboxState.RECONCILIATION_REQUIRED
            receipt.executor_id = None
            receipt.claim_expires_at = None
            receipt.execution_admission = None
            receipt.terminal_reason = reason
            receipt.reconciliation_revision = None

    def fail_terminal(
        self,
        claim: InboxExecutorClaim,
        reason: str,
        *,
        observed_at: datetime,
    ) -> None:
        identifier(reason, "reason")
        now = aware(observed_at, "observed_at")
        with self._lock:
            receipt = self._require_current_claim(claim, now)
            receipt.state = InboxState.FAILED_TERMINAL
            receipt.executor_id = None
            receipt.claim_expires_at = None
            receipt.execution_admission = None
            receipt.terminal_reason = reason

    def reconcile_retry_eligible(
        self,
        identity: ScopedMessageIdentity,
        operation_authority: CrossAuthorityReconciliationPort,
    ) -> None:
        """Re-admit only after one atomic snapshot durably proves effect absence."""

        with self._lock:
            receipt = self._require(identity)
            if receipt.state is not InboxState.RECONCILIATION_REQUIRED:
                raise InvalidTransition("only reconciliation-blocked receipt can become retry eligible")
            if receipt.operation_id is None:
                raise ReconciliationBlocked("receipt has no stable cross-authority operation identity")
            try:
                snapshot = operation_authority.snapshot(receipt.operation_id)
            except Exception as exc:
                raise ReconciliationBlocked("operation reconciliation authority failed closed") from exc
            if not isinstance(snapshot, CrossAuthorityOperationSnapshot):
                raise ReconciliationBlocked("operation authority did not return canonical atomic snapshot")
            if (
                snapshot.operation_id != receipt.operation_id
                or snapshot.state is not OperationState.PREPARED
                or snapshot.reconciliation_resolution is not ReconciliationResolution.EFFECT_PROVEN_ABSENT
                or not isinstance(snapshot.reconciliation_revision, str)
            ):
                raise ReconciliationBlocked("effect absence has not been durably reconciled")
            identifier(snapshot.reconciliation_revision, "reconciliation_revision")
            receipt.state = InboxState.ADMITTED
            receipt.terminal_reason = None
            receipt.reconciliation_revision = snapshot.reconciliation_revision

    def reconcile_completed(
        self,
        identity: ScopedMessageIdentity,
        result_link: EffectResultLink,
        *,
        operation_authority: CrossAuthorityReconciliationPort | None = None,
    ) -> None:
        if not isinstance(result_link, EffectResultLink):
            raise ValueError("reconciliation completion requires durable result link")
        with self._lock:
            receipt = self._require(identity)
            if receipt.state is not InboxState.RECONCILIATION_REQUIRED:
                raise InvalidTransition("only reconciliation-blocked receipt can be reconciled")
            if receipt.operation_id is None:
                raise ReconciliationBlocked(
                    "reconciliation completion requires stable operation identity and durable evidence authority"
                )
            if operation_authority is None:
                raise ReconciliationBlocked("reconciliation completion requires operation authority")
            try:
                snapshot = operation_authority.snapshot(receipt.operation_id)
            except Exception as exc:
                raise ReconciliationBlocked("operation reconciliation authority failed closed") from exc
            if not isinstance(snapshot, CrossAuthorityOperationSnapshot):
                raise ReconciliationBlocked("operation authority did not return canonical atomic snapshot")
            if (
                snapshot.operation_id != receipt.operation_id
                or snapshot.state is not OperationState.COMPLETED
                or snapshot.outcome != result_link
                or snapshot.reconciliation_resolution is not ReconciliationResolution.EFFECT_CONFIRMED
                or not isinstance(snapshot.reconciliation_revision, str)
            ):
                raise ReconciliationBlocked("confirmed effect/result has not been durably reconciled")
            identifier(snapshot.reconciliation_revision, "reconciliation_revision")
            receipt.reconciliation_revision = snapshot.reconciliation_revision
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

    def execution_admission(
        self,
        identity: ScopedMessageIdentity,
    ) -> AsyncExecutionAdmission | None:
        with self._lock:
            return self._require(identity).execution_admission

    def _require(self, identity: ScopedMessageIdentity) -> _Receipt:
        if not isinstance(identity, ScopedMessageIdentity):
            raise ValueError("ScopedMessageIdentity is required")
        receipt = self._receipts.get(identity.key)
        if receipt is None:
            raise InvalidTransition("unknown inbox identity")
        return receipt

    def _require_current_claim(
        self,
        claim: InboxExecutorClaim,
        observed_at: datetime,
    ) -> _Receipt:
        if not isinstance(claim, InboxExecutorClaim):
            raise InvalidTransition("current InboxExecutorClaim is required")
        receipt = self._require(claim.identity)
        if receipt.state is InboxState.PROCESSING and receipt.claim_expires_at is not None:
            if receipt.claim_expires_at <= observed_at:
                receipt.state = InboxState.RECONCILIATION_REQUIRED
                receipt.executor_id = None
                receipt.claim_expires_at = None
                receipt.execution_admission = None
                receipt.terminal_reason = "processing_lease_expired_effect_absence_unproven"
                receipt.reconciliation_revision = None
        if (
            receipt.state is not InboxState.PROCESSING
            or receipt.executor_id != claim.executor_id
            or receipt.execution_generation != claim.execution_generation
            or receipt.claim_expires_at != claim.claim_expires_at
            or receipt.execution_admission != claim.execution_admission
        ):
            raise InvalidTransition("stale/non-owner/expired inbox executor cannot mutate receipt")
        return receipt
