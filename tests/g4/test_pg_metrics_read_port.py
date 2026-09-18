from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "apps/g4-metrics"))


def load_bff():
    path = ROOT / "apps/g4-metrics/bff_server.py"
    spec = importlib.util.spec_from_file_location("jlmirror_g4_pg_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("G4 BFF cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


G4 = load_bff()


class FakePg:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, str]]] = []

    def query(self, sql: str, **variables: str) -> str:
        self.calls.append((sql, variables))
        return self.responses.pop(0)


def definition_row() -> dict:
    return {
        "metric_definition_id":"metric-cpu",
        "monitoring_resource_id":"resource-101",
        "monitoring_source_id":"source-a",
        "source_instance_generation":"generation-a",
        "generation_state":"active_generation",
        "name":"CPU utilization",
        "value_kind":"number",
        "unit":"%",
        "scope_state":"in_scope",
        "scope_projection_revision":1,
        "scope_evidence_state":"current",
        "definition_state":"active",
        "provider_object_kind":None,
        "provider_external_ref":None,
    }


def current_row() -> dict:
    return {
        "metric_definition_id":"metric-cpu",
        "monitoring_resource_id":"resource-101",
        "monitoring_source_id":"source-a",
        "source_instance_generation":"generation-a",
        "generation_state":"active_generation",
        "scope_state":"in_scope",
        "scope_evidence_state":"current",
        "current_observation_id":"obs-2",
        "observed_at":"2026-09-18T05:10:00+00:00",
        "accepted_at":"2026-09-18T05:10:01+00:00",
        "value_kind":"number",
        "value":42.5,
        "evidence_state":"current",
        "projection_revision":2,
        "last_changed_at":"2026-09-18T05:10:01+00:00",
    }


def history_payload(*, cursor_valid=True, finalized_at="2025-09-18T06:00:00+00:00", items=None):
    detail = {**definition_row(), "provider_object_kind":"zabbix_item", "provider_external_ref":"2001"}
    return {
        "definition": detail,
        "cursor_valid": cursor_valid,
        "items": [] if items is None else items,
        "coverage": [{
            "coverage_state":"finalized",
            "finalized_through_clock":1758175200,
            "finalized_through_at": finalized_at,
        }],
    }


class PgReadTests(unittest.TestCase):
    def test_definition_list_is_resource_scoped_and_active_generation_only(self):
        pg = FakePg([json.dumps({"cursor_valid": True, "items": [definition_row()]})])
        rows, next_cursor = G4.PgMetricsReadPort(pg).list_definitions(
            tenant_id="tenant-a",
            monitoring_resource_id="resource-101",
            cursor=None,
            limit=100,
        )
        self.assertEqual(rows[0].metric_definition_id, "metric-cpu")
        self.assertIsNone(next_cursor)
        sql, variables = pg.calls[0]
        self.assertEqual(variables, {
            "tenant":"tenant-a",
            "resource_id":"resource-101",
            "cursor":"",
            "fetch_limit":"101",
        })
        self.assertIn("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY", sql)
        self.assertIn("active_source_instance_generation", sql)
        self.assertIn("monitoring_resource_id=:'resource_id'", sql)
        self.assertIn("'cursor_valid'", sql)

    def test_current_list_does_not_query_history(self):
        pg = FakePg([json.dumps({"cursor_valid": True, "items": [current_row()]})])
        rows, next_cursor = G4.PgMetricsReadPort(pg).list_current(
            tenant_id="tenant-a",
            monitoring_resource_id="resource-101",
            cursor=None,
            limit=100,
        )
        self.assertEqual(len(rows), 1)
        self.assertIsNone(next_cursor)
        sql = pg.calls[0][0].lower()
        self.assertIn("metric_current_state", sql)
        self.assertNotIn("metric_observation o", sql)

    def test_definition_page_uses_limit_plus_one_and_returns_anchor(self):
        first = definition_row()
        second = {**definition_row(), "metric_definition_id":"metric-mem", "name":"Memory"}
        pg = FakePg([json.dumps({"cursor_valid": True, "items": [first, second]})])
        rows, next_cursor = G4.PgMetricsReadPort(pg).list_definitions(
            tenant_id="tenant-a",
            monitoring_resource_id="resource-101",
            cursor=None,
            limit=1,
        )
        self.assertEqual([row.metric_definition_id for row in rows], ["metric-cpu"])
        self.assertEqual(next_cursor, "metric-cpu")
        self.assertEqual(pg.calls[0][1]["fetch_limit"], "2")

    def test_definition_cursor_is_validated_in_same_snapshot_and_scope(self):
        pg = FakePg([json.dumps({"cursor_valid": False, "items": []})])
        with self.assertRaises(ValueError):
            G4.PgMetricsReadPort(pg).list_definitions(
                tenant_id="tenant-a",
                monitoring_resource_id="resource-101",
                cursor="metric-other",
                limit=100,
            )
        sql, variables = pg.calls[0]
        self.assertEqual(variables["cursor"], "metric-other")
        self.assertIn("WITH eligible AS", sql)
        self.assertIn("FROM eligible WHERE metric_definition_id=:'cursor'", sql)
        self.assertIn("active_source_instance_generation", sql)
        self.assertEqual(len(pg.calls), 1)

    def test_history_cursor_is_validated_in_same_metric_window_and_snapshot(self):
        pg = FakePg([json.dumps(history_payload(cursor_valid=False))])
        with self.assertRaises(ValueError):
            G4.PgMetricsReadPort(pg).history(
                tenant_id="tenant-a",
                metric_definition_id="metric-cpu",
                from_ts="2025-09-18T05:00:00Z",
                to_ts="2025-09-18T06:00:00Z",
                cursor="obs-outside-window",
                limit=100,
            )
        sql, variables = pg.calls[0]
        self.assertEqual(variables["cursor"], "obs-outside-window")
        self.assertIn("observation_id=:'cursor'", sql)
        self.assertIn("observed_at >= :'from_ts'::timestamptz", sql)
        self.assertIn("observed_at < :'to_ts'::timestamptz", sql)
        self.assertIn("'coverage'", sql)
        self.assertEqual(len(pg.calls), 1)

    def test_history_is_exact_metric_finite_window_and_single_snapshot(self):
        pg = FakePg([json.dumps(history_payload())])
        result = G4.PgMetricsReadPort(pg).history(
            tenant_id="tenant-a",
            metric_definition_id="metric-cpu",
            from_ts="2025-09-18T05:00:00Z",
            to_ts="2025-09-18T06:00:00Z",
            cursor=None,
            limit=100,
        )
        sql, variables = pg.calls[0]
        self.assertEqual(variables["metric_id"], "metric-cpu")
        self.assertEqual(variables["from_ts"], "2025-09-18T05:00:00Z")
        self.assertEqual(variables["to_ts"], "2025-09-18T06:00:00Z")
        self.assertEqual(variables["fetch_limit"], "101")
        self.assertIn("WITH definition AS", sql)
        self.assertIn("anchor_row AS", sql)
        self.assertIn("coverage AS", sql)
        self.assertEqual(result.coverage.state, "complete")
        self.assertIsNone(result.next_cursor)
        self.assertEqual(len(pg.calls), 1)

    def test_finalized_checkpoint_short_of_window_is_incomplete(self):
        pg = FakePg([json.dumps(history_payload(finalized_at="2025-09-18T05:00:00+00:00"))])
        result = G4.PgMetricsReadPort(pg).history(
            tenant_id="tenant-a",
            metric_definition_id="metric-cpu",
            from_ts="2025-09-18T05:00:00Z",
            to_ts="2025-09-18T06:00:00Z",
            cursor=None,
            limit=100,
        )
        self.assertEqual(result.coverage.state, "incomplete")

    def test_history_limit_plus_one_returns_observation_anchor(self):
        first = {
            "observation_id":"obs-1",
            "metric_definition_id":"metric-cpu",
            "monitoring_resource_id":"resource-101",
            "monitoring_source_id":"source-a",
            "source_instance_generation":"generation-a",
            "observed_at":"2025-09-18T05:00:00+00:00",
            "accepted_at":"2025-09-18T05:00:01+00:00",
            "value_kind":"number",
            "value":40.0,
        }
        second = {**first, "observation_id":"obs-2", "observed_at":"2025-09-18T05:01:00+00:00"}
        pg = FakePg([json.dumps(history_payload(items=[first, second]))])
        result = G4.PgMetricsReadPort(pg).history(
            tenant_id="tenant-a",
            metric_definition_id="metric-cpu",
            from_ts="2025-09-18T05:00:00Z",
            to_ts="2025-09-18T06:00:00Z",
            cursor=None,
            limit=1,
        )
        self.assertEqual([row.observation_id for row in result.observations], ["obs-1"])
        self.assertEqual(result.next_cursor, "obs-1")


if __name__ == "__main__":
    unittest.main()
