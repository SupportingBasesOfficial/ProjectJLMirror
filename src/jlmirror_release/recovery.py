from __future__ import annotations

from dataclasses import dataclass

from .model import OutcomeClass, ReleaseError
from .provenance import require_immutable_evidence_reference


@dataclass(frozen=True)
class RecoveryClassificationEvidence:
    evidence_reference: str
    authority_profile_and_version: str
    scope_binding: str
    current: bool
    effect_outcome_ambiguous: bool
    irreversible_without_governed_migration: bool
    previous_runtime_can_interpret_current_state: bool
    rollback_configuration_evidence_current: bool
    cell_compatibility_allows_previous: bool
    release_policy_and_verifier_current: bool
    release_target_state_allows_rollback: bool
    security_governance_reliability_current: bool
    required_evidence_preserved: bool

    def validate_for(self, expected_scope: str) -> None:
        require_immutable_evidence_reference("recovery_classification.evidence_reference", self.evidence_reference)
        if not self.authority_profile_and_version:
            raise ReleaseError("recovery classification requires an owning authority profile/version")
        if not expected_scope or self.scope_binding != expected_scope:
            raise ReleaseError("recovery classification evidence is bound to a different release scope")
        if not self.current:
            raise ReleaseError("recovery classification evidence is not current")


def classify_change_outcome(evidence: RecoveryClassificationEvidence, *, expected_scope: str) -> OutcomeClass:
    evidence.validate_for(expected_scope)
    if evidence.effect_outcome_ambiguous:
        return OutcomeClass.RECONCILIATION_REQUIRED
    if evidence.irreversible_without_governed_migration:
        return OutcomeClass.IRREVERSIBLE_WITHOUT_GOVERNED_MIGRATION
    rollback_inputs = (
        evidence.previous_runtime_can_interpret_current_state,
        evidence.rollback_configuration_evidence_current,
        evidence.cell_compatibility_allows_previous,
        evidence.release_policy_and_verifier_current,
        evidence.release_target_state_allows_rollback,
        evidence.security_governance_reliability_current,
        evidence.required_evidence_preserved,
    )
    if all(rollback_inputs):
        return OutcomeClass.ROLLBACK_ELIGIBLE
    return OutcomeClass.FORWARD_RECOVERY_REQUIRED
