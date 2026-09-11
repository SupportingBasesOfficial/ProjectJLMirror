from __future__ import annotations

import unittest

from jlmirror_monitoring.problem_reads import (
    MAX_PROBLEM_PAGE_SIZE,
    MAX_PROBLEM_RESPONSE_BYTES,
    MonitoringProblemReadRepository,
    ProblemCursorAnchor,
    ProblemCursorInvalidError,
    ProblemGenerationState,
    ProblemListFilters,
    ProblemReadAuthorizer,
    ProblemReadRow,
    list_problem_page,
)
from jlmirror_monitoring.problem_state import CanonicalProblemState, ProblemSeverityClass


def row(
    problem_id: str,
    opened_at: int,
    *,
    tenant_id: str = "tenant-a",
    source_generation: str = "gen-active",
    active_generation: str = "gen-active",
    state: CanonicalProblemState = CanonicalProblemState.ACTIVE,
    severity: ProblemSeverityClass = ProblemSeverityClass.WARNING,
    size: int = 100,
) -> ProblemReadRow:
    return ProblemReadRow(
        tenant_id=tenant_id,
        problem_id=problem_id,
        monitoring_source_id="source-a",
        monitoring_resource_id="resource-a",
        source_instance_generation=source_generation,
        active_source_instance_generation=active_generation,
        problem_state=state,
        severity_class=severity,
        summary=f"problem {problem_id}",
        opened_at_epoch_seconds=opened_at,
        resolved_at_epoch_seconds=None if state is CanonicalProblemState.ACTIVE else opened_at + 10,
        evidence_state="current",
        provider_acknowledged=False,
        serialized_size_bytes=size,
    )


class FakeAuthorizer(ProblemReadAuthorizer):
    def __init__(self) -> None:
        self.calls: list[ProblemListFilters] = []

    def authorize_problem_read(self, filters: ProblemListFilters) -> None:
        self.calls.append(filters)


class FakeRepository(MonitoringProblemReadRepository):
    def __init__(self, rows: tuple[ProblemReadRow, ...]) -> None:
        self.rows = rows
        self.resolve_calls = 0

    def resolve_problem_anchor(
        self,
        filters: ProblemListFilters,
        problem_id: str,
    ) -> ProblemCursorAnchor | None:
        self.resolve_calls += 1
        for item in self.rows:
            if (
                item.problem_id == problem_id
                and item.tenant_id == filters.tenant_id
                and item.generation_state is filters.generation_state
            ):
                return ProblemCursorAnchor(item.problem_id, item.opened_at_epoch_seconds)
        return None

    def list_problem_rows(
        self,
        filters: ProblemListFilters,
        *,
        after: ProblemCursorAnchor | None,
        limit: int,
    ) -> tuple[ProblemReadRow, ...]:
        eligible = [item for item in self.rows if item.generation_state is filters.generation_state]
        if after is not None:
            anchor_key = (-after.opened_at_epoch_seconds, after.problem_id)
            eligible = [item for item in eligible if (-item.opened_at_epoch_seconds, item.problem_id) > anchor_key]
        return tuple(eligible[:limit])


class ProblemReadContractTests(unittest.TestCase):
    def test_page_order_and_anchor_cursor_are_deterministic(self) -> None:
        repository = FakeRepository((row("a", 300), row("b", 300), row("c", 200)))
        authorizer = FakeAuthorizer()
        filters = ProblemListFilters("tenant-a")

        first = list_problem_page(filters, authorizer=authorizer, repository=repository, limit=2)
        self.assertEqual([item.problem_id for item in first.items], ["a", "b"])
        self.assertEqual(first.next_cursor, "b")
        self.assertEqual(first.cache_control, "no-store")

        second = list_problem_page(
            filters,
            authorizer=authorizer,
            repository=repository,
            cursor=first.next_cursor,
            limit=2,
        )
        self.assertEqual([item.problem_id for item in second.items], ["c"])
        self.assertIsNone(second.next_cursor)
        self.assertEqual(authorizer.calls, [filters, filters])
        self.assertEqual(repository.resolve_calls, 1)

    def test_cursor_is_only_anchor_identity_and_wrong_generation_fails_sparsely(self) -> None:
        repository = FakeRepository(
            (row("historical", 100, source_generation="gen-old", active_generation="gen-active"),)
        )
        filters = ProblemListFilters("tenant-a", generation_state=ProblemGenerationState.ACTIVE)
        with self.assertRaisesRegex(ProblemCursorInvalidError, "validation.cursor_invalid"):
            list_problem_page(
                filters,
                authorizer=FakeAuthorizer(),
                repository=repository,
                cursor="historical",
            )

    def test_cross_tenant_anchor_fails_sparsely(self) -> None:
        repository = FakeRepository((row("foreign", 100, tenant_id="tenant-b"),))
        filters = ProblemListFilters("tenant-a")
        with self.assertRaisesRegex(ProblemCursorInvalidError, "validation.cursor_invalid"):
            list_problem_page(
                filters,
                authorizer=FakeAuthorizer(),
                repository=repository,
                cursor="foreign",
            )

    def test_default_generation_is_active_only(self) -> None:
        repository = FakeRepository(
            (
                row("active", 200),
                row("old", 100, source_generation="gen-old", active_generation="gen-active"),
            )
        )
        page = list_problem_page(
            ProblemListFilters("tenant-a"),
            authorizer=FakeAuthorizer(),
            repository=repository,
        )
        self.assertEqual([item.problem_id for item in page.items], ["active"])

    def test_historical_active_problem_remains_historical_evidence(self) -> None:
        historical = row(
            "old-active",
            100,
            source_generation="gen-old",
            active_generation="gen-active",
            state=CanonicalProblemState.ACTIVE,
        )
        self.assertIs(historical.generation_state, ProblemGenerationState.HISTORICAL)
        repository = FakeRepository((historical,))
        page = list_problem_page(
            ProblemListFilters("tenant-a", generation_state=ProblemGenerationState.HISTORICAL),
            authorizer=FakeAuthorizer(),
            repository=repository,
        )
        self.assertEqual(page.items[0].problem_state, CanonicalProblemState.ACTIVE)
        self.assertIs(page.items[0].generation_state, ProblemGenerationState.HISTORICAL)

    def test_page_limit_and_serialized_byte_budget_are_finite(self) -> None:
        with self.assertRaises(ValueError):
            list_problem_page(
                ProblemListFilters("tenant-a"),
                authorizer=FakeAuthorizer(),
                repository=FakeRepository(()),
                limit=MAX_PROBLEM_PAGE_SIZE + 1,
            )

        repository = FakeRepository(
            (
                row("a", 300, size=MAX_PROBLEM_RESPONSE_BYTES // 2 + 1),
                row("b", 200, size=MAX_PROBLEM_RESPONSE_BYTES // 2 + 1),
            )
        )
        with self.assertRaisesRegex(ValueError, "serialized byte budget"):
            list_problem_page(
                ProblemListFilters("tenant-a"),
                authorizer=FakeAuthorizer(),
                repository=repository,
                limit=2,
            )

    def test_repository_cannot_return_cross_tenant_row(self) -> None:
        repository = FakeRepository((row("foreign", 100, tenant_id="tenant-b"),))
        with self.assertRaisesRegex(ValueError, "outside current filters"):
            list_problem_page(
                ProblemListFilters("tenant-a"),
                authorizer=FakeAuthorizer(),
                repository=repository,
            )

    def test_repository_cannot_return_rows_outside_requested_filters(self) -> None:
        repository = FakeRepository((row("p1", 100),))
        filters = ProblemListFilters("tenant-a", monitoring_resource_id="resource-b")
        with self.assertRaisesRegex(ValueError, "outside current filters"):
            list_problem_page(filters, authorizer=FakeAuthorizer(), repository=repository)

    def test_repository_order_violation_fails_closed(self) -> None:
        repository = FakeRepository((row("later", 100), row("earlier", 200)))
        with self.assertRaisesRegex(ValueError, "deterministic ordering"):
            list_problem_page(
                ProblemListFilters("tenant-a"),
                authorizer=FakeAuthorizer(),
                repository=repository,
            )


if __name__ == "__main__":
    unittest.main()
