from __future__ import annotations

from dataclasses import dataclass

from jlmirror_observability import HealthAssessment, HealthState

from .model import DeploymentIntent, ReleaseError


@dataclass(frozen=True)
class HealthGateEvidence:
    assessment: HealthAssessment
    evidence_reference: str
    owning_policy_profile_and_version: str
    policy_current: bool
    admission_eligible: bool

    def __post_init__(self) -> None:
        if not self.evidence_reference or not self.owning_policy_profile_and_version:
            raise ReleaseError("health gate requires evidence and owning policy identity")


@dataclass(frozen=True)
class RuntimeVerificationEvidence:
    evidence_reference: str
    evidence_current: bool
    observed_artifact_identity: str | None
    observed_configuration_generation: str | None
    runtime_profile_set: tuple[str, ...]
    runtime_admission_current: bool
    configuration_current: bool
    release_policy_current: bool
    verifier_authority_current: bool
    required_health_profile_ids: tuple[str, ...]
    health_gates: tuple[HealthGateEvidence, ...]
    vendor_controller_green: bool = False


def verify_runtime(intent: DeploymentIntent, evidence: RuntimeVerificationEvidence) -> None:
    if not evidence.evidence_reference or not evidence.evidence_current:
        raise ReleaseError("runtime verification requires current durable evidence")
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

    gates = {}
    for gate in evidence.health_gates:
        pid = gate.assessment.profile_id
        if pid in gates:
            raise ReleaseError(f"duplicate health gate evidence: {pid}")
        gates[pid] = gate
    if set(evidence.required_health_profile_ids) - gates.keys():
        raise ReleaseError("required Phase 12 health evidence is missing")
    for profile_id in evidence.required_health_profile_ids:
        gate = gates[profile_id]
        item = gate.assessment
        if not item.evidence_complete or item.state is HealthState.UNKNOWN:
            raise ReleaseError(f"required health evidence is not current/complete: {profile_id}")
        if item.state in {HealthState.UNAVAILABLE, HealthState.QUARANTINED, HealthState.DRAINING}:
            raise ReleaseError(f"health state is not eligible for protected serving admission: {profile_id}")
        if not gate.policy_current or not gate.admission_eligible:
            raise ReleaseError(f"owning Phase 12 policy has not admitted health state for release: {profile_id}")
    # DEGRADED may be eligible only when its current owning policy explicitly admits it.
    # vendor_controller_green is evidence only and deliberately ignored as authority.
