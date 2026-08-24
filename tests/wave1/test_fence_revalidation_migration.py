from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authority.fence_sql_contract import validate_fence_revalidation_sql_text  # noqa: E402

SQL_PATH = ROOT / "sql" / "wave1" / "002_revalidate_authority_fence_contract.sql"


class FenceRevalidationMigrationTests(unittest.TestCase):
    def test_real_revalidation_migration_is_fail_closed(self):
        text = SQL_PATH.read_text(encoding="utf-8")
        self.assertEqual(validate_fence_revalidation_sql_text(text), [])

    def test_existing_rows_must_be_validated_not_only_future_rows(self):
        text = SQL_PATH.read_text(encoding="utf-8")
        weakened = text.replace(
            "ALTER TABLE platform.authority_fences\n    VALIDATE CONSTRAINT wave1_fence_scope_id_canonical;\n",
            "",
            1,
        )
        findings = validate_fence_revalidation_sql_text(weakened)
        self.assertTrue(any("VALIDATE CONSTRAINT wave1_fence_scope_id_canonical" in f for f in findings))

    def test_revalidation_cannot_rewrite_bad_authority_rows_to_pass(self):
        text = SQL_PATH.read_text(encoding="utf-8")
        weakened = text + "\nUPDATE platform.authority_fences SET authority_state = 'active';\n"
        findings = validate_fence_revalidation_sql_text(weakened)
        self.assertTrue(any("must not normalize/delete" in f for f in findings))

    def test_revalidation_preserves_positive_epoch_contract(self):
        text = SQL_PATH.read_text(encoding="utf-8")
        weakened = text.replace("CHECK (current_fence_epoch > 0) NOT VALID", "CHECK (current_fence_epoch >= 0) NOT VALID")
        findings = validate_fence_revalidation_sql_text(weakened)
        self.assertTrue(any("current_fence_epoch > 0" in f for f in findings))


if __name__ == "__main__":
    unittest.main(verbosity=2)
