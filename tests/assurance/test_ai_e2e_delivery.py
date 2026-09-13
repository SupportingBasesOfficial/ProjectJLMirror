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

    def test_alert_policy_requires_separate_authority(self) -> None:
        import json
        manifest = json.loads(validator.MANIFEST.read_text(encoding="utf-8"))
        g7 = next(g for g in manifest["gates"] if g["id"] == "G7")
        self.assertEqual(g7["authority_prerequisite"], "separate_alert_policy_evaluation_authorization")

    def test_every_gate_requires_e2e_proof(self) -> None:
        import json
        manifest = json.loads(validator.MANIFEST.read_text(encoding="utf-8"))
        self.assertTrue(all(g["requires_e2e"] is True for g in manifest["gates"]))


if __name__ == "__main__":
    unittest.main()
