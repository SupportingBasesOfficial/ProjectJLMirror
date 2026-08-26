from __future__ import annotations

from dataclasses import dataclass

from .model import ALLOWED_ENVIRONMENT_CLASSES, ArtifactIdentity, RELEASE_PRINCIPALS, ReleaseError, SourceTrustClass


@dataclass(frozen=True)
class BuildProvenanceEvidence:
    source_state_id: str
    source_trust_class: SourceTrustClass
    accepted_change_authority_proven: bool
    release_policy_profile_and_version: str
    release_policy_current: bool
    builder_principal_class: str
    builder_authorized_current: bool
    declared_input_set_id: str
    declared_inputs_integrity_proven: bool
    build_record_id: str
    artifact: ArtifactIdentity
    provenance_profile: str
    provenance_record_id: str
    provenance_verifier_profile_and_version: str
    provenance_verifier_current: bool
    sbom_or_dependency_inventory_reference: str
    artifact_attestation_profile: str
    artifact_retired: bool = False


def validate_build_provenance(evidence: BuildProvenanceEvidence) -> None:
    if evidence.source_trust_class is not SourceTrustClass.ACCEPTED_REVIEW_STATE:
        raise ReleaseError("trusted build requires accepted exact source trust state")
    if not evidence.source_state_id or not evidence.accepted_change_authority_proven:
        raise ReleaseError("accepted source requires exact state and change-authority evidence")
    if not evidence.release_policy_profile_and_version or not evidence.release_policy_current:
        raise ReleaseError("trusted release policy profile/currentness is required")
    if evidence.builder_principal_class != "principal.release-build@1":
        raise ReleaseError("trusted build must use the bounded release build principal")
    if evidence.builder_principal_class not in RELEASE_PRINCIPALS or not evidence.builder_authorized_current:
        raise ReleaseError("builder principal authority is not current")
    if not evidence.declared_input_set_id or not evidence.declared_inputs_integrity_proven:
        raise ReleaseError("declared build inputs require integrity-bound evidence")
    required = (evidence.build_record_id, evidence.provenance_profile, evidence.provenance_record_id, evidence.provenance_verifier_profile_and_version, evidence.sbom_or_dependency_inventory_reference, evidence.artifact_attestation_profile)
    if not all(required):
        raise ReleaseError("provenance/SBOM/attestation records are required")
    if not evidence.provenance_verifier_current:
        raise ReleaseError("retired/stale provenance verifier cannot establish trusted evidence")
    if evidence.artifact_retired:
        raise ReleaseError("retired artifact is not eligible for new promotion/deployment")


@dataclass(frozen=True)
class PromotionEvidence:
    promotion_id: str
    promotion_principal_class: str
    approval_current: bool
    release_policy_profile_and_version: str
    release_policy_current: bool
    artifact_identity: str
    target_configuration_identity: str
    target_configuration_generation: str
    target_configuration_semantic_profile: str
    target_environment_class: str
    validation_evidence_current: bool
    compatibility_evidence_current: bool


def require_promotion_authority(promotion: PromotionEvidence, provenance: BuildProvenanceEvidence) -> None:
    validate_build_provenance(provenance)
    if promotion.promotion_principal_class != "principal.release-promote@1":
        raise ReleaseError("promotion requires the bounded release promotion principal")
    if not promotion.promotion_id or not promotion.approval_current:
        raise ReleaseError("promotion approval is required")
    if not promotion.release_policy_profile_and_version or not promotion.release_policy_current:
        raise ReleaseError("promotion requires current exact release policy")
    if promotion.release_policy_profile_and_version != provenance.release_policy_profile_and_version:
        raise ReleaseError("promotion policy differs from provenanced build policy")
    if promotion.artifact_identity != provenance.artifact.canonical:
        raise ReleaseError("promotion artifact differs from provenanced immutable artifact")
    if not all((promotion.target_configuration_identity, promotion.target_configuration_generation, promotion.target_configuration_semantic_profile)):
        raise ReleaseError("promotion requires exact target configuration identity/generation/profile")
    if promotion.target_environment_class not in ALLOWED_ENVIRONMENT_CLASSES:
        raise ReleaseError("promotion target environment class is not canonical")
    if not promotion.validation_evidence_current or not promotion.compatibility_evidence_current:
        raise ReleaseError("promotion requires current validation and compatibility evidence")
