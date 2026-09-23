from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/g4-metrics"))

from metrics import (  # noqa: E402
    HistoryCoverage,
    HistoryRead,
    MetricCurrentRecord,
    MetricDefinitionRecord,
    MetricObservationRecord,
    MetricsView,
    METRIC_READ_ACTION,
    RESOURCE_READ_ACTION,
)


class Authorization:
    def __init__(self) -> None:
        self.actor_ref = "principal-a"
        self.calls: list[tuple[str, str, str]] = []
        self.revoked = False

    def require(self, *, actor_ref: str, tenant_id: str, action: str):
        if self.revoked:
            raise RuntimeError("revoked")
        self.calls.append((actor_ref, tenant_id, action))
        return object()


def definition(*, generation="active_generation") -> MetricDefinitionRecord:
    return MetricDefinitionRecord(
        metric_definition_id="metric-cpu",
        monitoring_resource_id="resource-101",
        monitoring_source_id="source-a",
        source_instance_generation="generation-a",
        generation_state=generation,
        name="CPU utilization",
        value_kind="number",
        unit="%",
        scope_state="in_scope",
        scope_projection_revision=1,
        scope_evidence_state="current",
        definition_state="active",
        provider_object_kind="zabbix_item",
        provider_external_ref="2001",
    )


def current(*, generation="active_generation", evidence="current", value=42.5) -> MetricCurrentRecord:
    return MetricCurrentRecord(
        metric_definition_id="metric-cpu",
        monitoring_resource_id="resource-101",
        monitoring_source_id="source-a",
        source_instance_generation="generation-a",
        generation_state=generation,
        scope_state="in_scope",
        scope_evidence_state="current",
        current_observation_id="obs-2" if value is not None else None,
        observed_at="2026-09-18T05:10:00Z" if value is not None else None,
        accepted_at="2026-09-18T05:10:01Z" if value is not None else None,
        value_kind="number",
        value=value,
        evidence_state=evidence,
        projection_revision=2,
        last_changed_at="2026-09-18T05:10:01Z" if value is not None else None,
    )


def observation(*, generation="generation-a", metric="metric-cpu") -> MetricObservationRecord:
    return MetricObservationRecord(
        observation_id="obs-1",
        metric_definition_id=metric,
        monitoring_resource_id="resource-101",
        monitoring_source_id="source-a",
        source_instance_generation=generation,
        observed_at="2026-09-18T05:00:00Z",
        accepted_at="2026-09-18T05:00:01Z",
        value_kind="number",
        value=40.0,
    )


class Repository:
    def __init__(self) -> None:
        self.definition = definition()
        self.current = current()
        self.coverage = HistoryCoverage(
            state="complete",
            covered_through="2026-09-18T06:00:00Z",
            gap_refs=(),
        )
        self.observations = (observation(),)

    def list_definitions(
        self,
        *,
        tenant_id: str,
        monitoring_resource_id: str,
        cursor: str | None,
        limit: int,
    ):
        if cursor == "invalid":
            raise ValueError("cursor_invalid")
        rows = (self.definition,) if tenant_id == "tenant-a" and monitoring_resource_id == "resource-101" else ()
        return rows[:limit], "metric-next" if rows and limit == 1 and self.definition.metric_definition_id != "metric-next" else None

    def get_definition(self, *, tenant_id: str, metric_definition_id: str):
        return self.definition if tenant_id == "tenant-a" and metric_definition_id == "metric-cpu" else None

    def list_current(
        self,
        *,
        tenant_id: str,
        monitoring_resource_id: str,
        cursor: str | None,
        limit: int,
    ):
        if cursor == "invalid":
            raise ValueError("cursor_invalid")
        rows = (self.current,) if tenant_id == "tenant-a" and monitoring_resource_id == "resource-101" else ()
        return rows[:limit], "metric-next" if rows and limit == 1 else None

    def get_current(self, *, tenant_id: str, metric_definition_id: str):
        return self.current if tenant_id == "tenant-a" and metric_definition_id == "metric-cpu" else None

    def history(
        self,
        *,
        tenant_id: str,
        metric_definition_id: str,
        from_ts: str,
        to_ts: str,
        cursor: str | None,
        limit: int,
    ):
        if cursor == "invalid":
            raise ValueError("cursor_invalid")
        if tenant_id != "tenant-a" or metric_definition_id != "metric-cpu":
            return None
        return HistoryRead(
            definition=self.definition,
            coverage=self.coverage,
            observations=self.observations[:limit],
            next_cursor="obs-next" if len(self.observations) > limit else None,
        )


class MetricsTests(unittest.TestCase):
    def test_definitions_are_metadata_only_and_reauthorize(self):
        auth = Authorization()
        view = MetricsView(repository=Repository(), authorization=auth).list_definitions(
            tenant_id="tenant-a",
            monitoring_resource_id="resource-101",
        )
        item = view["items"][0]
        self.assertEqual(item["metric_definition_id"], "metric-cpu")
        self.assertNotIn("value", item)
        self.assertNotIn("external_references", item)
        self.assertEqual(auth.calls, [
            ("principal-a", "tenant-a", RESOURCE_READ_ACTION),
            ("principal-a", "tenant-a", METRIC_READ_ACTION),
            ("principal-a", "tenant-a", RESOURCE_READ_ACTION),
            ("principal-a", "tenant-a", METRIC_READ_ACTION),
        ])

    def test_definition_list_preserves_anchor_continuation(self):
        view = MetricsView(repository=Repository(), authorization=Authorization()).list_definitions(
            tenant_id="tenant-a",
            monitoring_resource_id="resource-101",
            limit=1,
        )
        self.assertEqual(view["next_cursor"], "metric-next")

    def test_current_list_preserves_anchor_continuation(self):
        view = MetricsView(repository=Repository(), authorization=Authorization()).list_current(
            tenant_id="tenant-a",
            monitoring_resource_id="resource-101",
            limit=1,
        )
        self.assertEqual(view["next_cursor"], "metric-next")

    def test_invalid_cursor_fails_closed(self):
        service = MetricsView(repository=Repository(), authorization=Authorization())
        with self.assertRaises(ValueError):
            service.list_definitions(
                tenant_id="tenant-a",
                monitoring_resource_id="resource-101",
                cursor="invalid",
            )
        with self.assertRaises(ValueError):
            service.history(
                tenant_id="tenant-a",
                metric_definition_id="metric-cpu",
                from_ts="2026-09-18T05:00:00Z",
                to_ts="2026-09-18T06:00:00Z",
                cursor="invalid",
            )

    def test_definition_detail_exposes_only_bounded_provider_reference(self):
        view = MetricsView(repository=Repository(), authorization=Authorization()).get_definition(
            tenant_id="tenant-a",
            metric_definition_id="metric-cpu",
        )
        self.assertEqual(view["external_references"], {
            "provider_object_kind": "zabbix_item",
            "provider_external_ref": "2001",
        })

    def test_missing_current_value_remains_null_not_zero(self):
        repo = Repository()
        repo.current = current(value=None, evidence="incomplete")
        item = MetricsView(repository=repo, authorization=Authorization()).list_current(
            tenant_id="tenant-a",
            monitoring_resource_id="resource-101",
        )["items"][0]
        self.assertIsNone(item["value"])
        self.assertIsNone(item["current_observation_id"])
        self.assertEqual(item["evidence_state"], "incomplete")

    def test_historical_current_can_never_present_as_current(self):
        repo = Repository()
        repo.current = current(generation="historical_generation", evidence="current")
        item = MetricsView(repository=repo, authorization=Authorization()).get_current(
            tenant_id="tenant-a",
            metric_definition_id="metric-cpu",
        )
        self.assertEqual(item["generation_state"], "historical_generation")
        self.assertEqual(item["evidence_state"], "stale")

    def test_scope_uncertainty_downgrades_current_evidence(self):
        repo = Repository()
        repo.current = replace(repo.current, scope_evidence_state="reconciliation_required")
        item = MetricsView(repository=repo, authorization=Authorization()).get_current(
            tenant_id="tenant-a",
            metric_definition_id="metric-cpu",
        )
        self.assertEqual(item["evidence_state"], "reconciliation_required")

    def test_history_requires_finite_window(self):
        service = MetricsView(repository=Repository(), authorization=Authorization())
        with self.assertRaises(ValueError):
            service.history(
                tenant_id="tenant-a",
                metric_definition_id="metric-cpu",
                from_ts="2026-09-17T00:00:00Z",
                to_ts="2026-09-19T00:00:01Z",
            )

    def test_history_preserves_explicit_completeness(self):
        value = MetricsView(repository=Repository(), authorization=Authorization()).history(
            tenant_id="tenant-a",
            metric_definition_id="metric-cpu",
            from_ts="2026-09-18T05:00:00Z",
            to_ts="2026-09-18T06:00:00Z",
        )
        self.assertEqual(value["completeness"]["state"], "complete")
        self.assertEqual(value["items"][0]["metric_definition_id"], "metric-cpu")
        self.assertIsNone(value["next_cursor"])

    def test_complete_history_requires_covered_through(self):
        repo = Repository()
        repo.coverage = HistoryCoverage(state="complete", covered_through=None, gap_refs=())
        with self.assertRaises(RuntimeError):
            MetricsView(repository=repo, authorization=Authorization()).history(
                tenant_id="tenant-a",
                metric_definition_id="metric-cpu",
                from_ts="2026-09-18T05:00:00Z",
                to_ts="2026-09-18T06:00:00Z",
            )

    def test_complete_history_must_cover_requested_to(self):
        repo = Repository()
        repo.coverage = HistoryCoverage(
            state="complete",
            covered_through="2026-09-18T05:30:00Z",
            gap_refs=(),
        )
        with self.assertRaises(RuntimeError):
            MetricsView(repository=repo, authorization=Authorization()).history(
                tenant_id="tenant-a",
                metric_definition_id="metric-cpu",
                from_ts="2026-09-18T05:00:00Z",
                to_ts="2026-09-18T06:00:00Z",
            )

    def test_history_rejects_cross_metric_union(self):
        repo = Repository()
        repo.observations = (observation(metric="metric-other"),)
        with self.assertRaises(RuntimeError):
            MetricsView(repository=repo, authorization=Authorization()).history(
                tenant_id="tenant-a",
                metric_definition_id="metric-cpu",
                from_ts="2026-09-18T05:00:00Z",
                to_ts="2026-09-18T06:00:00Z",
            )

    def test_history_rejects_cross_generation_union(self):
        repo = Repository()
        repo.observations = (observation(generation="generation-old"),)
        with self.assertRaises(RuntimeError):
            MetricsView(repository=repo, authorization=Authorization()).history(
                tenant_id="tenant-a",
                metric_definition_id="metric-cpu",
                from_ts="2026-09-18T05:00:00Z",
                to_ts="2026-09-18T06:00:00Z",
            )


if __name__ == "__main__":
    unittest.main()
