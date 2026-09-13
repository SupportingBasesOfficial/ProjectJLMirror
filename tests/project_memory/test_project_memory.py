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

    def test_decision_references_do_not_count_as_definitions(self) -> None:
        sample = """
| JLM-DEC-017 | old decision | superseded by JLM-DEC-018 | accepted |
| JLM-DEC-018 | replacement decision | current authority | accepted |
| JLM-DEC-019 | extra | current | accepted |
| JLM-DEC-020 | extra | current | accepted |
| JLM-DEC-021 | extra | current | accepted |
| JLM-DEC-022 | extra | current | accepted |
| JLM-DEC-023 | extra | current | accepted |
| JLM-DEC-024 | extra | current | accepted |
| JLM-DEC-025 | extra | current | accepted |
| JLM-DEC-026 | extra | current | accepted |
"""
        self.assertEqual(
            validator.decision_definition_ids(sample)[:2],
            ["JLM-DEC-017", "JLM-DEC-018"],
        )
        self.assertEqual(validator.decision_supersession_targets(sample), ["JLM-DEC-018"])
        self.assertEqual(validator.validate_decision_register(sample), 10)

    def test_duplicate_decision_definitions_remain_detectable(self) -> None:
        sample = """
| JLM-DEC-018 | first definition | x | accepted |
| JLM-DEC-018 | duplicate definition | y | accepted |
"""
        ids = validator.decision_definition_ids(sample)
        self.assertNotEqual(len(ids), len(set(ids)))

    def test_dangling_supersession_target_is_rejected(self) -> None:
        rows = [f"| JLM-DEC-{i:03d} | decision | current | accepted |" for i in range(1, 11)]
        rows[0] = "| JLM-DEC-001 | decision | superseded by JLM-DEC-999 | accepted |"
        with self.assertRaisesRegex(AssertionError, "project_memory_missing_supersession_target:JLM-DEC-999"):
            validator.validate_decision_register("\n".join(rows))

    def test_commented_out_workflow_command_is_not_accepted(self) -> None:
        workflow = validator.WORKFLOW.read_text(encoding="utf-8")
        mutated = workflow.replace(
            "run: python3 tools/assurance/validate_repository.py",
            "# run: python3 tools/assurance/validate_repository.py",
            1,
        )
        with self.assertRaisesRegex(AssertionError, "project_memory_workflow_missing_active_line"):
            validator.validate_project_memory_workflow(mutated)


if __name__ == "__main__":
    unittest.main()
