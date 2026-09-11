from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTH = ROOT / "implementation/wave-4-problem-state-authorization/AUTHORIZATION.md"
MANIFEST = ROOT / "implementation/wave-4-problem-state-authorization/AUTHORIZATION_MANIFEST.json"


class ProblemStateAuthorizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.auth = AUTH.read_text(encoding="utf-8")
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_authorization_remains_bounded_and_proposed(self) -> None:
        self.assertEqual(self.manifest["authorization_id"], "wave4.monitoring-problem-state@1")
        self.assertEqual(self.manifest["status"], "proposed_bounded_implementation_authorization")
        self.assertEqual(self.manifest["canonical_base"], "4908e5124f2d182146d0366030c1dd64c778a423")

    def test_provider_reads_have_separate_authority_meanings(self) -> None:
        self.assertIn("problem.get", self.auth)
        self.assertIn("event.get", self.auth)
        self.assertIn("trigger.get", self.auth)
        self.assertIn("TRIGGER METADATA != PROBLEM LIFECYCLE AUTHORITY", self.auth)

    def test_incomplete_absence_cannot_resolve(self) -> None:
        self.assertIn("ABSENCE FROM INCOMPLETE problem.get != RESOLVED", self.auth)
        self.assertTrue(self.manifest["negative_resolution_requires_authoritative_evidence"])

    def test_provider_acknowledgement_is_not_platform_authority(self) -> None:
        self.assertTrue(self.manifest["provider_acknowledgement_is_metadata_only"])
        self.assertIn("PROVIDER ACKNOWLEDGED != JLMIRROR ACKNOWLEDGEMENT", self.auth)

    def test_problem_polling_is_independent(self) -> None:
        self.assertTrue(self.manifest["requires_independent_poll_authority"])
        self.assertIn("independent recovery-safe poll epoch/generation/admission stream", self.auth)

    def test_downstream_product_authorities_remain_blocked(self) -> None:
        for field in (
            "health_projection_authorized",
            "alerting_authorized",
            "itsm_authorized",
            "provider_writeback_authorized",
            "frontend_authorized",
        ):
            self.assertFalse(self.manifest[field])
        self.assertEqual(self.manifest["production_authority"], "none")

    def test_runtime_is_not_in_authorization_pr(self) -> None:
        self.assertFalse((ROOT / "src/jlmirror_monitoring/problem_state.py").exists())
        self.assertFalse((ROOT / "sql/wave4/042_zabbix_problem_state.sql").exists())


if __name__ == "__main__":
    unittest.main()
