from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authority.validate_fence_revalidation_safety import (  # noqa: E402
    validate_bootstrap_safety_text,
    validate_revalidation_safety_text,
)

BOOTSTRAP = ROOT / "sql" / "wave1" / "001_platform_authority_fence.sql"
REUSE = ROOT / "sql" / "wave1" / "002_revalidate_authority_fence_contract.sql"
BOUNDARY = ROOT / "implementation" / "wave-1" / "FENCE_DEFAULT_ACL_AUTHORITY_BOUNDARY.md"

REQUIRED_LAWS = {
    "PUBLIC REVOKED != NONOWNER DEFAULT ACL ABSENT",
    "DEFAULT ACL PREFLIGHT != MATERIALIZED OBJECT ACL PROOF",
    "MATERIALIZED OBJECT ACL CLEAN != DEFAULT ACL SAFE FOR FUTURE CREATE",
    "OBJECT ACL CLEAN != OWNER ROLE UNASSUMABLE",
    "OBJECT ACL CLEAN != PREDEFINED ALL-DATA AUTHORITY ABSENT",
    "SCHEMA LOCATION != DEFINER AUTHORITY BOUNDARY",
    "POST-BOOTSTRAP REJECTION != FAIL-CLOSED BOOTSTRAP",
    "MISSING REUSE ROUTINE != SAFE CREATE OR REPLACE",
    "PREEXISTING ROUTINE ACL CLEAN != POSTCANONICAL ROUTINE ACL CLEAN",
    "PRE-CREATE DEFAULT ACL CHECK != POST-CREATE ACL ASSERTION",
    "REUSE REPAIR != REUSE ADMISSION",
    "WAVE 1 HARDENING != WAVE 2 AUTHORIZATION",
}


class FenceDefaultAclAuthorityTests(unittest.TestCase):
    def bootstrap(self) -> str:
        return BOOTSTRAP.read_text(encoding="utf-8")

    def reuse(self) -> str:
        return REUSE.read_text(encoding="utf-8")

    def assert_bootstrap_fails(self, text: str) -> None:
        self.assertTrue(validate_bootstrap_safety_text(text))

    def assert_reuse_fails(self, text: str) -> None:
        self.assertTrue(validate_revalidation_safety_text(text))

    def test_boundary_materializes_default_acl_authority_laws(self):
        text = BOUNDARY.read_text(encoding="utf-8")
        missing = {law for law in REQUIRED_LAWS if law not in text}
        self.assertFalse(missing, missing)

    def test_real_migrations_close_default_acl_creation_authority(self):
        self.assertEqual(validate_bootstrap_safety_text(self.bootstrap()), [])
        self.assertEqual(validate_revalidation_safety_text(self.reuse()), [])

    def test_bootstrap_default_acl_catalog_is_authority_bound(self):
        text = self.bootstrap()
        self.assert_bootstrap_fails(text.replace("FROM pg_catalog.pg_default_acl d", "FROM pg_catalog.pg_proc d", 1))
        self.assert_bootstrap_fails(
            text.replace(
                "d.defaclrole OPERATOR(pg_catalog.=) current_user::pg_catalog.regrole::oid",
                "d.defaclrole OPERATOR(pg_catalog.<>) current_user::pg_catalog.regrole::oid",
                1,
            )
        )
        self.assert_bootstrap_fails(text.replace("d.defaclnamespace OPERATOR(pg_catalog.=) 0", "d.defaclnamespace OPERATOR(pg_catalog.<>) 0", 1))
        self.assert_bootstrap_fails(text.replace("d.defaclobjtype IN ('n', 'r', 'f')", "d.defaclobjtype IN ('n', 'r')", 1))
        self.assert_bootstrap_fails(
            text.replace(
                "acl.grantee OPERATOR(pg_catalog.<>) d.defaclrole",
                "acl.grantee OPERATOR(pg_catalog.=) d.defaclrole",
                1,
            )
        )

    def test_bootstrap_fresh_privilege_reachability_is_preflighted(self):
        text = self.bootstrap()
        self.assert_bootstrap_fails(
            text.replace(
                "WITH RECURSIVE owner_role_members(member_oid) AS (",
                "WITH RECURSIVE owner_role_notes(member_oid) AS (",
                1,
            )
        )
        # The all-data roots are deliberately referenced by more than one independent
        # guard. Remove every occurrence so the falsification tests the property rather
        # than whichever textual occurrence happens to appear first.
        self.assert_bootstrap_fails(
            text.replace("pg_catalog.to_regrole('pg_write_all_data')::oid", "pg_catalog.to_regrole('pg_monitor')::oid")
        )
        self.assert_bootstrap_fails(
            text.replace(
                "Wave 1 fresh bootstrap rejects non-owner predefined all-data authority before fence creation",
                "Wave 1 fresh bootstrap all-data authority checked later",
                1,
            )
        )
        self.assert_bootstrap_fails(
            text.replace(
                "Wave 1 fresh bootstrap rejects migration-owner SECURITY DEFINER authority before fence creation",
                "Wave 1 fresh bootstrap SECURITY DEFINER authority checked later",
                1,
            )
        )

    def test_bootstrap_requires_materialized_acl_assertion_before_commit(self):
        text = self.bootstrap()
        self.assert_bootstrap_fails(text.replace("DO $wave1_bootstrap_privilege_assert$", "DO $wave1_bootstrap_privilege_note$", 1))
        self.assert_bootstrap_fails(
            text.replace(
                "pg_catalog.COALESCE(p.proacl, pg_catalog.acldefault('f', p.proowner))",
                "pg_catalog.COALESCE(p.proacl, pg_catalog.acldefault('r', p.proowner))",
                1,
            )
        )
        self.assert_bootstrap_fails(
            text.replace(
                "fresh fence authority routine materialized non-owner privileges",
                "fresh fence authority routine privileges checked later",
                1,
            )
        )

    def test_reuse_must_reject_incomplete_canonical_routine_set(self):
        text = self.reuse()
        self.assert_reuse_fails(
            text.replace(
                "IF v_schema IS NULL OR v_table IS NULL OR v_initialize IS NULL OR v_advance IS NULL THEN",
                "IF v_schema IS NULL OR v_table IS NULL THEN",
                1,
            )
        )
        self.assert_reuse_fails(
            text.replace(
                "Wave 1 reuse requires the complete canonical fence authority object set before mutation",
                "Wave 1 reused fence privilege objects are incomplete",
                1,
            )
        )

    def test_reuse_requires_postcanonical_acl_assertion(self):
        text = self.reuse()
        self.assert_reuse_fails(text.replace("DO $wave1_postcanonical_privilege_assert$", "DO $wave1_postcanonical_privilege_note$", 1))
        self.assert_reuse_fails(
            text.replace(
                "Wave 1 reuse canonical routine materialized non-owner privileges before commit",
                "Wave 1 reuse canonical routine privileges checked later",
                1,
            )
        )
        self.assert_reuse_fails(
            text.replace(
                "p.proconfig IS DISTINCT FROM ARRAY['search_path=pg_catalog']::text[]",
                "false",
                1,
            )
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)