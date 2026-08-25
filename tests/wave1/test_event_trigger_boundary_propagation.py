from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
ASSURANCE = ROOT / "implementation" / "wave-1" / "ASSURANCE.md"
PRIVILEGE_BOUNDARY = ROOT / "implementation" / "wave-1" / "FENCE_PRIVILEGE_BOUNDARY.md"
BOOTSTRAP_SQL = ROOT / "sql" / "wave1" / "001_platform_authority_fence.sql"
REVALIDATION_SQL = ROOT / "sql" / "wave1" / "002_revalidate_authority_fence_contract.sql"

LAW = "EVENT-TRIGGER CATALOG PREFLIGHT != CLOSED EVENT-TRIGGER EXECUTION WINDOW"
CATALOG = "pg_catalog.pg_event_trigger"
DOC_PREDICATE = "evtenabled <> 'D'"
SQL_PREDICATE = "et.evtenabled <> 'D'"
SESSION_GUARD = "SET LOCAL event_triggers = off"
CURRENT_SETTING = "current_setting('event_triggers')"


class EventTriggerBoundaryPropagationTests(unittest.TestCase):
    def test_authority_law_is_pinned_in_privilege_boundary(self):
        text = PRIVILEGE_BOUNDARY.read_text(encoding="utf-8")
        self.assertIn(LAW, text)
        self.assertIn(CATALOG, text)
        self.assertIn(DOC_PREDICATE, text)
        self.assertIn(SESSION_GUARD, text)
        self.assertIn(CURRENT_SETTING, text)
        self.assertIn("migration 001", text)
        self.assertIn("migration 002", text)

    def test_assurance_requires_closed_event_trigger_execution_window_for_both_migrations(self):
        text = ASSURANCE.read_text(encoding="utf-8")
        self.assertIn(CATALOG, text)
        self.assertIn(DOC_PREDICATE, text)
        self.assertIn(SESSION_GUARD, text)
        self.assertIn(CURRENT_SETTING, text)
        self.assertIn("migration 001", text)
        self.assertIn("migration 002", text)
        self.assertIn("before fence DDL", text)

    def test_bootstrap_carries_exact_session_catalog_and_predicate_guards(self):
        text = BOOTSTRAP_SQL.read_text(encoding="utf-8")
        self.assertIn(SESSION_GUARD + ";", text)
        self.assertIn(CURRENT_SETTING, text)
        self.assertIn(CATALOG, text)
        self.assertIn(SQL_PREDICATE, text)
        self.assertIn("wave1_bootstrap_event_trigger_guard", text)
        self.assertLess(text.index("wave1_bootstrap_event_trigger_guard"), text.index("CREATE SCHEMA IF NOT EXISTS platform"))

    def test_revalidation_carries_exact_session_catalog_and_predicate_guards(self):
        text = REVALIDATION_SQL.read_text(encoding="utf-8")
        self.assertIn(SESSION_GUARD + ";", text)
        self.assertIn(CURRENT_SETTING, text)
        self.assertIn(CATALOG, text)
        self.assertIn(SQL_PREDICATE, text)
        self.assertIn("wave1_event_trigger_guard", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
