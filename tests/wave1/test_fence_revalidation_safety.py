from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authority.validate_fence_revalidation_safety import (  # noqa: E402
    validate_revalidation_safety_text,
)

SQL_PATH = ROOT / "sql" / "wave1" / "002_revalidate_authority_fence_contract.sql"


class FenceRevalidationSafetyTests(unittest.TestCase):
    def text(self) -> str:
        return SQL_PATH.read_text(encoding="utf-8")

    def test_real_migration_is_atomic_replication_and_event_trigger_safe(self):
        self.assertEqual(validate_revalidation_safety_text(self.text()), [])

    def test_missing_begin_fails_closed(self):
        weakened = self.text().replace("BEGIN;\n", "", 1)
        findings = validate_revalidation_safety_text(weakened)
        self.assertTrue(any("BEGIN" in finding for finding in findings))

    def test_missing_commit_fails_closed(self):
        weakened = self.text().replace("\nCOMMIT;\n", "\n", 1)
        findings = validate_revalidation_safety_text(weakened)
        self.assertTrue(any("COMMIT" in finding for finding in findings))

    def test_early_commit_fails_closed(self):
        weakened = self.text().replace(
            "ALTER TABLE platform.authority_fences\n    DROP CONSTRAINT",
            "COMMIT;\n\nALTER TABLE platform.authority_fences\n    DROP CONSTRAINT",
            1,
        )
        findings = validate_revalidation_safety_text(weakened)
        self.assertTrue(any("COMMIT" in finding or "transaction" in finding for finding in findings))

    def test_missing_access_exclusive_lock_fails_closed(self):
        weakened = self.text().replace(
            "LOCK TABLE platform.authority_fences IN ACCESS EXCLUSIVE MODE;\n",
            "",
            1,
        )
        findings = validate_revalidation_safety_text(weakened)
        self.assertTrue(any("ACCESS EXCLUSIVE" in finding for finding in findings))

    def test_lock_after_validation_fails_closed(self):
        text = self.text()
        lock = "LOCK TABLE platform.authority_fences IN ACCESS EXCLUSIVE MODE;\n"
        weakened = text.replace(lock, "", 1).replace("END\n$$;", "END\n$$;\n\n" + lock, 1)
        findings = validate_revalidation_safety_text(weakened)
        self.assertTrue(any("ordering" in finding for finding in findings))

    def test_missing_set_local_event_triggers_off_fails_closed(self):
        weakened = self.text().replace("SET LOCAL event_triggers = off;\n", "", 1)
        findings = validate_revalidation_safety_text(weakened)
        self.assertTrue(any("SET LOCAL event_triggers" in finding for finding in findings))

    def test_non_local_event_trigger_disable_fails_closed(self):
        weakened = self.text().replace(
            "SET LOCAL event_triggers = off;",
            "SET event_triggers = off;",
            1,
        )
        findings = validate_revalidation_safety_text(weakened)
        self.assertTrue(any("SET LOCAL event_triggers" in finding for finding in findings))

    def test_event_trigger_reenable_fails_closed(self):
        weakened = self.text().replace(
            "LOCK TABLE platform.authority_fences IN ACCESS EXCLUSIVE MODE;",
            "SET LOCAL event_triggers = on;\n\nLOCK TABLE platform.authority_fences IN ACCESS EXCLUSIVE MODE;",
            1,
        )
        findings = validate_revalidation_safety_text(weakened)
        self.assertTrue(any("exactly one SET LOCAL event_triggers" in finding for finding in findings))

    def test_event_trigger_disable_must_precede_preflight(self):
        text = self.text()
        token = "SET LOCAL event_triggers = off;\n\n"
        weakened = text.replace(token, "", 1).replace(
            "LOCK TABLE platform.authority_fences IN ACCESS EXCLUSIVE MODE;",
            token + "LOCK TABLE platform.authority_fences IN ACCESS EXCLUSIVE MODE;",
            1,
        )
        findings = validate_revalidation_safety_text(weakened)
        self.assertTrue(any("session guard" in finding or "ordering" in finding for finding in findings))

    def test_event_trigger_disable_cannot_be_comment_laundered(self):
        weakened = self.text().replace(
            "SET LOCAL event_triggers = off;",
            "-- SET LOCAL event_triggers = off;",
            1,
        )
        findings = validate_revalidation_safety_text(weakened)
        self.assertTrue(any("SET LOCAL event_triggers" in finding for finding in findings))

    def test_event_trigger_guard_requires_current_setting_proof(self):
        weakened = self.text().replace(
            "WHEN current_setting('event_triggers') IS DISTINCT FROM 'off' THEN 0\n    ",
            "",
            1,
        )
        findings = validate_revalidation_safety_text(weakened)
        self.assertTrue(any("locally disabled" in finding for finding in findings))

    def test_event_trigger_guard_requires_pg_event_trigger_catalog(self):
        weakened = self.text().replace(
            "FROM pg_catalog.pg_event_trigger et",
            "FROM pg_catalog.pg_trigger et",
            1,
        )
        findings = validate_revalidation_safety_text(weakened)
        self.assertTrue(any("event trigger" in finding.lower() for finding in findings))

    def test_event_trigger_guard_must_reject_every_non_disabled_trigger(self):
        weakened = self.text().replace(
            "WHERE et.evtenabled <> 'D'",
            "WHERE et.evtenabled = 'D'",
            1,
        )
        findings = validate_revalidation_safety_text(weakened)
        self.assertTrue(any("event trigger" in finding.lower() for finding in findings))

    def test_event_trigger_guard_must_precede_fence_ddl(self):
        text = self.text()
        marker = (
            "SELECT 1 / CASE\n"
            "    WHEN current_setting('event_triggers') IS DISTINCT FROM 'off' THEN 0\n"
            "    WHEN EXISTS (\n"
            "        SELECT 1\n"
            "          FROM pg_catalog.pg_event_trigger et\n"
            "         WHERE et.evtenabled <> 'D'\n"
            "    ) THEN 0\n"
            "    ELSE 1\n"
            "END AS wave1_event_trigger_guard;\n\n"
        )
        weakened = text.replace(marker, "", 1).replace(
            "ALTER TABLE platform.authority_fences\n    ALTER COLUMN fence_scope_id SET NOT NULL,",
            marker + "ALTER TABLE platform.authority_fences\n    ALTER COLUMN fence_scope_id SET NOT NULL,",
            1,
        )
        findings = validate_revalidation_safety_text(weakened)
        self.assertTrue(any("event-trigger" in finding.lower() or "event trigger" in finding.lower() for finding in findings))

    def test_event_trigger_guard_cannot_be_comment_laundered(self):
        weakened = self.text().replace(
            "FROM pg_catalog.pg_event_trigger et",
            "FROM pg_catalog.pg_trigger et\n         -- FROM pg_catalog.pg_event_trigger et",
            1,
        )
        findings = validate_revalidation_safety_text(weakened)
        self.assertTrue(any("event trigger" in finding.lower() for finding in findings))

    def test_logical_replication_guard_requires_pg_subscription_rel(self):
        weakened = self.text().replace(
            "FROM pg_catalog.pg_subscription_rel sr",
            "FROM pg_catalog.pg_class sr",
            1,
        )
        findings = validate_revalidation_safety_text(weakened)
        self.assertTrue(any("logical-replication" in finding for finding in findings))

    def test_logical_replication_guard_must_bind_exact_fence_table(self):
        weakened = self.text().replace(
            "WHERE sr.srrelid = v_table",
            "WHERE sr.srrelid <> v_table",
            1,
        )
        findings = validate_revalidation_safety_text(weakened)
        self.assertTrue(any("logical-replication" in finding for finding in findings))

    def test_logical_replication_guard_cannot_be_comment_laundered(self):
        weakened = self.text().replace(
            "WHERE sr.srrelid = v_table",
            "WHERE false\n           -- WHERE sr.srrelid = v_table",
            1,
        )
        findings = validate_revalidation_safety_text(weakened)
        self.assertTrue(any("logical-replication" in finding for finding in findings))


if __name__ == "__main__":
    unittest.main(verbosity=2)
