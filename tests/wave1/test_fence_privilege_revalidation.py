from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authority.validate_wave1_privileges import (  # noqa: E402
    SQL_PATH,
    validate_text,
)


class FencePrivilegeRevalidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SQL_PATH.read_text(encoding="utf-8")

    def test_current_privilege_contract_passes(self):
        self.assertEqual(validate_text(self.text), [])

    def test_table_owner_guard_cannot_be_removed(self):
        mutated = self.text.replace(
            "c.relowner\n          FROM pg_class c",
            "c.oid\n          FROM pg_class c",
            1,
        )
        findings = validate_text(mutated)
        self.assertTrue(any("c.relowner" in finding for finding in findings))

    def test_non_owner_table_acl_guard_cannot_be_removed(self):
        mutated = self.text.replace(
            "acl.grantee <> c.relowner",
            "acl.grantee = c.relowner",
            1,
        )
        findings = validate_text(mutated)
        self.assertTrue(any("acl.grantee <> c.relowner" in finding for finding in findings))

    def test_non_owner_function_acl_guard_cannot_be_removed(self):
        mutated = self.text.replace(
            "acl.grantee <> p.proowner",
            "acl.grantee = p.proowner",
            1,
        )
        findings = validate_text(mutated)
        self.assertTrue(any("acl.grantee <> p.proowner" in finding for finding in findings))

    def test_comment_cannot_launder_removed_acl_guard(self):
        mutated = self.text.replace(
            "acl.grantee <> c.relowner",
            "acl.grantee = c.relowner",
            1,
        ) + "\n-- acl.grantee <> c.relowner\n"
        findings = validate_text(mutated)
        self.assertTrue(any("acl.grantee <> c.relowner" in finding for finding in findings))

    def test_validator_rejects_role_mapping_grants(self):
        mutated = self.text + "\nGRANT UPDATE ON platform.authority_fences TO serving_role;\n"
        findings = validate_text(mutated)
        self.assertTrue(any("must not mutate C2 role mapping" in finding for finding in findings))


if __name__ == "__main__":
    unittest.main(verbosity=2)
