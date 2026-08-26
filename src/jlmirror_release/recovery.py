from __future__ import annotations

from dataclasses import dataclass

from .model import OutcomeClass


@dataclass(frozen=True)
class RecoveryClassificationEvidence:
    effect_outcome_ambiguous: bool
    irreversible_without_governed_migration: bool
    previous_runtime_can_interpret_current_state: bool
    rollback_configuration_evidence_current: bool
    cell_compatibility_allows_previous: bool
    release_policy_and_verifier_current: bool
    release_target_state_allows_rollback: bool
    security_governance_reliability_current: bool
    required_evidence_preserved: bool


def classify_change_outcome(evidence: RecoveryClassificationEvidence) -> OutcomeClass:
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
