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


def baseline_rows(extra: int = 0) -> list[str]:
    rows = [
        f"| {decision_id} | {meaning} | current | accepted |"
        for decision_id, meaning in validator.BASELINE_DECISION_MEANINGS.items()
    ]
    for i in range(18, 18 + extra):
        rows.append(f"| JLM-DEC-{i:03d} | appended decision {i} | current | accepted |")
    return rows


class ProjectMemoryTests(unittest.TestCase):
    def test_validator_passes(self) -> None:
        files, decisions = validator.validate()
        self.assertEqual(files, 12)
        self.assertGreaterEqual(decisions, len(validator.BASELINE_DECISION_IDS))

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

    def test_seeded_decision_ids_are_exactly_declared(self) -> None:
        self.assertEqual(
            validator.BASELINE_DECISION_IDS,
            tuple(f"JLM-DEC-{i:03d}" for i in range(1, 18)),
        )

    def test_seeded_decision_meanings_are_exactly_declared(self) -> None:
        self.assertEqual(len(validator.BASELINE_DECISION_MEANINGS), 17)
        self.assertEqual(
            validator.BASELINE_DECISION_MEANINGS["JLM-DEC-012"],
            "Alert v1 lifecycle is `active \\| resolved`; resolved is terminal",
        )
        self.assertEqual(
            validator.BASELINE_DECISION_MEANINGS["JLM-DEC-017"],
            "Repository truth outranks assistant/chat memory",
        )

    def test_decision_register_escapes_lifecycle_pipe(self) -> None:
        text = (validator.MEMORY / "DECISION-REGISTER.md").read_text(encoding="utf-8")
        self.assertIn("`active \\| resolved`", text)
        self.assertNotIn("`active | resolved`", text)

    def test_decision_references_do_not_count_as_definitions(self) -> None:
        rows = baseline_rows(extra=1)
        rows[16] = "| JLM-DEC-017 | Repository truth outranks assistant/chat memory | superseded by JLM-DEC-018 | accepted |"
        rows[17] = "| JLM-DEC-018 | replacement decision | current authority | accepted |"
        sample = "\n".join(rows)
        ids = validator.decision_definition_ids(sample)
        self.assertEqual(ids[-2:], ["JLM-DEC-017", "JLM-DEC-018"])
        self.assertEqual(validator.decision_supersession_targets(sample), ["JLM-DEC-018"])
        self.assertEqual(validator.validate_decision_register(sample), 18)

    def test_duplicate_decision_definitions_remain_detectable(self) -> None:
        rows = baseline_rows()
        rows.append("| JLM-DEC-017 | Repository truth outranks assistant/chat memory | current | accepted |")
        ids = validator.decision_definition_ids("\n".join(rows))
        self.assertNotEqual(len(ids), len(set(ids)))
        with self.assertRaisesRegex(AssertionError, "project_memory_duplicate_decision_definition_id"):
            validator.validate_decision_register("\n".join(rows))

    def test_missing_seeded_decision_is_rejected(self) -> None:
        rows = baseline_rows()
        rows.pop(16)
        with self.assertRaisesRegex(AssertionError, "project_memory_missing_baseline_decision:JLM-DEC-017"):
            validator.validate_decision_register("\n".join(rows))

    def test_hidden_seeded_decisions_do_not_count(self) -> None:
        hidden = "<!--\n" + "\n".join(baseline_rows()) + "\n-->"
        with self.assertRaisesRegex(AssertionError, "project_memory_missing_baseline_decision:JLM-DEC-001"):
            validator.validate_decision_register(hidden)

    def test_fenced_seeded_decisions_do_not_count(self) -> None:
        hidden = "```markdown\n" + "\n".join(baseline_rows()) + "\n```"
        with self.assertRaisesRegex(AssertionError, "project_memory_missing_baseline_decision:JLM-DEC-001"):
            validator.validate_decision_register(hidden)

    def test_overindented_pseudo_closing_fence_does_not_expose_rows(self) -> None:
        hidden = "```markdown\n    ```\n" + "\n".join(baseline_rows()) + "\n```"
        with self.assertRaisesRegex(AssertionError, "project_memory_missing_baseline_decision:JLM-DEC-001"):
            validator.validate_decision_register(hidden)

    def test_script_raw_html_block_does_not_expose_rows(self) -> None:
        hidden = '<script type="text/plain">\n' + "\n".join(baseline_rows()) + "\n</script>"
        with self.assertRaisesRegex(AssertionError, "project_memory_missing_baseline_decision:JLM-DEC-001"):
            validator.validate_decision_register(hidden)

    def test_block_html_region_does_not_expose_rows(self) -> None:
        hidden = "<div>\n" + "\n".join(baseline_rows()) + "\n</div>\n"
        with self.assertRaisesRegex(AssertionError, "project_memory_missing_baseline_decision:JLM-DEC-001"):
            validator.validate_decision_register(hidden)

    def test_processing_instruction_does_not_expose_rows(self) -> None:
        hidden = "<?hidden\n" + "\n".join(baseline_rows()) + "\n?>"
        with self.assertRaisesRegex(AssertionError, "project_memory_missing_baseline_decision:JLM-DEC-001"):
            validator.validate_decision_register(hidden)

    def test_cdata_block_does_not_expose_rows(self) -> None:
        hidden = "<![CDATA[\n" + "\n".join(baseline_rows()) + "\n]]>"
        with self.assertRaisesRegex(AssertionError, "project_memory_missing_baseline_decision:JLM-DEC-001"):
            validator.validate_decision_register(hidden)

    def test_declaration_block_does_not_expose_rows(self) -> None:
        hidden = "<!DECLARATION\n" + "\n".join(baseline_rows()) + "\n>"
        with self.assertRaisesRegex(AssertionError, "project_memory_missing_baseline_decision:JLM-DEC-001"):
            validator.validate_decision_register(hidden)

    def test_generic_complete_html_tag_region_does_not_expose_rows(self) -> None:
        hidden = "<custom hidden>\n" + "\n".join(baseline_rows()) + "\n\n"
        with self.assertRaisesRegex(AssertionError, "project_memory_missing_baseline_decision:JLM-DEC-001"):
            validator.validate_decision_register(hidden)

    def test_malformed_seeded_decision_id_is_rejected_as_missing(self) -> None:
        rows = baseline_rows()
        rows[16] = "| JLM-DEC-O17 | malformed | current | accepted |"
        with self.assertRaisesRegex(AssertionError, "project_memory_missing_baseline_decision:JLM-DEC-017"):
            validator.validate_decision_register("\n".join(rows))

    def test_seeded_decision_meaning_rewrite_is_rejected(self) -> None:
        rows = baseline_rows()
        rows[16] = "| JLM-DEC-017 | Chat memory outranks repository truth | current | accepted |"
        with self.assertRaisesRegex(AssertionError, "project_memory_baseline_decision_meaning_changed:JLM-DEC-017"):
            validator.validate_decision_register("\n".join(rows))

    def test_unescaped_lifecycle_pipe_is_rejected(self) -> None:
        rows = baseline_rows()
        rows[11] = rows[11].replace("\\|", "|", 1)
        with self.assertRaisesRegex(AssertionError, "project_memory_baseline_decision_meaning_changed:JLM-DEC-012"):
            validator.validate_decision_register("\n".join(rows))

    def test_seeded_decision_may_be_explicitly_superseded_without_rewrite(self) -> None:
        rows = baseline_rows(extra=1)
        rows[16] = "| JLM-DEC-017 | Repository truth outranks assistant/chat memory | superseded by JLM-DEC-018 | accepted |"
        self.assertEqual(validator.validate_decision_register("\n".join(rows)), 18)

    def test_new_decisions_may_be_appended(self) -> None:
        rows = baseline_rows(extra=2)
        self.assertEqual(validator.validate_decision_register("\n".join(rows)), 19)

    def test_dangling_supersession_target_is_rejected(self) -> None:
        rows = baseline_rows()
        rows[0] = "| JLM-DEC-001 | JLMirror is provider-neutral, not a Zabbix UI | superseded by JLM-DEC-999 | accepted |"
        with self.assertRaisesRegex(AssertionError, "project_memory_missing_supersession_target:JLM-DEC-999"):
            validator.validate_decision_register("\n".join(rows))

    def test_malformed_supersession_target_is_rejected(self) -> None:
        rows = baseline_rows()
        for malformed in ("JLM-DEC-99", "JLM-DEC-O02"):
            mutated = list(rows)
            mutated[0] = f"| JLM-DEC-001 | JLMirror is provider-neutral, not a Zabbix UI | superseded by {malformed} | accepted |"
            with self.assertRaisesRegex(AssertionError, "project_memory_malformed_supersession:JLM-DEC-001"):
                validator.validate_decision_register("\n".join(mutated))

    def test_self_supersession_is_rejected(self) -> None:
        rows = baseline_rows()
        rows[0] = "| JLM-DEC-001 | JLMirror is provider-neutral, not a Zabbix UI | superseded by JLM-DEC-001 | accepted |"
        with self.assertRaisesRegex(AssertionError, "project_memory_supersession_self_reference:JLM-DEC-001"):
            validator.validate_decision_register("\n".join(rows))

    def test_supersession_cycle_is_rejected(self) -> None:
        rows = baseline_rows()
        rows[0] = "| JLM-DEC-001 | JLMirror is provider-neutral, not a Zabbix UI | superseded by JLM-DEC-002 | accepted |"
        rows[1] = "| JLM-DEC-002 | Tenant isolation is foundational | superseded by JLM-DEC-001 | accepted |"
        with self.assertRaisesRegex(AssertionError, "project_memory_supersession_cycle"):
            validator.validate_decision_register("\n".join(rows))

    def test_commented_out_workflow_command_is_not_accepted(self) -> None:
        workflow = validator.WORKFLOW.read_text(encoding="utf-8")
        mutated = workflow.replace(
            "run: python3 tools/assurance/validate_repository.py",
            "# run: python3 tools/assurance/validate_repository.py",
            1,
        )
        with self.assertRaisesRegex(AssertionError, "project_memory_workflow_missing_executable_step"):
            validator.validate_project_memory_workflow(mutated)

    def test_conditionally_disabled_workflow_step_is_not_accepted(self) -> None:
        workflow = validator.WORKFLOW.read_text(encoding="utf-8")
        mutated = workflow.replace(
            "      - name: Falsify canonical project-memory guardrails\n",
            "      - name: Falsify canonical project-memory guardrails\n        if: ${{ false }}\n",
            1,
        )
        with self.assertRaisesRegex(AssertionError, "project_memory_workflow_condition_not_allowed"):
            validator.validate_project_memory_workflow(mutated)

    def test_quoted_condition_key_is_not_accepted(self) -> None:
        workflow = validator.WORKFLOW.read_text(encoding="utf-8")
        mutated = workflow.replace(
            "      - name: Falsify canonical project-memory guardrails\n",
            "      - name: Falsify canonical project-memory guardrails\n        \"if\": ${{ false }}\n",
            1,
        )
        with self.assertRaisesRegex(AssertionError, "project_memory_workflow_condition_not_allowed"):
            validator.validate_project_memory_workflow(mutated)

    def test_explicit_mapping_condition_key_is_not_accepted(self) -> None:
        workflow = validator.WORKFLOW.read_text(encoding="utf-8")
        mutated = workflow.replace(
            "      - name: Falsify canonical project-memory guardrails\n",
            "      - name: Falsify canonical project-memory guardrails\n        ? if\n        : ${{ false }}\n",
            1,
        )
        with self.assertRaisesRegex(AssertionError, "project_memory_workflow_step_explicit_key_not_allowed"):
            validator.validate_project_memory_workflow(mutated)

    def test_job_level_condition_is_not_accepted(self) -> None:
        workflow = validator.WORKFLOW.read_text(encoding="utf-8")
        mutated = workflow.replace(
            "  project-memory:\n",
            "  project-memory:\n    if: ${{ false }}\n",
            1,
        )
        with self.assertRaisesRegex(AssertionError, "project_memory_workflow_job_condition_not_allowed"):
            validator.validate_project_memory_workflow(mutated)

    def test_required_run_decoy_under_env_is_not_accepted(self) -> None:
        workflow = validator.WORKFLOW.read_text(encoding="utf-8")
        required = "run: PYTHONPATH=tools/assurance:tools/project_memory python3 tools/assurance/test_validate_d4c_selection.py"
        mutated = workflow.replace(
            "      - name: Falsify canonical project-memory guardrails\n        " + required + "\n",
            "      - name: Falsify canonical project-memory guardrails\n        run: 'true'\n        env:\n          " + required + "\n",
            1,
        )
        with self.assertRaisesRegex(AssertionError, "project_memory_workflow_missing_executable_step:Falsify canonical project-memory guardrails"):
            validator.validate_project_memory_workflow(mutated)

    def test_checkout_ref_decoy_outside_with_is_not_accepted(self) -> None:
        workflow = validator.WORKFLOW.read_text(encoding="utf-8")
        mutated = workflow.replace(
            "          ref: ${{ steps.target.outputs.sha }}\n",
            "          ref: main\n",
            1,
        ).replace(
            "      - name: Validate canonical project memory\n",
            "      - name: Validate canonical project memory\n        env:\n          ref: ${{ steps.target.outputs.sha }}\n",
            1,
        )
        with self.assertRaisesRegex(AssertionError, "project_memory_workflow_checkout_binding_invalid"):
            validator.validate_project_memory_workflow(mutated)

    def test_verify_exact_head_command_is_bound_to_verify_step(self) -> None:
        workflow = validator.WORKFLOW.read_text(encoding="utf-8")
        mutated = workflow.replace(
            '          test "$(git rev-parse HEAD)" = "$EXPECTED_SHA"\n',
            "          true\n",
            1,
        ).replace(
            "      - name: Validate canonical project memory\n",
            '      - name: Validate canonical project memory\n        env:\n          DECOY: test "$(git rev-parse HEAD)" = "$EXPECTED_SHA"\n',
            1,
        )
        with self.assertRaisesRegex(AssertionError, "project_memory_workflow_verify_head_binding_invalid"):
            validator.validate_project_memory_workflow(mutated)


if __name__ == "__main__":
    unittest.main()
