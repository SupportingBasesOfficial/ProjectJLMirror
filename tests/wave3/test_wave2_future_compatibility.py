import unittest

from tools.wave3.validate_accepted_wave2_compatibility import (
    ACCEPTED_WAVE2_SHA,
    PROTECTED_WAVE2_DRIFT_BASELINE_SHA,
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

    def test_known_deferred_items_addition_is_not_flagged_as_protected_substrate_change(self):
        self.assertEqual(
            future_substrate_drift_findings(["implementation/wave-2/KNOWN_DEFERRED_ITEMS.md"]),
            [],
        )

    def test_unlisted_new_file_under_wave2_implementation_folder_still_fails_closed(self):
        findings = future_substrate_drift_findings(["implementation/wave-2/SOME_OTHER_NEW_FILE.md"])
        self.assertTrue(findings)
        self.assertIn("protected substrate changed", findings[0])

    def test_drift_baseline_is_a_distinct_pointer_from_the_immutable_historical_anchor(self):
        # These two constants must never be merged back into one: ACCEPTED_WAVE2_SHA anchors a
        # frozen, one-time historical fact (what PR #24 contained) and must never move again;
        # PROTECTED_WAVE2_DRIFT_BASELINE_SHA is the deliberately movable edge a legitimate
        # corrective PR repins. Regression guard for the recursion PR #29 hit: if these ever
        # collapse back into a single constant, every future corrective PR to protected Wave 2
        # substrate becomes permanently unmergeable again, exactly as it was before this fix.
        self.assertNotEqual(ACCEPTED_WAVE2_SHA, PROTECTED_WAVE2_DRIFT_BASELINE_SHA)

    def test_live_head_has_no_undeclared_drift_since_the_baseline(self):
        # Regression test for the PR #29 incident: this is the exact same diff live CI runs
        # (future_substrate_drift_findings() with paths=None, against real git history). It must
        # be empty on a clean tree. The day a genuine corrective PR touches protected substrate,
        # this test fails locally and fast, naming exactly what still needs its own repin PR —
        # instead of only being discovered on the next CI run against main.
        self.assertEqual(future_substrate_drift_findings(), [])

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
