from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authority.validate_publication_guard_ancestry import (  # noqa: E402
    BOOTSTRAP_PATH,
    MANIFEST_PATH,
    REUSE_PATH,
    validate_bootstrap_ancestry,
    validate_manifest_object,
    validate_reuse_ancestry,
)


class PublicationGuardAncestryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bootstrap = BOOTSTRAP_PATH.read_text(encoding="utf-8")
        cls.reuse = REUSE_PATH.read_text(encoding="utf-8")
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_real_migrations_and_manifest_bind_exact_fail_closed_structure(self):
        self.assertEqual(validate_bootstrap_ancestry(self.bootstrap), [])
        self.assertEqual(validate_reuse_ancestry(self.reuse), [])
        self.assertEqual(validate_manifest_object(self.manifest), [])

    def test_dynamic_schema_query_cannot_move_to_false_sibling_if(self):
        guard_start = self.reuse.index(
            "    IF pg_catalog.to_regclass('pg_catalog.pg_publication_namespace') IS NOT NULL THEN"
        )
        dynamic_start = self.reuse.index("        EXECUTE\n", guard_start)
        outer_end_anchor = "    END IF;\nEND\n$wave1_revalidate$;"
        outer_end = self.reuse.index(outer_end_anchor, dynamic_start)
        dynamic_and_result = self.reuse[dynamic_start:outer_end]
        replacement = (
            "    IF pg_catalog.to_regclass('pg_catalog.pg_publication_namespace') IS NOT NULL THEN\n"
            "        NULL;\n"
            "    END IF;\n"
            "    IF false THEN\n"
            + dynamic_and_result
            + "    END IF;\n"
        )
        mutated = self.reuse[:guard_start] + replacement + self.reuse[outer_end + len("    END IF;\n"):]
        findings = validate_reuse_ancestry(mutated)
        self.assertTrue(any("exact children" in finding for finding in findings), findings)

    def test_reuse_static_guard_cannot_be_swallowed_by_exception_handler(self):
        start = self.reuse.index(
            "    IF EXISTS (\n        SELECT 1 FROM pg_catalog.pg_publication_rel pr"
        )
        end = self.reuse.index("    END IF;", start) + len("    END IF;\n")
        guard = self.reuse[start:end]
        wrapped = (
            "    BEGIN\n"
            + guard
            + "    EXCEPTION WHEN OTHERS THEN\n"
            "        NULL;\n"
            "    END;\n"
        )
        mutated = self.reuse[:start] + wrapped + self.reuse[end:]
        findings = validate_reuse_ancestry(mutated)
        self.assertTrue(any("EXCEPTION handler" in finding for finding in findings), findings)

    def test_bootstrap_guard_cannot_be_swallowed_by_exception_handler(self):
        start = self.bootstrap.index(
            "    IF EXISTS (\n        SELECT 1\n          FROM pg_catalog.pg_publication p"
        )
        end = self.bootstrap.index("    END IF;", start) + len("    END IF;\n")
        guard = self.bootstrap[start:end]
        wrapped = (
            "    BEGIN\n"
            + guard
            + "    EXCEPTION WHEN OTHERS THEN\n"
            "        NULL;\n"
            "    END;\n"
        )
        mutated = self.bootstrap[:start] + wrapped + self.bootstrap[end:]
        findings = validate_bootstrap_ancestry(mutated)
        self.assertTrue(any("EXCEPTION handler" in finding for finding in findings), findings)

    def test_exception_keyword_in_dead_literal_is_not_handler(self):
        marker = "    EXECUTE 'CREATE SCHEMA platform';"
        mutated = self.bootstrap.replace(
            marker,
            "    PERFORM 'EXCEPTION WHEN OTHERS THEN NULL';\n" + marker,
            1,
        )
        self.assertEqual(validate_bootstrap_ancestry(mutated), [])

    def test_manifest_cannot_launder_ancestry_or_exception_policy(self):
        mutations = (
            ("fresh_preflight", "exception_handlers_allowed", True),
            ("reuse_preflight", "schema_query_and_result_are_exact_children", False),
            ("reuse_preflight", "exception_handlers_allowed", True),
            ("reuse_preflight", "top_level_return_allowed", True),
        )
        for section, field, value in mutations:
            with self.subTest(section=section, field=field):
                mutated = json.loads(json.dumps(self.manifest))
                mutated[section][field] = value
                self.assertTrue(validate_manifest_object(mutated))

    def test_manifest_cannot_drop_forbidden_substitution(self):
        for substitution in (
            "numeric_control_depth_for_block_ancestry",
            "raise_exception_presence_for_unsuppressed_failure",
        ):
            with self.subTest(substitution=substitution):
                mutated = json.loads(json.dumps(self.manifest))
                mutated["forbidden_substitutions"].remove(substitution)
                self.assertTrue(validate_manifest_object(mutated))

    def test_manifest_cannot_enable_product_or_wave2(self):
        mutated = json.loads(json.dumps(self.manifest))
        mutated["product_feature_activation"] = "enabled"
        self.assertTrue(validate_manifest_object(mutated))

        mutated = json.loads(json.dumps(self.manifest))
        mutated["wave_2_authorized"] = True
        self.assertTrue(validate_manifest_object(mutated))


if __name__ == "__main__":
    unittest.main(verbosity=2)
