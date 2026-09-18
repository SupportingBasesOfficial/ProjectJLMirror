from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"apps/g8-human-operations"))

from read_ui import AuthContext,alert_api,resource_api,render_alert


class FakePort:
    def alert_human_operations(self,tenant_id,alert_id):
        if alert_id!="alert-a":
            raise KeyError(alert_id)
        return {
            "alert_id":"alert-a",
            "alert_lifecycle_state":"active",
            "current_action":{"owner_principal_id":"principal-owner","action_kind":"investigate_alert"},
            "acknowledgements":[{"principal_id":"principal-ack","acknowledged_at":"2026-09-18T12:00:00Z"}],
            "visibility":[{"viewer_side":"customer","visibility_state":"not_viewed_yet"}],
            "timeline":[{"kind":"acknowledged","occurred_at":"2026-09-18T12:00:00Z"}],
        }

    def resource_responsibilities(self,tenant_id,resource_id):
        return [
            {"principal_id":"principal-a","responsibility_role":"technical_responsible"},
            {"principal_id":"principal-b","responsibility_role":"service_owner"},
        ]


class ReadUiTests(unittest.TestCase):
    def setUp(self):
        self.port=FakePort()
        self.auth=AuthContext("tenant-a","principal-reader",frozenset({"human-operations:read"}))

    def test_dimensions_remain_distinct(self):
        value=alert_api(self.port,self.auth,"alert-a")
        self.assertEqual(value["current_action"]["owner_principal_id"],"principal-owner")
        self.assertEqual(value["acknowledgements"][0]["principal_id"],"principal-ack")
        self.assertNotEqual(
            value["current_action"]["owner_principal_id"],
            value["acknowledgements"][0]["principal_id"],
        )
        html=render_alert(self.port,self.auth,"alert-a")
        self.assertIn("Current action",html)
        self.assertIn("Acknowledgements",html)
        self.assertIn("Visibility",html)

    def test_multiple_resource_responsibles(self):
        rows=resource_api(self.port,self.auth,"resource-a")["items"]
        self.assertEqual(len(rows),2)

    def test_scope_required(self):
        with self.assertRaises(PermissionError):
            alert_api(self.port,AuthContext("tenant-a","p",frozenset()),"alert-a")


if __name__=="__main__":
    unittest.main()
