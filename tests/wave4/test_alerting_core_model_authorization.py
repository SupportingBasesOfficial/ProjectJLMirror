from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTH = ROOT / "implementation/wave-4-alerting-core-model-authorization/AUTHORIZATION.md"
MANIFEST = ROOT / "implementation/wave-4-alerting-core-model-authorization/AUTHORIZATION_MANIFEST.json"


class AlertingCoreModelAuthorizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.auth = AUTH.read_text(encoding="utf-8")
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_identity_and_base_are_exact(self) -> None:
        self.assertEqual(self.manifest["authorization_id"], "wave4.alerting-core-model@1")
        self.assertEqual(self.manifest["canonical_base"], "e7cb9512846926f01429d3fbc4c6d6b0a2a9db71")
        self.assertEqual(self.manifest["owner_domain"], "alerting")

    def test_lifecycle_is_minimal_and_terminal(self) -> None:
        self.assertEqual(self.manifest["lifecycle_states"], ["active", "resolved"])
        self.assertTrue(self.manifest["resolved_is_terminal"])
        self.assertFalse(self.manifest["same_alert_id_reopen_authorized"])
        self.assertIn("A resolved `alert_id` never reopens", self.auth)

    def test_source_family_is_closed_and_unambiguous(self) -> None:
        self.assertEqual(
            self.manifest["source_kinds"],
            ["monitoring_problem", "monitoring_health_projection"],
        )
        self.assertFalse(self.manifest["mixed_source_family_authorized"])
        self.assertIn("one Alert occurrence has exactly one source evidence family", self.auth)
        self.assertIn("MUST NOT carry `problem_id`", self.auth)

    def test_policy_identity_version_is_mandatory_for_future_effects(self) -> None:
        self.assertTrue(self.manifest["policy_identity_version_required_for_effectful_transition"])
        self.assertFalse(self.manifest["policyless_lifecycle_transition_authorized"])
        self.assertIn("There is no policy-less create/resolve path", self.auth)
        self.assertIn("later edit/new version of a policy cannot retroactively change", self.auth)

    def test_monitoring_does_not_become_alert_authority(self) -> None:
        self.assertFalse(self.manifest["monitoring_event_is_alert"])
        self.assertFalse(self.manifest["monitoring_state_is_alert_state"])
        self.assertFalse(self.manifest["provider_id_is_alert_identity"])
        self.assertIn("EVENT ARRIVAL != ALERT CREATION AUTHORITY", self.auth)

    def test_policy_evaluation_and_automatic_mutation_remain_blocked(self) -> None:
        self.assertFalse(self.manifest["alert_policy_evaluation_authorized"])
        self.assertFalse(self.manifest["automatic_creation_authorized"])
        self.assertFalse(self.manifest["automatic_resolution_authorized"])
        self.assertIn("there is **no automatic Alert creation or resolution authority**", self.auth)

    def test_ack_and_suppression_are_not_lifecycle_states(self) -> None:
        self.assertFalse(self.manifest["acknowledgement_authorized"])
        self.assertFalse(self.manifest["suppression_authorized"])
        self.assertIn("`acknowledged` as a lifecycle state", self.auth)
        self.assertIn("`suppressed` as a lifecycle state", self.auth)

    def test_downstream_effects_remain_blocked(self) -> None:
        for field in (
            "routing_authorized",
            "notification_authorized",
            "notification_delivery_authorized",
            "escalation_authorized",
            "realtime_authorized",
            "public_webhook_authorized",
            "itsm_authorized",
            "aiops_authorized",
            "automation_authorized",
            "provider_writeback_authorized",
            "frontend_authorized",
        ):
            self.assertFalse(self.manifest[field])

    def test_transition_and_currentness_laws_are_closed(self) -> None:
        self.assertTrue(self.manifest["transition_history_immutable"])
        self.assertTrue(self.manifest["tenant_isolation_required"])
        self.assertTrue(self.manifest["source_currentness_required_for_future_effects"])
        self.assertFalse(self.manifest["broker_order_is_authority"])
        self.assertFalse(self.manifest["provider_time_is_lifecycle_authority"])

    def test_no_production_authority(self) -> None:
        self.assertEqual(self.manifest["production_authority"], "none")


if __name__ == "__main__":
    unittest.main()
