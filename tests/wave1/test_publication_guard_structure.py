from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authority.validate_publication_guard_structure import (  # noqa: E402
    BOOTSTRAP_PATH,
    REUSE_PATH,
    validate_bootstrap_structure,
    validate_reuse_structure,
)


class PublicationGuardStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bootstrap = BOOTSTRAP_PATH.read_text(encoding="utf-8")
        cls.reuse = REUSE_PATH.read_text(encoding="utf-8")

    def test_real_migrations_have_reachable_publication_guards(self):
        self.assertEqual(validate_bootstrap_structure(self.bootstrap), [])
        self.assertEqual(validate_reuse_structure(self.reuse), [])

    def test_bootstrap_guard_cannot_hide_inside_false_if(self):
        start = self.bootstrap.index("    IF EXISTS (\n        SELECT 1\n          FROM pg_catalog.pg_publication p")
        end = self.bootstrap.index("    END IF;", start) + len("    END IF;\n")
        guard = self.bootstrap[start:end]
        wrapped = "    IF false THEN\n" + guard + "    END IF;\n"
        mutated = self.bootstrap[:start] + wrapped + self.bootstrap[end:]
        findings = validate_bootstrap_structure(mutated)
        self.assertTrue(any("control depth" in finding for finding in findings), findings)

    def test_bootstrap_guard_cannot_hide_inside_zero_iteration_loop(self):
        start = self.bootstrap.index("    IF EXISTS (\n        SELECT 1\n          FROM pg_catalog.pg_publication p")
        end = self.bootstrap.index("    END IF;", start) + len("    END IF;\n")
        guard = self.bootstrap[start:end]
        wrapped = "    WHILE false LOOP\n" + guard + "    END LOOP;\n"
        mutated = self.bootstrap[:start] + wrapped + self.bootstrap[end:]
        findings = validate_bootstrap_structure(mutated)
        self.assertTrue(any("control depth" in finding for finding in findings), findings)

    def test_bootstrap_guard_cannot_be_laundered_through_dollar_literal(self):
        start = self.bootstrap.index("    IF EXISTS (\n        SELECT 1\n          FROM pg_catalog.pg_publication p")
        end = self.bootstrap.index("    END IF;", start) + len("    END IF;\n")
        guard = self.bootstrap[start:end]
        mutated = self.bootstrap[:start] + "    PERFORM $dead$\n" + guard + "    $dead$;\n" + self.bootstrap[end:]
        findings = validate_bootstrap_structure(mutated)
        self.assertTrue(any("missing" in finding for finding in findings), findings)

    def test_reuse_static_guard_cannot_hide_inside_false_if(self):
        start = self.reuse.index("    IF EXISTS (\n        SELECT 1 FROM pg_catalog.pg_publication p")
        end = self.reuse.index("    END IF;", start) + len("    END IF;\n")
        guard = self.reuse[start:end]
        wrapped = "    IF false THEN\n" + guard + "    END IF;\n"
        mutated = self.reuse[:start] + wrapped + self.reuse[end:]
        findings = validate_reuse_structure(mutated)
        self.assertTrue(any("control depth" in finding for finding in findings), findings)

    def test_reuse_static_guard_cannot_be_laundered_through_dollar_literal(self):
        start = self.reuse.index("    IF EXISTS (\n        SELECT 1 FROM pg_catalog.pg_publication_rel pr")
        end = self.reuse.index("    END IF;", start) + len("    END IF;\n")
        guard = self.reuse[start:end]
        mutated = self.reuse[:start] + "    PERFORM $dead$\n" + guard + "    $dead$;\n" + self.reuse[end:]
        findings = validate_reuse_structure(mutated)
        self.assertTrue(any("explicit publication relation guard" in finding for finding in findings), findings)

    def test_schema_query_cannot_hide_inside_extra_false_if(self):
        start = self.reuse.index("        EXECUTE\n            'SELECT EXISTS ('")
        end = self.reuse.index("            USING v_schema;", start) + len("            USING v_schema;\n")
        query = self.reuse[start:end]
        wrapped = "        IF false THEN\n" + query + "        END IF;\n"
        mutated = self.reuse[:start] + wrapped + self.reuse[end:]
        findings = validate_reuse_structure(mutated)
        self.assertTrue(any("dynamic query must execute directly" in finding for finding in findings), findings)

    def test_schema_result_guard_cannot_hide_inside_extra_false_if(self):
        start = self.reuse.index("        IF v_schema_publication_exists THEN")
        end = self.reuse.index("        END IF;", start) + len("        END IF;\n")
        guard = self.reuse[start:end]
        wrapped = "        IF false THEN\n" + guard + "        END IF;\n"
        mutated = self.reuse[:start] + wrapped + self.reuse[end:]
        findings = validate_reuse_structure(mutated)
        self.assertTrue(any("control depth 1" in finding for finding in findings), findings)

    def test_reuse_top_level_return_bypass_is_rejected(self):
        marker = "    -- Inbound logical replication is an external writer authority."
        mutated = self.reuse.replace(marker, "    RETURN;\n\n" + marker, 1)
        findings = validate_reuse_structure(mutated)
        self.assertIn("reuse publication preflight contains top-level RETURN bypass", findings)


if __name__ == "__main__":
    unittest.main(verbosity=2)
