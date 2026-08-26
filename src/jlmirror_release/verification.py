from __future__ import annotations

from dataclasses import dataclass

from jlmirror_observability import (
    EXPECTED_RELIABILITY_PROFILE_IDS,
    HealthAssessment,
    HealthState,
    RELIABILITY_OBSERVABILITY_JOINS,
)

from .model import DeploymentIntent, ReleaseError
from .provenance import require_immutable_evidence_reference


def runtime_verification_scope_for(intent: DeploymentIntent) -> str:
    return f"deployment:{intent.target_id}:{intent.deployment_operation_id}"


@dataclass(frozen=True)
class RuntimeVerificationRequirements:
    """Current release-policy authority for the exact runtime-verification gate set."""

    authority_profile_and_version: str
    evidence_reference: str
    scope_binding: str
    release_target_state_version: int
    release_policy_profile_and_version: str
    release_policy_evidence_reference: str
    required_reliability_profile_ids: tuple[str, ...]
    required_health_profile_ids: tuple[str, ...]
    current: bool

    def validate_for(
        self,
        intent: DeploymentIntent,
        *,
        expected_release_target_state_version: int,
        expected_release_policy_evidence_reference: str,
    ) -> tuple[str, ...]:
        if self.authority_profile_and_version != intent.release_policy_profile_and_version:
            raise ReleaseError("runtime verification requirements must be owned by the current release-policy profile")
        require_immutable_evidence_reference("runtime_requirements.evidence_reference", self.evidence_reference)
        require_immutable_evidence_reference(
            "runtime_requirements.release_policy_evidence_reference",
            self.release_policy_evidence_reference,
        )
        if self.scope_binding != runtime_verification_scope_for(intent):
            raise ReleaseError("runtime verification requirements are bound to a different deployment scope")
        if self.release_target_state_version != expected_release_target_state_version:
            raise ReleaseError("runtime verification requirements are bound to a different release-target state version")
        if self.release_policy_profile_and_version != intent.release_policy_profile_and_version:
            raise ReleaseError("runtime verification requirements use a different release-policy profile")
        if self.release_policy_evidence_reference != expected_release_policy_evidence_reference:
            raise ReleaseError("runtime verification requirements are not bound to the current runtime release-policy evidence")
        if not self.current:
            raise ReleaseError("runtime verification requirements authority is not current")

        reliability_ids = self.required_reliability_profile_ids
        health_ids = self.required_health_profile_ids
        if not reliability_ids or len(set(reliability_ids)) != len(reliability_ids):
            raise ReleaseError("runtime verification requires a non-empty unique reliability gate set")
        if not health_ids or len(set(health_ids)) != len(health_ids):
            raise ReleaseError("runtime verification requires a non-empty unique health gate set")

        unknown_reliability = set(reliability_ids) - EXPECTED_RELIABILITY_PROFILE_IDS
        if unknown_reliability:
            raise ReleaseError(
                "runtime verification requirements reference unknown reliability profiles: "
                + ",".join(sorted(unknown_reliability))
            )

        known_health = {
            health_id
            for join in RELIABILITY_OBSERVABILITY_JOINS.values()
            for health_id in join.health_profile_ids
        }
        unknown_health = set(health_ids) - known_health
        if unknown_health:
            raise ReleaseError(
                "runtime verification requirements reference unknown Phase 12 health profiles: "
                + ",".join(sorted(unknown_health))
            )

        implied_health = {
            health_id
            for reliability_id in reliability_ids
            for health_id in RELIABILITY_OBSERVABILITY_JOINS[reliability_id].health_profile_ids
        }
        missing_implied = implied_health - set(health_ids)
        if missing_implied:
            raise ReleaseError(
                "runtime verification health gate set omits Phase 11 -> Phase 12 required joins: "
                + ",".join(sorted(missing_implied))
            )
        return tuple(health_ids)


@dataclass(frozen=True)
class HealthGateEvidence:
    assessment: HealthAssessment
    evidence_reference: str
    owning_policy_profile_and_version: str
    policy_evidence_reference: str
    scope_binding: str
    release_target_state_version: int
    policy_current: bool
    admission_eligible: bool

    def __post_init__(self) -> None:
        require_immutable_evidence_reference("health_gate.evidence_reference", self.evidence_reference)
        require_immutable_evidence_reference("health_gate.policy_evidence_reference", self.policy_evidence_reference)
        if not self.owning_policy_profile_and_version or not self.scope_binding:
            raise ReleaseError("health gate requires evidence, owning policy identity and exact scope")
        if self.release_target_state_version < 0:
            raise ReleaseError("health gate release-target state version cannot be negative")


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
    requirements: RuntimeVerificationRequirements
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

    required_health_profile_ids = evidence.requirements.validate_for(
        intent,
        expected_release_target_state_version=expected_release_target_state_version,
        expected_release_policy_evidence_reference=evidence.release_policy_evidence_reference,
    )

    gates: dict[str, HealthGateEvidence] = {}
    for gate in evidence.health_gates:
        pid = gate.assessment.profile_id
        if pid in gates:
            raise ReleaseError(f"duplicate health gate evidence: {pid}")
        if gate.scope_binding != expected_scope:
            raise ReleaseError(f"health gate evidence is bound to a different deployment scope: {pid}")
        if gate.release_target_state_version != expected_release_target_state_version:
            raise ReleaseError(f"health gate evidence is bound to a different release-target state version: {pid}")
        gates[pid] = gate

    required_set = set(required_health_profile_ids)
    actual_set = set(gates)
    if actual_set != required_set:
        missing = required_set - actual_set
        extra = actual_set - required_set
        details = []
        if missing:
            details.append("missing=" + ",".join(sorted(missing)))
        if extra:
            details.append("unexpected=" + ",".join(sorted(extra)))
        raise ReleaseError("runtime health evidence must match the exact release-policy-required gate set: " + ";".join(details))

    for profile_id in required_health_profile_ids:
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
