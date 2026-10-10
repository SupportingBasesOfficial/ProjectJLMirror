"""Observability domain router — signal catalog, evidence pipeline, health assessment.

Exposes operations from ``jlmirror_observability``. See ADR-014 (observability).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from jlmirror_observability import (
    EXPECTED_RELIABILITY_PROFILE_IDS,
    missing_health,
)
from jlmirror_observability.catalog import join_for

router = APIRouter()


class ReliabilityProfileResponse(BaseModel):
    reliability_profile_id: str
    diagnostic_signal_ids: list[str]
    health_profile_ids: list[str]
    sli_profile_ids: list[str]
    alert_profile_ids: list[str]


@router.get("/observability/profiles", response_model=list[str])
async def list_reliability_profiles() -> list[str]:
    """List all accepted reliability profile IDs."""
    return sorted(EXPECTED_RELIABILITY_PROFILE_IDS)


@router.get("/observability/profiles/{profile_id}", response_model=ReliabilityProfileResponse)
async def get_reliability_profile(profile_id: str) -> ReliabilityProfileResponse:
    """Get the observability join for a reliability profile."""
    try:
        join = join_for(profile_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return ReliabilityProfileResponse(
        reliability_profile_id=join.reliability_profile_id,
        diagnostic_signal_ids=list(join.diagnostic_signal_ids),
        health_profile_ids=list(join.health_profile_ids),
        sli_profile_ids=list(join.sli_profile_ids),
        alert_profile_ids=list(join.alert_profile_ids),
    )


class HealthAssessmentRequest(BaseModel):
    profile_id: str
    reason_class: str = "telemetry_missing"


class HealthAssessmentResponse(BaseModel):
    profile_id: str
    health_state: str
    reason_class: str
    evidence_complete: bool


@router.post("/observability/health/missing", response_model=HealthAssessmentResponse)
async def assess_missing_health(
    body: HealthAssessmentRequest,
) -> HealthAssessmentResponse:
    """Produce a missing-telemetry health assessment (unknown state)."""
    assessment = missing_health(body.profile_id, body.reason_class)
    return HealthAssessmentResponse(
        profile_id=assessment.profile_id,
        health_state=assessment.state.value,
        reason_class=assessment.reason_class,
        evidence_complete=assessment.evidence_complete,
    )
