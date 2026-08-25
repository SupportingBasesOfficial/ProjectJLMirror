from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authority.fence_sql_contract import validate_fence_revalidation_sql_text  # noqa: E402
from tools.authority.validate_fence_revalidation_safety import (  # noqa: E402
    validate_bootstrap_safety_text,
    validate_revalidation_safety_text,
)

BOUNDARY = ROOT / "implementation" / "wave-1" / "FENCE_REUSE_ADMISSION_BOUNDARY.md"
SQL_001 = ROOT / "sql" / "wave1" / "001_platform_authority_fence.sql"
SQL_002 = ROOT / "sql" / "wave1" / "002_revalidate_authority_fence_contract.sql"

REQUIRED_BOUNDARY_LAWS = {
    "TABLE ABSENT != AUTHORITY NAMESPACE FRESH",
    "PARTIAL AUTHORITY OBJECT SET != BOOTSTRAP MUTATION ELIGIBILITY",
    "STRUCTURAL REUSE PASS != PRIVILEGE REUSE ADMISSION",
    "POST-COMMIT PRIVILEGE CHECK != FAIL-CLOSED REUSE",
    "COLUMN C COLLATION != PRIMARY-KEY C COLLATION",
    "PRIMARY KEY SHAPE != PRIMARY-KEY OPERATOR-CLASS AUTHORITY",
    "ON CONFLICT TARGET MATCH != CANONICAL CONFLICT EQUALITY",
    "WAVE 1 HARDENING != WAVE 2 AUTHORIZATION",
}


class FenceReuseAdmissionBoundaryTests(unittest.TestCase):
    def test_boundary_pins_all_latest_reuse_authority_laws(self):
        text = BOUNDARY.read_text(encoding="utf-8")
        missing = REQUIRED_BOUNDARY_LAWS - {law for law in REQUIRED_BOUNDARY_LAWS if law in text}
        self.assertFalse(missing, missing)

    def test_real_bootstrap_and_reuse_migrations_conform(self):
        bootstrap = SQL_001.read_text(encoding="utf-8")
        reuse = SQL_002.read_text(encoding="utf-8")
        self.assertEqual(validate_bootstrap_safety_text(bootstrap), [])
        self.assertEqual(validate_revalidation_safety_text(reuse), [])
        self.assertEqual(validate_fence_revalidation_sql_text(reuse), [])

    def test_boundary_required_catalog_anchors_match_sql(self):
        bootstrap = SQL_001.read_text(encoding="utf-8")
        reuse = SQL_002.read_text(encoding="utf-8")
        for token in (
            "pg_catalog.to_regnamespace('platform')",
            "platform.initialize_authority_fence(text,text,text)",
            "platform.advance_authority_fence(text,bigint,text,text,text)",
        ):
            self.assertIn(token, bootstrap)
        for token in (
            "DO $wave1_reuse_privilege_preflight$",
            "i.indcollation[0]",
            "i.indclass[0]",
            "v_text_btree_opclass",
            "pg_catalog.pg_opclass",
        ):
            self.assertIn(token, reuse)


if __name__ == "__main__":
    unittest.main(verbosity=2)
