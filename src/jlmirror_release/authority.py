from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from threading import RLock

from .compatibility import RolloutCompatibilityEvidence, require_rollout_compatibility
from .configuration import ConfigurationValidationEvidence, require_validation_for_target
from .model import DeploymentIntent, PromotionState, ReleaseError
from .provenance import (
    BuildProvenanceEvidence, PromotionEvidence, require_immutable_evidence_reference,
    require_promotion_authority,
)
from .verification import RuntimeVerificationEvidence, RuntimeVerificationRequirements, verify_runtime


class DeploymentObservation(str, Enum):
    NOT_OBSERVED = "not_observed"
    EFFECT_CONFIRMED = "effect_confirmed"
    EFFECT_ABSENT_PROVEN = "effect_absent_proven"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class ReleaseTargetState:
    target_id: str
    release_target_state_version: int
    current_artifact_identity: str | None = None
    current_configuration_generation: str | None = None
    unresolved_operation_id: str | None = None
    pending_artifact_identity: str | None = None
    pending_configuration_generation: str | None = None


@dataclass
class _MutableReleaseTargetState:
    target_id: str
    release_target_state_version: int
    current_artifact_identity: str | None = None
    current_configuration_generation: str | None = None
    unresolved_operation_id: str | None = None
    pending_artifact_identity: str | None = None
    pending_configuration_generation: str | None = None


@dataclass(frozen=True)
class CurrentAuthorityEvidence:
    gate_id: str
    authority_profile_and_version: str
    evidence_reference: str
    scope_binding: str
    release_target_state_version: int
    current: bool

    @staticmethod
    def scope_for(intent: DeploymentIntent) -> str:
        return f"deployment:{intent.target_id}:{intent.deployment_operation_id}"

    def validate_for(
        self,
        intent: DeploymentIntent,
        expected_gate_id: str,
        *,
        expected_target_state_version: int | None = None,
        expected_authority_profile_and_version: str | None = None,
    ) -> None:
        if self.gate_id != expected_gate_id:
            raise ReleaseError(f"release authority evidence gate mismatch: expected {expected_gate_id}")
        if not self.authority_profile_and_version:
            raise ReleaseError(f"{expected_gate_id} requires an owning authority profile/version")
        if (expected_authority_profile_and_version is not None and
            self.authority_profile_and_version != expected_authority_profile_and_version):
            raise ReleaseError(
                f"{expected_gate_id} authority evidence uses a different owning profile/version"
            )
        require_immutable_evidence_reference(f"{expected_gate_id}.evidence_reference", self.evidence_reference)
        if self.scope_binding != self.scope_for(intent):
            raise ReleaseError(f"{expected_gate_id} authority evidence is bound to a different deployment scope")
        expected_version = (
            intent.expected_release_target_state_version
            if expected_target_state_version is None
            else expected_target_state_version
        )
        if self.release_target_state_version != expected_version:
            raise ReleaseError(f"{expected_gate_id} authority evidence is bound to a different target-state version")
        if not self.current:
            raise ReleaseError(f"{expected_gate_id} authority evidence is not current")


@dataclass(frozen=True)
class DeploymentRecord:
    intent: DeploymentIntent
    state: PromotionState
    promotion_evidence_reference: str
    configuration_validation_evidence_reference: str
    rollout_compatibility_evidence_reference: str
    admission_gate_evidence_references: tuple[str, ...]
    runtime_verification_requirements: RuntimeVerificationRequirements
    runtime_requirements_evidence_reference: str
    resulting_release_target_state_version_or_pending: int | None = None
    durable_target_evidence_reference: str | None = None
    observed_artifact_identity: str | None = None
    observed_configuration_generation: str | None = None
    runtime_verification_evidence_reference: str | None = None
    reconciliation_authority_evidence_reference: str | None = None


@dataclass(frozen=True)
class DeploymentAdmissionEvidence:
    provenance: BuildProvenanceEvidence
    promotion: PromotionEvidence
    configuration_validation: ConfigurationValidationEvidence
    rollout_compatibility: RolloutCompatibilityEvidence
    deployment_principal_class: str
    current_authority_gates: tuple[CurrentAuthorityEvidence, ...]
    runtime_verification_requirements: RuntimeVerificationRequirements


_REQUIRED_ADMISSION_GATES = frozenset({
    "deployment_principal",
    "release_policy",
    "release_target_authority",
    "reliability",
    "security_recovery",
})
_TERMINAL_STATES = frozenset({PromotionState.COMPLETED, PromotionState.REJECTED, PromotionState.ABORTED, PromotionState.SUPERSEDED})


def _validated_admission_gate_map(
    intent: DeploymentIntent,
    evidence: DeploymentAdmissionEvidence,
) -> dict[str, CurrentAuthorityEvidence]:
    gates: dict[str, CurrentAuthorityEvidence] = {}
    for gate in evidence.current_authority_gates:
        if gate.gate_id in gates:
            raise ReleaseError(f"duplicate deployment admission authority gate: {gate.gate_id}")
        gates[gate.gate_id] = gate
    if set(gates) != _REQUIRED_ADMISSION_GATES:
        missing = sorted(_REQUIRED_ADMISSION_GATES - set(gates))
        extra = sorted(set(gates) - _REQUIRED_ADMISSION_GATES)
        raise ReleaseError(f"deployment admission authority gate set mismatch: missing={missing} extra={extra}")

    fixed_owner_profiles = {
        "deployment_principal": "principal.release-deploy@1",
        "release_policy": intent.release_policy_profile_and_version,
    }
    for gate_id, gate in gates.items():
        gate.validate_for(
            intent,
            gate_id,
            expected_authority_profile_and_version=fixed_owner_profiles.get(gate_id),
        )
    return gates


def require_deployment_admission(intent: DeploymentIntent, evidence: DeploymentAdmissionEvidence) -> None:
    require_promotion_authority(evidence.promotion, evidence.provenance)
    promotion = evidence.promotion
    if promotion.promotion_id != intent.promotion_id:
        raise ReleaseError("deployment intent is bound to a different promotion")
    if promotion.artifact_identity != intent.artifact.canonical:
        raise ReleaseError("deployment artifact differs from promoted artifact")
    if promotion.target_id != intent.target_id:
        raise ReleaseError("promotion target differs from deployment target")
    if promotion.target_environment_class != intent.target_environment_class:
        raise ReleaseError("deployment target environment differs from promotion evidence")
    if promotion.validation_scope is not intent.validation_scope:
        raise ReleaseError("promotion validation scope differs from deployment intent")
    if promotion.rollout_scope_id != intent.rollout_scope:
        raise ReleaseError("promotion rollout scope differs from deployment intent")
    if tuple(promotion.runtime_profile_set) != tuple(intent.runtime_profile_set):
        raise ReleaseError("promotion runtime profile set differs from deployment intent")
    if (promotion.target_configuration_identity != intent.configuration.identity or
        promotion.target_configuration_generation != intent.configuration.generation or
        promotion.target_configuration_semantic_profile != intent.configuration.semantic_profile):
        raise ReleaseError("deployment target configuration differs from promotion evidence")
    if promotion.release_policy_profile_and_version != intent.release_policy_profile_and_version:
        raise ReleaseError("deployment release policy differs from promotion policy")
    if promotion.schema_state != intent.schema_state:
        raise ReleaseError("promotion schema compatibility state differs from deployment intent")
    if promotion.api_compatibility_family != intent.api_compatibility_family:
        raise ReleaseError("promotion API compatibility family differs from deployment intent")
    if tuple(promotion.event_compatibility_set) != tuple(intent.event_compatibility_set):
        raise ReleaseError("promotion event compatibility set differs from deployment intent")

    config = evidence.configuration_validation
    if config.target_configuration != intent.configuration:
        raise ReleaseError("configuration validation evidence is bound to another target configuration")
    if config.validation_scope is not intent.validation_scope:
        raise ReleaseError("configuration validation evidence is bound to another validation scope")
    require_validation_for_target(config)
    if promotion.configuration_validation_evidence_reference != config.evidence_reference:
        raise ReleaseError("promotion and deployment use different configuration validation evidence")

    rollout = evidence.rollout_compatibility
    if rollout.release_scope_id != intent.rollout_scope:
        raise ReleaseError("rollout compatibility evidence is bound to another scope")
    if rollout.validation_scope is not intent.validation_scope:
        raise ReleaseError("rollout validation scope differs from deployment intent")
    require_rollout_compatibility(rollout)
    if promotion.rollout_compatibility_evidence_reference != rollout.evidence_reference:
        raise ReleaseError("promotion and deployment use different rollout compatibility evidence")

    cell = rollout.cell_compatibility
    if cell.applicable:
        if (promotion.cell_compatibility_metadata_identity != cell.metadata_identity or
            promotion.cell_compatibility_metadata_generation != cell.metadata_generation):
            raise ReleaseError("promotion and deployment use different cell compatibility metadata")
    elif (promotion.cell_compatibility_metadata_identity is not None or
          promotion.cell_compatibility_metadata_generation is not None):
        raise ReleaseError("promotion cannot bind cell compatibility metadata when rollout marks it non-applicable")

    if evidence.deployment_principal_class != "principal.release-deploy@1":
        raise ReleaseError("effectful deployment requires bounded release deploy principal")
    gate_map = _validated_admission_gate_map(intent, evidence)
    if not evidence.provenance.release_policy_current:
        raise ReleaseError("build provenance policy is not current")

    evidence.runtime_verification_requirements.validate_for(
        intent,
        expected_release_target_state_version=intent.expected_release_target_state_version + 1,
        expected_release_policy_evidence_reference=gate_map["release_policy"].evidence_reference,
    )


class DeploymentAuthority:
    """Reference model for Phase 14 admission, create-or-observe and target fencing."""

    def __init__(self, target: ReleaseTargetState) -> None:
        if target.release_target_state_version < 0 or not target.target_id:
            raise ReleaseError("invalid initial release target state")
        self._target = _MutableReleaseTargetState(**target.__dict__)
        self._records: dict[str, DeploymentRecord] = {}
        self._lock = RLock()

    @property
    def target(self) -> ReleaseTargetState:
        with self._lock:
            return ReleaseTargetState(**self._target.__dict__)

    def create_or_observe(self, intent: DeploymentIntent, admission: DeploymentAdmissionEvidence) -> DeploymentRecord:
        require_deployment_admission(intent, admission)
        gate_map = _validated_admission_gate_map(intent, admission)
        with self._lock:
            existing = self._records.get(intent.deployment_operation_id)
            if existing is not None:
                if existing.intent != intent:
                    raise ReleaseError("same deployment_operation_id with conflicting immutable semantics")
                if existing.runtime_verification_requirements != admission.runtime_verification_requirements:
                    raise ReleaseError("same deployment operation cannot replace persisted runtime verification requirements")
                return existing
            if intent.target_id != self._target.target_id:
                raise ReleaseError("deployment target identity mismatch")
            if intent.expected_release_target_state_version != self._target.release_target_state_version:
                raise ReleaseError("stale expected release target state version")
            if self._target.unresolved_operation_id is not None:
                raise ReleaseError("unresolved prior operation blocks a new effectful deployment")
            record = DeploymentRecord(
                intent=intent,
                state=PromotionState.DEPLOYING,
                promotion_evidence_reference=admission.promotion.promotion_evidence_reference,
                configuration_validation_evidence_reference=admission.configuration_validation.evidence_reference,
                rollout_compatibility_evidence_reference=admission.rollout_compatibility.evidence_reference,
                admission_gate_evidence_references=tuple(gate_map[key].evidence_reference for key in sorted(gate_map)),
                runtime_verification_requirements=admission.runtime_verification_requirements,
                runtime_requirements_evidence_reference=admission.runtime_verification_requirements.evidence_reference,
            )
            self._records[intent.deployment_operation_id] = record
            self._target.unresolved_operation_id = intent.deployment_operation_id
            return record

    def observe_effect(
        self,
        operation_id: str,
        observation: DeploymentObservation,
        *,
        observed_artifact_identity: str | None = None,
        observed_configuration_generation: str | None = None,
        durable_target_evidence_reference: str | None = None,
        reconciliation_authority: CurrentAuthorityEvidence | None = None,
    ) -> DeploymentRecord:
        with self._lock:
            try:
                record = self._records[operation_id]
            except KeyError as exc:
                raise ReleaseError("unknown deployment operation") from exc
            if record.state in _TERMINAL_STATES:
                if record.state is PromotionState.ABORTED and observation is DeploymentObservation.EFFECT_ABSENT_PROVEN:
                    return record
                raise ReleaseError("terminal deployment outcome cannot be reinterpreted")
            if record.state is PromotionState.RUNTIME_VERIFICATION:
                if (observation is DeploymentObservation.EFFECT_CONFIRMED and
                    observed_artifact_identity == record.intent.artifact.canonical and
                    observed_configuration_generation == record.intent.configuration.generation):
                    return record
                raise ReleaseError("effect already confirmed; only runtime verification may advance")
            if observation in {DeploymentObservation.AMBIGUOUS, DeploymentObservation.NOT_OBSERVED}:
                updated = replace(record, state=PromotionState.RECONCILIATION_REQUIRED)
                self._records[operation_id] = updated
                return updated

            resolving_reconciliation = record.state is PromotionState.RECONCILIATION_REQUIRED
            if durable_target_evidence_reference is None:
                raise ReleaseError("confirmed/absent deployment outcome requires durable target evidence")
            require_immutable_evidence_reference("durable_target_evidence_reference", durable_target_evidence_reference)
            reconciliation_ref = record.reconciliation_authority_evidence_reference
            if resolving_reconciliation:
                if reconciliation_authority is None:
                    raise ReleaseError("reconciliation-required deployment needs scoped current authority evidence")
                reconciliation_authority.validate_for(
                    record.intent,
                    "reconciliation_authority",
                    expected_target_state_version=self._target.release_target_state_version,
                )
                reconciliation_ref = reconciliation_authority.evidence_reference

            if observation is DeploymentObservation.EFFECT_ABSENT_PROVEN:
                self._clear_pending(operation_id)
                updated = replace(
                    record,
                    state=PromotionState.ABORTED,
                    durable_target_evidence_reference=durable_target_evidence_reference,
                    reconciliation_authority_evidence_reference=reconciliation_ref,
                )
                self._records[operation_id] = updated
                return updated
            if observed_artifact_identity != record.intent.artifact.canonical:
                raise ReleaseError("runtime artifact identity does not match deployment intent")
            if observed_configuration_generation != record.intent.configuration.generation:
                raise ReleaseError("runtime configuration generation does not match deployment intent")

            next_version = self._target.release_target_state_version + 1
            if next_version != record.runtime_verification_requirements.release_target_state_version:
                raise ReleaseError("confirmed deployment target version differs from pre-authorized runtime verification requirements")
            self._target.release_target_state_version = next_version
            self._target.pending_artifact_identity = observed_artifact_identity
            self._target.pending_configuration_generation = observed_configuration_generation
            updated = replace(
                record,
                state=PromotionState.RUNTIME_VERIFICATION,
                resulting_release_target_state_version_or_pending=next_version,
                durable_target_evidence_reference=durable_target_evidence_reference,
                observed_artifact_identity=observed_artifact_identity,
                observed_configuration_generation=observed_configuration_generation,
                reconciliation_authority_evidence_reference=reconciliation_ref,
            )
            self._records[operation_id] = updated
            return updated

    def complete_runtime_verification(self, operation_id: str, evidence: RuntimeVerificationEvidence) -> DeploymentRecord:
        with self._lock:
            try:
                record = self._records[operation_id]
            except KeyError as exc:
                raise ReleaseError("unknown deployment operation") from exc
            if record.state is PromotionState.COMPLETED:
                return record
            if record.state is not PromotionState.RUNTIME_VERIFICATION:
                raise ReleaseError("runtime verification can complete only after effect confirmation")
            if self._target.unresolved_operation_id != operation_id:
                raise ReleaseError("deployment operation lost current target resolution ownership")
            verify_runtime(
                record.intent,
                evidence,
                record.runtime_verification_requirements,
                expected_release_target_state_version=self._target.release_target_state_version,
            )
            if self._target.pending_artifact_identity != record.intent.artifact.canonical:
                raise ReleaseError("pending target artifact differs from verified deployment intent")
            if self._target.pending_configuration_generation != record.intent.configuration.generation:
                raise ReleaseError("pending target configuration differs from verified deployment intent")
            self._target.current_artifact_identity = self._target.pending_artifact_identity
            self._target.current_configuration_generation = self._target.pending_configuration_generation
            self._clear_pending(operation_id)
            updated = replace(
                record,
                state=PromotionState.COMPLETED,
                runtime_verification_evidence_reference=evidence.evidence_reference,
            )
            self._records[operation_id] = updated
            return updated

    def _clear_pending(self, operation_id: str) -> None:
        if self._target.unresolved_operation_id == operation_id:
            self._target.unresolved_operation_id = None
        self._target.pending_artifact_identity = None
        self._target.pending_configuration_generation = None
