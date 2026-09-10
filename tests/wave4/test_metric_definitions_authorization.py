from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
AUTH = ROOT / "implementation/wave-4-metric-definitions-authorization/AUTHORIZATION.md"
MANIFEST = ROOT / "implementation/wave-4-metric-definitions-authorization/AUTHORIZATION_MANIFEST.json"


class MetricDefinitionsAuthorizationTests(unittest.TestCase):
    def test_authorization_is_bounded_and_preimplementation(self) -> None:
        auth = AUTH.read_text(encoding="utf-8")
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

        self.assertEqual(manifest["authorization_id"], "wave4.monitoring-metric-definitions@1")
        self.assertEqual(manifest["authorization_state"], "proposed")
        self.assertEqual(manifest["implementation_authority_before_merge"], "blocked")
        self.assertEqual(manifest["merge_authorization"], "not_granted")

        for marker in (
            "METRIC DEFINITION IDENTITY != PROVIDER ITEM ID",
            "METRIC DEFINITION != PROVIDER BINDING",
            "ITEM.GET LASTVALUE != AUTHORIZED CURRENT-STATE INGESTION IN THIS SLICE",
            "ITEM.GET METADATA != METRIC HISTORY",
            "SCOPE EXCLUSION != METRIC RETIREMENT",
            "GENERATION RETIREMENT != METRIC RETIREMENT",
            "UNCERTAINTY != NEGATIVE EVIDENCE",
            "ITEM-DEFINITION POLL GENERATION != HOST-INVENTORY POLL GENERATION",
            "SHARED RECOVERY EPOCH/ADMISSION FRAMEWORK != SHARED ENDPOINT POLL SEQUENCE",
            "provider_object_kind = zabbix_item",
            "Boolean is not inferred from integer `0/1`",
        ):
            self.assertIn(marker, auth)

        forbidden = {
            "metric_current_state_persistence",
            "item_get_lastvalue_as_current_state",
            "metric_history_ingestion",
            "history_get",
            "metric_observation_storage",
            "trigger_problem_event_ingestion",
            "health_projection",
            "provider_write_back",
            "shared_host_inventory_poll_generation_for_item_definitions",
            "frontend_route_or_navigation_creation",
            "production_deployment",
        }
        self.assertTrue(forbidden <= set(manifest["explicitly_not_authorized"]))

    def test_binding_and_poll_authority_are_explicitly_separated(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        authorized = set(manifest["authorized_behavior"])
        invariants = set(manifest["required_invariants"])

        self.assertIn("separate_zabbix_item_binding_and_provenance", authorized)
        self.assertIn("canonical_resource_ownership_required", authorized)
        self.assertIn("retirement_only_from_complete_authoritative_negative_item_snapshot", authorized)
        self.assertIn("reuse_existing_recovery_epoch_and_admission_framework", authorized)
        self.assertIn("distinct_item_definition_poll_generation_stream", authorized)
        self.assertIn("item_definition_poll_generation_distinct_from_host_inventory_poll_generation", invariants)
        self.assertIn("shared_recovery_epoch_admission_does_not_imply_shared_endpoint_poll_sequence", invariants)


if __name__ == "__main__":
    unittest.main()
