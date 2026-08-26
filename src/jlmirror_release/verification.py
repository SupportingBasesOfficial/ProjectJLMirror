from __future__ import annotations

from dataclasses import dataclass

from jlmirror_observability import HealthAssessment, HealthState

from .model import DeploymentIntent, ReleaseError


@dataclass(frozen=True)
class RuntimeVerificationEvidence:
    observed_artifact_identity: str | None
    observed_configuration_generation: str | None
    runtime_profile_set: tuple[str, ...]
    runtime_admission_current: bool
    configuration_current: bool
    release_policy_current: bool
    verifier_authority_current: bool
    required_health_profile_ids: tuple[str, ...]
    health_assessments: tuple[HealthAssessment, ...]
    vendor_controller_green: bool = False


def verify_runtime(intent: DeploymentIntent, evidence: RuntimeVerificationEvidence) -> None:
    """Verify actual runtime state; vendor/controller green is intentionally insufficient."""
    if evidence.observed_artifact_identity is None:
        raise ReleaseError("running immutable artifact identity must be independently observed")
    if evidence.observed_artifact_identity != intent.artifact.canonical:
        raise ReleaseError("observed runtime artifact differs from approved immutable artifact")
    if evidence.observed_configuration_generation != intent.configuration.generation:
        raise ReleaseError("observed target configuration generation is not current intent")
    if tuple(evidence.runtime_profile_set) != tuple(intent.runtime_profile_set):
        raise ReleaseError("runtime profile set differs from approved release intent")
    if not evidence.runtime_admission_current:
        raise ReleaseError("deployment success cannot substitute for current runtime admission")
    if not evidence.configuration_current:
        raise ReleaseError("target configuration currentness is not proven")
    if not evidence.release_policy_current or not evidence.verifier_authority_current:
        raise ReleaseError("release policy/verifier currentness is not proven")

    assessments = {item.profile_id: item for item in evidence.health_assessments}
    if set(evidence.required_health_profile_ids) - assessments.keys():
        raise ReleaseError("required Phase 12 health evidence is missing")
    for profile_id in evidence.required_health_profile_ids:
        item = assessments[profile_id]
        if not item.evidence_complete or item.state is HealthState.UNKNOWN:
            raise ReleaseError(f"required health evidence is not current/complete: {profile_id}")
    # Health evidence is a gate input/evidence surface, never authorization by itself.
    # vendor_controller_green is deliberately ignored as an authority input.
