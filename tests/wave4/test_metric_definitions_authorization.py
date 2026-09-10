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
            "frontend_route_or_navigation_creation",
            "production_deployment",
        }
        self.assertTrue(forbidden <= set(manifest["explicitly_not_authorized"]))

    def test_binding_is_explicitly_separate_from_definition_identity(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        authorized = set(manifest["authorized_behavior"])
        self.assertIn("separate_zabbix_item_binding_and_provenance", authorized)
        self.assertIn("canonical_resource_ownership_required", authorized)
        self.assertIn("retirement_only_from_complete_authoritative_negative_item_snapshot", authorized)


if __name__ == "__main__":
    unittest.main()
