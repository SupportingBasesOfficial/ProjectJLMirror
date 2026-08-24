from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol

from .model import AdmissionDenied

MAX_SIGNED_BIGINT = 9_223_372_036_854_775_807
EFFECT_ELIGIBLE_FENCE_AUTHORITY_STATE = "active"
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$")


def _identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise ValueError(f"{field} must be an explicit canonical identifier")
    return value


def _epoch(value: object, field: str) -> int:
    if type(value) is not int or not 0 < value <= MAX_SIGNED_BIGINT:
        raise ValueError(f"{field} outside positive signed BIGINT range")
    return value


@dataclass(frozen=True)
class FenceRecord:
    fence_scope_id: str
    current_fence_epoch: int
    current_generation_id: str
    authority_state: str

    def __post_init__(self) -> None:
        _identifier(self.fence_scope_id, "fence_scope_id")
        _identifier(self.current_generation_id, "current_generation_id")
        _identifier(self.authority_state, "authority_state")
        _epoch(self.current_fence_epoch, "current_fence_epoch")


@dataclass(frozen=True)
class FenceToken:
    fence_scope_id: str
    fence_epoch: int
    generation_id: str

    def __post_init__(self) -> None:
        _identifier(self.fence_scope_id, "fence_scope_id")
        _identifier(self.generation_id, "generation_id")
        _epoch(self.fence_epoch, "fence_epoch")


class FenceAuthorityPort(Protocol):
    def current(self, fence_scope_id: str) -> FenceRecord | None:
        """Return current owning fence state."""

    def acquire_successor(
        self,
        *,
        fence_scope_id: str,
        expected_predecessor_epoch: int,
        expected_predecessor_generation_id: str,
        successor_generation_id: str,
        successor_state: str,
    ) -> FenceRecord | None:
        """Atomically compare exact active predecessor + increment epoch; None means no winner."""


def _require_effect_eligible_authority_state(state: object) -> None:
    if state != EFFECT_ELIGIBLE_FENCE_AUTHORITY_STATE:
        raise AdmissionDenied("fence authority state is not effect-eligible")


def admit_fenced_effect(*, token: FenceToken, current: FenceRecord) -> None:
    """Reject non-active, stale, wrong-scope, wrong-generation and forged-higher fence claims."""

    if not isinstance(token, FenceToken) or not isinstance(current, FenceRecord):
        raise AdmissionDenied("fence evidence is malformed")
    _require_effect_eligible_authority_state(current.authority_state)
    if token.fence_scope_id != current.fence_scope_id:
        raise AdmissionDenied("fence scope mismatch")
    if token.fence_epoch != current.current_fence_epoch:
        raise AdmissionDenied("fence epoch is not exactly current")
    if token.generation_id != current.current_generation_id:
        raise AdmissionDenied("fence generation binding is not current")


def acquire_next_fence(
    *,
    authority: FenceAuthorityPort,
    fence_scope_id: str,
    expected_predecessor_epoch: int,
    successor_generation_id: str,
    successor_state: str = EFFECT_ELIGIBLE_FENCE_AUTHORITY_STATE,
    expected_predecessor_generation_id: str | None = None,
) -> FenceRecord:
    try:
        _identifier(fence_scope_id, "fence_scope_id")
        _identifier(successor_generation_id, "successor_generation_id")
        _identifier(successor_state, "successor_state")
    except ValueError as exc:
        raise AdmissionDenied("fence acquisition input is not canonical") from exc
    if type(expected_predecessor_epoch) is not int or expected_predecessor_epoch <= 0:
        raise AdmissionDenied("expected predecessor epoch must be a positive integer")
    if expected_predecessor_epoch >= MAX_SIGNED_BIGINT:
        raise AdmissionDenied("fence epoch exhausted; governed migration required")

    observed = authority.current(fence_scope_id)
    if not isinstance(observed, FenceRecord):
        raise AdmissionDenied("expected fence predecessor is absent or malformed")
    if observed.fence_scope_id != fence_scope_id:
        raise AdmissionDenied("fence authority returned predecessor from another scope")
    _require_effect_eligible_authority_state(observed.authority_state)
    if observed.current_fence_epoch != expected_predecessor_epoch:
        raise AdmissionDenied("expected fence predecessor is not current")
    predecessor_generation = (
        expected_predecessor_generation_id
        if expected_predecessor_generation_id is not None
        else observed.current_generation_id
    )
    try:
        _identifier(predecessor_generation, "expected_predecessor_generation_id")
    except ValueError as exc:
        raise AdmissionDenied("expected fence predecessor generation is malformed") from exc
    if observed.current_generation_id != predecessor_generation:
        raise AdmissionDenied("expected fence predecessor generation is not current")

    winner = authority.acquire_successor(
        fence_scope_id=fence_scope_id,
        expected_predecessor_epoch=expected_predecessor_epoch,
        expected_predecessor_generation_id=predecessor_generation,
        successor_generation_id=successor_generation_id,
        successor_state=successor_state,
    )
    if not isinstance(winner, FenceRecord):
        raise AdmissionDenied("fence successor acquisition lost or returned malformed authority")
    if winner.fence_scope_id != fence_scope_id:
        raise AdmissionDenied("fence authority returned the wrong scope")
    if winner.current_fence_epoch != expected_predecessor_epoch + 1:
        raise AdmissionDenied("fence authority returned a non-monotonic successor")
    if winner.current_generation_id != successor_generation_id:
        raise AdmissionDenied("fence authority returned the wrong successor generation")
    if winner.authority_state != successor_state:
        raise AdmissionDenied("fence authority returned the wrong successor state")
    return winner
