from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authority.fence_sql_contract import validate_fence_revalidation_sql_text, validate_fence_sql_text  # noqa: E402

SQL_001 = ROOT / "sql" / "wave1" / "001_platform_authority_fence.sql"
SQL_002 = ROOT / "sql" / "wave1" / "002_revalidate_authority_fence_contract.sql"


class FenceCollationTests(unittest.TestCase):
    def test_storage_and_compare_contract_require_deterministic_c_collation(self):
        text = SQL_001.read_text(encoding="utf-8")
        self.assertEqual(validate_fence_sql_text(text), [])

        weakened = text.replace('fence_scope_id text COLLATE "C" NOT NULL', 'fence_scope_id text NOT NULL', 1)
        self.assertTrue(any('fence_scope_id text COLLATE "C" NOT NULL' in item for item in validate_fence_sql_text(weakened)))

        canonical = 'authority_fences.fence_scope_id COLLATE "C" OPERATOR(pg_catalog.=) p_fence_scope_id COLLATE "C"'
        weakened = text.replace(canonical, 'authority_fences.fence_scope_id OPERATOR(pg_catalog.=) p_fence_scope_id', 1)
        self.assertTrue(any('fence_scope_id COLLATE "C"' in item for item in validate_fence_sql_text(weakened)))

    def test_reused_table_must_prove_c_collation_on_authority_text_columns(self):
        text = SQL_002.read_text(encoding="utf-8")
        self.assertEqual(validate_fence_revalidation_sql_text(text), [])
        token = "attcollation IS DISTINCT FROM 'pg_catalog.\"C\"'::pg_catalog.regcollation"
        weakened = text.replace(token, "false", 1)
        self.assertTrue(any("attcollation" in item for item in validate_fence_revalidation_sql_text(weakened)))

    def test_reused_check_dependency_cannot_switch_collation_authority(self):
        text = SQL_002.read_text(encoding="utf-8")
        token = "d.refobjid OPERATOR(pg_catalog.<>) 'pg_catalog.\"C\"'::pg_catalog.regcollation"
        weakened = text.replace(token, "false", 1)
        self.assertTrue(any("dependency" in item or "collation" in item for item in validate_fence_revalidation_sql_text(weakened)))

    def test_reused_primary_key_must_prove_index_c_collation(self):
        text = SQL_002.read_text(encoding="utf-8")
        token = "i.indcollation[0] OPERATOR(pg_catalog.=) 'pg_catalog.\"C\"'::pg_catalog.regcollation::oid"
        weakened = text.replace(token, "i.indcollation[0] OPERATOR(pg_catalog.<>) 0", 1)
        findings = validate_fence_revalidation_sql_text(weakened)
        self.assertTrue(any("indcollation" in item.lower() or "primary key" in item.lower() or "collation" in item.lower() for item in findings), findings)

    def test_reused_primary_key_must_prove_catalog_text_btree_opclass(self):
        text = SQL_002.read_text(encoding="utf-8")
        weakened = text.replace(
            "i.indclass[0] OPERATOR(pg_catalog.=) v_text_btree_opclass",
            "i.indclass[0] OPERATOR(pg_catalog.<>) v_text_btree_opclass",
            1,
        )
        findings = validate_fence_revalidation_sql_text(weakened)
        self.assertTrue(any("indclass" in item.lower() or "primary key" in item.lower() or "opclass" in item.lower() for item in findings), findings)

    def test_reused_primary_key_must_be_catalog_btree(self):
        text = SQL_002.read_text(encoding="utf-8")
        weakened = text.replace(
            "index_class.relam OPERATOR(pg_catalog.=) v_btree_am",
            "index_class.relam OPERATOR(pg_catalog.<>) v_btree_am",
            1,
        )
        findings = validate_fence_revalidation_sql_text(weakened)
        self.assertTrue(any("relam" in item.lower() or "primary key" in item.lower() or "btree" in item.lower() for item in findings), findings)


if __name__ == "__main__":
    unittest.main(verbosity=2)
