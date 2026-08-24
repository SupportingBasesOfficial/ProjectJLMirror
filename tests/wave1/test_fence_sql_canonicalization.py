from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authority.fence_sql_contract import (  # noqa: E402
    CANONICAL_IDENTIFIER_REGEX,
    validate_fence_sql_text,
)

SQL_PATH = ROOT / "sql" / "wave1" / "001_platform_authority_fence.sql"


class FenceSqlCanonicalizationTests(unittest.TestCase):
    def test_real_fence_sql_enforces_portable_identifier_grammar(self):
        text = SQL_PATH.read_text(encoding="utf-8")
        self.assertEqual(validate_fence_sql_text(text), [])

    def test_trim_only_storage_constraint_is_not_sufficient(self):
        text = SQL_PATH.read_text(encoding="utf-8")
        weakened = text.replace(
            f"        CHECK (fence_scope_id ~ '{CANONICAL_IDENTIFIER_REGEX}')\n",
            "",
            1,
        )
        findings = validate_fence_sql_text(weakened)
        self.assertTrue(any("fence_scope_id" in finding for finding in findings))

    def test_successor_input_cannot_drop_canonical_generation_check(self):
        text = SQL_PATH.read_text(encoding="utf-8")
        weakened = text.replace(
            f"       AND p_successor_generation_id ~ '{CANONICAL_IDENTIFIER_REGEX}'\n",
            "",
            1,
        )
        findings = validate_fence_sql_text(weakened)
        self.assertTrue(any("p_successor_generation_id" in finding for finding in findings))

    def test_sql_grammar_rejects_whitespace_and_control_form_by_construction(self):
        self.assertNotIn("\\s", CANONICAL_IDENTIFIER_REGEX)
        self.assertNotIn(" ", CANONICAL_IDENTIFIER_REGEX)
        self.assertEqual(CANONICAL_IDENTIFIER_REGEX[0], "^")
        self.assertEqual(CANONICAL_IDENTIFIER_REGEX[-1], "$")


if __name__ == "__main__":
    unittest.main(verbosity=2)
