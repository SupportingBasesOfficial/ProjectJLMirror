import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authority.validate_wave1 import EXPECTED_FORBIDDEN_SUBSTITUTIONS


MANIFEST = ROOT / "implementation" / "wave-1" / "IMPLEMENTATION_MANIFEST.json"


class Wave1ImplementationManifestTests(unittest.TestCase):
    def load_manifest(self):
        return json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_authority_base_is_exact_accepted_wave0_main(self):
        manifest = self.load_manifest()
        self.assertEqual(
            manifest["authority_base"],
            "main@5b56ad94566b48b72a993ee8f5cf7e983127ab21",
        )

    def test_exact_wave1_slice_set(self):
        manifest = self.load_manifest()
        self.assertEqual(
            set(manifest["implementation_slices"]),
            {"impl.identity-bff@1", "impl.control-plane@1", "impl.platform-runtime@1"},
        )
        self.assertEqual(manifest["scope"], "authority_skeleton_only")
        self.assertEqual(manifest["product_feature_activation"], "none")
        self.assertFalse(manifest["next_wave_authorized"])

    def test_residual_c2_choices_are_explicitly_non_selected(self):
        manifest = self.load_manifest()
        expected = {
            "identity_provider",
            "session_store",
            "csrf_mechanism",
            "workload_identity_issuer_attestation_backend",
            "service_mesh",
            "secret_manager_kms",
            "configuration_distribution",
            "orchestrator_scheduler",
            "ingress_load_balancer",
            "physical_environment_mapping",
        }
        self.assertEqual(set(manifest["residual_c2_choices_not_selected"]), expected)

    def test_ir_d_profiles_are_the_only_closed_protocol_profiles(self):
        manifest = self.load_manifest()
        self.assertEqual(manifest["closed_protocol_profiles"], ["IR-D-001", "IR-D-002", "IR-D-003"])

    def test_forbidden_authority_substitutions_match_validator_contract_exactly(self):
        manifest = self.load_manifest()
        self.assertEqual(
            manifest["forbidden_authority_substitutions"],
            EXPECTED_FORBIDDEN_SUBSTITUTIONS,
        )


if __name__ == "__main__":
    unittest.main()
