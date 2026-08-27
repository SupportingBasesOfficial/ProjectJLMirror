from __future__ import annotations

from dataclasses import dataclass

from .model import ReleaseError, ValidationScope
from .provenance import require_immutable_evidence_reference


@dataclass(frozen=True)
class NoApplicableCaseEvidence:
    reason: str
    authority_profile: str
    evidence_reference: str
    scope_binding: str
    current: bool

    def validate_for(self, expected_scope: str) -> None:
        if not all((self.reason, self.authority_profile, self.scope_binding)):
            raise ReleaseError("NO_APPLICABLE_CASE requires reason, authority, evidence and exact scope")
        require_immutable_evidence_reference("no_applicable_case.evidence_reference", self.evidence_reference)
        if not self.current:
            raise ReleaseError("NO_APPLICABLE_CASE evidence is not current")
        if self.scope_binding != expected_scope:
            raise ReleaseError("NO_APPLICABLE_CASE evidence is bound to a different release scope")


@dataclass(frozen=True)
class MixedVersionMatrix:
    runtime_compatible: bool
    schema_compatible: bool
    api_compatible: bool
    event_compatible: bool
    configuration_compatible: bool
    worker_compatible: bool
    policy_verifier_compatible: bool

    @property
    def all_supported(self) -> bool:
        return all((self.runtime_compatible, self.schema_compatible, self.api_compatible,
                    self.event_compatible, self.configuration_compatible,
                    self.worker_compatible, self.policy_verifier_compatible))


@dataclass(frozen=True)
class CellCompatibilityEvidence:
    applicable: bool
    metadata_identity: str | None = None
    metadata_generation: str | None = None
    metadata_current: bool = False
    combination_admitted: bool = False
    no_applicable_case: NoApplicableCaseEvidence | None = None


@dataclass(frozen=True)
class RolloutCompatibilityEvidence:
    evidence_reference: str
    evidence_current: bool
    release_scope_id: str
    mixed_version: MixedVersionMatrix
    validation_scope: ValidationScope
    cell_affecting_release: bool
    reference_cell_evidence_current: bool
    reference_cell_no_applicable_case: NoApplicableCaseEvidence | None
    cell_compatibility: CellCompatibilityEvidence


def require_rollout_compatibility(evidence: RolloutCompatibilityEvidence) -> None:
    require_immutable_evidence_reference("rollout_compatibility.evidence_reference", evidence.evidence_reference)
    if not evidence.evidence_current:
        raise ReleaseError("rollout compatibility requires a current durable evidence reference")
    if not evidence.release_scope_id:
        raise ReleaseError("rollout compatibility requires an exact release scope")
    if not evidence.mixed_version.all_supported:
        raise ReleaseError("mixed-version coexistence is not proven compatible")
    if evidence.cell_affecting_release:
        if evidence.validation_scope is not ValidationScope.REFERENCE_CELL:
            if evidence.reference_cell_no_applicable_case is None:
                raise ReleaseError("cell/runtime/schema-affecting release requires reference-cell evidence or evidence-backed NO_APPLICABLE_CASE")
            evidence.reference_cell_no_applicable_case.validate_for(evidence.release_scope_id)
        elif not evidence.reference_cell_evidence_current:
            raise ReleaseError("reference-cell validation evidence is not current")
        cell = evidence.cell_compatibility
        if not cell.applicable:
            raise ReleaseError("cell-affecting release requires current cell compatibility metadata")
        if cell.no_applicable_case is not None:
            raise ReleaseError("applicable cell compatibility cannot also claim NO_APPLICABLE_CASE")
        if not all((cell.metadata_identity, cell.metadata_generation, cell.metadata_current, cell.combination_admitted)):
            raise ReleaseError("cell compatibility metadata is missing, stale or incompatible")
    else:
        if evidence.reference_cell_no_applicable_case is not None:
            evidence.reference_cell_no_applicable_case.validate_for(evidence.release_scope_id)
        cell = evidence.cell_compatibility
        if cell.applicable:
            if cell.no_applicable_case is not None:
                raise ReleaseError("applicable cell compatibility cannot also claim NO_APPLICABLE_CASE")
            if not all((cell.metadata_identity, cell.metadata_generation, cell.metadata_current, cell.combination_admitted)):
                raise ReleaseError("applicable cell compatibility evidence is incomplete")
        else:
            if cell.no_applicable_case is None:
                raise ReleaseError("non-applicable cell compatibility requires evidence-backed NO_APPLICABLE_CASE")
            cell.no_applicable_case.validate_for(evidence.release_scope_id)
