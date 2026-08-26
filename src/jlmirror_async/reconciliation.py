from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from .model import (
    EffectResultLink,
    InvalidTransition,
    OperationState,
    ReconciliationBlocked,
    ReconciliationResolution,
    identifier,
)


@dataclass(frozen=True)
class OperationAttempt:
    operation_id: str
    attempt_generation: int
    executor_id: str


@dataclass
class _Operation:
    operation_id: str
    tenant_id: str | None
    owner_contract: str
    state: OperationState = OperationState.PREPARED
    attempt_generation: int = 0
    executor_id: str | None = None
    outcome: EffectResultLink | None = None
    ambiguity_reason: str | None = None


class InMemoryCrossAuthorityOperationLedger:
    """Reference model for stable-operation ambiguity and reconciliation.

    A timeout/lost response cannot be interpreted as effect absence. Another
    attempt becomes eligible only after an accepted reconciliation proves absence.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._operations: dict[str, _Operation] = {}

    def prepare(
        self,
        operation_id: str,
        owner_contract: str,
        *,
        tenant_id: str | None = None,
    ) -> None:
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
            self._operations[operation_id] = _Operation(
                operation_id=operation_id,
                tenant_id=tenant_id,
                owner_contract=owner_contract,
            )

    def begin_attempt(self, operation_id: str, executor_id: str) -> OperationAttempt:
        identifier(executor_id, "executor_id")
        with self._lock:
            operation = self._require(operation_id)
            if operation.state is OperationState.RECONCILIATION_REQUIRED:
                raise ReconciliationBlocked("ambiguous operation must reconcile before another attempt")
            if operation.state is not OperationState.PREPARED:
                raise InvalidTransition("operation is not eligible for a new effect attempt")
            operation.state = OperationState.ATTEMPTING
            operation.attempt_generation += 1
            operation.executor_id = executor_id
            return OperationAttempt(
                operation_id=operation_id,
                attempt_generation=operation.attempt_generation,
                executor_id=executor_id,
            )

    def complete(self, attempt: OperationAttempt, outcome: EffectResultLink) -> None:
        if not isinstance(outcome, EffectResultLink):
            raise ValueError("cross-authority completion requires durable result identity")
        with self._lock:
            operation = self._require_current_attempt(attempt)
            operation.state = OperationState.COMPLETED
            operation.outcome = outcome
            operation.executor_id = None
            operation.ambiguity_reason = None

    def mark_ambiguous(self, attempt: OperationAttempt, reason: str) -> None:
        identifier(reason, "reason")
        with self._lock:
            operation = self._require_current_attempt(attempt)
            operation.state = OperationState.RECONCILIATION_REQUIRED
            operation.executor_id = None
            operation.ambiguity_reason = reason

    def fail_terminal(self, attempt: OperationAttempt, reason: str) -> None:
        identifier(reason, "reason")
        with self._lock:
            operation = self._require_current_attempt(attempt)
            operation.state = OperationState.FAILED_TERMINAL
            operation.executor_id = None
            operation.ambiguity_reason = reason

    def reconcile(
        self,
        operation_id: str,
        resolution: ReconciliationResolution,
        *,
        confirmed_outcome: EffectResultLink | None = None,
    ) -> OperationState:
        if not isinstance(resolution, ReconciliationResolution):
            raise ValueError("resolution must be canonical")
        with self._lock:
            operation = self._require(operation_id)
            if operation.state is not OperationState.RECONCILIATION_REQUIRED:
                raise InvalidTransition("only ambiguous operation can be reconciled")

            if resolution is ReconciliationResolution.STILL_UNKNOWN:
                return operation.state
            if resolution is ReconciliationResolution.EFFECT_CONFIRMED:
                if not isinstance(confirmed_outcome, EffectResultLink):
                    raise ValueError("confirmed effect requires durable outcome identity")
                operation.state = OperationState.COMPLETED
                operation.outcome = confirmed_outcome
                operation.ambiguity_reason = None
                return operation.state
            if confirmed_outcome is not None:
                raise ValueError("proven-absent resolution cannot carry confirmed outcome")
            operation.state = OperationState.PREPARED
            operation.ambiguity_reason = None
            return operation.state

    def state(self, operation_id: str) -> OperationState:
        with self._lock:
            return self._require(operation_id).state

    def outcome(self, operation_id: str) -> EffectResultLink | None:
        with self._lock:
            return self._require(operation_id).outcome

    def _require(self, operation_id: str) -> _Operation:
        identifier(operation_id, "operation_id")
        operation = self._operations.get(operation_id)
        if operation is None:
            raise InvalidTransition("unknown operation_id")
        return operation

    def _require_current_attempt(self, attempt: OperationAttempt) -> _Operation:
        if not isinstance(attempt, OperationAttempt):
            raise InvalidTransition("current OperationAttempt is required")
        operation = self._require(attempt.operation_id)
        if (
            operation.state is not OperationState.ATTEMPTING
            or operation.executor_id != attempt.executor_id
            or operation.attempt_generation != attempt.attempt_generation
        ):
            raise InvalidTransition("stale/non-owner operation attempt cannot mutate state")
        return operation
