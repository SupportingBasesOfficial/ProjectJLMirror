import unittest

from jlmirror_release import (
    ArtifactIdentity, BuildProvenanceEvidence, CellCompatibilityEvidence,
    MixedVersionMatrix, NoApplicableCaseEvidence, OutcomeClass, PromotionEvidence,
    RecoveryClassificationEvidence, ReleaseError, RolloutCompatibilityEvidence,
    SourceTrustClass, ValidationScope, classify_change_outcome,
    require_promotion_authority, require_rollout_compatibility, validate_build_provenance,
)

ARTIFACT = ArtifactIdentity("sha256", "c" * 64)


def provenance(**changes):
    values = dict(
        source_state_id="source-sha", source_trust_class=SourceTrustClass.ACCEPTED_REVIEW_STATE,
        accepted_change_authority_proven=True, release_policy_profile_and_version="release-policy@1",
        release_policy_current=True, builder_principal_class="principal.release-build@1",
        builder_authorized_current=True, declared_input_set_id="inputs-1",
        declared_inputs_integrity_proven=True, build_record_id="build-1", artifact=ARTIFACT,
        provenance_profile="release.provenance@1", provenance_record_id="prov-1",
        provenance_verifier_profile_and_version="verifier@1", provenance_verifier_current=True,
        sbom_or_dependency_inventory_reference="sbom-1", artifact_attestation_profile="attestation@1",
        artifact_retired=False,
    )
    values.update(changes)
    return BuildProvenanceEvidence(**values)


def promotion(**changes):
    values = dict(
        promotion_id="prom-1", promotion_evidence_reference="evidence:promotion-1",
        promotion_principal_class="principal.release-promote@1",
        approval_current=True, approval_evidence_reference="evidence:approval-1",
        release_policy_profile_and_version="release-policy@1", release_policy_current=True,
        artifact_identity=ARTIFACT.canonical, target_id="scope-a",
        target_environment_class="environment.validation@1", validation_scope=ValidationScope.GENERAL,
        rollout_scope_id="scope-a", runtime_profile_set=("runtime.api@1",),
        target_configuration_identity="cfg", target_configuration_generation="g1",
        target_configuration_semantic_profile="config.release@1",
        configuration_validation_evidence_reference="evidence:config-1",
        rollout_compatibility_evidence_reference="evidence:rollout-1",
        schema_state="compatible", api_compatibility_family="api.v1",
        event_compatibility_set=("event.v1",), required_evidence_set_reference="evidence:set-1",
        validation_evidence_current=True, compatibility_evidence_current=True,
    )
    values.update(changes)
    return PromotionEvidence(**values)


def mixed(**changes):
    values = dict(runtime_compatible=True, schema_compatible=True, api_compatible=True,
                  event_compatible=True, configuration_compatible=True, worker_compatible=True,
                  policy_verifier_compatible=True)
    values.update(changes)
    return MixedVersionMatrix(**values)


def nac(scope, current=True):
    return NoApplicableCaseEvidence("not applicable for exact scoped release", "release.compatibility-policy@1", "evidence:nac", scope, current)


def rollout(scope, *, matrix=None, validation_scope=ValidationScope.GENERAL,
            cell_affecting=False, reference_current=False, reference_nac=None,
            cell=None, evidence_reference="evidence:rollout-1", evidence_current=True):
    return RolloutCompatibilityEvidence(
        evidence_reference=evidence_reference, evidence_current=evidence_current,
        release_scope_id=scope, mixed_version=matrix or mixed(), validation_scope=validation_scope,
        cell_affecting_release=cell_affecting, reference_cell_evidence_current=reference_current,
        reference_cell_no_applicable_case=reference_nac,
        cell_compatibility=cell or CellCompatibilityEvidence(False, no_applicable_case=nac(scope)),
    )


class ProvenanceCompatibilityTests(unittest.TestCase):
    def test_provenance_accepts_current_bounded_chain(self):
        validate_build_provenance(provenance())

    def test_stale_verifier_cannot_establish_trusted_provenance(self):
        with self.assertRaises(ReleaseError):
            validate_build_provenance(provenance(provenance_verifier_current=False))

    def test_candidate_source_cannot_be_laundered_by_build(self):
        with self.assertRaises(ReleaseError):
            validate_build_provenance(provenance(source_trust_class=SourceTrustClass.UNTRUSTED_CANDIDATE))

    def test_wrong_builder_principal_fails(self):
        with self.assertRaises(ReleaseError):
            validate_build_provenance(provenance(builder_principal_class="principal.release-untrusted-validation@1"))

    def test_retired_artifact_cannot_gain_new_promotion(self):
        with self.assertRaises(ReleaseError):
            validate_build_provenance(provenance(artifact_retired=True))

    def test_promotion_binds_exact_artifact_config_profile_environment_and_lineage(self):
        require_promotion_authority(promotion(), provenance())

    def test_registry_presence_or_wrong_artifact_cannot_promote(self):
        with self.assertRaises(ReleaseError):
            require_promotion_authority(promotion(artifact_identity="sha256:" + "d" * 64), provenance())

    def test_noncanonical_promotion_environment_fails(self):
        with self.assertRaises(ReleaseError):
            require_promotion_authority(promotion(target_environment_class="staging"), provenance())

    def test_promotion_requires_durable_validation_and_compatibility_lineage(self):
        for mutation in (
            {"promotion_evidence_reference": ""},
            {"approval_evidence_reference": ""},
            {"configuration_validation_evidence_reference": ""},
            {"rollout_compatibility_evidence_reference": ""},
            {"required_evidence_set_reference": ""},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(ReleaseError):
                require_promotion_authority(promotion(**mutation), provenance())

    def test_partial_cell_metadata_binding_fails(self):
        with self.assertRaises(ReleaseError):
            require_promotion_authority(promotion(cell_compatibility_metadata_identity="cell-meta", cell_compatibility_metadata_generation=None), provenance())

    def test_mixed_version_failure_blocks_rollout(self):
        scope = "scope-a"
        evidence = rollout(scope, matrix=mixed(event_compatible=False), reference_nac=nac(scope))
        with self.assertRaises(ReleaseError):
            require_rollout_compatibility(evidence)

    def test_rollout_requires_current_durable_evidence_reference(self):
        scope = "scope-a"
        with self.assertRaises(ReleaseError):
            require_rollout_compatibility(rollout(scope, evidence_reference="", evidence_current=False))

    def test_cell_affecting_release_requires_reference_cell_or_evidence_backed_nac(self):
        scope = "scope-a"
        evidence = rollout(
            scope, cell_affecting=True,
            cell=CellCompatibilityEvidence(True, "cell-compat", "g1", True, True),
        )
        with self.assertRaises(ReleaseError):
            require_rollout_compatibility(evidence)

    def test_free_text_cannot_launder_reference_cell_no_applicable_case(self):
        scope = "scope-a"
        evidence = rollout(
            scope, cell_affecting=True, reference_nac=nac(scope, current=False),
            cell=CellCompatibilityEvidence(True, "cell-compat", "g1", True, True),
        )
        with self.assertRaises(ReleaseError):
            require_rollout_compatibility(evidence)

    def test_nac_scope_mismatch_fails_closed(self):
        scope = "scope-a"
        evidence = rollout(scope, reference_nac=nac(scope), cell=CellCompatibilityEvidence(False, no_applicable_case=nac("scope-b")))
        with self.assertRaises(ReleaseError):
            require_rollout_compatibility(evidence)

    def test_cell_affecting_release_requires_current_cell_compatibility(self):
        scope = "scope-a"
        evidence = rollout(
            scope, validation_scope=ValidationScope.REFERENCE_CELL, cell_affecting=True,
            reference_current=True, cell=CellCompatibilityEvidence(True, "cell-compat", "g1", False, True),
        )
        with self.assertRaises(ReleaseError):
            require_rollout_compatibility(evidence)

    def test_ambiguous_effect_classifies_reconciliation_first(self):
        result = classify_change_outcome(RecoveryClassificationEvidence(True, False, True, True, True, True, True, True, True))
        self.assertEqual(result, OutcomeClass.RECONCILIATION_REQUIRED)

    def test_any_currentness_regression_forces_forward_recovery(self):
        result = classify_change_outcome(RecoveryClassificationEvidence(False, False, True, True, True, False, True, True, True))
        self.assertEqual(result, OutcomeClass.FORWARD_RECOVERY_REQUIRED)

    def test_rollback_requires_all_current_eligibility_inputs(self):
        result = classify_change_outcome(RecoveryClassificationEvidence(False, False, True, True, True, True, True, True, True))
        self.assertEqual(result, OutcomeClass.ROLLBACK_ELIGIBLE)


if __name__ == "__main__":
    unittest.main()
