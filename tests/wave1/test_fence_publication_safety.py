from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authority.validate_fence_publication_safety import (  # noqa: E402
    BOUNDARY_PATH,
    BOOTSTRAP_PATH,
    C2_DATABASE_ADMIN_CHOICE,
    MANIFEST_PATH,
    REUSE_PATH,
    validate_bootstrap_publication_text,
    validate_boundary_text,
    validate_manifest_object,
    validate_reuse_publication_text,
)

INDEPENDENT_REQUIRED_REUSE_GUARDS = {
    "inbound_subscription_mapping_absent",
    "explicit_publication_relation_absent",
    "for_all_tables_publication_absent",
    "schema_publication_absent_when_catalog_supported",
}
INDEPENDENT_REQUIRED_FORBIDDEN_SUBSTITUTIONS = {
    "acl_clean_for_logical_replication_disclosure_absent",
    "inbound_replication_writer_absent_for_outbound_publication_absent",
    "publication_catalog_snapshot_clean_for_concurrent_superuser_authority_absent",
    "table_lock_held_for_database_admin_authority_revoked",
}


class FencePublicationSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bootstrap = BOOTSTRAP_PATH.read_text(encoding="utf-8")
        cls.reuse = REUSE_PATH.read_text(encoding="utf-8")
        cls.boundary = BOUNDARY_PATH.read_text(encoding="utf-8")
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def assert_bootstrap_fails(self, text: str, needle: str | None = None) -> None:
        findings = validate_bootstrap_publication_text(text)
        self.assertTrue(findings)
        if needle:
            self.assertTrue(any(needle.lower() in finding.lower() for finding in findings), findings)

    def assert_reuse_fails(self, text: str, needle: str | None = None) -> None:
        findings = validate_reuse_publication_text(text)
        self.assertTrue(findings)
        if needle:
            self.assertTrue(any(needle.lower() in finding.lower() for finding in findings), findings)

    def test_real_fence_migrations_and_manifest_close_static_replication_surfaces(self):
        self.assertEqual(validate_bootstrap_publication_text(self.bootstrap), [])
        self.assertEqual(validate_reuse_publication_text(self.reuse), [])
        self.assertEqual(validate_boundary_text(self.boundary), [])
        self.assertEqual(validate_manifest_object(self.manifest), [])

    def test_manifest_independently_pins_reuse_guards_and_c2_boundary(self):
        self.assertEqual(set(self.manifest["reuse_required_guards"]), INDEPENDENT_REQUIRED_REUSE_GUARDS)
        self.assertEqual(
            set(self.manifest["forbidden_substitutions"]),
            INDEPENDENT_REQUIRED_FORBIDDEN_SUBSTITUTIONS,
        )
        c2 = self.manifest["c2_database_admin_boundary"]
        self.assertEqual(c2["choice_id"], C2_DATABASE_ADMIN_CHOICE)
        self.assertIs(c2["concurrent_superuser_or_equivalent_admin_exclusion_selected"], False)
        self.assertIs(c2["catalog_preflight_claims_permanent_admin_absence"], False)
        self.assertIs(c2["requires_separate_reviewed_role_and_operational_mapping"], True)
        self.assertEqual(self.manifest["product_feature_activation"], "none")
        self.assertIs(self.manifest["wave_2_authorized"], False)

    def test_manifest_cannot_launder_c2_admin_selection_or_permanent_absence(self):
        for field in (
            "concurrent_superuser_or_equivalent_admin_exclusion_selected",
            "catalog_preflight_claims_permanent_admin_absence",
        ):
            with self.subTest(field=field):
                mutated = json.loads(json.dumps(self.manifest))
                mutated["c2_database_admin_boundary"][field] = True
                self.assertTrue(validate_manifest_object(mutated))

        mutated = json.loads(json.dumps(self.manifest))
        mutated["c2_database_admin_boundary"]["choice_id"] = "different_admin_mapping"
        self.assertTrue(validate_manifest_object(mutated))

    def test_manifest_cannot_drop_reuse_guard_or_forbidden_substitution(self):
        mutated = json.loads(json.dumps(self.manifest))
        mutated["reuse_required_guards"].remove("schema_publication_absent_when_catalog_supported")
        self.assertTrue(validate_manifest_object(mutated))

        mutated = json.loads(json.dumps(self.manifest))
        mutated["forbidden_substitutions"].remove(
            "publication_catalog_snapshot_clean_for_concurrent_superuser_authority_absent"
        )
        self.assertTrue(validate_manifest_object(mutated))

    def test_manifest_cannot_authorize_wave2_or_product_feature(self):
        mutated = json.loads(json.dumps(self.manifest))
        mutated["wave_2_authorized"] = True
        self.assertTrue(validate_manifest_object(mutated))

        mutated = json.loads(json.dumps(self.manifest))
        mutated["product_feature_activation"] = "enabled"
        self.assertTrue(validate_manifest_object(mutated))

    def test_fresh_all_tables_publication_guard_is_catalog_bound_and_pre_create(self):
        self.assert_bootstrap_fails(
            self.bootstrap.replace("FROM pg_catalog.pg_publication p", "FROM pg_catalog.pg_class p", 1),
            "parsed FOR ALL TABLES",
        )
        self.assert_bootstrap_fails(
            self.bootstrap.replace("WHERE p.puballtables", "WHERE NOT p.puballtables", 1),
            "parsed FOR ALL TABLES",
        )
        guard_start = self.bootstrap.index("IF EXISTS (\n        SELECT 1\n          FROM pg_catalog.pg_publication p")
        guard_end = self.bootstrap.index("    END IF;", guard_start) + len("    END IF;\n")
        guard = self.bootstrap[guard_start:guard_end]
        moved = self.bootstrap[:guard_start] + self.bootstrap[guard_end:]
        create_anchor = "    EXECUTE 'CREATE SCHEMA platform';"
        moved = moved.replace(create_anchor, create_anchor + "\n\n" + guard, 1)
        self.assert_bootstrap_fails(moved, "before first persistent CREATE")

    def test_fresh_publication_comment_laundering_is_rejected(self):
        weakened = self.bootstrap.replace("FROM pg_catalog.pg_publication p", "FROM pg_catalog.pg_class p", 1)
        weakened += "\n-- FROM pg_catalog.pg_publication p\n-- WHERE p.puballtables\n"
        self.assert_bootstrap_fails(weakened, "parsed FOR ALL TABLES")

    def test_fresh_publication_string_literal_laundering_is_rejected(self):
        weakened = self.bootstrap.replace("WHERE p.puballtables", "WHERE false", 1)
        anchor = "    EXECUTE 'CREATE SCHEMA platform';"
        weakened = weakened.replace(
            anchor,
            "    PERFORM 'WHERE p.puballtables';\n" + anchor,
            1,
        )
        self.assert_bootstrap_fails(weakened, "parsed FOR ALL TABLES")

    def test_reuse_inbound_subscription_guard_remains_exact(self):
        self.assert_reuse_fails(
            self.reuse.replace("FROM pg_catalog.pg_subscription_rel sr", "FROM pg_catalog.pg_class sr", 1),
            "inbound subscription",
        )
        self.assert_reuse_fails(
            self.reuse.replace("sr.srrelid OPERATOR(pg_catalog.=) v_table", "sr.srrelid OPERATOR(pg_catalog.<>) v_table", 1),
            "inbound subscription",
        )

    def test_reuse_explicit_publication_guard_is_exact(self):
        self.assert_reuse_fails(
            self.reuse.replace("FROM pg_catalog.pg_publication_rel pr", "FROM pg_catalog.pg_class pr", 1),
            "explicit publication",
        )
        self.assert_reuse_fails(
            self.reuse.replace("pr.prrelid OPERATOR(pg_catalog.=) v_table", "pr.prrelid OPERATOR(pg_catalog.<>) v_table", 1),
            "explicit publication",
        )

    def test_reuse_all_tables_publication_guard_is_exact(self):
        self.assert_reuse_fails(
            self.reuse.replace("FROM pg_catalog.pg_publication p", "FROM pg_catalog.pg_class p", 1),
            "FOR ALL TABLES",
        )
        self.assert_reuse_fails(
            self.reuse.replace("WHERE p.puballtables", "WHERE NOT p.puballtables", 1),
            "FOR ALL TABLES",
        )

    def test_reuse_publication_string_literal_laundering_is_rejected(self):
        weakened = self.reuse.replace("WHERE p.puballtables", "WHERE false", 1)
        marker = "    -- PostgreSQL 15+ can publish every current/future table in a schema."
        weakened = weakened.replace(marker, "    PERFORM 'WHERE p.puballtables';\n\n" + marker, 1)
        self.assert_reuse_fails(weakened, "FOR ALL TABLES")

    def test_reuse_schema_publication_guard_is_version_tolerant_and_target_bound(self):
        self.assert_reuse_fails(
            self.reuse.replace(
                "pg_catalog.to_regclass('pg_catalog.pg_publication_namespace') IS NOT NULL",
                "true",
                1,
            ),
            "version-tolerant",
        )
        self.assert_reuse_fails(
            self.reuse.replace(
                "FROM pg_catalog.pg_publication_namespace pn",
                "FROM pg_catalog.pg_namespace pn",
                1,
            ),
            "dynamic predicate",
        )
        self.assert_reuse_fails(
            self.reuse.replace(
                "pn.pnnspid OPERATOR(pg_catalog.=) $1",
                "pn.pnnspid OPERATOR(pg_catalog.<>) $1",
                1,
            ),
            "dynamic predicate",
        )
        self.assert_reuse_fails(self.reuse.replace("USING v_schema", "USING 0", 1), "EXECUTE/INTO/USING")

    def test_reuse_schema_dynamic_query_cannot_be_laundered_by_dead_literal(self):
        weakened = self.reuse.replace(
            "'WHERE pn.pnnspid OPERATOR(pg_catalog.=) $1)'",
            "'WHERE false)'",
            1,
        )
        marker = "        EXECUTE\n"
        weakened = weakened.replace(
            marker,
            "        PERFORM 'WHERE pn.pnnspid OPERATOR(pg_catalog.=) $1';\n" + marker,
            1,
        )
        self.assert_reuse_fails(weakened, "dynamic predicate")

    def test_reuse_publication_guards_cannot_move_after_mutation(self):
        start = self.reuse.index("    -- Inbound logical replication is an external writer authority.")
        end = self.reuse.index("END\n$wave1_revalidate$;", start)
        guards = self.reuse[start:end]
        weakened = self.reuse[:start] + self.reuse[end:]
        mutation = "ALTER TABLE platform.authority_fences\n    ALTER COLUMN fence_scope_id SET NOT NULL,"
        weakened = weakened.replace(mutation, mutation + "\n\n" + guards, 1)
        self.assert_reuse_fails(weakened)

    def test_reuse_transaction_commit_and_lock_are_authority_boundaries(self):
        self.assert_reuse_fails(self.reuse.replace("BEGIN;\n", "", 1), "BEGIN")
        self.assert_reuse_fails(self.reuse.replace("\nCOMMIT;", "", 1), "COMMIT")
        self.assert_reuse_fails(
            self.reuse.replace("LOCK TABLE platform.authority_fences IN ACCESS EXCLUSIVE MODE;", "", 1),
            "ACCESS EXCLUSIVE",
        )

    def test_reuse_publication_comment_laundering_is_rejected(self):
        weakened = self.reuse.replace("FROM pg_catalog.pg_publication_rel pr", "FROM pg_catalog.pg_class pr", 1)
        weakened += "\n-- FROM pg_catalog.pg_publication_rel pr\n-- pr.prrelid OPERATOR(pg_catalog.=) v_table\n"
        self.assert_reuse_fails(weakened, "explicit publication")

    def test_boundary_laws_cannot_be_laundered_by_duplicates(self):
        laws = (
            "ACL CLEAN != LOGICAL REPLICATION DISCLOSURE ABSENT",
            "INBOUND REPLICATION WRITER ABSENT != OUTBOUND PUBLICATION ABSENT",
            "PUBLICATION CATALOG SNAPSHOT CLEAN != CONCURRENT SUPERUSER AUTHORITY ABSENT",
        )
        for law in laws:
            with self.subTest(law=law):
                self.assertGreater(self.boundary.count(law), 0)
                mutated = self.boundary.replace(law, law.replace(" != ", " == "))
                self.assertTrue(validate_boundary_text(mutated))


if __name__ == "__main__":
    unittest.main(verbosity=2)
