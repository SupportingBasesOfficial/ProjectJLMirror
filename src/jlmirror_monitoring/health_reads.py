from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, Sequence

from .health_projection import EvidenceState, HealthClass, MAX_HEALTH_PAGE_ROWS, MAX_HEALTH_SERIALIZED_BYTES


class HealthGenerationState(StrEnum):
    ACTIVE = "active_generation"
    HISTORICAL = "historical_generation"


class HealthCursorInvalidError(ValueError):
    """Cursor validation is intentionally sparse and carries no authorization signal."""


@dataclass(frozen=True)
class HealthListFilters:
    tenant_id: str
    monitoring_source_id: str | None = None
    generation_state: HealthGenerationState = HealthGenerationState.ACTIVE
    health_class: HealthClass | None = None
    evidence_state: EvidenceState | None = None

    def __post_init__(self) -> None:
        if not self.tenant_id or len(self.tenant_id) > 256:
            raise ValueError("tenant_id must be bounded non-empty text")
        if self.monitoring_source_id is not None and (
            not self.monitoring_source_id or len(self.monitoring_source_id) > 512
        ):
            raise ValueError("monitoring_source_id must be bounded non-empty text when supplied")


@dataclass(frozen=True)
class HealthReadRow:
    tenant_id: str
    monitoring_resource_id: str
    monitoring_source_id: str
    source_instance_generation: str
    active_source_instance_generation: str
    health_class: HealthClass
    evidence_state: EvidenceState
    projection_revision: int
    serialized_size_bytes: int

    @property
    def generation_state(self) -> HealthGenerationState:
        if self.source_instance_generation == self.active_source_instance_generation:
            return HealthGenerationState.ACTIVE
        return HealthGenerationState.HISTORICAL


@dataclass(frozen=True)
class HealthReadPage:
    items: tuple[HealthReadRow, ...]
    next_cursor: str | None
    cache_control: str = "private, no-cache"
    cache_profile: str = "private_revalidate"


class HealthReadAuthorizer(Protocol):
    def authorize_health_read(self, filters: HealthListFilters) -> None:
        """Re-establish current tenant/placement/action authority for this exact request."""
        ...


class MonitoringHealthReadRepository(Protocol):
    def resolve_health_anchor(
        self,
        filters: HealthListFilters,
        monitoring_resource_id: str,
    ) -> HealthReadRow | None:
        """Resolve the anchor only when currently eligible under exactly these filters."""
        ...

    def list_health_rows(
        self,
        filters: HealthListFilters,
        *,
        after_monitoring_resource_id: str | None,
        limit: int,
    ) -> Sequence[HealthReadRow]:
        """Return rows ordered by monitoring_resource_id ASC."""
        ...


def _matches(row: HealthReadRow, filters: HealthListFilters) -> bool:
    if row.tenant_id != filters.tenant_id:
        return False
    if filters.monitoring_source_id is not None and row.monitoring_source_id != filters.monitoring_source_id:
        return False
    if row.generation_state is not filters.generation_state:
        return False
    if filters.health_class is not None and row.health_class is not filters.health_class:
        return False
    if filters.evidence_state is not None and row.evidence_state is not filters.evidence_state:
        return False
    return True


def list_health_page(
    filters: HealthListFilters,
    *,
    authorizer: HealthReadAuthorizer,
    repository: MonitoringHealthReadRepository,
    cursor: str | None = None,
    limit: int = 100,
) -> HealthReadPage:
    if limit < 1 or limit > MAX_HEALTH_PAGE_ROWS:
        raise ValueError("health page limit exceeds bounded policy")
    if cursor is not None and (not cursor or len(cursor) > 512):
        raise HealthCursorInvalidError("validation.cursor_invalid")

    authorizer.authorize_health_read(filters)

    after: str | None = None
    if cursor is not None:
        anchor = repository.resolve_health_anchor(filters, cursor)
        if anchor is None or anchor.monitoring_resource_id != cursor or not _matches(anchor, filters):
            raise HealthCursorInvalidError("validation.cursor_invalid")
        after = cursor

    rows = tuple(repository.list_health_rows(filters, after_monitoring_resource_id=after, limit=limit + 1))
    if len(rows) > limit + 1:
        raise ValueError("health repository violated bounded page contract")
    if tuple(sorted(rows, key=lambda row: row.monitoring_resource_id)) != rows:
        raise ValueError("health repository violated deterministic ordering contract")
    if any(not _matches(row, filters) for row in rows):
        raise ValueError("health repository returned a row outside current filters")

    emitted = rows[:limit]
    if sum(row.serialized_size_bytes for row in emitted) > MAX_HEALTH_SERIALIZED_BYTES:
        raise ValueError("health response exceeds bounded serialized byte budget")

    next_cursor = emitted[-1].monitoring_resource_id if len(rows) > limit and emitted else None
    return HealthReadPage(tuple(emitted), next_cursor)
