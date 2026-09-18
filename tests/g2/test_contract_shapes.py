from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts/g2-monitoring-source-onboarding"


class ContractShapeTests(unittest.TestCase):
    def load(self, name: str) -> dict:
        return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))

    def test_create_contract_is_closed_and_secret_reference_only(self):
        schema = self.load("create-source.schema.json")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            set(schema["required"]),
            {
                "provider_profile",
                "display_name",
                "provider_configuration",
                "credential_binding_ref",
                "configured_provider_scope",
            },
        )
        properties = schema["properties"]
        self.assertEqual(properties["provider_profile"]["const"], "zabbix")
        self.assertIn("credential_binding_ref", properties)
        forbidden = {"api_token", "password", "secret", "credential_value"}
        self.assertTrue(forbidden.isdisjoint(properties))

    def test_onboarding_view_is_closed_and_truthful(self):
        schema = self.load("onboarding-view.schema.json")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            set(schema["required"]),
            {
                "monitoring_source_id",
                "monitoring_sync_operation_id",
                "state",
                "provider_connection_confirmed",
                "can_recheck",
            },
        )
        self.assertEqual(
            set(schema["properties"]["state"]["enum"]),
            {
                "validation_pending",
                "current",
                "incomplete",
                "reconciliation_required",
                "unavailable",
            },
        )
        serialized = json.dumps(schema, sort_keys=True)
        for forbidden in ("api_token", "password", "credential_value"):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
