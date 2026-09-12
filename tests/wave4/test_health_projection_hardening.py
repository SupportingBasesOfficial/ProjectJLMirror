from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLL_GUARD = (ROOT / "sql/wave4/050_health_projection_current_poll_guard.sql").read_text(encoding="utf-8").lower()
CLASS_GUARD = (ROOT / "sql/wave4/051_health_projection_exact_class_guard.sql").read_text(encoding="utf-8").lower()


class HealthProjectionHardeningTests(unittest.TestCase):
    def test_current_evidence_is_bound_to_exact_current_problem_poll(self) -> None:
        self.assertIn("s.problem_poll_epoch=e.problem_poll_epoch", POLL_GUARD)
        self.assertIn("s.problem_poll_generation=e.problem_poll_generation", POLL_GUARD)
        self.assertIn("current health requires exact current problem state poll", POLL_GUARD)

    def test_current_class_is_derived_not_executor_selected(self) -> None:
        self.assertIn("v_expected_health", CLASS_GUARD)
        self.assertIn("p.severity_class='critical'", CLASS_GUARD)
        self.assertIn("v_expected_health:='unhealthy'", CLASS_GUARD)
        self.assertIn("p.severity_class in ('warning','degraded')", CLASS_GUARD)
        self.assertIn("v_expected_health:='degraded'", CLASS_GUARD)
        self.assertIn("p.severity_class='unknown'", CLASS_GUARD)
        self.assertIn("v_expected_health:='healthy'", CLASS_GUARD)
        self.assertIn("new.health_class <> v_expected_health", CLASS_GUARD)
        self.assertIn("current health class does not equal canonical problem state derivation", CLASS_GUARD)

    def test_noncurrent_evidence_can_never_be_healthy(self) -> None:
        self.assertIn("elsif new.health_class='healthy'", CLASS_GUARD)
        self.assertIn("healthy cannot be projected from non-current evidence", CLASS_GUARD)


if __name__ == "__main__":
    unittest.main()
