import unittest

from jlmirror_observability import HealthAssessment, HealthState
from jlmirror_release import (
    ArtifactIdentity, ConfigurationValidationEvidence, DeploymentAuthority, DeploymentIntent,
    DeploymentObservation, PromotionState, ReleaseError, ReleaseTargetState,
    RuntimeVerificationEvidence, SourceTrustClass, TargetConfiguration, ValidationScope,
    require_trusted_build_source, require_validation_for_target, verify_runtime,
)

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


def intent(op="op-1", expected=4, digest=DIGEST_A, config_generation="cfg-7"):
    return DeploymentIntent(
        deployment_operation_id=op, target_id="validation-cell-a",
        expected_release_target_state_version=expected,
        artifact=ArtifactIdentity("sha256", digest),
        configuration=TargetConfiguration("cfg", config_generation, "config.release@1"),
        target_environment_class="environment.validation@1",
        runtime_profile_set=("runtime.api@1",), promotion_id="promotion-1",
        release_policy_profile_and_version="release-policy@1",
        validation_scope=ValidationScope.GENERAL, rollout_scope="validation-cell-a",
        schema_state="compatible", api_compatibility_family="api.v1",
        event_compatibility_set=("event.v1",),
    )


def runtime_evidence(digest=DIGEST_A, config_generation="cfg-7", admission=True):
    return RuntimeVerificationEvidence(
        observed_artifact_identity=f"sha256:{digest}",
        observed_configuration_generation=config_generation,
        runtime_profile_set=("runtime.api@1",), runtime_admission_current=admission,
        configuration_current=True, release_policy_current=True,
        verifier_authority_current=True, required_health_profile_ids=("health.cell@1",),
        health_assessments=(HealthAssessment("health.cell@1", HealthState.HEALTHY, "current", True),),
        vendor_controller_green=True,
    )


class ReleaseTests(unittest.TestCase):
    def test_untrusted_source_cannot_enter_trusted_build(self):
        with self.assertRaises(ReleaseError):
            require_trusted_build_source(SourceTrustClass.UNTRUSTED_CANDIDATE, exact_source_state_proven=True, accepted_change_authority_proven=True)

    def test_accepted_source_still_requires_exact_authority_evidence(self):
        with self.assertRaises(ReleaseError):
            require_trusted_build_source(SourceTrustClass.ACCEPTED_REVIEW_STATE, exact_source_state_proven=True, accepted_change_authority_proven=False)

    def test_create_or_observe_same_semantics(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        self.assertEqual(authority.create_or_observe(intent()), authority.create_or_observe(intent()))

    def test_same_operation_conflicting_semantics_is_integrity_conflict(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        authority.create_or_observe(intent())
        with self.assertRaises(ReleaseError):
            authority.create_or_observe(intent(digest=DIGEST_B))

    def test_stale_expected_target_version_rejected(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 5))
        with self.assertRaises(ReleaseError):
            authority.create_or_observe(intent(expected=4))

    def test_unresolved_prior_operation_blocks_new_effect(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        authority.create_or_observe(intent("op-1"))
        with self.assertRaises(ReleaseError):
            authority.create_or_observe(intent("op-2"))

    def test_lost_observation_becomes_reconciliation_required(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        authority.create_or_observe(intent())
        result = authority.observe_effect("op-1", DeploymentObservation.NOT_OBSERVED)
        self.assertEqual(result.state, PromotionState.RECONCILIATION_REQUIRED)
        self.assertEqual(authority.target.unresolved_operation_id, "op-1")

    def test_ambiguous_observation_does_not_advance_target(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        authority.create_or_observe(intent())
        authority.observe_effect("op-1", DeploymentObservation.AMBIGUOUS)
        self.assertEqual(authority.target.release_target_state_version, 4)

    def test_effect_confirmation_requires_exact_artifact_and_config(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        authority.create_or_observe(intent())
        with self.assertRaises(ReleaseError):
            authority.observe_effect("op-1", DeploymentObservation.EFFECT_CONFIRMED, observed_artifact_identity=f"sha256:{DIGEST_B}", observed_configuration_generation="cfg-7")

    def test_effect_confirmation_enters_runtime_verification_and_stays_unresolved(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        authority.create_or_observe(intent())
        result = authority.observe_effect("op-1", DeploymentObservation.EFFECT_CONFIRMED, observed_artifact_identity=f"sha256:{DIGEST_A}", observed_configuration_generation="cfg-7")
        self.assertEqual(result.state, PromotionState.RUNTIME_VERIFICATION)
        self.assertEqual(authority.target.release_target_state_version, 5)
        self.assertEqual(authority.target.unresolved_operation_id, "op-1")
        self.assertIsNone(authority.target.current_artifact_identity)

    def test_duplicate_effect_confirmation_does_not_advance_target_twice(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        authority.create_or_observe(intent())
        authority.observe_effect("op-1", DeploymentObservation.EFFECT_CONFIRMED, observed_artifact_identity=f"sha256:{DIGEST_A}", observed_configuration_generation="cfg-7")
        again = authority.observe_effect("op-1", DeploymentObservation.EFFECT_CONFIRMED, observed_artifact_identity=f"sha256:{DIGEST_A}", observed_configuration_generation="cfg-7")
        self.assertEqual(again.resulting_release_target_state_version_or_pending, 5)
        self.assertEqual(authority.target.release_target_state_version, 5)

    def test_new_operation_blocked_until_runtime_verification_completes(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        authority.create_or_observe(intent())
        authority.observe_effect("op-1", DeploymentObservation.EFFECT_CONFIRMED, observed_artifact_identity=f"sha256:{DIGEST_A}", observed_configuration_generation="cfg-7")
        with self.assertRaises(ReleaseError):
            authority.create_or_observe(intent("op-2", expected=5))

    def test_runtime_verification_completion_makes_pending_artifact_current(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        authority.create_or_observe(intent())
        authority.observe_effect("op-1", DeploymentObservation.EFFECT_CONFIRMED, observed_artifact_identity=f"sha256:{DIGEST_A}", observed_configuration_generation="cfg-7")
        result = authority.complete_runtime_verification("op-1", runtime_evidence())
        self.assertEqual(result.state, PromotionState.COMPLETED)
        self.assertIsNone(authority.target.unresolved_operation_id)
        self.assertEqual(authority.target.current_artifact_identity, f"sha256:{DIGEST_A}")

    def test_vendor_green_is_not_runtime_verification(self):
        good = runtime_evidence()
        evidence = RuntimeVerificationEvidence(None, good.observed_configuration_generation, good.runtime_profile_set, True, True, True, True, good.required_health_profile_ids, good.health_assessments, True)
        with self.assertRaises(ReleaseError):
            verify_runtime(intent(), evidence)

    def test_runtime_admission_is_independent_gate(self):
        with self.assertRaises(ReleaseError):
            verify_runtime(intent(), runtime_evidence(admission=False))

    def test_missing_required_health_profile_fails(self):
        evidence = RuntimeVerificationEvidence(f"sha256:{DIGEST_A}", "cfg-7", ("runtime.api@1",), True, True, True, True, ("health.cell@1","health.security-authority@1"), (HealthAssessment("health.cell@1", HealthState.HEALTHY, "current", True),))
        with self.assertRaises(ReleaseError):
            verify_runtime(intent(), evidence)

    def test_same_artifact_does_not_prove_different_config_safe(self):
        validation = TargetConfiguration("validation-config", "v1", "config.release@1")
        target = TargetConfiguration("production-config", "p1", "config.release@1")
        with self.assertRaises(ReleaseError):
            require_validation_for_target(ConfigurationValidationEvidence(validation, target, False, False))

    def test_secret_copy_cannot_prove_configuration_equivalence(self):
        validation = TargetConfiguration("validation-config", "v1", "config.release@1")
        target = TargetConfiguration("production-config", "p1", "config.release@1")
        with self.assertRaises(ReleaseError):
            require_validation_for_target(ConfigurationValidationEvidence(validation, target, True, False, True))


if __name__ == "__main__":
    unittest.main()
