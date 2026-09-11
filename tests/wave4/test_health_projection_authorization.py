from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTH = ROOT / "implementation/wave-4-health-projection-authorization/AUTHORIZATION.md"
MANIFEST = ROOT / "implementation/wave-4-health-projection-authorization/AUTHORIZATION_MANIFEST.json"


class HealthProjectionAuthorizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.auth = AUTH.read_text(encoding="utf-8")
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_authorization_is_bounded_and_proposed(self) -> None:
        self.assertEqual(self.manifest["authorization_id"], "wave4.monitoring-health-projection@1")
        self.assertEqual(self.manifest["status"], "proposed_bounded_implementation_authorization")
        self.assertEqual(self.manifest["canonical_base"], "1da4350cb860d759549b6302e575a02af6f07b09")
        self.assertEqual(self.manifest["production_authority"], "none")

    def test_health_classes_and_conservative_mapping_are_fixed(self) -> None:
        self.assertEqual(
            self.manifest["canonical_health_class"],
            ["unknown", "healthy", "degraded", "unhealthy"],
        )
        self.assertIn("active `critical` problem requires `unhealthy`", self.auth)
        self.assertIn("active `warning` or `degraded` problems require health to be at least `degraded`", self.auth)
        self.assertIn("active `unknown`-severity problem prevents the resource from being proven `healthy`", self.auth)
        self.assertIn("informational-only active problems may coexist with `healthy`", self.auth)

    def test_health_is_derived_not_provider_polling(self) -> None:
        self.assertFalse(self.manifest["provider_polling_authorized"])
        self.assertIn("HEALTH DERIVATION != PROVIDER POLLING AUTHORITY", self.auth)
        self.assertIn("authorizes no new Zabbix/provider API read", self.auth)

    def test_stale_or_historical_evidence_cannot_claim_current_health(self) -> None:
        self.assertFalse(self.manifest["historical_generation_current_authority"])
        self.assertFalse(self.manifest["stale_evidence_can_prove_healthy"])
        self.assertIn("STALE/INCOMPLETE EVIDENCE != PROVEN HEALTHY", self.auth)
        self.assertIn("HISTORICAL GENERATION != CURRENT HEALTH AUTHORITY", self.auth)

    def test_provider_acknowledgement_is_not_health_authority(self) -> None:
        self.assertFalse(self.manifest["provider_acknowledgement_health_authority"])
        self.assertIn("PROVIDER ACKNOWLEDGED != HEALTH AUTHORITY", self.auth)

    def test_read_contract_is_existing_monitoring_api_profile(self) -> None:
        self.assertEqual(self.manifest["health_read_action"], "monitoring.health.read")
        self.assertEqual(self.manifest["health_cache_class"], "private_revalidate")
        self.assertEqual(self.manifest["health_cursor_anchor"], "monitoring_resource_id")
        self.assertIn("monitoring_resource_id` in ascending deterministic order", self.auth)

    def test_cross_domain_and_downstream_authorities_remain_blocked(self) -> None:
        for field in (
            "cross_domain_health_event_authorized",
            "alerting_authorized",
            "itsm_authorized",
            "automation_authorized",
            "aiops_authorized",
            "provider_writeback_authorized",
            "frontend_authorized",
        ):
            self.assertFalse(self.manifest[field])
        self.assertIn("does not authorize a public/cross-domain `health.changed` integration event", self.auth)

    def test_runtime_is_not_in_authorization_pr(self) -> None:
        self.assertFalse((ROOT / "src/jlmirror_monitoring/health_projection.py").exists())
        self.assertFalse((ROOT / "sql/wave4/047_health_projection.sql").exists())


if __name__ == "__main__":
    unittest.main()
