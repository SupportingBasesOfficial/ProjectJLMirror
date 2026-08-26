import unittest

from jlmirror_release import (
    ArtifactIdentity, BuildProvenanceEvidence, CellCompatibilityEvidence,
    MixedVersionMatrix, OutcomeClass, PromotionEvidence, RecoveryClassificationEvidence,
    ReleaseError, RolloutCompatibilityEvidence, SourceTrustClass, ValidationScope,
    classify_change_outcome, require_promotion_authority, require_rollout_compatibility,
    validate_build_provenance,
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


def mixed(**changes):
    values = dict(runtime_compatible=True, schema_compatible=True, api_compatible=True,
                  event_compatible=True, configuration_compatible=True, worker_compatible=True,
                  policy_verifier_compatible=True)
    values.update(changes)
    return MixedVersionMatrix(**values)


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

    def test_promotion_binds_exact_artifact_and_config(self):
        p = provenance()
        promotion = PromotionEvidence("prom-1", "principal.release-promote@1", True, True, p.artifact.canonical, "cfg", "g1", "environment.validation@1", True, True)
        require_promotion_authority(promotion, p)

    def test_registry_presence_or_wrong_artifact_cannot_promote(self):
        p = provenance()
        promotion = PromotionEvidence("prom-1", "principal.release-promote@1", True, True, "sha256:" + "d" * 64, "cfg", "g1", "environment.validation@1", True, True)
        with self.assertRaises(ReleaseError):
            require_promotion_authority(promotion, p)

    def test_mixed_version_failure_blocks_rollout(self):
        evidence = RolloutCompatibilityEvidence(
            mixed(event_compatible=False), ValidationScope.GENERAL, False, False,
            "not cell affecting", CellCompatibilityEvidence(False, no_applicable_case_reason="not cell affecting"),
        )
        with self.assertRaises(ReleaseError):
            require_rollout_compatibility(evidence)

    def test_cell_affecting_release_requires_reference_cell_or_nac(self):
        evidence = RolloutCompatibilityEvidence(
            mixed(), ValidationScope.GENERAL, True, False, None,
            CellCompatibilityEvidence(True, "cell-compat", "g1", True, True),
        )
        with self.assertRaises(ReleaseError):
            require_rollout_compatibility(evidence)

    def test_cell_affecting_release_requires_current_cell_compatibility(self):
        evidence = RolloutCompatibilityEvidence(
            mixed(), ValidationScope.REFERENCE_CELL, True, True, None,
            CellCompatibilityEvidence(True, "cell-compat", "g1", False, True),
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
