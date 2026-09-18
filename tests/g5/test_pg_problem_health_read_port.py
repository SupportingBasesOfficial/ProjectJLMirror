from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"apps/g5-problem-health"))


def load_bff():
    path=ROOT/"apps/g5-problem-health/bff_server.py"
    spec=importlib.util.spec_from_file_location("jlmirror_g5_pg_test",path)
    if spec is None or spec.loader is None:
        raise RuntimeError("G5 BFF cannot be loaded")
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    return module


G5=load_bff()


class FakePg:
    def __init__(self,responses):
        self.responses=list(responses)
        self.calls=[]
    def query(self,sql,**variables):
        self.calls.append((sql,variables))
        return self.responses.pop(0)


def problem_row(problem_id="problem-1",opened_at="2026-09-18T05:00:00+00:00"):
    return {
        "problem_id":problem_id,
        "monitoring_source_id":"source-a",
        "source_instance_generation":"generation-a",
        "generation_state":"active_generation",
        "monitoring_resource_id":"resource-101",
        "summary":"CPU threshold exceeded",
        "problem_state":"active",
        "severity_class":"warning",
        "opened_at":opened_at,
        "resolved_at":None,
        "last_confirmed_at":"2026-09-18T05:10:00+00:00",
        "evidence_state":"current",
        "provider_object_kind":None,
        "provider_external_ref":None,
    }


def health_row(resource_id="resource-101"):
    return {
        "monitoring_resource_id":resource_id,
        "monitoring_source_id":"source-a",
        "source_instance_generation":"generation-a",
        "generation_state":"active_generation",
        "scope_state":"in_scope",
        "scope_evidence_state":"current",
        "presence_state":"present",
        "presence_evidence_state":"current",
        "health_class":"degraded",
        "evidence_state":"current",
        "projection_revision":3,
        "last_changed_at":"2026-09-18T05:00:01+00:00",
        "last_evidence_at":"2026-09-18T05:10:01+00:00",
        "reason_refs":["problem-1"],
    }


class PgReadTests(unittest.TestCase):
    def test_problem_page_uses_same_snapshot_anchor_and_canonical_order(self):
        pg=FakePg([json.dumps({"cursor_valid":True,"items":[problem_row()]})])
        rows,next_cursor=G5.PgProblemHealthReadPort(pg).list_problems(
            tenant_id="tenant-a",
            monitoring_source_id=None,
            monitoring_resource_id="resource-101",
            generation_state="active_generation",
            problem_state=None,
            severity_class=None,
            cursor=None,
            limit=100,
        )
        self.assertEqual(rows[0].problem_id,"problem-1")
        self.assertIsNone(next_cursor)
        sql,variables=pg.calls[0]
        self.assertIn("REPEATABLE READ READ ONLY",sql)
        self.assertIn("ORDER BY e.opened_at DESC,e.problem_id ASC",sql)
        self.assertIn("active_source_instance_generation",sql)
        self.assertEqual(variables["resource_id"],"resource-101")
        self.assertEqual(variables["fetch_limit"],"101")

    def test_problem_cursor_is_revalidated_in_same_filters_and_generation(self):
        pg=FakePg([json.dumps({"cursor_valid":False,"items":[]})])
        with self.assertRaises(ValueError):
            G5.PgProblemHealthReadPort(pg).list_problems(
                tenant_id="tenant-a",
                monitoring_source_id="source-a",
                monitoring_resource_id="resource-101",
                generation_state="active_generation",
                problem_state="active",
                severity_class="warning",
                cursor="problem-old",
                limit=100,
            )
        sql,variables=pg.calls[0]
        self.assertEqual(variables["cursor"],"problem-old")
        self.assertIn("FROM eligible",sql)
        self.assertIn("problem_state=:'problem_state'",sql)
        self.assertIn("severity_class=:'severity_class'",sql)
        self.assertEqual(len(pg.calls),1)

    def test_problem_limit_plus_one_returns_problem_anchor(self):
        pg=FakePg([json.dumps({"cursor_valid":True,"items":[
            problem_row("problem-1","2026-09-18T05:00:00+00:00"),
            problem_row("problem-2","2026-09-18T04:00:00+00:00"),
        ]})])
        rows,next_cursor=G5.PgProblemHealthReadPort(pg).list_problems(
            tenant_id="tenant-a",
            monitoring_source_id=None,
            monitoring_resource_id=None,
            generation_state="active_generation",
            problem_state=None,
            severity_class=None,
            cursor=None,
            limit=1,
        )
        self.assertEqual([r.problem_id for r in rows],["problem-1"])
        self.assertEqual(next_cursor,"problem-1")

    def test_health_page_uses_same_snapshot_anchor(self):
        pg=FakePg([json.dumps({"cursor_valid":True,"items":[health_row()]})])
        rows,next_cursor=G5.PgProblemHealthReadPort(pg).list_health(
            tenant_id="tenant-a",
            monitoring_source_id=None,
            generation_state="active_generation",
            health_class=None,
            evidence_state=None,
            scope_state=None,
            cursor=None,
            limit=100,
        )
        self.assertEqual(rows[0].monitoring_resource_id,"resource-101")
        self.assertIsNone(next_cursor)
        sql,variables=pg.calls[0]
        self.assertIn("REPEATABLE READ READ ONLY",sql)
        self.assertIn("monitoring_resource_id=:'cursor'",sql)
        self.assertIn("presence_state",sql)
        self.assertEqual(variables["fetch_limit"],"101")

    def test_health_cursor_wrong_filter_fails_closed(self):
        pg=FakePg([json.dumps({"cursor_valid":False,"items":[]})])
        with self.assertRaises(ValueError):
            G5.PgProblemHealthReadPort(pg).list_health(
                tenant_id="tenant-a",
                monitoring_source_id="source-a",
                generation_state="active_generation",
                health_class="healthy",
                evidence_state="current",
                scope_state="in_scope",
                cursor="resource-other",
                limit=100,
            )
        self.assertEqual(len(pg.calls),1)

    def test_health_detail_rejects_ambiguous_generation_rows(self):
        pg=FakePg([json.dumps([health_row(),{**health_row(),"source_instance_generation":"generation-old","generation_state":"historical_generation"}])])
        with self.assertRaises(RuntimeError):
            G5.PgProblemHealthReadPort(pg).get_health(
                tenant_id="tenant-a",
                monitoring_resource_id="resource-101",
            )


if __name__=="__main__":
    unittest.main()
