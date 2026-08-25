from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authority.validate_fence_revalidation_safety import validate_bootstrap_safety_text  # noqa: E402

SQL_PATH = ROOT / "sql" / "wave1" / "001_platform_authority_fence.sql"


class FenceBootstrapSafetyTests(unittest.TestCase):
    def text(self) -> str:
        return SQL_PATH.read_text(encoding="utf-8")

    def assert_fails(self, text: str, needle: str | None = None) -> None:
        findings = validate_bootstrap_safety_text(text)
        self.assertTrue(findings)
        if needle:
            self.assertTrue(any(needle.lower() in item.lower() for item in findings), findings)

    def test_real_bootstrap_is_fresh_only_and_catalog_bound(self):
        self.assertEqual(validate_bootstrap_safety_text(self.text()), [])

    def test_transaction_boundaries_fail_closed(self):
        self.assert_fails(self.text().replace("BEGIN;\n", "", 1), "BEGIN")
        self.assert_fails(self.text().replace("\nCOMMIT;\n", "\n", 1), "COMMIT")

    def test_event_trigger_guard_is_exact_and_catalog_bound(self):
        text = self.text()
        self.assert_fails(text.replace("SET LOCAL event_triggers = off;", "SET event_triggers = off;", 1), "SET LOCAL event_triggers")
        self.assert_fails(text.replace("pg_catalog.current_setting('event_triggers')", "current_setting('event_triggers')", 1), "locally disabled")
        self.assert_fails(text.replace("FROM pg_catalog.pg_event_trigger et", "FROM pg_catalog.pg_trigger et", 1), "event trigger")
        self.assert_fails(text.replace("et.evtenabled OPERATOR(pg_catalog.<>) 'D'", "et.evtenabled OPERATOR(pg_catalog.=) 'D'", 1), "event trigger")

    def test_migration_search_path_must_be_exact_pg_catalog(self):
        self.assert_fails(
            self.text().replace("SET LOCAL search_path = pg_catalog;", "SET LOCAL search_path = public, pg_catalog;", 1),
            "search_path",
        )

    def test_existing_table_must_return_before_persistent_bootstrap_mutation(self):
        text = self.text()
        self.assert_fails(text.replace("IF v_existing_table IS NOT NULL THEN\n        RETURN;", "IF false THEN\n        RETURN;", 1), "fresh-only")
        moved = text.replace("IF v_existing_table IS NOT NULL THEN\n        RETURN;\n    END IF;\n\n", "", 1)
        moved = moved.replace("END\n$wave1_bootstrap$;", "IF v_existing_table IS NOT NULL THEN\n        RETURN;\n    END IF;\nEND\n$wave1_bootstrap$;", 1)
        self.assert_fails(moved, "fresh-only")

    def test_catalog_bound_expression_primitives_are_required(self):
        text = self.text()
        for old, new in (
            ("pg_catalog.btrim(fence_scope_id)", "btrim(fence_scope_id)"),
            ("OPERATOR(pg_catalog.~)", "~"),
            ("pg_catalog.statement_timestamp()", "statement_timestamp()"),
        ):
            with self.subTest(old=old):
                self.assert_fails(text.replace(old, new, 1), "invariant")

    def test_both_fence_functions_pin_pg_catalog_search_path(self):
        text = self.text()
        self.assertGreaterEqual(text.count("SET search_path = pg_catalog"), 2)
        self.assert_fails(text.replace("SET search_path = pg_catalog", "SET search_path = public, pg_catalog", 1), "search_path")


if __name__ == "__main__":
    unittest.main(verbosity=2)
