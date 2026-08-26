from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authority.validate_fence_publication_safety import (  # noqa: E402
    BOUNDARY_PATH,
    BOOTSTRAP_PATH,
    REUSE_PATH,
    validate_bootstrap_publication_text,
    validate_boundary_text,
    validate_reuse_publication_text,
)


class FencePublicationSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bootstrap = BOOTSTRAP_PATH.read_text(encoding="utf-8")
        cls.reuse = REUSE_PATH.read_text(encoding="utf-8")
        cls.boundary = BOUNDARY_PATH.read_text(encoding="utf-8")

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

    def test_real_fence_migrations_close_static_replication_surfaces(self):
        self.assertEqual(validate_bootstrap_publication_text(self.bootstrap), [])
        self.assertEqual(validate_reuse_publication_text(self.reuse), [])
        self.assertEqual(validate_boundary_text(self.boundary), [])

    def test_fresh_all_tables_publication_guard_is_catalog_bound_and_pre_create(self):
        self.assert_bootstrap_fails(
            self.bootstrap.replace("FROM pg_catalog.pg_publication p", "FROM pg_catalog.pg_class p", 1),
            "pg_publication",
        )
        self.assert_bootstrap_fails(
            self.bootstrap.replace("WHERE p.puballtables", "WHERE NOT p.puballtables", 1),
            "puballtables",
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
        self.assert_bootstrap_fails(weakened, "pg_publication")

    def test_reuse_inbound_subscription_guard_remains_exact(self):
        self.assert_reuse_fails(
            self.reuse.replace("FROM pg_catalog.pg_subscription_rel sr", "FROM pg_catalog.pg_class sr", 1),
            "pg_subscription_rel",
        )
        self.assert_reuse_fails(
            self.reuse.replace("sr.srrelid OPERATOR(pg_catalog.=) v_table", "sr.srrelid OPERATOR(pg_catalog.<>) v_table", 1),
            "srrelid",
        )

    def test_reuse_explicit_publication_guard_is_exact(self):
        self.assert_reuse_fails(
            self.reuse.replace("FROM pg_catalog.pg_publication_rel pr", "FROM pg_catalog.pg_class pr", 1),
            "pg_publication_rel",
        )
        self.assert_reuse_fails(
            self.reuse.replace("pr.prrelid OPERATOR(pg_catalog.=) v_table", "pr.prrelid OPERATOR(pg_catalog.<>) v_table", 1),
            "prrelid",
        )

    def test_reuse_all_tables_publication_guard_is_exact(self):
        self.assert_reuse_fails(
            self.reuse.replace("FROM pg_catalog.pg_publication p", "FROM pg_catalog.pg_class p", 1),
            "pg_publication",
        )
        self.assert_reuse_fails(
            self.reuse.replace("WHERE p.puballtables", "WHERE NOT p.puballtables", 1),
            "puballtables",
        )

    def test_reuse_schema_publication_guard_is_version_tolerant_and_target_bound(self):
        self.assert_reuse_fails(
            self.reuse.replace(
                "pg_catalog.to_regclass('pg_catalog.pg_publication_namespace') IS NOT NULL",
                "true",
                1,
            ),
            "pg_publication_namespace",
        )
        self.assert_reuse_fails(
            self.reuse.replace(
                "FROM pg_catalog.pg_publication_namespace pn",
                "FROM pg_catalog.pg_namespace pn",
                1,
            ),
            "pg_publication_namespace",
        )
        self.assert_reuse_fails(
            self.reuse.replace(
                "pn.pnnspid OPERATOR(pg_catalog.=) $1",
                "pn.pnnspid OPERATOR(pg_catalog.<>) $1",
                1,
            ),
            "pnnspid",
        )
        self.assert_reuse_fails(self.reuse.replace("USING v_schema", "USING 0", 1), "USING v_schema")

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
        self.assert_reuse_fails(weakened, "pg_publication_rel")

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