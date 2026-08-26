from __future__ import annotations

from dataclasses import dataclass

from .model import ReleaseError, ValidationScope


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
    no_applicable_case_reason: str | None = None


@dataclass(frozen=True)
class RolloutCompatibilityEvidence:
    mixed_version: MixedVersionMatrix
    validation_scope: ValidationScope
    cell_affecting_release: bool
    reference_cell_evidence_current: bool
    reference_cell_no_applicable_case_reason: str | None
    cell_compatibility: CellCompatibilityEvidence


def require_rollout_compatibility(evidence: RolloutCompatibilityEvidence) -> None:
    if not evidence.mixed_version.all_supported:
        raise ReleaseError("mixed-version coexistence is not proven compatible")
    if evidence.cell_affecting_release:
        if evidence.validation_scope is not ValidationScope.REFERENCE_CELL:
            if not evidence.reference_cell_no_applicable_case_reason:
                raise ReleaseError("cell/runtime/schema-affecting release requires reference-cell evidence or evidence-backed NO_APPLICABLE_CASE")
        elif not evidence.reference_cell_evidence_current:
            raise ReleaseError("reference-cell validation evidence is not current")
        cell = evidence.cell_compatibility
        if not cell.applicable:
            raise ReleaseError("cell-affecting release requires current cell compatibility metadata")
        if not all((cell.metadata_identity, cell.metadata_generation, cell.metadata_current, cell.combination_admitted)):
            raise ReleaseError("cell compatibility metadata is missing, stale or incompatible")
    else:
        cell = evidence.cell_compatibility
        if cell.applicable:
            if not all((cell.metadata_identity, cell.metadata_generation, cell.metadata_current, cell.combination_admitted)):
                raise ReleaseError("applicable cell compatibility evidence is incomplete")
        elif not cell.no_applicable_case_reason:
            raise ReleaseError("non-applicable cell compatibility requires explicit evidence-backed reason")
