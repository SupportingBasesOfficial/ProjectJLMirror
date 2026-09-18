from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"apps/g7-alert-policy-lifecycle"))

from read_ui import AuthContext, detail_api, list_api, render_detail, render_list


class FakeRead:
    def list_alerts(self, tenant_id, limit):
        return [{
            "alert_id":"alert-1","lifecycle_state":"active",
            "source_kind":"monitoring_problem","source_subject_id":"problem-1",
            "policy_id":"policy-a","policy_version":1,
        }][:limit]

    def get_alert(self, tenant_id, alert_id):
        if alert_id!="alert-1": return None
        return {
            "alert_id":"alert-1","lifecycle_state":"active",
            "source_kind":"monitoring_problem","source_subject_id":"problem-1",
            "policy_id":"policy-a","policy_version":1,
            "transitions":[{"to_lifecycle_state":"active","occurred_at":"2026-09-18T12:00:00Z"}],
        }


class ReadUiTests(unittest.TestCase):
    def setUp(self):
        self.port=FakeRead()
        self.auth=AuthContext("tenant-a","user-a",frozenset({"alerts:read"}))

    def test_list_is_bounded_and_tenant_protected(self):
        self.assertEqual(list_api(self.port,self.auth,500)["limit"],100)
        with self.assertRaises(PermissionError):
            list_api(self.port,AuthContext("tenant-a","user-a",frozenset()))

    def test_detail_and_html_expose_only_g7_facts(self):
        detail=detail_api(self.port,self.auth,"alert-1")
        self.assertEqual(detail["lifecycle_state"],"active")
        self.assertIn("<h1>Alerts</h1>",render_list(self.port,self.auth))
        self.assertIn("Lifecycle: active",render_detail(self.port,self.auth,"alert-1"))


if __name__=="__main__":
    unittest.main()
