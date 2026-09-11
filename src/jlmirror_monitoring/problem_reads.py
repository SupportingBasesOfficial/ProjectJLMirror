from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, Sequence

from .problem_state import CanonicalProblemState, ProblemSeverityClass

MAX_PROBLEM_PAGE_SIZE = 200
MAX_PROBLEM_RESPONSE_BYTES = 1_048_576


class ProblemGenerationState(StrEnum):
    ACTIVE = "active_generation"
    HISTORICAL = "historical_generation"


class ProblemCursorInvalidError(ValueError):
    """Sparse cursor failure: callers must not infer whether the anchor exists elsewhere."""


@dataclass(frozen=True)
class ProblemListFilters:
    tenant_id: str
    monitoring_source_id: str | None = None
    monitoring_resource_id: str | None = None
    generation_state: ProblemGenerationState = ProblemGenerationState.ACTIVE
    problem_state: CanonicalProblemState | None = None
    severity_class: ProblemSeverityClass | None = None
    opened_from_epoch_seconds: int | None = None
    opened_to_epoch_seconds: int | None = None

    def __post_init__(self) -> None:
        if not self.tenant_id or len(self.tenant_id) > 256:
            raise ValueError("tenant_id must be bounded non-empty text")
        for name, value, ceiling in (
            ("monitoring_source_id", self.monitoring_source_id, 512),
            ("monitoring_resource_id", self.monitoring_resource_id, 512),
        ):
            if value is not None and (not value or len(value) > ceiling):
                raise ValueError(f"{name} must be bounded non-empty text when supplied")
        if self.opened_from_epoch_seconds is not None and self.opened_from_epoch_seconds <= 0:
            raise ValueError("opened_from must be positive when supplied")
        if self.opened_to_epoch_seconds is not None and self.opened_to_epoch_seconds <= 0:
            raise ValueError("opened_to must be positive when supplied")
        if (
            self.opened_from_epoch_seconds is not None
            and self.opened_to_epoch_seconds is not None
            and self.opened_from_epoch_seconds >= self.opened_to_epoch_seconds
        ):
            raise ValueError("opened_from must be earlier than opened_to")


@dataclass(frozen=True)
class ProblemCursorAnchor:
    problem_id: str
    opened_at_epoch_seconds: int

    def __post_init__(self) -> None:
        if not self.problem_id or len(self.problem_id) > 512:
            raise ValueError("problem cursor identity must be bounded non-empty text")
        if self.opened_at_epoch_seconds <= 0:
            raise ValueError("problem cursor opened_at must be positive")


@dataclass(frozen=True)
class ProblemReadRow:
    tenant_id: str
    problem_id: str
    monitoring_source_id: str
    monitoring_resource_id: str
    source_instance_generation: str
    active_source_instance_generation: str
    problem_state: CanonicalProblemState
    severity_class: ProblemSeverityClass
    summary: str
    opened_at_epoch_seconds: int
    resolved_at_epoch_seconds: int | None
    evidence_state: str
    provider_acknowledged: bool
    serialized_size_bytes: int

    def __post_init__(self) -> None:
        for name, value, ceiling in (
            ("tenant_id", self.tenant_id, 256),
            ("problem_id", self.problem_id, 512),
            ("monitoring_source_id", self.monitoring_source_id, 512),
            ("monitoring_resource_id", self.monitoring_resource_id, 512),
            ("source_instance_generation", self.source_instance_generation, 512),
            ("active_source_instance_generation", self.active_source_instance_generation, 512),
        ):
            if not value or len(value) > ceiling:
                raise ValueError(f"{name} must be bounded non-empty text")
        if not self.summary or len(self.summary) > 8192:
            raise ValueError("problem summary must be bounded non-empty text")
        if self.opened_at_epoch_seconds <= 0:
            raise ValueError("opened_at must be positive")
        if self.resolved_at_epoch_seconds is not None and self.resolved_at_epoch_seconds <= 0:
            raise ValueError("resolved_at must be positive when supplied")
        if self.serialized_size_bytes <= 0 or self.serialized_size_bytes > MAX_PROBLEM_RESPONSE_BYTES:
            raise ValueError("serialized problem row exceeds bounded response policy")

    @property
    def generation_state(self) -> ProblemGenerationState:
        if self.source_instance_generation == self.active_source_instance_generation:
            return ProblemGenerationState.ACTIVE
        return ProblemGenerationState.HISTORICAL


@dataclass(frozen=True)
class ProblemReadPage:
    items: tuple[ProblemReadRow, ...]
    next_cursor: str | None
    cache_control: str = "no-store"


class ProblemReadAuthorizer(Protocol):
    def authorize_problem_read(self, filters: ProblemListFilters) -> None:
        """Re-establish current auth/placement/owning authorization for this exact page/filter set."""
        ...


class MonitoringProblemReadRepository(Protocol):
    def resolve_problem_anchor(
        self,
        filters: ProblemListFilters,
        problem_id: str,
    ) -> ProblemCursorAnchor | None:
        """Resolve an anchor only when it is currently eligible under exactly these filters."""
        ...

    def list_problem_rows(
        self,
        filters: ProblemListFilters,
        *,
        after: ProblemCursorAnchor | None,
        limit: int,
    ) -> Sequence[ProblemReadRow]:
        """Return authoritative rows ordered by opened_at DESC, problem_id ASC."""
        ...


def _sort_key(row: ProblemReadRow) -> tuple[int, str]:
    return (-row.opened_at_epoch_seconds, row.problem_id)


def _matches_filters(row: ProblemReadRow, filters: ProblemListFilters) -> bool:
    if row.tenant_id != filters.tenant_id:
        return False
    if filters.monitoring_source_id is not None and row.monitoring_source_id != filters.monitoring_source_id:
        return False
    if filters.monitoring_resource_id is not None and row.monitoring_resource_id != filters.monitoring_resource_id:
        return False
    if row.generation_state is not filters.generation_state:
        return False
    if filters.problem_state is not None and row.problem_state is not filters.problem_state:
        return False
    if filters.severity_class is not None and row.severity_class is not filters.severity_class:
        return False
    if (
        filters.opened_from_epoch_seconds is not None
        and row.opened_at_epoch_seconds < filters.opened_from_epoch_seconds
    ):
        return False
    if (
        filters.opened_to_epoch_seconds is not None
        and row.opened_at_epoch_seconds >= filters.opened_to_epoch_seconds
    ):
        return False
    return True


def list_problem_page(
    filters: ProblemListFilters,
    *,
    authorizer: ProblemReadAuthorizer,
    repository: MonitoringProblemReadRepository,
    cursor: str | None = None,
    limit: int = 100,
) -> ProblemReadPage:
    if limit < 1 or limit > MAX_PROBLEM_PAGE_SIZE:
        raise ValueError("problem page limit exceeds bounded policy")
    if cursor is not None and (not cursor or len(cursor) > 512):
        raise ProblemCursorInvalidError("validation.cursor_invalid")

    # Possession of an anchor never carries authority. Current tenant/source/resource
    # ownership and generation eligibility are re-established for every page.
    authorizer.authorize_problem_read(filters)

    anchor: ProblemCursorAnchor | None = None
    if cursor is not None:
        anchor = repository.resolve_problem_anchor(filters, cursor)
        if anchor is None or anchor.problem_id != cursor:
            raise ProblemCursorInvalidError("validation.cursor_invalid")

    rows = tuple(repository.list_problem_rows(filters, after=anchor, limit=limit + 1))
    if len(rows) > limit + 1:
        raise ValueError("problem repository violated bounded page contract")
    if tuple(sorted(rows, key=_sort_key)) != rows:
        raise ValueError("problem repository violated deterministic ordering contract")
    if any(not _matches_filters(row, filters) for row in rows):
        raise ValueError("problem repository returned a row outside current filters")

    emitted = rows[:limit]
    if sum(row.serialized_size_bytes for row in emitted) > MAX_PROBLEM_RESPONSE_BYTES:
        raise ValueError("problem response exceeds bounded serialized byte budget")

    next_cursor = emitted[-1].problem_id if len(rows) > limit and emitted else None
    return ProblemReadPage(tuple(emitted), next_cursor)
