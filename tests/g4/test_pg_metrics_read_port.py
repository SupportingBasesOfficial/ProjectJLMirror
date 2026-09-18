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


class PgReadTests(unittest.TestCase):
    def test_definition_list_is_resource_scoped_and_active_generation_only(self):
        pg = FakePg([json.dumps([definition_row()])])
        rows = G4.PgMetricsReadPort(pg).list_definitions(
            tenant_id="tenant-a",
            monitoring_resource_id="resource-101",
        )
        self.assertEqual(rows[0].metric_definition_id, "metric-cpu")
        sql, variables = pg.calls[0]
        self.assertEqual(variables, {"tenant":"tenant-a","resource_id":"resource-101"})
        self.assertIn("SET LOCAL jlmirror.tenant_id=:'tenant'", sql)
        self.assertIn("active_source_instance_generation", sql)
        self.assertIn("monitoring_resource_id=:'resource_id'", sql)

    def test_current_list_does_not_query_history(self):
        row = {
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
        pg = FakePg([json.dumps([row])])
        G4.PgMetricsReadPort(pg).list_current(
            tenant_id="tenant-a",
            monitoring_resource_id="resource-101",
        )
        sql = pg.calls[0][0].lower()
        self.assertIn("metric_current_state", sql)
        self.assertNotIn("metric_observation o", sql)

    def test_history_is_exact_metric_and_finite_window(self):
        pg = FakePg([
            json.dumps({**definition_row(), "provider_object_kind":"zabbix_item", "provider_external_ref":"2001"}),
            json.dumps([]),
            json.dumps([{
                "coverage_state":"finalized",
                "finalized_through_clock":1758175200,
                "finalized_through_at":"2025-09-18T06:00:00+00:00",
            }]),
        ])
        result = G4.PgMetricsReadPort(pg).history(
            tenant_id="tenant-a",
            metric_definition_id="metric-cpu",
            from_ts="2025-09-18T05:00:00Z",
            to_ts="2025-09-18T06:00:00Z",
            limit=100,
        )
        history_sql, variables = pg.calls[1]
        self.assertEqual(variables["metric_id"], "metric-cpu")
        self.assertEqual(variables["from_ts"], "2025-09-18T05:00:00Z")
        self.assertEqual(variables["to_ts"], "2025-09-18T06:00:00Z")
        self.assertIn("o.observed_at >= :'from_ts'::timestamptz", history_sql)
        self.assertIn("o.observed_at < :'to_ts'::timestamptz", history_sql)
        self.assertEqual(result.coverage.state, "complete")

    def test_finalized_checkpoint_short_of_window_is_incomplete(self):
        pg = FakePg([
            json.dumps({**definition_row(), "provider_object_kind":"zabbix_item", "provider_external_ref":"2001"}),
            json.dumps([]),
            json.dumps([{
                "coverage_state":"finalized",
                "finalized_through_clock":1758171600,
                "finalized_through_at":"2025-09-18T05:00:00+00:00",
            }]),
        ])
        result = G4.PgMetricsReadPort(pg).history(
            tenant_id="tenant-a",
            metric_definition_id="metric-cpu",
            from_ts="2025-09-18T05:00:00Z",
            to_ts="2025-09-18T06:00:00Z",
            limit=100,
        )
        self.assertEqual(result.coverage.state, "incomplete")


if __name__ == "__main__":
    unittest.main()
