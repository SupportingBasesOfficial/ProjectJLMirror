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

    def test_column_acl_catalog_guard_cannot_be_removed(self):
        mutated = self.text.replace(
            "FROM pg_attribute a",
            "FROM pg_class a",
            1,
        )
        findings = validate_text(mutated)
        self.assertTrue(any("pg_attribute" in finding for finding in findings))

    def test_column_acl_guard_must_cover_live_user_columns(self):
        mutated = self.text.replace(
            "AND a.attnum > 0\n           AND NOT a.attisdropped",
            "AND a.attnum = 0\n           AND a.attisdropped",
            1,
        )
        findings = validate_text(mutated)
        self.assertTrue(any("attnum > 0" in finding or "attisdropped" in finding for finding in findings))

    def test_non_owner_column_acl_guard_cannot_be_removed(self):
        mutated = self.text.replace(
            "AND acl.grantee <> current_user::regrole::oid",
            "AND acl.grantee = current_user::regrole::oid",
            1,
        )
        findings = validate_text(mutated)
        self.assertTrue(any("a.attacl" in finding or "current_user::regrole::oid" in finding for finding in findings))

    def test_column_acl_guard_must_read_attacl_not_table_acl(self):
        mutated = self.text.replace(
            "aclexplode(a.attacl) AS acl",
            "aclexplode(NULL::aclitem[]) AS acl",
            1,
        )
        findings = validate_text(mutated)
        self.assertTrue(any("a.attacl" in finding for finding in findings))

    def test_non_owner_function_acl_guard_cannot_be_removed(self):
        mutated = self.text.replace(
            "acl.grantee <> p.proowner",
            "acl.grantee = p.proowner",
            1,
        )
        findings = validate_text(mutated)
        self.assertTrue(any("acl.grantee <> p.proowner" in finding for finding in findings))

    def test_transitive_owner_role_membership_guard_cannot_be_removed(self):
        mutated = self.text.replace(
            "WITH RECURSIVE owner_role_members(member_oid) AS (",
            "WITH owner_role_members(member_oid) AS (",
            1,
        )
        findings = validate_text(mutated)
        self.assertTrue(any("owner_role_members" in finding for finding in findings))

    def test_role_membership_guard_must_start_from_current_owner_role(self):
        mutated = self.text.replace(
            "WHERE m.roleid = current_user::regrole::oid",
            "WHERE m.member = current_user::regrole::oid",
            1,
        )
        findings = validate_text(mutated)
        self.assertTrue(any("pg_auth_members" in finding or "owner_role_members" in finding for finding in findings))

    def test_comment_cannot_launder_removed_acl_guard(self):
        mutated = self.text.replace(
            "acl.grantee <> c.relowner",
            "acl.grantee = c.relowner",
            1,
        ) + "\n-- acl.grantee <> c.relowner\n"
        findings = validate_text(mutated)
        self.assertTrue(any("acl.grantee <> c.relowner" in finding for finding in findings))

    def test_comment_cannot_launder_removed_column_acl_guard(self):
        mutated = self.text.replace(
            "aclexplode(a.attacl) AS acl",
            "aclexplode(NULL::aclitem[]) AS acl",
            1,
        ) + "\n-- aclexplode(a.attacl) AS acl\n"
        findings = validate_text(mutated)
        self.assertTrue(any("a.attacl" in finding for finding in findings))

    def test_comment_cannot_launder_removed_membership_guard(self):
        mutated = self.text.replace(
            "WITH RECURSIVE owner_role_members(member_oid) AS (",
            "WITH owner_role_members(member_oid) AS (",
            1,
        ) + "\n-- WITH RECURSIVE owner_role_members(member_oid) AS (\n"
        findings = validate_text(mutated)
        self.assertTrue(any("owner_role_members" in finding for finding in findings))

    def test_validator_rejects_role_mapping_grants(self):
        mutated = self.text + "\nGRANT UPDATE ON platform.authority_fences TO serving_role;\n"
        findings = validate_text(mutated)
        self.assertTrue(any("must not mutate C2 role mapping" in finding for finding in findings))


if __name__ == "__main__":
    unittest.main(verbosity=2)
