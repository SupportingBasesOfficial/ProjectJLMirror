from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authority.wave1_scope import (  # noqa: E402
    ACCEPTED_WAVE1_SHA,
    validate_wave1_scope,
)


class Wave1ScopeGuardTests(unittest.TestCase):
    def test_accepted_wave1_delta_is_inside_authorized_wave1_paths(self):
        self.assertEqual(validate_wave1_scope(ROOT), [])

    def test_explicit_accepted_head_is_equivalent_to_default(self):
        self.assertEqual(validate_wave1_scope(ROOT, head=ACCEPTED_WAVE1_SHA), [])

    def test_product_app_path_is_rejected(self):
        findings = validate_wave1_scope(ROOT, paths=["apps/api/routes/tenants.py"])
        self.assertTrue(any("escapes authorized path set" in f for f in findings))

    def test_normative_docs_cannot_be_changed_by_wave1(self):
        findings = validate_wave1_scope(
            ROOT,
            paths=["docs/09-api-contracts/authentication-authorization-and-tenant-context.md"],
        )
        self.assertTrue(any("escapes authorized path set" in f for f in findings))

    def test_wave2_path_is_still_rejected_as_hypothetical_wave1_delta(self):
        findings = validate_wave1_scope(ROOT, paths=["implementation/wave-2/README.md"])
        self.assertTrue(any("escapes authorized path set" in f for f in findings))

    def test_authorized_paths_are_accepted(self):
        paths = [
            ".github/workflows/deterministic-assurance.yml",
            "implementation/wave-1/README.md",
            "src/jlmirror_authority/control_plane.py",
            "sql/wave1/001_platform_authority_fence.sql",
            "tests/wave1/test_panorama.py",
            "tools/authority/validate_wave1.py",
        ]
        self.assertEqual(validate_wave1_scope(ROOT, paths=paths), [])

    def test_noncanonical_path_is_rejected(self):
        findings = validate_wave1_scope(ROOT, paths=["src/jlmirror_authority/../escape.py"])
        self.assertTrue(any("non-canonical" in f for f in findings))


if __name__ == "__main__":
    unittest.main(verbosity=2)
