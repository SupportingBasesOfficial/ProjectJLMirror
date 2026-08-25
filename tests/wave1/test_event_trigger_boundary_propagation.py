from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
ASSURANCE = ROOT / "implementation" / "wave-1" / "ASSURANCE.md"
PRIVILEGE_BOUNDARY = ROOT / "implementation" / "wave-1" / "FENCE_PRIVILEGE_BOUNDARY.md"
SQL = ROOT / "sql" / "wave1" / "002_revalidate_authority_fence_contract.sql"

LAW = "ROW/TABLE HOOKS CLEAN != DATABASE DDL EVENT-TRIGGER ABSENCE"
CATALOG = "pg_catalog.pg_event_trigger"
PREDICATE = "et.evtenabled <> 'D'"


class EventTriggerBoundaryPropagationTests(unittest.TestCase):
    def test_authority_law_is_pinned_in_privilege_boundary(self):
        text = PRIVILEGE_BOUNDARY.read_text(encoding="utf-8")
        self.assertIn(LAW, text)
        self.assertIn(CATALOG, text)
        self.assertIn(PREDICATE, text)

    def test_assurance_requires_database_event_trigger_absence(self):
        text = ASSURANCE.read_text(encoding="utf-8")
        self.assertIn(CATALOG, text)
        self.assertIn(PREDICATE, text)
        self.assertIn("before the first event-trigger-capable fence DDL", text)

    def test_executable_migration_carries_same_catalog_and_predicate(self):
        text = SQL.read_text(encoding="utf-8")
        self.assertIn(CATALOG, text)
        self.assertIn(PREDICATE, text)
        self.assertIn("wave1_event_trigger_guard", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
