from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "tools" / "project_memory" / "validate_project_memory.py"

spec = importlib.util.spec_from_file_location("project_memory_validator", VALIDATOR)
assert spec and spec.loader
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class ProjectMemoryTests(unittest.TestCase):
    def test_validator_passes(self) -> None:
        files, decisions = validator.validate()
        self.assertEqual(files, 12)
        self.assertGreaterEqual(decisions, 10)

    def test_required_corpus_is_exactly_declared(self) -> None:
        self.assertEqual(len(validator.REQUIRED_FILES), 12)
        self.assertIn("HUMAN-OPERATIONS-MODEL.md", validator.REQUIRED_FILES)
        self.assertIn("RECOVERY-PLAYBOOK-FOR-NEW-CHAT.md", validator.REQUIRED_FILES)

    def test_recovery_playbook_is_repository_first(self) -> None:
        text = (validator.MEMORY / "RECOVERY-PLAYBOOK-FOR-NEW-CHAT.md").read_text(encoding="utf-8")
        self.assertIn("repository-backed accepted truth wins", text)
        self.assertIn("verify current `main` SHA", text)

    def test_human_visibility_is_not_best_effort_only(self) -> None:
        text = (validator.MEMORY / "HUMAN-OPERATIONS-MODEL.md").read_text(encoding="utf-8")
        self.assertIn("must not accept indefinite `view_status_unknown`", text)
        self.assertIn("internal operator", text)
        self.assertIn("customer-side responsible person", text)


if __name__ == "__main__":
    unittest.main()
