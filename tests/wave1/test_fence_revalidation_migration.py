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
        weakened = text.replace(
            "CHECK (current_fence_epoch > 0) NOT VALID",
            "CHECK (current_fence_epoch >= 0) NOT VALID",
            1,
        )
        findings = validate_fence_revalidation_sql_text(weakened)
        self.assertTrue(any("current_fence_epoch > 0" in f for f in findings))

    def test_revalidation_requires_bigint_epoch_storage(self):
        text = SQL_PATH.read_text(encoding="utf-8")
        weakened = text.replace(
            "IS DISTINCT FROM 'int8'::regtype",
            "IS DISTINCT FROM 'int4'::regtype",
            1,
        )
        findings = validate_fence_revalidation_sql_text(weakened)
        self.assertTrue(any("int8" in f for f in findings))

    def test_revalidation_requires_single_column_scope_primary_key(self):
        text = SQL_PATH.read_text(encoding="utf-8")
        weakened = text.replace(
            "c.conkey = ARRAY[a.attnum]::smallint[]",
            "c.conkey IS NOT NULL",
            1,
        )
        findings = validate_fence_revalidation_sql_text(weakened)
        self.assertTrue(any("c.conkey = ARRAY[a.attnum]" in f for f in findings))

    def test_revalidation_requires_expected_column_types(self):
        text = SQL_PATH.read_text(encoding="utf-8")
        weakened = text.replace(
            "IS DISTINCT FROM 'timestamptz'::regtype",
            "IS DISTINCT FROM 'timestamp'::regtype",
            1,
        )
        findings = validate_fence_revalidation_sql_text(weakened)
        self.assertTrue(any("timestamptz" in f for f in findings))

    def test_revalidation_requires_permanent_logged_relation(self):
        text = SQL_PATH.read_text(encoding="utf-8")
        weakened = text.replace("IS DISTINCT FROM 'p'", "IS DISTINCT FROM 'u'", 1)
        findings = validate_fence_revalidation_sql_text(weakened)
        self.assertTrue(any("DISTINCT FROM 'p'" in f for f in findings))

    def test_revalidation_requires_updated_at_not_null(self):
        text = SQL_PATH.read_text(encoding="utf-8")
        weakened = text.replace("    ALTER COLUMN updated_at SET NOT NULL;", ";", 1)
        findings = validate_fence_revalidation_sql_text(weakened)
        self.assertTrue(any("updated_at SET NOT NULL" in f for f in findings))

    def test_revalidation_rejects_generated_or_identity_authority_columns(self):
        text = SQL_PATH.read_text(encoding="utf-8")
        weakened = text.replace(
            "AND (attgenerated <> '' OR attidentity <> '')",
            "AND false",
            1,
        )
        findings = validate_fence_revalidation_sql_text(weakened)
        self.assertTrue(any("attgenerated" in f for f in findings))

    def test_revalidation_requires_non_internal_trigger_guard(self):
        text = SQL_PATH.read_text(encoding="utf-8")
        weakened = text.replace(
            "AND NOT t.tgisinternal",
            "AND t.tgisinternal\n           -- AND NOT t.tgisinternal",
            1,
        )
        findings = validate_fence_revalidation_sql_text(weakened)
        self.assertTrue(any("trigger behavior" in f for f in findings))

    def test_revalidation_requires_rewrite_rule_guard(self):
        text = SQL_PATH.read_text(encoding="utf-8")
        weakened = text.replace(
            "WHERE r.ev_class = v_table",
            "WHERE false\n           -- WHERE r.ev_class = v_table",
            1,
        )
        findings = validate_fence_revalidation_sql_text(weakened)
        self.assertTrue(any("rewrite-rule behavior" in f for f in findings))

    def test_executable_invariant_cannot_be_laundered_by_comment(self):
        text = SQL_PATH.read_text(encoding="utf-8")
        weakened = text.replace(
            "ALTER COLUMN updated_at SET NOT NULL",
            "ALTER COLUMN updated_at DROP NOT NULL\n    -- ALTER COLUMN updated_at SET NOT NULL",
            1,
        )
        findings = validate_fence_revalidation_sql_text(weakened)
        self.assertTrue(any("updated_at SET NOT NULL" in f for f in findings))


if __name__ == "__main__":
    unittest.main(verbosity=2)
