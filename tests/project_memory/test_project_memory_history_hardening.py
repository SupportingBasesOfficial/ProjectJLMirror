from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "tools" / "project_memory" / "validate_project_memory.py"

spec = importlib.util.spec_from_file_location("project_memory_validator_history", VALIDATOR)
assert spec and spec.loader
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def baseline_rows(extra: int = 0) -> list[str]:
    rows = [
        f"| {decision_id} | {meaning} | current | accepted |"
        for decision_id, meaning in validator.BASELINE_DECISION_MEANINGS.items()
    ]
    for i in range(18, 18 + extra):
        rows.append(f"| JLM-DEC-{i:03d} | appended decision {i} | current | accepted-source-{i} |")
    return rows


class ProjectMemoryHistoryHardeningTests(unittest.TestCase):
    def test_second_checkout_after_verification_is_rejected(self) -> None:
        workflow = validator.WORKFLOW.read_text(encoding="utf-8")
        mutated = workflow.replace(
            "      - name: Validate canonical project memory\n",
            "      - name: Checkout accepted main after verification\n"
            "        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1\n"
            "        with:\n"
            "          ref: main\n"
            "          persist-credentials: false\n"
            "          fetch-depth: 0\n"
            "          allow-unsafe-pr-checkout: false\n\n"
            "      - name: Validate canonical project memory\n",
            1,
        )
        with self.assertRaisesRegex(AssertionError, "project_memory_workflow_step_order_invalid"):
            validator.validate_project_memory_workflow(mutated)

    def test_prior_history_bindings_are_exact(self) -> None:
        workflow = validator.WORKFLOW.read_text(encoding="utf-8")
        mutated = workflow.replace(
            "PR_BASE_SHA: ${{ github.event.pull_request.base.sha }}",
            "PR_BASE_SHA: ${{ github.event.pull_request.head.sha }}",
            1,
        )
        with self.assertRaisesRegex(AssertionError, "project_memory_workflow_job_env_binding_invalid"):
            validator.validate_project_memory_workflow(mutated)

    def test_truncated_appended_decision_is_rejected(self) -> None:
        rows = baseline_rows()
        rows.append("| JLM-DEC-018 |")
        with self.assertRaisesRegex(AssertionError, "project_memory_decision_row_invalid:JLM-DEC-018"):
            validator.validate_decision_register("\n".join(rows))

    def test_appended_decision_requires_nonempty_authority_fields(self) -> None:
        rows = baseline_rows()
        rows.append("| JLM-DEC-018 | replacement decision | current | |")
        with self.assertRaisesRegex(AssertionError, "project_memory_decision_row_invalid:JLM-DEC-018"):
            validator.validate_decision_register("\n".join(rows))

    def test_prior_appended_decision_cannot_be_deleted(self) -> None:
        prior = "\n".join(baseline_rows(extra=1))
        current = "\n".join(baseline_rows())
        with self.assertRaisesRegex(AssertionError, "project_memory_prior_decision_missing:JLM-DEC-018"):
            validator.validate_decision_history(current, prior)

    def test_prior_appended_decision_meaning_cannot_be_rewritten(self) -> None:
        prior_rows = baseline_rows(extra=1)
        current_rows = baseline_rows(extra=1)
        current_rows[-1] = "| JLM-DEC-018 | rewritten opposite proposition | current | accepted-source-18 |"
        with self.assertRaisesRegex(AssertionError, "project_memory_prior_decision_meaning_changed:JLM-DEC-018"):
            validator.validate_decision_history("\n".join(current_rows), "\n".join(prior_rows))

    def test_prior_decision_may_gain_forward_supersession_metadata_without_rewrite(self) -> None:
        prior_rows = baseline_rows(extra=1)
        current_rows = baseline_rows(extra=2)
        current_rows[-2] = "| JLM-DEC-018 | appended decision 18 | superseded by JLM-DEC-019 | accepted-source-18 |"
        validator.validate_decision_history("\n".join(current_rows), "\n".join(prior_rows))
        self.assertEqual(validator.validate_decision_register("\n".join(current_rows), "\n".join(prior_rows)), 19)


if __name__ == "__main__":
    unittest.main()
