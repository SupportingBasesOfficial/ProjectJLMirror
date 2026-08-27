import unittest

from tools.wave3.validate_accepted_wave2_compatibility import (
    future_substrate_drift_findings,
    historical_scope_findings,
)


class Wave2FutureCompatibilityTests(unittest.TestCase):
    def test_future_wave_paths_do_not_retroactively_expand_wave2_scope(self):
        self.assertEqual(
            future_substrate_drift_findings([
                "implementation/wave-3/README.md",
                "src/jlmirror_observability/model.py",
                "src/jlmirror_release/authority.py",
                "tests/wave3/test_release.py",
            ]),
            [],
        )

    def test_future_change_to_wave2_substrate_fails_closed(self):
        findings = future_substrate_drift_findings(["src/jlmirror_async/inbox.py"])
        self.assertTrue(findings)
        self.assertIn("protected substrate changed", findings[0])

    def test_original_wave2_scope_still_rejects_wave3_as_hypothetical_wave2_delta(self):
        findings = historical_scope_findings(["implementation/wave-3/README.md"])
        self.assertTrue(findings)
        self.assertIn("escapes authorized path set", findings[0])

    def test_original_wave2_allowed_path_remains_allowed(self):
        self.assertEqual(historical_scope_findings(["src/jlmirror_async/inbox.py"]), [])

    def test_noncanonical_paths_fail_closed(self):
        self.assertTrue(future_substrate_drift_findings(["src/jlmirror_async/../evil.py"]))
        self.assertTrue(historical_scope_findings(["src/jlmirror_async/../evil.py"]))


if __name__ == "__main__":
    unittest.main()
