import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authority.validate_wave1 import EXPECTED_FORBIDDEN_SUBSTITUTIONS


MANIFEST = ROOT / "implementation" / "wave-1" / "IMPLEMENTATION_MANIFEST.json"
REQUIRED_PANORAMIC_SUBSTITUTIONS = {
    "principal_id_generation_match_for_principal_kind_authority",
    "destination_runtime_generation_for_executing_runtime_authority",
    "runtime_profile_generation_match_for_executing_environment_authority",
    "final_admission_without_current_executing_runtime_authority",
    "final_admission_scope_class_for_other_declaration_scope",
    "final_admission_tenant_requirement_for_other_declaration",
    "non_api_runtime_for_tenant_resource_admission",
    "authentication_strength_revision_for_different_policy_id",
    "nondeterministic_collation_for_fence_scope_authority",
    "required_fence_shape_for_absence_of_extra_write_constraints",
    "resource_scope_absence_for_resource_authority",
    "resource_scope_on_non_resource_authority",
    "table_acl_clean_for_column_acl_clean",
    "object_acl_clean_for_predefined_all_data_role_absent",
    "expected_function_acl_clean_for_residual_definer_authority_absent",
    "platform_schema_boundary_for_callable_owner_definer_absence",
    "local_fence_rules_clean_for_external_rewrite_dependency_absent",
    "local_database_authority_surfaces_clean_for_logical_replication_writer_absent",
    "row_table_hooks_clean_for_database_event_trigger_absence",
    "event_trigger_catalog_preflight_for_closed_execution_window",
    "validated_constraint_shape_for_atomic_constraint_replacement",
    "transactional_ddl_without_held_table_lock_for_closed_revalidation_window",
    "table_shape_match_for_referential_action_free",
    "primary_key_present_for_immediate_valid_ready_conflict_arbiter",
    "cross_tenant_action_match_for_target_set_authority",
}


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
            "database_admin_role_and_operational_mapping",
        }
        self.assertEqual(set(manifest["residual_c2_choices_not_selected"]), expected)

    def test_database_admin_boundary_cannot_disappear_from_residual_c2_inventory(self):
        manifest = self.load_manifest()
        self.assertIn(
            "database_admin_role_and_operational_mapping",
            manifest["residual_c2_choices_not_selected"],
        )

    def test_ir_d_profiles_are_the_only_closed_protocol_profiles(self):
        manifest = self.load_manifest()
        self.assertEqual(manifest["closed_protocol_profiles"], ["IR-D-001", "IR-D-002", "IR-D-003"])

    def test_forbidden_authority_substitutions_match_validator_contract_exactly(self):
        manifest = self.load_manifest()
        self.assertEqual(
            manifest["forbidden_authority_substitutions"],
            EXPECTED_FORBIDDEN_SUBSTITUTIONS,
        )

    def test_latest_panorama_substitutions_are_independently_required(self):
        manifest = self.load_manifest()
        actual = set(manifest["forbidden_authority_substitutions"])
        self.assertTrue(
            REQUIRED_PANORAMIC_SUBSTITUTIONS <= actual,
            REQUIRED_PANORAMIC_SUBSTITUTIONS - actual,
        )


if __name__ == "__main__":
    unittest.main()
