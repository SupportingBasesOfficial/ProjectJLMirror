import concurrent.futures
import unittest

from jlmirror_observability import HealthAssessment, HealthState
from jlmirror_release import (
    AcceptedSourceEvidence, ArtifactIdentity, BuildProvenanceEvidence, CellCompatibilityEvidence,
    ConfigurationValidationEvidence, CurrentAuthorityEvidence, DeploymentAdmissionEvidence,
    DeploymentAuthority, DeploymentIntent, DeploymentObservation, HealthGateEvidence,
    MixedVersionMatrix, NoApplicableCaseEvidence, PromotionEvidence, PromotionState,
    ReleaseError, ReleaseTargetState, RolloutCompatibilityEvidence,
    RuntimeVerificationEvidence, RuntimeVerificationRequirements, SourceTrustClass,
    TargetConfiguration, ValidationScope, require_trusted_build_source,
    require_validation_for_target, validate_build_provenance, verify_runtime,
)

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
SOURCE_STATE_ID = "1" * 40
ADMISSION_GATE_IDS = (
    "deployment_principal", "release_policy", "release_target_authority",
    "reliability", "security_recovery",
)
RUNTIME_RELIABILITY_REQUIREMENTS = (
    "rel.cell-transactional-store@1",
    "rel.security-session-authority@1",
    "rel.performance-cache@1",
)
RUNTIME_HEALTH_REQUIREMENTS = (
    "health.api-bff@1",
    "health.cell@1",
    "health.security-authority@1",
)


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


def deployment_scope(i=None):
    i = i or intent()
    return f"deployment:{i.target_id}:{i.deployment_operation_id}"


def accepted_source(trust_class=SourceTrustClass.ACCEPTED_REVIEW_STATE, **changes):
    values = dict(
        source_state_id=SOURCE_STATE_ID,
        source_trust_class=trust_class,
        source_change_authority_profile_and_version="source.change-authority@1",
        source_change_evidence_reference="evidence:source-change-1",
        review_assurance_profile_and_version="review.assurance@1",
        review_assurance_evidence_reference="evidence:review-assurance-1",
        source_trust_policy_profile_and_version="release-policy@1",
        source_trust_policy_evidence_reference="evidence:source-trust-policy-1",
    )
    values.update(changes)
    return AcceptedSourceEvidence(**values)


def provenance(digest=DIGEST_A, **changes):
    values = dict(
        accepted_source=accepted_source(),
        release_policy_profile_and_version="release-policy@1",
        release_policy_evidence_reference="evidence:build-release-policy-1",
        release_policy_current=True,
        builder_principal_class="principal.release-build@1",
        builder_authority_evidence_reference="evidence:builder-authority-1",
        builder_authorized_current=True,
        declared_input_set_id="inputs-1",
        declared_inputs_integrity_evidence_reference="evidence:input-integrity-1",
        declared_inputs_integrity_proven=True,
        build_record_id="evidence:build-1",
        artifact=ArtifactIdentity("sha256", digest),
        provenance_profile="release.provenance@1",
        provenance_record_id="evidence:provenance-1",
        provenance_verifier_profile_and_version="verifier@1",
        provenance_verifier_evidence_reference="evidence:provenance-verifier-1",
        provenance_verifier_current=True,
        sbom_or_dependency_inventory_reference="evidence:sbom-1",
        artifact_attestation_profile="attestation@1",
        artifact_lifecycle_evidence_reference="evidence:artifact-lifecycle-1",
    )
    values.update(changes)
    return BuildProvenanceEvidence(**values)


def nac(scope="validation-cell-a"):
    return NoApplicableCaseEvidence(
        reason="release does not alter cell/runtime/schema compatibility",
        authority_profile="release.compatibility-policy@1", evidence_reference="evidence:nac-1",
        scope_binding=scope, current=True,
    )


def rollout(scope="validation-cell-a", evidence_reference="evidence:rollout-1"):
    return RolloutCompatibilityEvidence(
        evidence_reference=evidence_reference, evidence_current=True, release_scope_id=scope,
        mixed_version=MixedVersionMatrix(True, True, True, True, True, True, True),
        validation_scope=ValidationScope.GENERAL, cell_affecting_release=False,
        reference_cell_evidence_current=False, reference_cell_no_applicable_case=nac(scope),
        cell_compatibility=CellCompatibilityEvidence(applicable=False, no_applicable_case=nac(scope)),
    )


def config_validation(i, evidence_reference="evidence:config-1"):
    return ConfigurationValidationEvidence(
        validation_configuration=i.configuration,
        target_configuration=i.configuration,
        validation_scope=i.validation_scope,
        evidence_reference=evidence_reference,
        evidence_current=True,
    )


def promotion_for(i, *, config_ref="evidence:config-1", rollout_ref="evidence:rollout-1", **changes):
    values = dict(
        promotion_id=i.promotion_id,
        promotion_evidence_reference="evidence:promotion-1",
        promotion_principal_class="principal.release-promote@1",
        promotion_principal_authority_evidence_reference="evidence:promotion-principal-1",
        promotion_principal_authorized_current=True,
        approval_current=True,
        approval_evidence_reference="evidence:approval-1",
        release_policy_profile_and_version=i.release_policy_profile_and_version,
        release_policy_evidence_reference="evidence:promotion-release-policy-1",
        release_policy_current=True,
        artifact_identity=i.artifact.canonical,
        target_id=i.target_id,
        target_environment_class=i.target_environment_class,
        validation_scope=i.validation_scope,
        rollout_scope_id=i.rollout_scope,
        runtime_profile_set=i.runtime_profile_set,
        target_configuration_identity=i.configuration.identity,
        target_configuration_generation=i.configuration.generation,
        target_configuration_semantic_profile=i.configuration.semantic_profile,
        configuration_validation_evidence_reference=config_ref,
        rollout_compatibility_evidence_reference=rollout_ref,
        schema_state=i.schema_state,
        api_compatibility_family=i.api_compatibility_family,
        event_compatibility_set=i.event_compatibility_set,
        required_evidence_set_reference="evidence:set-1",
        validation_evidence_current=True,
        compatibility_evidence_current=True,
    )
    values.update(changes)
    return PromotionEvidence(**values)


def authority_gate(i, gate_id, *, current=True, scope=None, version=None, evidence_reference=None):
    return CurrentAuthorityEvidence(
        gate_id=gate_id,
        authority_profile_and_version=f"release.{gate_id.replace('_', '-')}@1",
        evidence_reference=evidence_reference or f"evidence:admission-{gate_id}",
        scope_binding=scope or CurrentAuthorityEvidence.scope_for(i),
        release_target_state_version=i.expected_release_target_state_version if version is None else version,
        current=current,
    )


def admission_gates(i, overrides=None):
    overrides = overrides or {}
    result = []
    for gate_id in ADMISSION_GATE_IDS:
        kwargs = overrides.get(gate_id, {})
        result.append(authority_gate(i, gate_id, **kwargs))
    return tuple(result)


def admission(i=None, *, gate_overrides=None, **changes):
    i = i or intent()
    p = provenance(i.artifact.digest)
    values = dict(
        provenance=p,
        promotion=promotion_for(i),
        configuration_validation=config_validation(i),
        rollout_compatibility=rollout(i.rollout_scope),
        deployment_principal_class="principal.release-deploy@1",
        current_authority_gates=admission_gates(i, gate_overrides),
    )
    values.update(changes)
    return DeploymentAdmissionEvidence(**values)


def reconciliation_gate(i, *, current=True, scope=None, version=None, reference="evidence:reconciliation-authority-1"):
    return CurrentAuthorityEvidence(
        gate_id="reconciliation_authority",
        authority_profile_and_version="release.reconciliation-authority@1",
        evidence_reference=reference,
        scope_binding=scope or CurrentAuthorityEvidence.scope_for(i),
        release_target_state_version=i.expected_release_target_state_version if version is None else version,
        current=current,
    )


def runtime_requirements(scope, target_version, **changes):
    values = dict(
        authority_profile_and_version="release.runtime-verification-requirements@1",
        evidence_reference="evidence:runtime-requirements-1",
        scope_binding=scope,
        release_target_state_version=target_version,
        release_policy_profile_and_version="release-policy@1",
        release_policy_evidence_reference="evidence:runtime-release-policy-1",
        required_reliability_profile_ids=RUNTIME_RELIABILITY_REQUIREMENTS,
        required_health_profile_ids=RUNTIME_HEALTH_REQUIREMENTS,
        current=True,
    )
    values.update(changes)
    return RuntimeVerificationRequirements(**values)


def runtime_evidence(digest=DIGEST_A, config_generation="cfg-7", admission_current=True,
                     state=HealthState.HEALTHY, health_admitted=True, **changes):
    scope = changes.pop("scope_binding", deployment_scope())
    target_version = changes.pop("release_target_state_version", 5)
    requirements = changes.pop("requirements", runtime_requirements(scope, target_version))
    gates = tuple(
        HealthGateEvidence(
            HealthAssessment(profile_id, state, "current", True),
            f"evidence:{profile_id.replace('.', '-').replace('@', '-')}-1",
            "health-admission-policy@1",
            "evidence:health-admission-policy-1",
            scope,
            target_version,
            True,
            health_admitted,
        )
        for profile_id in RUNTIME_HEALTH_REQUIREMENTS
    )
    values = dict(
        evidence_reference="evidence:runtime-verification-1",
        evidence_current=True,
        scope_binding=scope,
        release_target_state_version=target_version,
        observed_artifact_identity=f"sha256:{digest}",
        observed_configuration_generation=config_generation,
        runtime_profile_set=("runtime.api@1",),
        runtime_admission_evidence_reference="evidence:runtime-admission-1",
        runtime_admission_current=admission_current,
        configuration_currentness_evidence_reference="evidence:configuration-currentness-1",
        configuration_current=True,
        release_policy_evidence_reference="evidence:runtime-release-policy-1",
        release_policy_current=True,
        verifier_authority_profile_and_version="principal.release-verify@1",
        verifier_authority_evidence_reference="evidence:runtime-verifier-authority-1",
        verifier_authority_current=True,
        requirements=requirements,
        health_gates=gates,
        vendor_controller_green=True,
    )
    values.update(changes)
    return RuntimeVerificationEvidence(**values)


def verify_direct(evidence):
    verify_runtime(intent(), evidence, expected_release_target_state_version=5)


class ReleaseTests(unittest.TestCase):
    def test_untrusted_source_cannot_enter_trusted_build(self):
        with self.assertRaises(ReleaseError):
            require_trusted_build_source(accepted_source(SourceTrustClass.UNTRUSTED_CANDIDATE))

    def test_source_trust_policy_must_bind_current_build_policy(self):
        with self.assertRaises(ReleaseError):
            validate_build_provenance(provenance(accepted_source=accepted_source(source_trust_policy_profile_and_version="release-policy@0")))

    def test_deployment_cannot_start_from_intent_or_promotion_id_alone(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        with self.assertRaises(TypeError):
            authority.create_or_observe(intent())

    def test_stale_deploy_principal_evidence_blocks_new_operation(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        i = intent()
        with self.assertRaises(ReleaseError):
            authority.create_or_observe(i, admission(i, gate_overrides={"deployment_principal": {"current": False}}))

    def test_admission_gate_set_must_be_complete_and_unique(self):
        i = intent()
        good = list(admission_gates(i))
        with self.assertRaises(ReleaseError):
            DeploymentAuthority(ReleaseTargetState(i.target_id, 4)).create_or_observe(i, admission(i, current_authority_gates=tuple(good[:-1])))
        with self.assertRaises(ReleaseError):
            DeploymentAuthority(ReleaseTargetState(i.target_id, 4)).create_or_observe(i, admission(i, current_authority_gates=tuple(good + [good[0]])))

    def test_admission_gate_evidence_must_bind_exact_scope_version_and_immutable_ref(self):
        i = intent()
        cases = (
            {"release_policy": {"scope": "deployment:other:op-1"}},
            {"release_policy": {"version": 3}},
            {"release_policy": {"evidence_reference": "latest"}},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides), self.assertRaises(ReleaseError):
                DeploymentAuthority(ReleaseTargetState(i.target_id, 4)).create_or_observe(i, admission(i, gate_overrides=overrides))

    def test_promotion_must_bind_exact_deployment_semantics(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        i = intent(); good = admission(i)
        bad = PromotionEvidence(**{**good.promotion.__dict__, "target_configuration_generation": "other"})
        with self.assertRaises(ReleaseError):
            authority.create_or_observe(i, admission(i, promotion=bad))

    def test_promotion_runtime_profile_set_cannot_be_recombined(self):
        i = intent(); good = admission(i)
        bad = PromotionEvidence(**{**good.promotion.__dict__, "runtime_profile_set": ("runtime.worker@1",)})
        with self.assertRaises(ReleaseError):
            DeploymentAuthority(ReleaseTargetState(i.target_id, 4)).create_or_observe(i, admission(i, promotion=bad))

    def test_promotion_validation_scope_cannot_be_recombined(self):
        i = intent(); good = admission(i)
        bad = PromotionEvidence(**{**good.promotion.__dict__, "validation_scope": ValidationScope.REFERENCE_CELL})
        with self.assertRaises(ReleaseError):
            DeploymentAuthority(ReleaseTargetState(i.target_id, 4)).create_or_observe(i, admission(i, promotion=bad))

    def test_promotion_rollout_scope_cannot_be_recombined(self):
        i = intent(); good = admission(i)
        bad = PromotionEvidence(**{**good.promotion.__dict__, "rollout_scope_id": "other-scope"})
        with self.assertRaises(ReleaseError):
            DeploymentAuthority(ReleaseTargetState(i.target_id, 4)).create_or_observe(i, admission(i, promotion=bad))

    def test_promotion_schema_api_event_compatibility_cannot_be_recombined(self):
        i = intent(); good = admission(i)
        for mutation in ({"schema_state": "other"}, {"api_compatibility_family": "api.v2"}, {"event_compatibility_set": ("event.v2",)}):
            bad = PromotionEvidence(**{**good.promotion.__dict__, **mutation})
            with self.subTest(mutation=mutation), self.assertRaises(ReleaseError):
                DeploymentAuthority(ReleaseTargetState(i.target_id, 4)).create_or_observe(i, admission(i, promotion=bad))

    def test_promotion_must_bind_same_configuration_evidence_reference(self):
        i = intent(); good = admission(i)
        bad = PromotionEvidence(**{**good.promotion.__dict__, "configuration_validation_evidence_reference": "evidence:other"})
        with self.assertRaises(ReleaseError):
            authority = DeploymentAuthority(ReleaseTargetState(i.target_id, 4))
            authority.create_or_observe(i, admission(i, promotion=bad))

    def test_promotion_must_bind_same_rollout_evidence_reference(self):
        i = intent(); good = admission(i)
        bad = PromotionEvidence(**{**good.promotion.__dict__, "rollout_compatibility_evidence_reference": "evidence:other"})
        with self.assertRaises(ReleaseError):
            DeploymentAuthority(ReleaseTargetState(i.target_id, 4)).create_or_observe(i, admission(i, promotion=bad))

    def test_same_configuration_still_requires_current_validation_evidence(self):
        i = intent()
        with self.assertRaises(ReleaseError):
            require_validation_for_target(ConfigurationValidationEvidence(i.configuration, i.configuration, i.validation_scope, "", False))

    def test_mutable_or_url_like_evidence_alias_is_rejected(self):
        i = intent()
        for reference in ("latest", "https://evidence.example/current", "target-evidence-1"):
            with self.subTest(reference=reference), self.assertRaises(ReleaseError):
                require_validation_for_target(ConfigurationValidationEvidence(i.configuration, i.configuration, i.validation_scope, reference, True))

    def test_create_or_observe_same_semantics(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        i = intent()
        self.assertEqual(authority.create_or_observe(i, admission(i)), authority.create_or_observe(i, admission(i)))

    def test_same_operation_conflicting_semantics_is_integrity_conflict(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        first = intent(); authority.create_or_observe(first, admission(first))
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

    def test_reconciliation_resolution_requires_current_scoped_authority_and_durable_evidence(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        i = intent(); authority.create_or_observe(i, admission(i)); authority.observe_effect("op-1", DeploymentObservation.AMBIGUOUS)
        with self.assertRaises(ReleaseError):
            authority.observe_effect("op-1", DeploymentObservation.EFFECT_ABSENT_PROVEN, durable_target_evidence_reference="evidence:target-1")
        with self.assertRaises(ReleaseError):
            authority.observe_effect("op-1", DeploymentObservation.EFFECT_ABSENT_PROVEN, durable_target_evidence_reference="evidence:target-1", reconciliation_authority=reconciliation_gate(i, current=False))
        with self.assertRaises(ReleaseError):
            authority.observe_effect("op-1", DeploymentObservation.EFFECT_ABSENT_PROVEN, durable_target_evidence_reference="evidence:target-1", reconciliation_authority=reconciliation_gate(i, scope="deployment:other:op-1"))

    def test_reconciliation_resolution_retains_authority_lineage(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        i = intent(); authority.create_or_observe(i, admission(i)); authority.observe_effect("op-1", DeploymentObservation.AMBIGUOUS)
        result = authority.observe_effect("op-1", DeploymentObservation.EFFECT_ABSENT_PROVEN, durable_target_evidence_reference="evidence:target-absence-1", reconciliation_authority=reconciliation_gate(i))
        self.assertEqual(result.state, PromotionState.ABORTED)
        self.assertEqual(result.reconciliation_authority_evidence_reference, "evidence:reconciliation-authority-1")

    def test_effect_confirmation_requires_durable_target_evidence(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        i = intent(); authority.create_or_observe(i, admission(i))
        with self.assertRaises(ReleaseError):
            authority.observe_effect("op-1", DeploymentObservation.EFFECT_CONFIRMED, observed_artifact_identity=f"sha256:{DIGEST_A}", observed_configuration_generation="cfg-7")

    def test_effect_confirmation_enters_runtime_verification_and_retains_evidence(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        i = intent(); authority.create_or_observe(i, admission(i))
        result = authority.observe_effect("op-1", DeploymentObservation.EFFECT_CONFIRMED, observed_artifact_identity=f"sha256:{DIGEST_A}", observed_configuration_generation="cfg-7", durable_target_evidence_reference="evidence:target-1")
        self.assertEqual(result.state, PromotionState.RUNTIME_VERIFICATION)
        self.assertEqual(result.durable_target_evidence_reference, "evidence:target-1")
        self.assertEqual(result.observed_artifact_identity, f"sha256:{DIGEST_A}")
        self.assertEqual(authority.target.release_target_state_version, 5)
        self.assertIsNone(authority.target.current_artifact_identity)

    def test_absence_resolution_retains_target_evidence(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        i = intent(); authority.create_or_observe(i, admission(i))
        result = authority.observe_effect("op-1", DeploymentObservation.EFFECT_ABSENT_PROVEN, durable_target_evidence_reference="evidence:target-absence-1")
        self.assertEqual(result.state, PromotionState.ABORTED)
        self.assertEqual(result.durable_target_evidence_reference, "evidence:target-absence-1")

    def test_runtime_verification_completion_retains_lineage(self):
        authority = DeploymentAuthority(ReleaseTargetState("validation-cell-a", 4))
        i = intent(); created = authority.create_or_observe(i, admission(i))
        self.assertEqual(created.promotion_evidence_reference, "evidence:promotion-1")
        self.assertEqual(created.configuration_validation_evidence_reference, "evidence:config-1")
        self.assertEqual(created.rollout_compatibility_evidence_reference, "evidence:rollout-1")
        self.assertEqual(len(created.admission_gate_evidence_references), 5)
        authority.observe_effect("op-1", DeploymentObservation.EFFECT_CONFIRMED, observed_artifact_identity=f"sha256:{DIGEST_A}", observed_configuration_generation="cfg-7", durable_target_evidence_reference="evidence:target-1")
        result = authority.complete_runtime_verification("op-1", runtime_evidence())
        self.assertEqual(result.state, PromotionState.COMPLETED)
        self.assertEqual(result.runtime_verification_evidence_reference, "evidence:runtime-verification-1")
        self.assertEqual(authority.target.current_artifact_identity, f"sha256:{DIGEST_A}")

    def test_runtime_verification_cannot_be_replayed_across_deployment_scope(self):
        with self.assertRaises(ReleaseError):
            verify_direct(runtime_evidence(scope_binding="deployment:validation-cell-a:other-op"))

    def test_runtime_verification_cannot_be_replayed_across_target_state_version(self):
        with self.assertRaises(ReleaseError):
            verify_direct(runtime_evidence(release_target_state_version=4))

    def test_runtime_currentness_booleans_require_immutable_lineage(self):
        cases = (
            {"runtime_admission_evidence_reference": "latest"},
            {"configuration_currentness_evidence_reference": ""},
            {"release_policy_evidence_reference": "https://policy/current"},
            {"verifier_authority_evidence_reference": "verifier-current"},
        )
        for mutation in cases:
            with self.subTest(mutation=mutation), self.assertRaises(ReleaseError):
                verify_direct(runtime_evidence(**mutation))

    def test_runtime_requirements_cannot_be_empty_or_duplicate(self):
        good = runtime_evidence()
        for mutation in (
            {"required_reliability_profile_ids": ()},
            {"required_health_profile_ids": ()},
            {"required_reliability_profile_ids": ("rel.cell-transactional-store@1", "rel.cell-transactional-store@1")},
            {"required_health_profile_ids": ("health.cell@1", "health.cell@1")},
        ):
            bad = RuntimeVerificationRequirements(**{**good.requirements.__dict__, **mutation})
            with self.subTest(mutation=mutation), self.assertRaises(ReleaseError):
                verify_direct(runtime_evidence(requirements=bad))

    def test_runtime_requirements_cannot_omit_implied_health_join(self):
        good = runtime_evidence()
        bad = RuntimeVerificationRequirements(**{
            **good.requirements.__dict__,
            "required_health_profile_ids": ("health.api-bff@1", "health.cell@1"),
        })
        with self.assertRaises(ReleaseError):
            verify_direct(runtime_evidence(requirements=bad))

    def test_runtime_requirements_must_bind_current_release_policy_lineage(self):
        good = runtime_evidence()
        for mutation in (
            {"release_policy_profile_and_version": "release-policy@0"},
            {"release_policy_evidence_reference": "evidence:other-policy"},
            {"current": False},
            {"evidence_reference": "latest"},
        ):
            bad = RuntimeVerificationRequirements(**{**good.requirements.__dict__, **mutation})
            with self.subTest(mutation=mutation), self.assertRaises(ReleaseError):
                verify_direct(runtime_evidence(requirements=bad))

    def test_runtime_requirements_cannot_be_replayed_across_scope_or_target_version(self):
        good = runtime_evidence()
        for mutation in (
            {"scope_binding": "deployment:validation-cell-a:other-op"},
            {"release_target_state_version": 4},
        ):
            bad = RuntimeVerificationRequirements(**{**good.requirements.__dict__, **mutation})
            with self.subTest(mutation=mutation), self.assertRaises(ReleaseError):
                verify_direct(runtime_evidence(requirements=bad))

    def test_health_policy_boolean_requires_immutable_policy_lineage(self):
        good = runtime_evidence()
        gate = good.health_gates[0]
        with self.assertRaises(ReleaseError):
            HealthGateEvidence(
                gate.assessment, gate.evidence_reference, gate.owning_policy_profile_and_version,
                "latest", gate.scope_binding, gate.release_target_state_version, True, True,
            )

    def test_health_gate_cannot_be_replayed_from_other_deployment_scope(self):
        good = runtime_evidence()
        gate = good.health_gates[0]
        bad_gate = HealthGateEvidence(
            gate.assessment, gate.evidence_reference, gate.owning_policy_profile_and_version,
            gate.policy_evidence_reference, "deployment:validation-cell-a:other-op",
            gate.release_target_state_version, True, True,
        )
        with self.assertRaises(ReleaseError):
            verify_direct(runtime_evidence(health_gates=(bad_gate,) + good.health_gates[1:]))

    def test_health_gate_cannot_be_replayed_across_target_state_version(self):
        good = runtime_evidence()
        gate = good.health_gates[0]
        bad_gate = HealthGateEvidence(
            gate.assessment, gate.evidence_reference, gate.owning_policy_profile_and_version,
            gate.policy_evidence_reference, gate.scope_binding, 4, True, True,
        )
        with self.assertRaises(ReleaseError):
            verify_direct(runtime_evidence(health_gates=(bad_gate,) + good.health_gates[1:]))

    def test_missing_one_required_health_gate_fails_closed(self):
        good = runtime_evidence()
        with self.assertRaises(ReleaseError):
            verify_direct(runtime_evidence(health_gates=good.health_gates[:-1]))

    def test_vendor_green_is_not_runtime_verification(self):
        good = runtime_evidence()
        evidence = RuntimeVerificationEvidence(**{
            **good.__dict__,
            "evidence_reference": "evidence:runtime-verification-2",
            "observed_artifact_identity": None,
            "vendor_controller_green": True,
        })
        with self.assertRaises(ReleaseError):
            verify_direct(evidence)

    def test_quarantined_health_cannot_be_released_even_if_complete(self):
        with self.assertRaises(ReleaseError):
            verify_direct(runtime_evidence(state=HealthState.QUARANTINED, health_admitted=True))

    def test_degraded_health_requires_current_owning_policy_admission(self):
        with self.assertRaises(ReleaseError):
            verify_direct(runtime_evidence(state=HealthState.DEGRADED, health_admitted=False))

    def test_same_artifact_does_not_prove_different_config_safe(self):
        validation = TargetConfiguration("validation-config", "v1", "config.release@1")
        target = TargetConfiguration("production-config", "p1", "config.release@1")
        evidence = ConfigurationValidationEvidence(validation, target, ValidationScope.GENERAL, "evidence:cfg-diff", True)
        with self.assertRaises(ReleaseError):
            require_validation_for_target(evidence)

    def test_config_equivalence_boolean_without_current_evidence_fails(self):
        validation = TargetConfiguration("validation-config", "v1", "config.release@1")
        target = TargetConfiguration("production-config", "p1", "config.release@1")
        evidence = ConfigurationValidationEvidence(validation, target, ValidationScope.GENERAL, "", False, semantic_equivalence_proven=True)
        with self.assertRaises(ReleaseError):
            require_validation_for_target(evidence)


if __name__ == "__main__":
    unittest.main()
