from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock

from .execution import (
    AsyncExecutionAdmission,
    AsyncExecutionRequest,
    CurrentAsyncExecutionAuthorityPort,
    require_current_execution,
)
from .model import (
    EffectResultLink,
    InvalidTransition,
    OperationState,
    ReconciliationBlocked,
    ReconciliationResolution,
    aware,
    identifier,
)


@dataclass(frozen=True)
class OperationAttempt:
    operation_id: str
    attempt_generation: int
    executor_id: str
    attempt_expires_at: datetime
    execution_admission: AsyncExecutionAdmission


@dataclass(frozen=True)
class ReconciliationEvidence:
    operation_id: str
    reconciliation_revision: str
    resolution: ReconciliationResolution
    confirmed_outcome: EffectResultLink | None = None

    def __post_init__(self) -> None:
        identifier(self.operation_id, "operation_id")
        identifier(self.reconciliation_revision, "reconciliation_revision")
        if not isinstance(self.resolution, ReconciliationResolution):
            raise ValueError("resolution must be canonical")
        if self.resolution is ReconciliationResolution.EFFECT_CONFIRMED:
            if not isinstance(self.confirmed_outcome, EffectResultLink):
                raise ValueError("confirmed reconciliation requires durable outcome identity")
        elif self.confirmed_outcome is not None:
            raise ValueError("non-confirmed reconciliation cannot carry confirmed outcome")


@dataclass
class _Operation:
    operation_id: str
    tenant_id: str | None
    owner_contract: str
    state: OperationState = OperationState.PREPARED
    attempt_generation: int = 0
    executor_id: str | None = None
    attempt_expires_at: datetime | None = None
    execution_admission: AsyncExecutionAdmission | None = None
    outcome: EffectResultLink | None = None
    ambiguity_reason: str | None = None
    reconciliation_revision: str | None = None
    reconciliation_resolution: ReconciliationResolution | None = None


class InMemoryCrossAuthorityOperationLedger:
    """Reference model for stable-operation ambiguity and reconciliation.

    Reconciliation evidence is append-only by `(operation_id, revision)`. A
    timeout/lost response or executor-lease expiry cannot be interpreted as effect
    absence. Another attempt becomes eligible only after an immutable evidence
    record proves absence. Every new attempt requires a fresh current execution
    admission for its exact operation scope.

    Append-only reconciliation history is distinct from the current attempt's
    resolution pointer. When `effect_proven_absent` re-opens an operation for a
    later attempt, the immutable historical evidence remains retained while the
    current pointer is consumed/cleared before the successor attempt begins.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._operations: dict[str, _Operation] = {}
        self._reconciliation_evidence: dict[tuple[str, str], ReconciliationEvidence] = {}

    def prepare(self, operation_id: str, owner_contract: str, *, tenant_id: str | None = None) -> None:
        identifier(operation_id, "operation_id")
        identifier(owner_contract, "owner_contract")
        if tenant_id is not None:
            identifier(tenant_id, "tenant_id")
        with self._lock:
            existing = self._operations.get(operation_id)
            if existing is not None:
                if existing.owner_contract != owner_contract or existing.tenant_id != tenant_id:
                    raise InvalidTransition("operation_id cannot be rebound to another authority scope")
                return
            self._operations[operation_id] = _Operation(operation_id, tenant_id, owner_contract)

    def begin_attempt(
        self,
        operation_id: str,
        executor_id: str,
        *,
        execution_authority: CurrentAsyncExecutionAuthorityPort,
        attempt_expires_at: datetime,
        runtime_profile_id: str = "runtime.worker@1",
    ) -> OperationAttempt:
        identifier(executor_id, "executor_id")
        with self._lock:
            operation = self._require(operation_id)
            if operation.state is OperationState.RECONCILIATION_REQUIRED:
                raise ReconciliationBlocked("ambiguous operation must reconcile before another attempt")
            if operation.state is not OperationState.PREPARED:
                raise InvalidTransition("operation is not eligible for a new effect attempt")
            if operation.reconciliation_resolution not in {
                None,
                ReconciliationResolution.EFFECT_PROVEN_ABSENT,
            }:
                raise InvalidTransition(
                    "prepared operation carries reconciliation state not eligible for a successor attempt"
                )
            request = AsyncExecutionRequest(
                authority_contract=operation.owner_contract,
                runtime_profile_id=runtime_profile_id,
                tenant_id=operation.tenant_id,
                operation_id=operation.operation_id,
            )
            try:
                admission = require_current_execution(execution_authority, request)
            except ValueError as exc:
                raise ReconciliationBlocked(
                    "current placement/authorization/runtime authority cannot be established"
                ) from exc
            expires = aware(attempt_expires_at, "attempt_expires_at")
            if expires <= aware(admission.observed_at, "execution_admission.observed_at"):
                raise ValueError("attempt_expires_at must be later than current execution admission")
            operation.state = OperationState.ATTEMPTING
            operation.attempt_generation += 1
            operation.executor_id = executor_id
            operation.attempt_expires_at = expires
            operation.execution_admission = admission
            operation.reconciliation_revision = None
            operation.reconciliation_resolution = None
            return OperationAttempt(
                operation_id,
                operation.attempt_generation,
                executor_id,
                expires,
                admission,
            )

    def expire_attempt(self, operation_id: str, *, observed_at: datetime) -> bool:
        now = aware(observed_at, "observed_at")
        with self._lock:
            operation = self._require(operation_id)
            if operation.state is not OperationState.ATTEMPTING:
                return False
            if operation.attempt_expires_at is None or operation.attempt_expires_at > now:
                return False
            self._block_for_reconciliation(
                operation,
                "attempt_lease_expired_effect_absence_unproven",
            )
            return True

    def complete(
        self,
        attempt: OperationAttempt,
        outcome: EffectResultLink,
        *,
        observed_at: datetime,
    ) -> None:
        if not isinstance(outcome, EffectResultLink):
            raise ValueError("cross-authority completion requires durable result identity")
        now = aware(observed_at, "observed_at")
        with self._lock:
            operation = self._require_current_attempt(attempt, now)
            operation.state = OperationState.COMPLETED
            operation.outcome = outcome
            operation.executor_id = None
            operation.attempt_expires_at = None
            operation.ambiguity_reason = None

    def mark_ambiguous(
        self,
        attempt: OperationAttempt,
        reason: str,
        *,
        observed_at: datetime,
    ) -> None:
        identifier(reason, "reason")
        now = aware(observed_at, "observed_at")
        with self._lock:
            operation = self._require_current_attempt(attempt, now)
            self._block_for_reconciliation(operation, reason)

    def fail_terminal(
        self,
        attempt: OperationAttempt,
        reason: str,
        *,
        observed_at: datetime,
    ) -> None:
        identifier(reason, "reason")
        now = aware(observed_at, "observed_at")
        with self._lock:
            operation = self._require_current_attempt(attempt, now)
            operation.state = OperationState.FAILED_TERMINAL
            operation.executor_id = None
            operation.attempt_expires_at = None
            operation.execution_admission = None
            operation.ambiguity_reason = reason

    def reconcile(
        self,
        operation_id: str,
        resolution: ReconciliationResolution,
        *,
        reconciliation_revision: str,
        confirmed_outcome: EffectResultLink | None = None,
    ) -> OperationState:
        evidence = ReconciliationEvidence(
            operation_id=operation_id,
            reconciliation_revision=reconciliation_revision,
            resolution=resolution,
            confirmed_outcome=confirmed_outcome,
        )
        with self._lock:
            operation = self._require(operation_id)
            if operation.state is not OperationState.RECONCILIATION_REQUIRED:
                raise InvalidTransition("only ambiguous operation can be reconciled")
            key = (operation_id, reconciliation_revision)
            existing = self._reconciliation_evidence.get(key)
            if existing is not None and existing != evidence:
                raise InvalidTransition("reconciliation revision cannot be reused for different evidence")
            self._reconciliation_evidence[key] = evidence
            operation.reconciliation_revision = reconciliation_revision
            operation.reconciliation_resolution = resolution
            if resolution is ReconciliationResolution.STILL_UNKNOWN:
                return operation.state
            if resolution is ReconciliationResolution.EFFECT_CONFIRMED:
                operation.state = OperationState.COMPLETED
                operation.outcome = confirmed_outcome
                operation.ambiguity_reason = None
                return operation.state
            operation.state = OperationState.PREPARED
            operation.outcome = None
            operation.ambiguity_reason = None
            return operation.state

    def state(self, operation_id: str) -> OperationState:
        with self._lock:
            return self._require(operation_id).state

    def outcome(self, operation_id: str) -> EffectResultLink | None:
        with self._lock:
            return self._require(operation_id).outcome

    def execution_admission(self, operation_id: str) -> AsyncExecutionAdmission | None:
        with self._lock:
            return self._require(operation_id).execution_admission

    def reconciliation_resolution(self, operation_id: str) -> ReconciliationResolution | None:
        with self._lock:
            return self._require(operation_id).reconciliation_resolution

    def reconciliation_revision(self, operation_id: str) -> str | None:
        with self._lock:
            return self._require(operation_id).reconciliation_revision

    def reconciliation_evidence(
        self,
        operation_id: str,
        reconciliation_revision: str,
    ) -> ReconciliationEvidence | None:
        identifier(operation_id, "operation_id")
        identifier(reconciliation_revision, "reconciliation_revision")
        with self._lock:
            return self._reconciliation_evidence.get((operation_id, reconciliation_revision))

    def _block_for_reconciliation(self, operation: _Operation, reason: str) -> None:
        operation.state = OperationState.RECONCILIATION_REQUIRED
        operation.executor_id = None
        operation.attempt_expires_at = None
        operation.execution_admission = None
        operation.ambiguity_reason = reason
        operation.reconciliation_revision = None
        operation.reconciliation_resolution = None

    def _require(self, operation_id: str) -> _Operation:
        identifier(operation_id, "operation_id")
        operation = self._operations.get(operation_id)
        if operation is None:
            raise InvalidTransition("unknown operation_id")
        return operation

    def _require_current_attempt(self, attempt: OperationAttempt, observed_at: datetime) -> _Operation:
        if not isinstance(attempt, OperationAttempt):
            raise InvalidTransition("current OperationAttempt is required")
        operation = self._require(attempt.operation_id)
        if operation.state is OperationState.ATTEMPTING and operation.attempt_expires_at is not None:
            if operation.attempt_expires_at <= observed_at:
                self._block_for_reconciliation(
                    operation,
                    "attempt_lease_expired_effect_absence_unproven",
                )
        if (
            operation.state is not OperationState.ATTEMPTING
            or operation.executor_id != attempt.executor_id
            or operation.attempt_generation != attempt.attempt_generation
            or operation.attempt_expires_at != attempt.attempt_expires_at
            or operation.execution_admission != attempt.execution_admission
        ):
            raise InvalidTransition("stale/non-owner/expired operation attempt cannot mutate state")
        return operation
