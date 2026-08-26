import unittest

from jlmirror_release import (
    ArtifactIdentity,
    ConfigurationValidationEvidence,
    DeploymentAuthority,
    DeploymentIntent,
    DeploymentObservation,
    PromotionState,
    ReleaseError,
    ReleaseTargetState,
    RuntimeVerificationEvidence,
    SourceTrustClass,
    TargetConfiguration,
    require_trusted_build_source,
    require_validation_for_target,
    verify_runtime,
)


DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


def intent(op="op-1", expected=4, digest=DIGEST_A, config_generation="cfg-7"):
    return DeploymentIntent(
        deployment_operation_id=op,
        target_id="validation-cell-a",
        expected_release_target_state_version=expected,
        artifact=ArtifactIdentity("sha256", digest),
        configuration=TargetConfiguration("cfg", config_generation, "config.release@1"),
        target_environment_class="environment.validation@1",
        runtime_profile_set=("runtime.api@1",),
    )


class ReleaseTests(unittest.TestCase):
    def test_untrusted_source_cannot_enter_trusted_build(self):
        with self.assertRaises(ReleaseError):
            require_trusted_build_source(
                SourceTrustClass.UNTRUSTED_CANDIDATE,
                exact_source_state_proven=True,
                accepted_change_authority_proven=True,
            )

    def test_accepted_source_still_requires_exact_authority_evidence(self):
        with self.assertRaises(ReleaseError):
            require_trusted_build_source(
                SourceTrustClass.ACCEPTED_REVIEW_STATE,
                exact_source_state_proven=True,
                accepted_change_authority_proven=False,
            )

    def test_create_or_observe_same_semantics(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        first = authority.create_or_observe(intent())
        second = authority.create_or_observe(intent())
        self.assertEqual(first, second)

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
            authority.observe_effect(
                "op-1",
                DeploymentObservation.EFFECT_CONFIRMED,
                observed_artifact_identity=f"sha256:{DIGEST_B}",
                observed_configuration_generation="cfg-7",
            )

    def test_effect_confirmation_advances_release_target_only(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        authority.create_or_observe(intent())
        result = authority.observe_effect(
            "op-1",
            DeploymentObservation.EFFECT_CONFIRMED,
            observed_artifact_identity=f"sha256:{DIGEST_A}",
            observed_configuration_generation="cfg-7",
        )
        self.assertEqual(result.state, PromotionState.RUNTIME_VERIFICATION)
        self.assertEqual(authority.target.release_target_state_version, 5)

    def test_vendor_green_is_not_runtime_verification(self):
        with self.assertRaises(ReleaseError):
            verify_runtime(
                intent(),
                RuntimeVerificationEvidence(
                    observed_artifact_identity=None,
                    observed_configuration_generation="cfg-7",
                    runtime_profile_set=("runtime.api@1",),
                    runtime_admission_current=True,
                    health_evidence_present=True,
                    vendor_controller_green=True,
                ),
            )

    def test_runtime_admission_is_independent_gate(self):
        with self.assertRaises(ReleaseError):
            verify_runtime(
                intent(),
                RuntimeVerificationEvidence(
                    observed_artifact_identity=f"sha256:{DIGEST_A}",
                    observed_configuration_generation="cfg-7",
                    runtime_profile_set=("runtime.api@1",),
                    runtime_admission_current=False,
                    health_evidence_present=True,
                    vendor_controller_green=True,
                ),
            )

    def test_same_artifact_does_not_prove_different_config_safe(self):
        validation = TargetConfiguration("validation-config", "v1", "config.release@1")
        target = TargetConfiguration("production-config", "p1", "config.release@1")
        with self.assertRaises(ReleaseError):
            require_validation_for_target(
                ConfigurationValidationEvidence(
                    validation_configuration=validation,
                    target_configuration=target,
                    semantic_equivalence_proven=False,
                    target_specific_validation_proven=False,
                )
            )

    def test_secret_copy_cannot_prove_configuration_equivalence(self):
        validation = TargetConfiguration("validation-config", "v1", "config.release@1")
        target = TargetConfiguration("production-config", "p1", "config.release@1")
        with self.assertRaises(ReleaseError):
            require_validation_for_target(
                ConfigurationValidationEvidence(
                    validation_configuration=validation,
                    target_configuration=target,
                    semantic_equivalence_proven=True,
                    target_specific_validation_proven=False,
                    copied_secret_values_used_as_equivalence=True,
                )
            )


if __name__ == "__main__":
    unittest.main()
