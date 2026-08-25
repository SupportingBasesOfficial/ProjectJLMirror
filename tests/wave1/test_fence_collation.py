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


if __name__ == "__main__":
    unittest.main(verbosity=2)
