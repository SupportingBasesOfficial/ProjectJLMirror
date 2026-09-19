from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SQL=(ROOT/"sql/notification/001_notification_delivery.sql").read_text(encoding="utf-8")
LOWER=SQL.lower()
EXPECTED={
 "notification.notification_intent",
 "notification.notification_attempt",
 "notification.notification_provider_evidence",
 "notification.notification_projection",
 "notification.notification_dispatch_outbox",
 "notification.notification_callback_inbox",
}


class SqlBoundaryTests(unittest.TestCase):
    def test_exact_relation_surface_and_force_rls(self):
        found={
            f"{a.lower()}.{b.lower()}"
            for a,b in re.findall(r"create\s+table\s+([a-z_][\w]*)\.([a-z_][\w]*)",SQL,re.I)
            if a.lower()=="notification"
        }
        self.assertEqual(found,EXPECTED)
        for rel in EXPECTED:
            self.assertIn("alter table "+rel+" enable row level security",LOWER)
            self.assertIn("alter table "+rel+" force row level security",LOWER)

    def test_cross_domain_business_state_is_read_only(self):
        self.assertNotRegex(LOWER,r"\bupdate\s+alerting\.")
        self.assertNotRegex(LOWER,r"\binsert\s+into\s+alerting\.")
        self.assertNotRegex(LOWER,r"\bupdate\s+human_operations\.")
        self.assertNotRegex(LOWER,r"\binsert\s+into\s+human_operations\.")

    def test_delivery_and_view_markers_remain_separate(self):
        self.assertIn("external_read_observed",LOWER)
        self.assertIn("visibility_receipt",LOWER)
        self.assertIn("delivery_state",LOWER)


if __name__=="__main__":
    unittest.main()
