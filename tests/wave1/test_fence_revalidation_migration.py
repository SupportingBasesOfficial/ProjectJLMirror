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
    @classmethod
    def setUpClass(cls):
        cls.text = SQL_PATH.read_text(encoding="utf-8")

    def assert_fails(self, text: str) -> None:
        self.assertTrue(validate_fence_revalidation_sql_text(text))

    def test_real_revalidation_migration_is_fail_closed(self):
        self.assertEqual(validate_fence_revalidation_sql_text(self.text), [])

    def test_existing_rows_are_validated_before_function_replacement(self):
        self.assert_fails(self.text.replace("ALTER TABLE platform.authority_fences\n    VALIDATE CONSTRAINT wave1_fence_scope_id_canonical;\n", "", 1))

    def test_revalidation_cannot_rewrite_bad_authority_rows_before_validation(self):
        marker = "DO $wave1_revalidate$"
        self.assert_fails(self.text.replace(marker, "UPDATE platform.authority_fences SET authority_state = 'active';\n\n" + marker, 1))

    def test_positive_bigint_epoch_contract_is_exact(self):
        self.assert_fails(self.text.replace("CHECK (current_fence_epoch OPERATOR(pg_catalog.>) 0) NOT VALID", "CHECK (current_fence_epoch OPERATOR(pg_catalog.>=) 0) NOT VALID"))
        self.assert_fails(self.text.replace("'int8'::pg_catalog.regtype", "'int4'::pg_catalog.regtype"))

    def test_primary_key_is_single_column_immediate_valid_ready_live(self):
        mutations = (
            ("c.conkey OPERATOR(pg_catalog.=) ARRAY[a.attnum]::smallint[]", "c.conkey IS NOT NULL"),
            ("AND NOT c.condeferrable", "AND c.condeferrable"),
            ("AND i.indimmediate", "AND NOT i.indimmediate"),
            ("AND i.indisvalid", "AND NOT i.indisvalid"),
            ("AND i.indisready", "AND NOT i.indisready"),
            ("AND i.indislive", "AND NOT i.indislive"),
            ("AND i.indnkeyatts OPERATOR(pg_catalog.=) 1", "AND i.indnkeyatts OPERATOR(pg_catalog.>) 0"),
            ("AND i.indexprs IS NULL", "AND i.indexprs IS NOT NULL"),
            ("AND i.indpred IS NULL", "AND i.indpred IS NOT NULL"),
        )
        for old, new in mutations:
            with self.subTest(old=old):
                self.assert_fails(self.text.replace(old, new))

    def test_foreign_keys_are_rejected_in_both_directions(self):
        token = "c.conrelid OPERATOR(pg_catalog.=) v_table OR c.confrelid OPERATOR(pg_catalog.=) v_table"
        self.assert_fails(self.text.replace(token, "c.conrelid OPERATOR(pg_catalog.=) v_table"))
        self.assert_fails(self.text.replace(token, "c.confrelid OPERATOR(pg_catalog.=) v_table"))

    def test_external_rewrite_dependency_guard_is_exact(self):
        mutations = (
            ("FROM pg_catalog.pg_rewrite r", "FROM pg_catalog.pg_class r"),
            ("JOIN pg_catalog.pg_depend d", "JOIN pg_catalog.pg_class d"),
            ("d.refobjid OPERATOR(pg_catalog.=) v_table", "d.refobjid OPERATOR(pg_catalog.<>) v_table"),
            ("r.ev_class OPERATOR(pg_catalog.<>) v_table", "r.ev_class OPERATOR(pg_catalog.=) v_table"),
        )
        for old, new in mutations:
            with self.subTest(old=old):
                self.assert_fails(self.text.replace(old, new))

    def test_table_shape_and_column_types_are_exact(self):
        mutations = (
            ("SELECT pg_catalog.array_agg(attname::text ORDER BY attnum)", "SELECT ARRAY['fence_scope_id']::text[]"),
            ("'timestamptz'::pg_catalog.regtype", "'timestamp'::pg_catalog.regtype"),
            ("ROW('r'::\"char\", 'p'::\"char\", false, false, false)", "ROW('p'::\"char\", 'p'::\"char\", false, false, false)"),
            ("FROM pg_catalog.pg_inherits", "FROM pg_catalog.pg_class"),
            ("FROM pg_catalog.pg_policy", "FROM pg_catalog.pg_class"),
        )
        for old, new in mutations:
            with self.subTest(old=old):
                self.assert_fails(self.text.replace(old, new))

    def test_default_and_generated_identity_surfaces_are_exact(self):
        self.assert_fails(self.text.replace("a.attname OPERATOR(pg_catalog.<>) 'updated_at'", "false"))
        self.assert_fails(self.text.replace("IS DISTINCT FROM 'statement_timestamp()'", "IS DISTINCT FROM 'clock_timestamp()'"))
        self.assert_fails(self.text.replace("attgenerated OPERATOR(pg_catalog.<>) '' OR attidentity OPERATOR(pg_catalog.<>) ''", "false"))

    def test_trigger_rule_and_replication_surfaces_are_required(self):
        for old, new in (
            ("FROM pg_catalog.pg_trigger t", "FROM pg_catalog.pg_class t"),
            ("FROM pg_catalog.pg_rewrite r", "FROM pg_catalog.pg_class r"),
            ("FROM pg_catalog.pg_subscription_rel sr", "FROM pg_catalog.pg_class sr"),
        ):
            with self.subTest(old=old):
                self.assert_fails(self.text.replace(old, new))

    def test_catalog_dependency_guard_rejects_noncanonical_stored_expression_authority(self):
        for old, new in (
            ("LEFT JOIN pg_catalog.pg_proc p", "LEFT JOIN pg_catalog.pg_class p"),
            ("LEFT JOIN pg_catalog.pg_operator o", "LEFT JOIN pg_catalog.pg_class o"),
            ("p.pronamespace OPERATOR(pg_catalog.<>) 'pg_catalog'::pg_catalog.regnamespace", "false"),
            ("o.oprnamespace OPERATOR(pg_catalog.<>) 'pg_catalog'::pg_catalog.regnamespace", "false"),
            ("d.refobjid OPERATOR(pg_catalog.<>) 'pg_catalog.\"C\"'::pg_catalog.regcollation", "false"),
        ):
            with self.subTest(old=old):
                self.assert_fails(self.text.replace(old, new))

    def test_both_recreated_functions_pin_pg_catalog_search_path(self):
        self.assertEqual(self.text.count("SET search_path = pg_catalog"), 2)
        self.assert_fails(self.text.replace("SET search_path = pg_catalog", "SET search_path = public, pg_catalog"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
