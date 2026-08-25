from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authority.validate_fence_revalidation_safety import (  # noqa: E402
    validate_bootstrap_safety_text,
)

SQL_PATH = ROOT / "sql" / "wave1" / "001_platform_authority_fence.sql"


class FenceBootstrapSafetyTests(unittest.TestCase):
    def text(self) -> str:
        return SQL_PATH.read_text(encoding="utf-8")

    def test_real_bootstrap_closes_event_trigger_window_before_ddl(self):
        self.assertEqual(validate_bootstrap_safety_text(self.text()), [])

    def test_missing_begin_fails_closed(self):
        weakened = self.text().replace("BEGIN;\n", "", 1)
        self.assertTrue(any("BEGIN" in item for item in validate_bootstrap_safety_text(weakened)))

    def test_missing_commit_fails_closed(self):
        weakened = self.text().replace("\nCOMMIT;\n", "\n", 1)
        self.assertTrue(any("COMMIT" in item for item in validate_bootstrap_safety_text(weakened)))

    def test_early_commit_fails_closed(self):
        weakened = self.text().replace(
            "CREATE SCHEMA IF NOT EXISTS platform;",
            "COMMIT;\n\nCREATE SCHEMA IF NOT EXISTS platform;",
            1,
        )
        findings = validate_bootstrap_safety_text(weakened)
        self.assertTrue(any("COMMIT" in item or "transaction" in item for item in findings))

    def test_missing_set_local_fails_closed(self):
        weakened = self.text().replace("SET LOCAL event_triggers = off;\n", "", 1)
        self.assertTrue(
            any("SET LOCAL event_triggers" in item for item in validate_bootstrap_safety_text(weakened))
        )

    def test_non_local_set_fails_closed(self):
        weakened = self.text().replace(
            "SET LOCAL event_triggers = off;",
            "SET event_triggers = off;",
            1,
        )
        self.assertTrue(
            any("SET LOCAL event_triggers" in item for item in validate_bootstrap_safety_text(weakened))
        )

    def test_reenable_fails_closed(self):
        weakened = self.text().replace(
            "CREATE SCHEMA IF NOT EXISTS platform;",
            "SET LOCAL event_triggers = on;\n\nCREATE SCHEMA IF NOT EXISTS platform;",
            1,
        )
        self.assertTrue(
            any("exactly one SET LOCAL" in item for item in validate_bootstrap_safety_text(weakened))
        )

    def test_current_setting_proof_is_required(self):
        weakened = self.text().replace(
            "WHEN current_setting('event_triggers') IS DISTINCT FROM 'off' THEN 0\n    ",
            "",
            1,
        )
        self.assertTrue(any("locally disabled" in item for item in validate_bootstrap_safety_text(weakened)))

    def test_catalog_and_non_disabled_predicate_are_required(self):
        redirected = self.text().replace(
            "FROM pg_catalog.pg_event_trigger et",
            "FROM pg_catalog.pg_trigger et",
            1,
        )
        inverted = self.text().replace(
            "WHERE et.evtenabled <> 'D'",
            "WHERE et.evtenabled = 'D'",
            1,
        )
        self.assertTrue(any("event trigger" in item.lower() for item in validate_bootstrap_safety_text(redirected)))
        self.assertTrue(any("event trigger" in item.lower() for item in validate_bootstrap_safety_text(inverted)))

    def test_guard_must_precede_first_ddl(self):
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
            "END AS wave1_bootstrap_event_trigger_guard;\n\n"
        )
        weakened = text.replace(marker, "", 1).replace(
            "REVOKE CREATE ON SCHEMA platform FROM PUBLIC;",
            "REVOKE CREATE ON SCHEMA platform FROM PUBLIC;\n\n" + marker,
            1,
        )
        findings = validate_bootstrap_safety_text(weakened)
        self.assertTrue(any("before its first DDL" in item or "before CREATE SCHEMA" in item for item in findings))

    def test_guard_cannot_be_comment_laundered(self):
        weakened = self.text().replace(
            "FROM pg_catalog.pg_event_trigger et",
            "FROM pg_catalog.pg_trigger et\n         -- FROM pg_catalog.pg_event_trigger et",
            1,
        )
        self.assertTrue(any("event trigger" in item.lower() for item in validate_bootstrap_safety_text(weakened)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
