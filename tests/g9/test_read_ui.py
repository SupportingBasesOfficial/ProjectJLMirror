from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"apps/g9-notification-delivery"))

from read_ui import AuthContext,intent_api,render_intent


class Port:
    def get_intent(self,tenant_id,intent_id):
        return {
            "notification_intent_id":intent_id,
            "projection":{
                "delivery_state":"delivered",
                "external_read_observed":True,
                "native_visibility_state":"not_viewed_yet",
                "fallback_action_required":True,
            },
            "attempts":[{"attempt_number":1,"attempt_state":"sent"}],
            "provider_evidence":[{"evidence_kind":"delivered","observed_at":"2026-09-19T00:00:00Z"}],
        }
    def list_alert_intents(self,tenant_id,alert_id): return []


class ReadUiTests(unittest.TestCase):
    def test_delivery_external_read_and_native_view_are_distinct(self):
        auth=AuthContext("tenant-a","principal-a",frozenset({"notification:read"}))
        value=intent_api(Port(),auth,"intent-a")
        self.assertEqual(value["projection"]["delivery_state"],"delivered")
        self.assertTrue(value["projection"]["external_read_observed"])
        self.assertEqual(value["projection"]["native_visibility_state"],"not_viewed_yet")
        html=render_intent(Port(),auth,"intent-a")
        self.assertIn("Delivery: delivered",html)
        self.assertIn("External read evidence: True",html)
        self.assertIn("Authoritative native visibility: not_viewed_yet",html)


if __name__=="__main__":
    unittest.main()
