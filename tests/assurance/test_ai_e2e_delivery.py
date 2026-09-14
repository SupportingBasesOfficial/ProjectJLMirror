from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "tools" / "assurance" / "validate_ai_e2e_delivery.py"

spec = importlib.util.spec_from_file_location("validate_ai_e2e_delivery", VALIDATOR)
assert spec and spec.loader
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class AiE2EDeliveryTests(unittest.TestCase):
    def _clone_delivery_root(self) -> Path:
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        root = Path(td.name)
        for rel in (Path("docs/00-foundation/ai-e2e-delivery"), Path("implementation/e2e-delivery")):
            shutil.copytree(ROOT / rel, root / rel)
        return root

    def test_canonical_delivery_package_passes(self) -> None:
        docs, gates, layers = validator.validate()
        self.assertEqual(docs, 4)
        self.assertEqual(gates, 15)
        self.assertEqual(layers, 16)

    def test_first_full_stack_target_is_identity_tenant_shell(self) -> None:
        manifest = json.loads(validator.MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["first_full_stack_target"], "G1")

    def test_manifest_gate_names_are_canonical(self) -> None:
        manifest = json.loads(validator.MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(
            [gate["name"] for gate in manifest["gates"]],
            list(validator.EXPECTED_GATE_NAMES),
        )

    def test_authority_gated_stages_require_exact_separate_authority(self) -> None:
        manifest = json.loads(validator.MANIFEST.read_text(encoding="utf-8"))
        gates = {g["id"]: g for g in manifest["gates"]}
        self.assertEqual(gates["G7"]["authority_prerequisite"], "separate_alert_policy_evaluation_authorization")
        self.assertEqual(gates["G8"]["authority_prerequisite"], "responsibility_ack_visibility_authorization")

    def test_every_gate_requires_e2e_proof(self) -> None:
        manifest = json.loads(validator.MANIFEST.read_text(encoding="utf-8"))
        self.assertTrue(all(g["requires_e2e"] is True for g in manifest["gates"]))

    def test_visible_markdown_excludes_fences_comments_and_raw_html(self) -> None:
        sample = "\n".join((
            "### G0 — visible",
            "<!--",
            "### G1 — hidden-comment",
            "-->",
            "```text",
            "### G2 — hidden-fence",
            "```",
            "<script>",
            "### G3 — hidden-script",
            "</script>",
            "<pre>",
            "### G4 — hidden-pre",
            "</pre>",
            "### G5 — visible",
        ))
        self.assertEqual(
            validator._visible_markdown_lines(sample),
            ["### G0 — visible", "### G5 — visible"],
        )

    def test_visible_markdown_text_excludes_hidden_normative_prose(self) -> None:
        token = "READY_FOR_MERGE is not merge authorization"
        sample = "\n".join((
            "Visible rule remains authoritative.",
            "<!--",
            token,
            "-->",
            "```text",
            token,
            "```",
            "<script>",
            token,
            "</script>",
        ))
        visible = validator._visible_markdown_text(sample)
        self.assertIn("Visible rule remains authoritative.", visible)
        self.assertNotIn(token, visible)

    def test_hidden_roadmap_optimization_prose_does_not_satisfy_governance(self) -> None:
        root = self._clone_delivery_root()
        path = root / "docs/00-foundation/ai-e2e-delivery/PRODUCT-EXECUTION-ROADMAP.md"
        text = path.read_text(encoding="utf-8")
        token = validator.EXPECTED_OPTIMIZATION_SENTENCE
        self.assertIn(token, text)
        text = text.replace(token, f"<!--\n{token}\n-->\nOptimize for raw commit throughput.", 1)
        path.write_text(text, encoding="utf-8")
        with self.assertRaisesRegex(AssertionError, "roadmap_optimization_target_missing"):
            validator.validate(root)

    def test_hidden_constitution_merge_authority_does_not_satisfy_governance(self) -> None:
        root = self._clone_delivery_root()
        path = root / "docs/00-foundation/ai-e2e-delivery/AI-E2E-DELIVERY-CONSTITUTION.md"
        text = path.read_text(encoding="utf-8")
        token = "READY_FOR_MERGE is not merge authorization"
        self.assertIn(token, text)
        text = text.replace(token, f"```text\n{token}\n```\nREADY_FOR_MERGE authorizes merge automatically", 1)
        path.write_text(text, encoding="utf-8")
        with self.assertRaisesRegex(AssertionError, "constitution_missing:READY_FOR_MERGE is not merge authorization"):
            validator.validate(root)

    def test_manifest_schema_version_rejects_boolean(self) -> None:
        root = self._clone_delivery_root()
        path = root / "implementation/e2e-delivery/EXECUTION_MANIFEST.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["schema_version"] = True
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(AssertionError, "manifest_schema"):
            validator.validate(root)

    def test_heading_sequence_rejects_duplicate_reordered_and_shadow_ids(self) -> None:
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
        with self.assertRaisesRegex(AssertionError, "order_or_duplicate"):
            validator._validate_heading_sequence(
                "### S0 — zero\n### S1 — shadow replacement\n### S1 — one",
                expected,
                "S",
                "missing",
                "order_or_duplicate",
            )


if __name__ == "__main__":
    unittest.main()
