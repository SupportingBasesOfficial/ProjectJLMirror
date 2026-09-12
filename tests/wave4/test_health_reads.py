from __future__ import annotations

import unittest

from jlmirror_monitoring.health_projection import EvidenceState, HealthClass, MAX_HEALTH_PAGE_ROWS
from jlmirror_monitoring.health_reads import (
    HealthCursorInvalidError,
    HealthGenerationState,
    HealthListFilters,
    HealthReadRow,
    list_health_page,
)


class _Authorizer:
    def __init__(self) -> None:
        self.calls: list[HealthListFilters] = []

    def authorize_health_read(self, filters: HealthListFilters) -> None:
        self.calls.append(filters)


class _Repository:
    def __init__(self, rows: list[HealthReadRow]) -> None:
        self.rows = rows

    def resolve_health_anchor(self, filters: HealthListFilters, monitoring_resource_id: str) -> HealthReadRow | None:
        return next((row for row in self.rows if row.monitoring_resource_id == monitoring_resource_id), None)

    def list_health_rows(
        self,
        filters: HealthListFilters,
        *,
        after_monitoring_resource_id: str | None,
        limit: int,
    ) -> list[HealthReadRow]:
        rows = [row for row in self.rows if after_monitoring_resource_id is None or row.monitoring_resource_id > after_monitoring_resource_id]
        return rows[:limit]


def _row(resource_id: str, *, tenant_id: str = "tenant-1", generation: str = "gen-1", active: str = "gen-1") -> HealthReadRow:
    return HealthReadRow(
        tenant_id=tenant_id,
        monitoring_resource_id=resource_id,
        monitoring_source_id="source-1",
        source_instance_generation=generation,
        active_source_instance_generation=active,
        health_class=HealthClass.HEALTHY,
        evidence_state=EvidenceState.CURRENT,
        projection_revision=1,
        serialized_size_bytes=128,
    )


class HealthReadTests(unittest.TestCase):
    def test_page_reauthorizes_and_uses_resource_anchor(self) -> None:
        filters = HealthListFilters("tenant-1")
        authorizer = _Authorizer()
        repository = _Repository([_row("r-1"), _row("r-2"), _row("r-3")])
        page = list_health_page(filters, authorizer=authorizer, repository=repository, limit=2)
        self.assertEqual(tuple(row.monitoring_resource_id for row in page.items), ("r-1", "r-2"))
        self.assertEqual(page.next_cursor, "r-2")
        self.assertEqual(page.cache_profile, "private_revalidate")
        self.assertEqual(authorizer.calls, [filters])

    def test_cursor_is_revalidated_under_current_filters(self) -> None:
        filters = HealthListFilters("tenant-1", health_class=HealthClass.DEGRADED)
        authorizer = _Authorizer()
        repository = _Repository([_row("r-1")])
        with self.assertRaises(HealthCursorInvalidError):
            list_health_page(filters, authorizer=authorizer, repository=repository, cursor="r-1")
        self.assertEqual(authorizer.calls, [filters])

    def test_cross_tenant_row_is_rejected(self) -> None:
        filters = HealthListFilters("tenant-1")
        with self.assertRaises(ValueError):
            list_health_page(filters, authorizer=_Authorizer(), repository=_Repository([_row("r-1", tenant_id="tenant-2")]))

    def test_historical_row_does_not_match_active_default(self) -> None:
        filters = HealthListFilters("tenant-1")
        with self.assertRaises(ValueError):
            list_health_page(filters, authorizer=_Authorizer(), repository=_Repository([_row("r-1", generation="old", active="new")]))
        historical = HealthListFilters("tenant-1", generation_state=HealthGenerationState.HISTORICAL)
        page = list_health_page(historical, authorizer=_Authorizer(), repository=_Repository([_row("r-1", generation="old", active="new")]))
        self.assertEqual(len(page.items), 1)

    def test_ordering_and_limits_are_enforced(self) -> None:
        filters = HealthListFilters("tenant-1")
        with self.assertRaises(ValueError):
            list_health_page(filters, authorizer=_Authorizer(), repository=_Repository([_row("r-2"), _row("r-1")]))
        with self.assertRaises(ValueError):
            list_health_page(filters, authorizer=_Authorizer(), repository=_Repository([]), limit=MAX_HEALTH_PAGE_ROWS + 1)

    def test_byte_budget_is_enforced(self) -> None:
        huge = HealthReadRow(
            tenant_id="tenant-1",
            monitoring_resource_id="r-1",
            monitoring_source_id="source-1",
            source_instance_generation="gen-1",
            active_source_instance_generation="gen-1",
            health_class=HealthClass.HEALTHY,
            evidence_state=EvidenceState.CURRENT,
            projection_revision=1,
            serialized_size_bytes=1_048_577,
        )
        with self.assertRaises(ValueError):
            list_health_page(HealthListFilters("tenant-1"), authorizer=_Authorizer(), repository=_Repository([huge]))


if __name__ == "__main__":
    unittest.main()
