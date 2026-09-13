from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "tools" / "assurance" / "validate_ai_e2e_delivery.py"

spec = importlib.util.spec_from_file_location("validate_ai_e2e_delivery", VALIDATOR)
assert spec and spec.loader
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class AiE2EDeliveryTests(unittest.TestCase):
    def test_canonical_delivery_package_passes(self) -> None:
        docs, gates, layers = validator.validate()
        self.assertEqual(docs, 4)
        self.assertEqual(gates, 15)
        self.assertEqual(layers, 16)

    def test_first_full_stack_target_is_identity_tenant_shell(self) -> None:
        import json
        manifest = json.loads(validator.MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["first_full_stack_target"], "G1")

    def test_authority_gated_stages_require_exact_separate_authority(self) -> None:
        import json
        manifest = json.loads(validator.MANIFEST.read_text(encoding="utf-8"))
        gates = {g["id"]: g for g in manifest["gates"]}
        self.assertEqual(gates["G7"]["authority_prerequisite"], "separate_alert_policy_evaluation_authorization")
        self.assertEqual(gates["G8"]["authority_prerequisite"], "responsibility_ack_visibility_authorization")

    def test_every_gate_requires_e2e_proof(self) -> None:
        import json
        manifest = json.loads(validator.MANIFEST.read_text(encoding="utf-8"))
        self.assertTrue(all(g["requires_e2e"] is True for g in manifest["gates"]))

    def test_visible_markdown_excludes_fences_and_html_comments(self) -> None:
        sample = "\n".join((
            "### G0 — visible",
            "<!--",
            "### G1 — hidden-comment",
            "-->",
            "```text",
            "### G2 — hidden-fence",
            "```",
            "### G3 — visible",
        ))
        self.assertEqual(
            validator._visible_markdown_lines(sample),
            ["### G0 — visible", "### G3 — visible"],
        )

    def test_heading_sequence_rejects_duplicate_and_reordered_sections(self) -> None:
        expected = ("S0 — zero", "S1 — one")
        with self.assertRaisesRegex(AssertionError, "order_or_duplicate"):
            validator._validate_heading_sequence(
                "### S1 — one\n### S0 — zero",
                expected,
                "S",
                "missing",
                "order_or_duplicate",
            )
        with self.assertRaisesRegex(AssertionError, "order_or_duplicate"):
            validator._validate_heading_sequence(
                "### S0 — zero\n### S1 — one\n### S1 — one",
                expected,
                "S",
                "missing",
                "order_or_duplicate",
            )


if __name__ == "__main__":
    unittest.main()
