from __future__ import annotations

import unittest

from tools.authority.validate_wave1_privileges import (  # noqa: E402
    BOUNDARY_PATH,
    SQL_PATH,
    validate_boundary_text,
    validate_text,
)


class FencePrivilegeRevalidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SQL_PATH.read_text(encoding="utf-8")
        cls.boundary = BOUNDARY_PATH.read_text(encoding="utf-8")

    def assert_fails(self, text: str, needle: str | None = None) -> None:
        findings = validate_text(text)
        self.assertTrue(findings)
        if needle:
            self.assertTrue(any(needle.lower() in f.lower() for f in findings), findings)

    def test_current_privilege_contract_passes(self):
        self.assertEqual(validate_text(self.text), [])
        self.assertEqual(validate_boundary_text(self.boundary), [])

    def test_migration_search_path_is_catalog_only(self):
        self.assert_fails(
            self.text.replace("SET LOCAL search_path = pg_catalog;", "SET LOCAL search_path = public, pg_catalog;", 1),
            "search_path",
        )

    def test_owner_and_role_reachability_guards_cannot_be_removed(self):
        mutations = (
            (
                "SELECT n.nspowner\n          FROM pg_catalog.pg_namespace n",
                "SELECT n.nspowner\n          FROM pg_catalog.pg_class n",
                False,
            ),
            (
                "SELECT c.relowner\n          FROM pg_catalog.pg_class c",
                "SELECT c.relowner\n          FROM pg_catalog.pg_namespace c",
                False,
            ),
            (
                "WITH RECURSIVE owner_role_members(member_oid) AS (",
                "WITH owner_role_members(member_oid) AS (",
                False,
            ),
            (
                "WITH RECURSIVE all_data_role_members(role_oid, member_oid) AS (",
                "WITH all_data_role_members(role_oid, member_oid) AS (",
                False,
            ),
            (
                "pg_catalog.to_regrole('pg_read_all_data')::oid",
                "pg_catalog.to_regrole('pg_monitor')::oid",
                True,
            ),
        )
        for old, new, all_occurrences in mutations:
            with self.subTest(old=old):
                self.assertIn(old, self.text)
                weakened = self.text.replace(old, new) if all_occurrences else self.text.replace(old, new, 1)
                self.assert_fails(weakened)

    def test_object_and_column_acl_guards_cannot_be_removed(self):
        mutations = (
            ("pg_catalog.aclexplode(a.attacl)", "pg_catalog.aclexplode(NULL::aclitem[])"),
            (
                "acl.grantee OPERATOR(pg_catalog.<>) current_user::pg_catalog.regrole::oid",
                "acl.grantee OPERATOR(pg_catalog.=) current_user::pg_catalog.regrole::oid",
            ),
            (
                "acl.grantee OPERATOR(pg_catalog.<>) c.relowner",
                "acl.grantee OPERATOR(pg_catalog.=) c.relowner",
            ),
            (
                "acl.grantee OPERATOR(pg_catalog.<>) p.proowner",
                "acl.grantee OPERATOR(pg_catalog.=) p.proowner",
            ),
        )
        for old, new in mutations:
            with self.subTest(old=old):
                self.assertIn(old, self.text)
                self.assert_fails(self.text.replace(old, new, 1))

    def test_database_wide_fence_authoritative_security_definer_guard_is_required(self):
        owner_set = (
            "p.proowner IN (\n"
            "                   current_user::pg_catalog.regrole::oid,\n"
            "                   pg_catalog.to_regrole('pg_read_all_data')::oid,\n"
            "                   pg_catalog.to_regrole('pg_write_all_data')::oid\n"
            "               )\n"
            "           AND p.prosecdef"
        )
        self.assertIn(owner_set, self.text)
        # The contract deliberately repeats this guard before and after canonicalization.
        # Remove/replace every occurrence so a surviving redundant copy cannot make a
        # weakened mutation look safe to a presence-based validator.
        self.assert_fails(
            self.text.replace(
                owner_set,
                "p.proowner OPERATOR(pg_catalog.=) current_user::pg_catalog.regrole::oid\n           AND p.prosecdef",
            )
        )
        self.assert_fails(
            self.text.replace("pg_catalog.to_regrole('pg_read_all_data')::oid", "pg_catalog.to_regrole('pg_monitor')::oid")
        )
        self.assert_fails(
            self.text.replace("pg_catalog.to_regrole('pg_write_all_data')::oid", "pg_catalog.to_regrole('pg_monitor')::oid")
        )
        self.assert_fails(
            self.text.replace(
                "database contains fence-authoritative SECURITY DEFINER routine owned by migration or predefined all-data authority",
                "database contains migration-owner SECURITY DEFINER routine",
            )
        )

    def test_canonical_functions_must_retain_exact_catalog_search_path(self):
        weakened = self.text.replace(
            "p.proconfig IS DISTINCT FROM ARRAY['search_path=pg_catalog']::text[]",
            "false",
            1,
        )
        self.assert_fails(weakened, "search_path")

    def test_validator_rejects_role_mapping_grants(self):
        self.assert_fails(self.text + "\nGRANT UPDATE ON platform.authority_fences TO serving_role;\n", "role mapping")

    def test_boundary_semantic_separations_remain_pinned(self):
        for law in (
            "TABLE ACL CLEAN != COLUMN ACL CLEAN",
            "OBJECT ACL CLEAN != PREDEFINED ALL-DATA ROLE ABSENT",
            "ALL-DATA MEMBERSHIP CLEAN != ALL-DATA-OWNED DEFINER AUTHORITY ABSENT",
            "EXPECTED FUNCTION ACL CLEAN != RESIDUAL DEFINER AUTHORITY ABSENT",
            "SCHEMA LOCATION != DEFINER AUTHORITY BOUNDARY",
            "LOCAL FENCE RULE CLEAN != EXTERNAL REWRITE REACHABILITY ABSENT",
        ):
            with self.subTest(law=law):
                self.assertGreater(self.boundary.count(law), 0)
                mutated = self.boundary.replace(law, law.replace(" != ", " == "))
                self.assertTrue(validate_boundary_text(mutated))


if __name__ == "__main__":
    unittest.main(verbosity=2)