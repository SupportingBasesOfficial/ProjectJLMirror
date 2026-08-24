"""Small deterministic reference models for Wave 0 conformance harnesses.

These are test oracles, not runtime implementations and never hold Product or
security authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import Lock


class IdempotencyDecision(str, Enum):
    EXECUTE = "execute"
    OBSERVE_IN_PROGRESS = "observe_in_progress"
    REPLAY_COMPLETED = "replay_completed"
    CONFLICT = "conflict"


@dataclass
class IdempotencyRecord:
    fingerprint: str
    completed: bool = False
    outcome: str | None = None


@dataclass
class IdempotencyReference:
    records: dict[tuple[str, str], IdempotencyRecord] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock, repr=False, compare=False)

    def begin(self, scope: str, key: str, fingerprint: str) -> IdempotencyDecision:
        identity = (scope, key)
        with self._lock:
            existing = self.records.get(identity)
            if existing is None:
                self.records[identity] = IdempotencyRecord(fingerprint=fingerprint)
                return IdempotencyDecision.EXECUTE
            if existing.fingerprint != fingerprint:
                return IdempotencyDecision.CONFLICT
            if existing.completed:
                return IdempotencyDecision.REPLAY_COMPLETED
            return IdempotencyDecision.OBSERVE_IN_PROGRESS

    def complete(self, scope: str, key: str, outcome: str) -> None:
        with self._lock:
            record = self.records[(scope, key)]
            record.completed = True
            record.outcome = outcome


def tenant_effect_allowed(
    *, derived_tenant: str, requested_tenant: str, current_authority: bool
) -> bool:
    return current_authority and derived_tenant == requested_tenant


def ambiguous_external_effect_disposition(
    effect_proven_absent: bool, effect_proven_present: bool
) -> str:
    if effect_proven_absent and effect_proven_present:
        raise ValueError("contradictory effect evidence")
    if effect_proven_present:
        return "observe_completed_effect"
    if effect_proven_absent:
        return "safe_new_attempt_subject_to_current_authority"
    return "reconciliation_required"


@dataclass
class FenceReference:
    current_epoch: int = 1
    _lock: Lock = field(default_factory=Lock, repr=False, compare=False)

    def acquire_successor(self, expected_epoch: int) -> int:
        with self._lock:
            if expected_epoch != self.current_epoch:
                raise ValueError("stale predecessor")
            if self.current_epoch >= (2**63 - 1):
                raise OverflowError("fence epoch exhausted; fail closed")
            self.current_epoch += 1
            return self.current_epoch

    def effect_allowed(self, epoch: int) -> bool:
        with self._lock:
            return epoch == self.current_epoch

    def restore(
        self, restored_epoch: int, *, surviving_currentness_proven: bool = False
    ) -> str:
        with self._lock:
            if restored_epoch < self.current_epoch:
                return "quarantine_and_fence_forward"
            if not surviving_currentness_proven:
                return "quarantine_and_reconcile"
            if restored_epoch > self.current_epoch:
                self.current_epoch = restored_epoch
            return "continuity_proven"


@dataclass
class RecoveryReference:
    restore_marker: int
    fence_marker: int
    unresolved_sequences: set[int] = field(default_factory=set)
    current_authorities_proven: bool = False

    def __post_init__(self) -> None:
        if self.fence_marker < self.restore_marker:
            raise ValueError("F must not be before R")
        invalid = {
            n
            for n in self.unresolved_sequences
            if not (self.restore_marker < n <= self.fence_marker)
        }
        if invalid:
            raise ValueError("unresolved obligations must be inside (R,F]")

    def reconcile(self, sequence: int) -> None:
        self.unresolved_sequences.discard(sequence)

    def admission_allowed(self) -> bool:
        return self.current_authorities_proven and not self.unresolved_sequences
