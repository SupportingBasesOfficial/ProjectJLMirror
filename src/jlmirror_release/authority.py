from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import RLock

from .compatibility import RolloutCompatibilityEvidence, require_rollout_compatibility
from .configuration import ConfigurationValidationEvidence, require_validation_for_target
from .model import DeploymentIntent, PromotionState, ReleaseError, SourceTrustClass
from .provenance import BuildProvenanceEvidence, PromotionEvidence, require_promotion_authority
from .verification import RuntimeVerificationEvidence, verify_runtime


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
class DeploymentRecord:
    intent: DeploymentIntent
    state: PromotionState
    resulting_release_target_state_version_or_pending: int | None = None


@dataclass(frozen=True)
class DeploymentAdmissionEvidence:
    provenance: BuildProvenanceEvidence
    promotion: PromotionEvidence
    configuration_validation: ConfigurationValidationEvidence
    rollout_compatibility: RolloutCompatibilityEvidence
    deployment_principal_class: str
    deployment_principal_authorized_current: bool
    release_policy_current: bool
    release_target_authority_current: bool
    required_reliability_gates_current: bool
    required_security_recovery_gates_current: bool


_TERMINAL_STATES = frozenset({PromotionState.COMPLETED, PromotionState.REJECTED, PromotionState.ABORTED, PromotionState.SUPERSEDED})


def require_deployment_admission(intent: DeploymentIntent, evidence: DeploymentAdmissionEvidence) -> None:
    require_promotion_authority(evidence.promotion, evidence.provenance)
    promotion = evidence.promotion
    if promotion.promotion_id != intent.promotion_id:
        raise ReleaseError("deployment intent is bound to a different promotion")
    if promotion.artifact_identity != intent.artifact.canonical:
        raise ReleaseError("deployment artifact differs from promoted artifact")
    if (promotion.target_configuration_identity != intent.configuration.identity or
        promotion.target_configuration_generation != intent.configuration.generation or
        promotion.target_configuration_semantic_profile != intent.configuration.semantic_profile):
        raise ReleaseError("deployment target configuration differs from promotion evidence")
    if promotion.target_environment_class != intent.target_environment_class:
        raise ReleaseError("deployment target environment differs from promotion evidence")
    if promotion.release_policy_profile_and_version != intent.release_policy_profile_and_version:
        raise ReleaseError("deployment release policy differs from promotion policy")

    config = evidence.configuration_validation
    if config.target_configuration != intent.configuration:
        raise ReleaseError("configuration validation evidence is bound to another target configuration")
    require_validation_for_target(config)

    rollout = evidence.rollout_compatibility
    if rollout.release_scope_id != intent.rollout_scope:
        raise ReleaseError("rollout compatibility evidence is bound to another scope")
    if rollout.validation_scope is not intent.validation_scope:
        raise ReleaseError("rollout validation scope differs from deployment intent")
    require_rollout_compatibility(rollout)

    if evidence.deployment_principal_class != "principal.release-deploy@1":
        raise ReleaseError("effectful deployment requires bounded release deploy principal")
    if not all((evidence.deployment_principal_authorized_current, evidence.release_policy_current,
                evidence.release_target_authority_current, evidence.required_reliability_gates_current,
                evidence.required_security_recovery_gates_current)):
        raise ReleaseError("deployment admission current-authority gates are incomplete")
    if not evidence.provenance.release_policy_current:
        raise ReleaseError("build provenance policy is not current")


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
        with self._lock:
            existing = self._records.get(intent.deployment_operation_id)
            if existing is not None:
                if existing.intent != intent:
                    raise ReleaseError("same deployment_operation_id with conflicting immutable semantics")
                return existing
            if intent.target_id != self._target.target_id:
                raise ReleaseError("deployment target identity mismatch")
            if intent.expected_release_target_state_version != self._target.release_target_state_version:
                raise ReleaseError("stale expected release target state version")
            if self._target.unresolved_operation_id is not None:
                raise ReleaseError("unresolved prior operation blocks a new effectful deployment")
            record = DeploymentRecord(intent=intent, state=PromotionState.DEPLOYING)
            self._records[intent.deployment_operation_id] = record
            self._target.unresolved_operation_id = intent.deployment_operation_id
            return record

    def observe_effect(self, operation_id: str, observation: DeploymentObservation, *, observed_artifact_identity: str | None = None, observed_configuration_generation: str | None = None, durable_target_evidence_reference: str | None = None, reconciliation_authority_current: bool = False) -> DeploymentRecord:
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
                if observation is DeploymentObservation.EFFECT_CONFIRMED and observed_artifact_identity == record.intent.artifact.canonical and observed_configuration_generation == record.intent.configuration.generation:
                    return record
                raise ReleaseError("effect already confirmed; only runtime verification may advance")
            if observation in {DeploymentObservation.AMBIGUOUS, DeploymentObservation.NOT_OBSERVED}:
                updated = DeploymentRecord(record.intent, PromotionState.RECONCILIATION_REQUIRED, record.resulting_release_target_state_version_or_pending)
                self._records[operation_id] = updated
                return updated

            resolving_reconciliation = record.state is PromotionState.RECONCILIATION_REQUIRED
            if not durable_target_evidence_reference:
                raise ReleaseError("confirmed/absent deployment outcome requires durable target evidence")
            if resolving_reconciliation and not reconciliation_authority_current:
                raise ReleaseError("reconciliation-required deployment cannot be resolved without current reconciliation authority")

            if observation is DeploymentObservation.EFFECT_ABSENT_PROVEN:
                self._clear_pending(operation_id)
                updated = DeploymentRecord(record.intent, PromotionState.ABORTED)
                self._records[operation_id] = updated
                return updated
            if observed_artifact_identity != record.intent.artifact.canonical:
                raise ReleaseError("runtime artifact identity does not match deployment intent")
            if observed_configuration_generation != record.intent.configuration.generation:
                raise ReleaseError("runtime configuration generation does not match deployment intent")

            next_version = self._target.release_target_state_version + 1
            self._target.release_target_state_version = next_version
            self._target.pending_artifact_identity = observed_artifact_identity
            self._target.pending_configuration_generation = observed_configuration_generation
            updated = DeploymentRecord(record.intent, PromotionState.RUNTIME_VERIFICATION, next_version)
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
            verify_runtime(record.intent, evidence)
            if self._target.pending_artifact_identity != record.intent.artifact.canonical:
                raise ReleaseError("pending target artifact differs from verified deployment intent")
            if self._target.pending_configuration_generation != record.intent.configuration.generation:
                raise ReleaseError("pending target configuration differs from verified deployment intent")
            self._target.current_artifact_identity = self._target.pending_artifact_identity
            self._target.current_configuration_generation = self._target.pending_configuration_generation
            self._clear_pending(operation_id)
            updated = DeploymentRecord(record.intent, PromotionState.COMPLETED, record.resulting_release_target_state_version_or_pending)
            self._records[operation_id] = updated
            return updated

    def _clear_pending(self, operation_id: str) -> None:
        if self._target.unresolved_operation_id == operation_id:
            self._target.unresolved_operation_id = None
        self._target.pending_artifact_identity = None
        self._target.pending_configuration_generation = None


def require_trusted_build_source(source_trust_class: SourceTrustClass, *, exact_source_state_proven: bool, accepted_change_authority_proven: bool) -> None:
    if source_trust_class is not SourceTrustClass.ACCEPTED_REVIEW_STATE:
        raise ReleaseError("untrusted candidate source cannot enter trusted build authority")
    if not exact_source_state_proven or not accepted_change_authority_proven:
        raise ReleaseError("accepted source requires exact state and change-authority evidence")
