"""Release domain router — deployment authority, provenance, compatibility.

Exposes read-only operations from ``jlmirror_release``. The release domain
has complex evidence requirements (ADR-016); this router provides catalog
introspection and outcome classification. Full deployment admission requires
assembling many evidence objects and is left for a dedicated release workflow.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from jlmirror_release.model import OutcomeClass
from jlmirror_release.recovery import RecoveryClassificationEvidence, classify_change_outcome

router = APIRouter()


class OutcomeClassResponse(BaseModel):
    outcome: str


class RecoveryClassificationRequest(BaseModel):
    evidence_reference: str = "evidence:recovery-1"
    authority_profile_and_version: str = "authority.release-recovery@1"
    scope_binding: str
    current: bool = True
    effect_outcome_ambiguous: bool = False
    irreversible_without_governed_migration: bool = False
    previous_runtime_can_interpret_current_state: bool = True
    rollback_configuration_evidence_current: bool = True
    cell_compatibility_allows_previous: bool = True
    release_policy_and_verifier_current: bool = True
    release_target_state_allows_rollback: bool = True
    security_governance_reliability_current: bool = True
    required_evidence_preserved: bool = True


@router.post("/release/outcome/classify", response_model=OutcomeClassResponse)
async def classify_outcome(
    body: RecoveryClassificationRequest,
) -> OutcomeClassResponse:
    """Classify a change outcome from recovery classification evidence."""
    evidence = RecoveryClassificationEvidence(
        evidence_reference=body.evidence_reference,
        authority_profile_and_version=body.authority_profile_and_version,
        scope_binding=body.scope_binding,
        current=body.current,
        effect_outcome_ambiguous=body.effect_outcome_ambiguous,
        irreversible_without_governed_migration=body.irreversible_without_governed_migration,
        previous_runtime_can_interpret_current_state=body.previous_runtime_can_interpret_current_state,
        rollback_configuration_evidence_current=body.rollback_configuration_evidence_current,
        cell_compatibility_allows_previous=body.cell_compatibility_allows_previous,
        release_policy_and_verifier_current=body.release_policy_and_verifier_current,
        release_target_state_allows_rollback=body.release_target_state_allows_rollback,
        security_governance_reliability_current=body.security_governance_reliability_current,
        required_evidence_preserved=body.required_evidence_preserved,
    )
    try:
        outcome = classify_change_outcome(evidence, expected_scope=body.scope_binding)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Classification failed: {exc}",
        ) from exc
    return OutcomeClassResponse(outcome=outcome.value)


@router.get("/release/outcomes", response_model=list[str])
async def list_outcome_classes() -> list[str]:
    """List all accepted change outcome classes."""
    return [oc.value for oc in OutcomeClass]
