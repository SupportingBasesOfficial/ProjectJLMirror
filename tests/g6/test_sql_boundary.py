from __future__ import annotations

from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
SQL=(ROOT/"sql/integration/002_monitoring_alerting_consumer.sql").read_text(encoding="utf-8")
LOWER=SQL.lower()


class SqlBoundaryTests(unittest.TestCase):
    def test_reuses_wave2_inbox_without_new_substrate(self):
        self.assertIn("system.async_consumer_inbox",LOWER)
        self.assertNotIn("create table",LOWER)
        self.assertNotIn("create schema",LOWER)

    def test_only_transport_capabilities_are_created(self):
        for name in (
            "g6_admit_monitoring_alerting_message",
            "g6_claim_monitoring_alerting_receipt",
            "g6_complete_monitoring_alerting_resync",
        ):
            self.assertIn(name,LOWER)
        self.assertNotIn("alert_id",LOWER)
        self.assertNotIn("policy_id",LOWER)
        self.assertNotIn("lifecycle_state",LOWER)

    def test_application_role_receives_execute_not_table_mutation(self):
        self.assertIn("grant execute on function",LOWER)
        self.assertNotIn("grant insert on system.async_consumer_inbox to jlmirror_g6_alerting_transport_invoker",LOWER)
        self.assertNotIn("grant update on system.async_consumer_inbox to jlmirror_g6_alerting_transport_invoker",LOWER)

    def test_current_owner_reread_is_mandatory(self):
        self.assertIn("from monitoring.monitoring_source",LOWER)
        self.assertIn("from monitoring.monitoring_problem",LOWER)
        self.assertIn("from monitoring.health_projection",LOWER)
        self.assertIn("current_monitoring_owner_state_unavailable",LOWER)

    def test_expired_claim_blocks_blind_retry(self):
        self.assertIn("processing_lease_expired_effect_absence_unproven",LOWER)
        self.assertIn("reconciliation_required",LOWER)


if __name__=="__main__":
    unittest.main()
