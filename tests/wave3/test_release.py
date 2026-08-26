import concurrent.futures
import unittest

from jlmirror_observability import HealthAssessment, HealthState
from jlmirror_release import (
    ArtifactIdentity, BuildProvenanceEvidence, CellCompatibilityEvidence,
    ConfigurationValidationEvidence, DeploymentAdmissionEvidence, DeploymentAuthority,
    DeploymentIntent, DeploymentObservation, HealthGateEvidence, MixedVersionMatrix,
    NoApplicableCaseEvidence, PromotionEvidence, PromotionState, ReleaseError,
    ReleaseTargetState, RolloutCompatibilityEvidence, RuntimeVerificationEvidence,
    SourceTrustClass, TargetConfiguration, ValidationScope, require_trusted_build_source,
    require_validation_for_target, verify_runtime,
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


def provenance(digest=DIGEST_A):
    return BuildProvenanceEvidence(
        source_state_id="accepted-source-sha", source_trust_class=SourceTrustClass.ACCEPTED_REVIEW_STATE,
        accepted_change_authority_proven=True, release_policy_profile_and_version="release-policy@1",
        release_policy_current=True, builder_principal_class="principal.release-build@1",
        builder_authorized_current=True, declared_input_set_id="inputs-1",
        declared_inputs_integrity_proven=True, build_record_id="build-1",
        artifact=ArtifactIdentity("sha256", digest), provenance_profile="release.provenance@1",
        provenance_record_id="prov-1", provenance_verifier_profile_and_version="verifier@1",
        provenance_verifier_current=True, sbom_or_dependency_inventory_reference="sbom-1",
        artifact_attestation_profile="attestation@1",
    )


def nac(scope="validation-cell-a"):
    return NoApplicableCaseEvidence(
        reason="release does not alter cell/runtime/schema compatibility",
        authority_profile="release.compatibility-policy@1", evidence_reference="evidence:nac-1",
        scope_binding=scope, current=True,
    )


def rollout(scope="validation-cell-a"):
    return RolloutCompatibilityEvidence(
        release_scope_id=scope,
        mixed_version=MixedVersionMatrix(True, True, True, True, True, True, True),
        validation_scope=ValidationScope.GENERAL, cell_affecting_release=False,
        reference_cell_evidence_current=False, reference_cell_no_applicable_case=nac(scope),
        cell_compatibility=CellCompatibilityEvidence(applicable=False, no_applicable_case=nac(scope)),
    )


def admission(i=None, **changes):
    i = i or intent()
    p = provenance(i.artifact.digest)
    values = dict(
        provenance=p,
        promotion=PromotionEvidence(
            promotion_id=i.promotion_id, promotion_principal_class="principal.release-promote@1",
            approval_current=True, release_policy_profile_and_version=i.release_policy_profile_and_version,
            release_policy_current=True, artifact_identity=i.artifact.canonical,
            target_configuration_identity=i.configuration.identity,
            target_configuration_generation=i.configuration.generation,
            target_configuration_semantic_profile=i.configuration.semantic_profile,
            target_environment_class=i.target_environment_class, validation_evidence_current=True,
            compatibility_evidence_current=True,
        ),
        configuration_validation=ConfigurationValidationEvidence(i.configuration, i.configuration, False, False),
        rollout_compatibility=rollout(i.rollout_scope),
        deployment_principal_class="principal.release-deploy@1",
        deployment_principal_authorized_current=True, release_policy_current=True,
        release_target_authority_current=True, required_reliability_gates_current=True,
        required_security_recovery_gates_current=True,
    )
    values.update(changes)
    return DeploymentAdmissionEvidence(**values)


def runtime_evidence(digest=DIGEST_A, config_generation="cfg-7", admission_current=True,
                     state=HealthState.HEALTHY, health_admitted=True):
    assessment = HealthAssessment("health.cell@1", state, "current", True)
    return RuntimeVerificationEvidence(
        observed_artifact_identity=f"sha256:{digest}", observed_configuration_generation=config_generation,
        runtime_profile_set=("runtime.api@1",), runtime_admission_current=admission_current,
        configuration_current=True, release_policy_current=True, verifier_authority_current=True,
        required_health_profile_ids=("health.cell@1",),
        health_gates=(HealthGateEvidence(assessment, "health-admission-policy@1", True, health_admitted),),
        vendor_controller_green=True,
    )


class ReleaseTests(unittest.TestCase):
    def test_untrusted_source_cannot_enter_trusted_build(self):
        with self.assertRaises(ReleaseError):
            require_trusted_build_source(SourceTrustClass.UNTRUSTED_CANDIDATE, exact_source_state_proven=True, accepted_change_authority_proven=True)

    def test_deployment_cannot_start_from_intent_or_promotion_id_alone(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        with self.assertRaises(TypeError):
            authority.create_or_observe(intent())

    def test_stale_deploy_principal_blocks_new_operation(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        i = intent()
        with self.assertRaises(ReleaseError):
            authority.create_or_observe(i, admission(i, deployment_principal_authorized_current=False))

    def test_promotion_must_bind_exact_deployment_semantics(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        i = intent()
        good = admission(i)
        bad_promotion = PromotionEvidence(**{**good.promotion.__dict__, "target_configuration_generation": "other"})
        with self.assertRaises(ReleaseError):
            authority.create_or_observe(i, admission(i, promotion=bad_promotion))

    def test_create_or_observe_same_semantics(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        i = intent()
        self.assertEqual(authority.create_or_observe(i, admission(i)), authority.create_or_observe(i, admission(i)))

    def test_same_operation_conflicting_semantics_is_integrity_conflict(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        first = intent()
        authority.create_or_observe(first, admission(first))
        second = intent(digest=DIGEST_B)
        with self.assertRaises(ReleaseError):
            authority.create_or_observe(second, admission(second))

    def test_concurrent_incompatible_deployments_admit_one_winner(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        intents = [intent(op=f"op-{n}") for n in range(64)]
        def attempt(i):
            try:
                authority.create_or_observe(i, admission(i)); return True
            except ReleaseError:
                return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
            results = list(pool.map(attempt, intents))
        self.assertEqual(sum(results), 1)
        self.assertIsNotNone(authority.target.unresolved_operation_id)

    def test_external_target_snapshot_cannot_clear_fence(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        i = intent(); authority.create_or_observe(i, admission(i))
        snapshot = authority.target
        with self.assertRaises(Exception):
            snapshot.unresolved_operation_id = None
        self.assertEqual(authority.target.unresolved_operation_id, "op-1")

    def test_stale_expected_target_version_rejected(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 5))
        i = intent(expected=4)
        with self.assertRaises(ReleaseError):
            authority.create_or_observe(i, admission(i))

    def test_lost_observation_becomes_reconciliation_required(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        i = intent(); authority.create_or_observe(i, admission(i))
        result = authority.observe_effect("op-1", DeploymentObservation.NOT_OBSERVED)
        self.assertEqual(result.state, PromotionState.RECONCILIATION_REQUIRED)
        self.assertEqual(authority.target.release_target_state_version, 4)

    def test_reconciliation_resolution_requires_current_authority_and_durable_evidence(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        i = intent(); authority.create_or_observe(i, admission(i)); authority.observe_effect("op-1", DeploymentObservation.AMBIGUOUS)
        with self.assertRaises(ReleaseError):
            authority.observe_effect("op-1", DeploymentObservation.EFFECT_ABSENT_PROVEN, durable_target_evidence_reference="target-evidence-1", reconciliation_authority_current=False)

    def test_effect_confirmation_requires_durable_target_evidence(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        i = intent(); authority.create_or_observe(i, admission(i))
        with self.assertRaises(ReleaseError):
            authority.observe_effect("op-1", DeploymentObservation.EFFECT_CONFIRMED, observed_artifact_identity=f"sha256:{DIGEST_A}", observed_configuration_generation="cfg-7")

    def test_effect_confirmation_enters_runtime_verification(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        i = intent(); authority.create_or_observe(i, admission(i))
        result = authority.observe_effect("op-1", DeploymentObservation.EFFECT_CONFIRMED, observed_artifact_identity=f"sha256:{DIGEST_A}", observed_configuration_generation="cfg-7", durable_target_evidence_reference="target-evidence-1")
        self.assertEqual(result.state, PromotionState.RUNTIME_VERIFICATION)
        self.assertEqual(authority.target.release_target_state_version, 5)
        self.assertIsNone(authority.target.current_artifact_identity)

    def test_runtime_verification_completion_makes_pending_artifact_current(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        i = intent(); authority.create_or_observe(i, admission(i))
        authority.observe_effect("op-1", DeploymentObservation.EFFECT_CONFIRMED, observed_artifact_identity=f"sha256:{DIGEST_A}", observed_configuration_generation="cfg-7", durable_target_evidence_reference="target-evidence-1")
        result = authority.complete_runtime_verification("op-1", runtime_evidence())
        self.assertEqual(result.state, PromotionState.COMPLETED)
        self.assertEqual(authority.target.current_artifact_identity, f"sha256:{DIGEST_A}")

    def test_vendor_green_is_not_runtime_verification(self):
        good = runtime_evidence()
        evidence = RuntimeVerificationEvidence(None, good.observed_configuration_generation, good.runtime_profile_set, True, True, True, True, good.required_health_profile_ids, good.health_gates, True)
        with self.assertRaises(ReleaseError):
            verify_runtime(intent(), evidence)

    def test_quarantined_health_cannot_be_released_even_if_complete(self):
        with self.assertRaises(ReleaseError):
            verify_runtime(intent(), runtime_evidence(state=HealthState.QUARANTINED, health_admitted=True))

    def test_degraded_health_requires_current_owning_policy_admission(self):
        with self.assertRaises(ReleaseError):
            verify_runtime(intent(), runtime_evidence(state=HealthState.DEGRADED, health_admitted=False))

    def test_same_artifact_does_not_prove_different_config_safe(self):
        validation = TargetConfiguration("validation-config", "v1", "config.release@1")
        target = TargetConfiguration("production-config", "p1", "config.release@1")
        with self.assertRaises(ReleaseError):
            require_validation_for_target(ConfigurationValidationEvidence(validation, target, False, False))

    def test_config_equivalence_boolean_without_current_evidence_fails(self):
        validation = TargetConfiguration("validation-config", "v1", "config.release@1")
        target = TargetConfiguration("production-config", "p1", "config.release@1")
        with self.assertRaises(ReleaseError):
            require_validation_for_target(ConfigurationValidationEvidence(validation, target, True, False, evidence_reference=None, evidence_current=False))


if __name__ == "__main__":
    unittest.main()
