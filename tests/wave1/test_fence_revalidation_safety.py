from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authority.validate_fence_revalidation_safety import validate_revalidation_safety_text  # noqa: E402

SQL_PATH = ROOT / "sql" / "wave1" / "002_revalidate_authority_fence_contract.sql"


class FenceRevalidationSafetyTests(unittest.TestCase):
    def text(self) -> str:
        return SQL_PATH.read_text(encoding="utf-8")

    def assert_fails(self, text: str, needle: str | None = None) -> None:
        findings = validate_revalidation_safety_text(text)
        self.assertTrue(findings)
        if needle:
            self.assertTrue(any(needle.lower() in f.lower() for f in findings), findings)

    def test_real_migration_is_atomic_catalog_bound_and_replication_safe(self):
        self.assertEqual(validate_revalidation_safety_text(self.text()), [])

    def test_transaction_and_lock_boundaries_fail_closed(self):
        text = self.text()
        self.assert_fails(text.replace("BEGIN;\n", "", 1), "BEGIN")
        self.assert_fails(text.replace("\nCOMMIT;\n", "\n", 1), "COMMIT")
        self.assert_fails(text.replace("LOCK TABLE platform.authority_fences IN ACCESS EXCLUSIVE MODE;\n", "", 1), "ACCESS EXCLUSIVE")

    def test_event_trigger_and_search_path_guards_must_precede_lock(self):
        text = self.text()
        self.assert_fails(text.replace("SET LOCAL event_triggers = off;", "SET event_triggers = off;", 1), "SET LOCAL event_triggers")
        self.assert_fails(text.replace("SET LOCAL search_path = pg_catalog;", "SET LOCAL search_path = public, pg_catalog;", 1), "search_path")
        self.assert_fails(text.replace("pg_catalog.current_setting('event_triggers')", "current_setting('event_triggers')", 1), "locally disabled")
        self.assert_fails(text.replace("et.evtenabled OPERATOR(pg_catalog.<>) 'D'", "et.evtenabled OPERATOR(pg_catalog.=) 'D'", 1), "event trigger")

    def test_lock_cannot_move_after_reuse_validation(self):
        text = self.text()
        lock = "LOCK TABLE platform.authority_fences IN ACCESS EXCLUSIVE MODE;\n"
        weakened = text.replace(lock, "", 1).replace("END\n$wave1_revalidate$;", "END\n$wave1_revalidate$;\n\n" + lock, 1)
        self.assert_fails(weakened, "ordering")

    def test_logical_replication_writer_guard_is_exact(self):
        text = self.text()
        self.assert_fails(text.replace("FROM pg_catalog.pg_subscription_rel sr", "FROM pg_catalog.pg_class sr", 1), "logical-replication")
        self.assert_fails(text.replace("sr.srrelid OPERATOR(pg_catalog.=) v_table", "sr.srrelid OPERATOR(pg_catalog.<>) v_table", 1), "logical-replication")

    def test_stored_check_dependencies_must_be_catalog_bound(self):
        text = self.text()
        for old, new in (
            ("pg_catalog.pg_depend", "pg_catalog.pg_class"),
            ("pg_catalog.pg_operator", "pg_catalog.pg_class"),
            ("o.oprnamespace OPERATOR(pg_catalog.<>) 'pg_catalog'::pg_catalog.regnamespace", "false"),
            ("d.refobjid OPERATOR(pg_catalog.<>) 'pg_catalog.\"C\"'::pg_catalog.regcollation", "false"),
        ):
            with self.subTest(old=old):
                self.assert_fails(text.replace(old, new, 1), "trusted-resolution")

    def test_constraint_validation_precedes_function_replacement(self):
        text = self.text()
        marker = "CREATE OR REPLACE FUNCTION platform.initialize_authority_fence"
        function_block = text[text.index(marker):text.index("REVOKE ALL ON FUNCTION platform.initialize_authority_fence")]
        weakened = text.replace(function_block, "", 1).replace(
            "ALTER TABLE platform.authority_fences\n    VALIDATE CONSTRAINT wave1_fence_scope_id_canonical;",
            function_block + "\nALTER TABLE platform.authority_fences\n    VALIDATE CONSTRAINT wave1_fence_scope_id_canonical;",
            1,
        )
        self.assert_fails(weakened, "before function replacement")


if __name__ == "__main__":
    unittest.main(verbosity=2)
