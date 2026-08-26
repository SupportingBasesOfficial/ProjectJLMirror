from __future__ import annotations

from dataclasses import dataclass

from jlmirror_observability import HealthAssessment, HealthState

from .model import DeploymentIntent, ReleaseError
from .provenance import require_immutable_evidence_reference


def runtime_verification_scope_for(intent: DeploymentIntent) -> str:
    return f"deployment:{intent.target_id}:{intent.deployment_operation_id}"


@dataclass(frozen=True)
class HealthGateEvidence:
    assessment: HealthAssessment
    evidence_reference: str
    owning_policy_profile_and_version: str
    policy_evidence_reference: str
    scope_binding: str
    policy_current: bool
    admission_eligible: bool

    def __post_init__(self) -> None:
        require_immutable_evidence_reference("health_gate.evidence_reference", self.evidence_reference)
        require_immutable_evidence_reference("health_gate.policy_evidence_reference", self.policy_evidence_reference)
        if not self.owning_policy_profile_and_version or not self.scope_binding:
            raise ReleaseError("health gate requires evidence, owning policy identity and exact scope")


@dataclass(frozen=True)
class RuntimeVerificationEvidence:
    evidence_reference: str
    evidence_current: bool
    scope_binding: str
    release_target_state_version: int
    observed_artifact_identity: str | None
    observed_configuration_generation: str | None
    runtime_profile_set: tuple[str, ...]
    runtime_admission_evidence_reference: str
    runtime_admission_current: bool
    configuration_currentness_evidence_reference: str
    configuration_current: bool
    release_policy_evidence_reference: str
    release_policy_current: bool
    verifier_authority_profile_and_version: str
    verifier_authority_evidence_reference: str
    verifier_authority_current: bool
    required_health_profile_ids: tuple[str, ...]
    health_gates: tuple[HealthGateEvidence, ...]
    vendor_controller_green: bool = False


def verify_runtime(
    intent: DeploymentIntent,
    evidence: RuntimeVerificationEvidence,
    *,
    expected_release_target_state_version: int,
) -> None:
    require_immutable_evidence_reference("runtime_verification.evidence_reference", evidence.evidence_reference)
    if not evidence.evidence_current:
        raise ReleaseError("runtime verification requires current durable evidence")
    expected_scope = runtime_verification_scope_for(intent)
    if evidence.scope_binding != expected_scope:
        raise ReleaseError("runtime verification evidence is bound to a different deployment scope")
    if evidence.release_target_state_version != expected_release_target_state_version:
        raise ReleaseError("runtime verification evidence is bound to a different release-target state version")
    if evidence.observed_artifact_identity is None:
        raise ReleaseError("running immutable artifact identity must be independently observed")
    if evidence.observed_artifact_identity != intent.artifact.canonical:
        raise ReleaseError("observed runtime artifact differs from approved immutable artifact")
    if evidence.observed_configuration_generation != intent.configuration.generation:
        raise ReleaseError("observed target configuration generation is not current intent")
    if tuple(evidence.runtime_profile_set) != tuple(intent.runtime_profile_set):
        raise ReleaseError("runtime profile set differs from approved release intent")

    for name, value in (
        ("runtime_admission_evidence_reference", evidence.runtime_admission_evidence_reference),
        ("configuration_currentness_evidence_reference", evidence.configuration_currentness_evidence_reference),
        ("release_policy_evidence_reference", evidence.release_policy_evidence_reference),
        ("verifier_authority_evidence_reference", evidence.verifier_authority_evidence_reference),
    ):
        require_immutable_evidence_reference(name, value)
    if not evidence.runtime_admission_current:
        raise ReleaseError("deployment success cannot substitute for current runtime admission")
    if not evidence.configuration_current:
        raise ReleaseError("target configuration currentness is not proven")
    if not evidence.release_policy_current:
        raise ReleaseError("release policy currentness is not proven")
    if not evidence.verifier_authority_profile_and_version or not evidence.verifier_authority_current:
        raise ReleaseError("runtime verifier authority/currentness is not proven")

    gates = {}
    for gate in evidence.health_gates:
        pid = gate.assessment.profile_id
        if pid in gates:
            raise ReleaseError(f"duplicate health gate evidence: {pid}")
        if gate.scope_binding != expected_scope:
            raise ReleaseError(f"health gate evidence is bound to a different deployment scope: {pid}")
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
