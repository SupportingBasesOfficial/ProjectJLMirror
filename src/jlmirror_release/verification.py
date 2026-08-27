from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from jlmirror_observability import (
    EXPECTED_RELIABILITY_PROFILE_IDS,
    HealthAssessment,
    HealthState,
    RELIABILITY_OBSERVABILITY_JOINS,
)

from .model import (
    CANONICAL_RUNTIME_PROFILES,
    CANONICAL_WORKER_SPECIALIZATIONS,
    DeploymentIntent,
    ReleaseError,
)
from .provenance import require_immutable_evidence_reference

RUNTIME_REQUIREMENTS_AUTHORITY_PROFILE = "release.runtime-verification-requirements@1"
RUNTIME_VERIFIER_PRINCIPAL = "principal.release-verify@1"

# Phase 13 fixes these as the minimum non-conditional Phase 11 reliability bindings for
# each concrete runtime profile. Conditional bindings (for example cache/secret/external
# dependencies that are only present for a specific deployment) remain additional
# pre-effect requirements selected by the current release-policy authority.
#
# OPEN (recorded 2026-08-26, deliberately not resolved by this wave -- requires an explicit
# product/security decision, not a silent implementation default): four profiles below
# (runtime.worker@1, runtime.untrusted-parser@1, runtime.edge-optional@1 and, in
# WORKER_SPECIALIZATION_MINIMUM_RELIABILITY_BINDINGS below, worker.reconciliation@1) carry an
# empty non-conditional floor. Combined with the fact that RuntimeVerificationRequirements
# (submitted inside the same DeploymentAdmissionEvidence payload as everything else the deploy
# submitter assembles) has no dedicated principal/authority-class field distinguishing it from
# the deploy principal -- unlike its sibling evidence classes (PromotionEvidence,
# BuildProvenanceEvidence, DeploymentAdmissionEvidence itself) -- a deployment declared with one
# of these four profiles can have its entire required_reliability_profile_ids/
# required_health_profile_ids set chosen by the same submitter that requests the deployment,
# with no floor tying it to the deployment's actual risk surface. This is architecturally
# consistent with the rest of this reference model (no evidence class here has real
# cryptographic principal separation; require_immutable_evidence_reference is a format check,
# not a resolution against an independently persisted record -- that is presumably delegated to
# an out-of-scope trusted evidence store). Closing it for real requires either: (a) a genuinely
# independent release-policy-authority evidence chain feeding required_health_profile_ids
# (not merely another self-declared field in the same submitter payload), or (b) an explicit,
# reviewed decision that the empty floor for these four profiles is intentional risk acceptance.
# Do not fill in a non-empty floor here without that decision -- an invented minimum would be a
# silent security-relevant judgment call, not a mechanical fix.
RUNTIME_PROFILE_MINIMUM_RELIABILITY_BINDINGS: Mapping[str, frozenset[str]] = MappingProxyType({
    "runtime.web-bff@1": frozenset({"rel.security-session-authority@1"}),
    "runtime.api@1": frozenset({
        "rel.cell-transactional-store@1",
        "rel.security-session-authority@1",
        "rel.performance-cache@1",
        "rel.configuration-authority@1",
    }),
    "runtime.worker@1": frozenset(),
    "runtime.realtime@1": frozenset({
        "rel.realtime-fanout@1",
        "rel.security-session-authority@1",
        "rel.replay-consume-state@1",
    }),
    "runtime.control-plane@1": frozenset({
        "rel.control-plane-placement@1",
        "rel.placement-reference-cache@1",
        "rel.configuration-authority@1",
    }),
    "runtime.automation@1": frozenset({"rel.privileged-operations@1"}),
    "runtime.untrusted-parser@1": frozenset(),
    "runtime.migration-admin@1": frozenset({
        "rel.privileged-operations@1",
        "rel.cell-transactional-store@1",
        "rel.configuration-authority@1",
    }),
    "runtime.recovery@1": frozenset({
        "rel.privileged-operations@1",
        "rel.control-plane-placement@1",
        "rel.replay-consume-state@1",
        "rel.secret-key-authority@1",
    }),
    "runtime.edge-optional@1": frozenset(),
})

# Phase 13 also fixes exact reliability bindings for concrete worker specializations.
# Entries described as "exact affected/additional profile when applicable" stay additive
# release-policy requirements rather than being guessed here. Reconciliation therefore has
# no universal fixed profile beyond the exact affected profile(s) that the pre-effect
# requirements authority must record for the concrete operation.
WORKER_SPECIALIZATION_MINIMUM_RELIABILITY_BINDINGS: Mapping[str, frozenset[str]] = MappingProxyType({
    "worker.outbox-publication@1": frozenset({"rel.outbox-publication@1", "rel.broker-job-transport@1"}),
    "worker.async-consumer@1": frozenset({"rel.consumer-inbox-effect@1", "rel.broker-job-transport@1"}),
    "worker.provider-integration@1": frozenset({"rel.external-provider@1"}),
    "worker.webhook-delivery@1": frozenset({"rel.webhook-delivery@1"}),
    "worker.reporting-export@1": frozenset({"rel.reporting-derived@1"}),
    "worker.customer-telemetry@1": frozenset({"rel.customer-telemetry-acceptance@1"}),
    "worker.artifact-lifecycle@1": frozenset({"rel.artifact-storage@1"}),
    "worker.reconciliation@1": frozenset(),
})

if frozenset(RUNTIME_PROFILE_MINIMUM_RELIABILITY_BINDINGS) != CANONICAL_RUNTIME_PROFILES:
    raise RuntimeError("Phase 13 runtime reliability binding table does not cover the canonical runtime profile set")
if frozenset(WORKER_SPECIALIZATION_MINIMUM_RELIABILITY_BINDINGS) != CANONICAL_WORKER_SPECIALIZATIONS:
    raise RuntimeError("Phase 13 worker reliability binding table does not cover the canonical specialization set")


def runtime_verification_scope_for(intent: DeploymentIntent) -> str:
    return f"deployment:{intent.target_id}:{intent.deployment_operation_id}"


def minimum_reliability_for_intent(intent: DeploymentIntent) -> frozenset[str]:
    """Return fixed Phase 13 runtime + worker reliability minimums for an exact deployment intent."""
    runtime_profile_set = intent.runtime_profile_set
    if not runtime_profile_set:
        raise ReleaseError("runtime profile set cannot be empty when deriving release reliability gates")
    if len(set(runtime_profile_set)) != len(runtime_profile_set):
        raise ReleaseError("runtime profile set cannot contain duplicate runtime profiles")
    unknown = set(runtime_profile_set) - CANONICAL_RUNTIME_PROFILES
    if unknown:
        raise ReleaseError(
            "runtime profile set contains unknown Phase 13 runtime profiles: " + ",".join(sorted(unknown))
        )
    required: set[str] = set()
    for runtime_profile_id in runtime_profile_set:
        required.update(RUNTIME_PROFILE_MINIMUM_RELIABILITY_BINDINGS[runtime_profile_id])

    if "runtime.worker@1" in runtime_profile_set:
        if not intent.worker_specialization_set:
            raise ReleaseError("runtime.worker@1 release requirements need exact worker specialization binding")
        for worker_specialization_id in intent.worker_specialization_set:
            required.update(WORKER_SPECIALIZATION_MINIMUM_RELIABILITY_BINDINGS[worker_specialization_id])
    return frozenset(required)


@dataclass(frozen=True)
class RuntimeVerificationRequirements:
    """Pre-effect release-policy-governed authority for the exact runtime-verification gate set."""

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
        expected_release_policy_evidence_reference: str | None = None,
    ) -> tuple[str, ...]:
        if self.authority_profile_and_version != RUNTIME_REQUIREMENTS_AUTHORITY_PROFILE:
            raise ReleaseError("runtime verification requirements use an unknown authority profile")
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
        if (expected_release_policy_evidence_reference is not None and
            self.release_policy_evidence_reference != expected_release_policy_evidence_reference):
            raise ReleaseError("runtime verification requirements are not bound to the deployment-admission release-policy evidence")
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

        mandatory_reliability = minimum_reliability_for_intent(intent)
        missing_mandatory_reliability = mandatory_reliability - set(reliability_ids)
        if missing_mandatory_reliability:
            raise ReleaseError(
                "runtime verification requirements omit mandatory Phase 13 reliability bindings: "
                + ",".join(sorted(missing_mandatory_reliability))
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
    release_policy_profile_and_version: str
    release_policy_evidence_reference: str
    release_policy_current: bool
    verifier_authority_profile_and_version: str
    verifier_authority_evidence_reference: str
    verifier_authority_current: bool
    health_gates: tuple[HealthGateEvidence, ...]
    vendor_controller_green: bool = False
    worker_specialization_set: tuple[str, ...] = ()


def verify_runtime(
    intent: DeploymentIntent,
    evidence: RuntimeVerificationEvidence,
    requirements: RuntimeVerificationRequirements,
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
    if tuple(evidence.worker_specialization_set) != tuple(intent.worker_specialization_set):
        raise ReleaseError("worker specialization set differs from approved release intent")

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
    if evidence.release_policy_profile_and_version != intent.release_policy_profile_and_version:
        raise ReleaseError("runtime verification is using a different release-policy profile")
    if evidence.release_policy_evidence_reference != requirements.release_policy_evidence_reference:
        raise ReleaseError(
            "runtime verification release-policy evidence differs from the pre-effect requirements policy lineage"
        )
    if not evidence.release_policy_current:
        raise ReleaseError("release policy currentness is not proven")
    if evidence.verifier_authority_profile_and_version != RUNTIME_VERIFIER_PRINCIPAL:
        raise ReleaseError("runtime verification requires the canonical release verifier principal")
    if not evidence.verifier_authority_current:
        raise ReleaseError("runtime verifier authority/currentness is not proven")

    required_health_profile_ids = requirements.validate_for(
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
