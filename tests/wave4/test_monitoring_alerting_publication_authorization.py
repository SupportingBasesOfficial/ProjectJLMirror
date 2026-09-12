from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTH = ROOT / "implementation/wave-4-monitoring-alerting-publication-authorization/AUTHORIZATION.md"
MANIFEST = ROOT / "implementation/wave-4-monitoring-alerting-publication-authorization/AUTHORIZATION_MANIFEST.json"


class MonitoringAlertingPublicationAuthorizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.auth = AUTH.read_text(encoding="utf-8")
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_authorization_identity_and_base_are_exact(self) -> None:
        self.assertEqual(self.manifest["authorization_id"], "wave4.monitoring-alerting-publication@1")
        self.assertEqual(self.manifest["canonical_base"], "193883f0b3ddfd3531ceb54e0849c2f6e04744bc")
        self.assertEqual(self.manifest["production_authority"], "none")

    def test_exact_contract_names_are_fixed(self) -> None:
        self.assertEqual(
            self.manifest["contracts"],
            ["monitoring.problem-state.changed", "monitoring.health-projection.changed"],
        )
        self.assertIn("subject_type    monitoring_problem", self.auth)
        self.assertIn("subject_type    monitoring_resource", self.auth)

    def test_phase10_envelope_is_inherited_without_weakened_identity(self) -> None:
        self.assertTrue(self.manifest["inherits_phase10_logical_envelope"])
        self.assertTrue(self.manifest["stable_message_id_required"])
        self.assertTrue(self.manifest["redelivery_reuses_same_message_id"])
        for marker in (
            "message_id            stable immutable logical event identity",
            "occurred_at           authoritative local transition commit time",
            "correlation_id        required",
            "causation_id          nullable only for accepted root transition",
            "Publish ambiguity, dispatcher retry and redelivery MUST reuse the same logical `message_id`",
        ):
            self.assertIn(marker, self.auth)

    def test_events_are_invalidation_not_state_replication(self) -> None:
        self.assertTrue(self.manifest["events_are_invalidation_not_state_replication"])
        self.assertTrue(self.manifest["consumer_must_reread_monitoring"])
        self.assertFalse(self.manifest["semantic_state_values_allowed_in_payload"])
        self.assertFalse(self.manifest["broker_order_is_authority"])
        self.assertIn("EVENT ARRIVAL != CURRENT STATE AUTHORITY", self.auth)
        self.assertIn("BROKER ORDER != OWNER-DOMAIN ORDER", self.auth)
        self.assertIn("EVENT PAYLOAD != CURRENT PROBLEM/HEALTH STATE REPLICA", self.auth)

    def test_problem_payload_excludes_provider_and_semantic_state_authority(self) -> None:
        self.assertFalse(self.manifest["provider_ids_allowed_in_payload"])
        self.assertFalse(self.manifest["provider_payload_allowed"])
        self.assertFalse(self.manifest["metric_values_allowed"])
        self.assertIn("deliberately omits `problem_state` and `severity_class`", self.auth)
        self.assertIn("MUST NOT include provider-native event/trigger IDs", self.auth)
        self.assertIn("summary/free text", self.auth)

    def test_health_payload_excludes_semantic_state_authority(self) -> None:
        self.assertFalse(self.manifest["semantic_state_values_allowed_in_payload"])
        self.assertIn("deliberately omits `health_class` and `health_evidence_state`", self.auth)
        self.assertIn("problem/health semantic state values in event payloads", self.auth)

    def test_publication_is_bound_to_exact_durable_transition_record(self) -> None:
        self.assertIn("`problem_transition_id` MUST reference that exact immutable Monitoring transition record", self.auth)
        self.assertIn("`health_transition_id` MUST reference that exact immutable Monitoring transition record", self.auth)
        self.assertIn("pure re-confirmation, evidence refresh, stale/incomplete marking, metadata refresh or projection update", self.auth)
        self.assertIn("creates **no** `monitoring.problem-state.changed` event", self.auth)

    def test_alerting_business_authority_remains_blocked(self) -> None:
        for field in (
            "alert_lifecycle_authorized",
            "alert_acknowledgement_authorized",
            "alert_suppression_authorized",
            "notification_authorized",
            "escalation_authorized",
            "routing_authorized",
            "itsm_authorized",
            "automation_authorized",
            "aiops_authorized",
        ):
            self.assertFalse(self.manifest[field])
        self.assertEqual(
            self.manifest["authorized_consumer_effect"],
            "durable_invalidation_resync_responsibility_only",
        )

    def test_public_and_realtime_surfaces_remain_blocked(self) -> None:
        self.assertFalse(self.manifest["public_webhook_authorized"])
        self.assertFalse(self.manifest["browser_realtime_authorized"])
        self.assertIn("PUBLIC WEBHOOK != INTERNAL INTEGRATION EVENT", self.auth)
        self.assertIn("BROWSER REALTIME != INTERNAL INTEGRATION EVENT", self.auth)

    def test_no_new_transport_substrate_is_authorized(self) -> None:
        self.assertFalse(self.manifest["new_broker_or_outbox_substrate_authorized"])
        self.assertIn("No new broker, outbox substrate or telemetry stream is authorized", self.auth)

    def test_historical_generation_cannot_restore_current_authority(self) -> None:
        self.assertFalse(self.manifest["historical_generation_current_authority"])
        self.assertIn("HISTORICAL GENERATION != CURRENT ALERTING INPUT AUTHORITY", self.auth)
        self.assertIn("zero authority to restore current state", self.auth)


if __name__ == "__main__":
    unittest.main()
