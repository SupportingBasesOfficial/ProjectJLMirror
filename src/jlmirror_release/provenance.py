from __future__ import annotations

from dataclasses import dataclass
import re

from .model import ALLOWED_ENVIRONMENT_CLASSES, ArtifactIdentity, RELEASE_PRINCIPALS, ReleaseError, SourceTrustClass, ValidationScope

_EVIDENCE_REFERENCE_RE = re.compile(r"^evidence:[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,190}$")
_GIT_SOURCE_STATE_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")


def require_immutable_evidence_reference(name: str, value: str) -> None:
    """Wave 3 evidence references are immutable durable record identities, never mutable aliases/URLs."""
    if not isinstance(value, str) or not _EVIDENCE_REFERENCE_RE.fullmatch(value):
        raise ReleaseError(f"{name} must be an immutable durable evidence record identity")


@dataclass(frozen=True)
class AcceptedSourceEvidence:
    source_state_id: str
    source_trust_class: SourceTrustClass
    source_change_authority_profile_and_version: str
    source_change_evidence_reference: str
    review_assurance_profile_and_version: str
    review_assurance_evidence_reference: str

    def validate(self) -> None:
        if self.source_trust_class is not SourceTrustClass.ACCEPTED_REVIEW_STATE:
            raise ReleaseError("trusted build requires accepted exact source trust state")
        if not isinstance(self.source_state_id, str) or not _GIT_SOURCE_STATE_RE.fullmatch(self.source_state_id):
            raise ReleaseError("accepted source state must be an exact immutable Git object id")
        if not self.source_change_authority_profile_and_version:
            raise ReleaseError("accepted source requires source/change authority profile/version")
        if not self.review_assurance_profile_and_version:
            raise ReleaseError("accepted source requires review/assurance authority profile/version")
        require_immutable_evidence_reference(
            "source_change_evidence_reference", self.source_change_evidence_reference
        )
        require_immutable_evidence_reference(
            "review_assurance_evidence_reference", self.review_assurance_evidence_reference
        )
        if self.source_change_evidence_reference == self.review_assurance_evidence_reference:
            raise ReleaseError("source/change and review/assurance evidence identities must remain distinct")


def require_trusted_build_source(source: AcceptedSourceEvidence) -> None:
    """Establish trusted build source only from exact accepted source/change + review evidence."""
    if not isinstance(source, AcceptedSourceEvidence):
        raise ReleaseError("trusted build source requires canonical AcceptedSourceEvidence")
    source.validate()


@dataclass(frozen=True)
class BuildProvenanceEvidence:
    accepted_source: AcceptedSourceEvidence
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

    @property
    def source_state_id(self) -> str:
        return self.accepted_source.source_state_id

    @property
    def source_trust_class(self) -> SourceTrustClass:
        return self.accepted_source.source_trust_class


def validate_build_provenance(evidence: BuildProvenanceEvidence) -> None:
    require_trusted_build_source(evidence.accepted_source)
    if not evidence.release_policy_profile_and_version or not evidence.release_policy_current:
        raise ReleaseError("trusted release policy profile/currentness is required")
    if evidence.builder_principal_class != "principal.release-build@1":
        raise ReleaseError("trusted build must use the bounded release build principal")
    if evidence.builder_principal_class not in RELEASE_PRINCIPALS or not evidence.builder_authorized_current:
        raise ReleaseError("builder principal authority is not current")
    if not evidence.declared_input_set_id or not evidence.declared_inputs_integrity_proven:
        raise ReleaseError("declared build inputs require integrity-bound evidence")
    required = (evidence.build_record_id, evidence.provenance_profile, evidence.provenance_record_id,
                evidence.provenance_verifier_profile_and_version,
                evidence.sbom_or_dependency_inventory_reference, evidence.artifact_attestation_profile)
    if not all(required):
        raise ReleaseError("provenance/SBOM/attestation records are required")
    if not evidence.provenance_verifier_current:
        raise ReleaseError("retired/stale provenance verifier cannot establish trusted evidence")
    if evidence.artifact_retired:
        raise ReleaseError("retired artifact is not eligible for new promotion/deployment")


@dataclass(frozen=True)
class PromotionEvidence:
    promotion_id: str
    promotion_evidence_reference: str
    promotion_principal_class: str
    approval_current: bool
    approval_evidence_reference: str
    release_policy_profile_and_version: str
    release_policy_current: bool
    artifact_identity: str
    target_id: str
    target_environment_class: str
    validation_scope: ValidationScope
    rollout_scope_id: str
    runtime_profile_set: tuple[str, ...]
    target_configuration_identity: str
    target_configuration_generation: str
    target_configuration_semantic_profile: str
    configuration_validation_evidence_reference: str
    rollout_compatibility_evidence_reference: str
    schema_state: str
    api_compatibility_family: str
    event_compatibility_set: tuple[str, ...]
    required_evidence_set_reference: str
    validation_evidence_current: bool
    compatibility_evidence_current: bool
    cell_compatibility_metadata_identity: str | None = None
    cell_compatibility_metadata_generation: str | None = None


def require_promotion_authority(promotion: PromotionEvidence, provenance: BuildProvenanceEvidence) -> None:
    validate_build_provenance(provenance)
    if promotion.promotion_principal_class != "principal.release-promote@1":
        raise ReleaseError("promotion requires the bounded release promotion principal")
    for name, value in (
        ("promotion_evidence_reference", promotion.promotion_evidence_reference),
        ("approval_evidence_reference", promotion.approval_evidence_reference),
        ("configuration_validation_evidence_reference", promotion.configuration_validation_evidence_reference),
        ("rollout_compatibility_evidence_reference", promotion.rollout_compatibility_evidence_reference),
        ("required_evidence_set_reference", promotion.required_evidence_set_reference),
    ):
        require_immutable_evidence_reference(name, value)
    if not promotion.promotion_id or not promotion.approval_current:
        raise ReleaseError("promotion approval and durable promotion evidence are required")
    if not promotion.release_policy_profile_and_version or not promotion.release_policy_current:
        raise ReleaseError("promotion requires current exact release policy")
    if promotion.release_policy_profile_and_version != provenance.release_policy_profile_and_version:
        raise ReleaseError("promotion policy differs from provenanced build policy")
    if promotion.artifact_identity != provenance.artifact.canonical:
        raise ReleaseError("promotion artifact differs from provenanced immutable artifact")
    if not all((promotion.target_id, promotion.rollout_scope_id,
                promotion.target_configuration_identity, promotion.target_configuration_generation,
                promotion.target_configuration_semantic_profile,
                promotion.schema_state, promotion.api_compatibility_family)):
        raise ReleaseError("promotion requires exact target, configuration, compatibility and evidence lineage")
    if not promotion.runtime_profile_set or not promotion.event_compatibility_set:
        raise ReleaseError("promotion requires runtime and event compatibility sets")
    if promotion.target_environment_class not in ALLOWED_ENVIRONMENT_CLASSES:
        raise ReleaseError("promotion target environment class is not canonical")
    if not promotion.validation_evidence_current or not promotion.compatibility_evidence_current:
        raise ReleaseError("promotion requires current validation and compatibility evidence")
    cell_identity = promotion.cell_compatibility_metadata_identity
    cell_generation = promotion.cell_compatibility_metadata_generation
    if (cell_identity is None) != (cell_generation is None):
        raise ReleaseError("promotion cell compatibility metadata identity/generation must be jointly bound")
