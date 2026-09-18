from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "apps/g3-resource-inventory"))


def load_bff():
    path = ROOT / "apps/g3-resource-inventory/bff_server.py"
    spec = importlib.util.spec_from_file_location("jlmirror_g3_pg_read_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("G3 BFF cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


G3 = load_bff()


def canonical_row(*, generation_state: str = "active_generation") -> dict:
    return {
        "monitoring_resource_id": "resource-101",
        "monitoring_source_id": "source-a",
        "source_instance_generation": "generation-a",
        "generation_state": generation_state,
        "display_name": "Core Switch",
        "resource_kind": "host",
        "scope_state": "in_scope",
        "scope_projection_revision": 1,
        "scope_evidence_state": "current",
        "presence_state": "present",
        "presence_evidence_state": "current",
        "provider_object_kind": "zabbix_host",
        "provider_external_ref": "101",
        "last_observed_at": "2026-09-18T00:00:00+00:00",
        "last_confirmed_present_at": "2026-09-18T00:00:00+00:00",
        "created_at": "2026-09-18T00:00:00+00:00",
        "updated_at": "2026-09-18T00:00:00+00:00",
    }


class FakePg:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, str]]] = []

    def query(self, sql: str, **variables: str) -> str:
        self.calls.append((sql, variables))
        return self.responses.pop(0)


class PgResourceReadPortTests(unittest.TestCase):
    def test_list_is_tenant_scoped_and_active_generation_only(self):
        pg = FakePg([json.dumps([canonical_row()])])
        rows = G3.PgResourceReadPort(pg).list_active(tenant_id="tenant-a")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].monitoring_resource_id, "resource-101")

        sql, variables = pg.calls[0]
        self.assertEqual(variables, {"tenant": "tenant-a"})
        self.assertIn("SET LOCAL jlmirror.tenant_id=:'tenant'", sql)
        self.assertIn("FROM monitoring.monitoring_resource r", sql)
        self.assertIn("JOIN monitoring.monitoring_source s", sql)
        self.assertIn("r.source_instance_generation=s.active_source_instance_generation", sql)
        self.assertIn("ORDER BY r.monitoring_resource_id", sql)

    def test_detail_derives_historical_generation_against_current_source_pointer(self):
        pg = FakePg([json.dumps(canonical_row(generation_state="historical_generation"))])
        row = G3.PgResourceReadPort(pg).get(
            tenant_id="tenant-a",
            monitoring_resource_id="resource-101",
        )
        self.assertEqual(row.generation_state, "historical_generation")

        sql, variables = pg.calls[0]
        self.assertEqual(variables, {"tenant": "tenant-a", "resource_id": "resource-101"})
        self.assertIn("CASE", sql)
        self.assertIn("active_source_instance_generation", sql)
        self.assertIn("r.monitoring_resource_id=:'resource_id'", sql)

    def test_list_rejects_unbounded_result(self):
        pg = FakePg([json.dumps([canonical_row()] * 501)])
        with self.assertRaises(RuntimeError):
            G3.PgResourceReadPort(pg).list_active(tenant_id="tenant-a")

    def test_projection_shape_drift_fails_closed(self):
        drifted = canonical_row()
        drifted["unexpected"] = "field"
        pg = FakePg([json.dumps([drifted])])
        with self.assertRaises(RuntimeError):
            G3.PgResourceReadPort(pg).list_active(tenant_id="tenant-a")


if __name__ == "__main__":
    unittest.main()
