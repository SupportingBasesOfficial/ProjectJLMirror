from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .model import DeploymentIntent, PromotionState, ReleaseError, SourceTrustClass
from .verification import RuntimeVerificationEvidence, verify_runtime


class DeploymentObservation(str, Enum):
    NOT_OBSERVED = "not_observed"
    EFFECT_CONFIRMED = "effect_confirmed"
    EFFECT_ABSENT_PROVEN = "effect_absent_proven"
    AMBIGUOUS = "ambiguous"


@dataclass
class ReleaseTargetState:
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


_TERMINAL_STATES = frozenset({PromotionState.COMPLETED, PromotionState.REJECTED, PromotionState.ABORTED, PromotionState.SUPERSEDED})


class DeploymentAuthority:
    """Reference model for Phase 14 create-or-observe and target fencing."""

    def __init__(self, target: ReleaseTargetState) -> None:
        self.target = target
        self._records: dict[str, DeploymentRecord] = {}

    def create_or_observe(self, intent: DeploymentIntent) -> DeploymentRecord:
        existing = self._records.get(intent.deployment_operation_id)
        if existing is not None:
            if existing.intent != intent:
                raise ReleaseError("same deployment_operation_id with conflicting immutable semantics")
            return existing
        if intent.target_id != self.target.target_id:
            raise ReleaseError("deployment target identity mismatch")
        if intent.expected_release_target_state_version != self.target.release_target_state_version:
            raise ReleaseError("stale expected release target state version")
        if self.target.unresolved_operation_id is not None:
            raise ReleaseError("unresolved prior operation blocks a new effectful deployment")
        record = DeploymentRecord(intent=intent, state=PromotionState.DEPLOYING)
        self._records[intent.deployment_operation_id] = record
        self.target.unresolved_operation_id = intent.deployment_operation_id
        return record

    def observe_effect(self, operation_id: str, observation: DeploymentObservation, *, observed_artifact_identity: str | None = None, observed_configuration_generation: str | None = None) -> DeploymentRecord:
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

        if observation is DeploymentObservation.EFFECT_ABSENT_PROVEN:
            self._clear_pending(operation_id)
            updated = DeploymentRecord(record.intent, PromotionState.ABORTED)
            self._records[operation_id] = updated
            return updated

        if observed_artifact_identity != record.intent.artifact.canonical:
            raise ReleaseError("runtime artifact identity does not match deployment intent")
        if observed_configuration_generation != record.intent.configuration.generation:
            raise ReleaseError("runtime configuration generation does not match deployment intent")

        next_version = self.target.release_target_state_version + 1
        self.target.release_target_state_version = next_version
        self.target.pending_artifact_identity = observed_artifact_identity
        self.target.pending_configuration_generation = observed_configuration_generation
        updated = DeploymentRecord(record.intent, PromotionState.RUNTIME_VERIFICATION, next_version)
        self._records[operation_id] = updated
        return updated

    def complete_runtime_verification(self, operation_id: str, evidence: RuntimeVerificationEvidence) -> DeploymentRecord:
        try:
            record = self._records[operation_id]
        except KeyError as exc:
            raise ReleaseError("unknown deployment operation") from exc
        if record.state is PromotionState.COMPLETED:
            return record
        if record.state is not PromotionState.RUNTIME_VERIFICATION:
            raise ReleaseError("runtime verification can complete only after effect confirmation")
        if self.target.unresolved_operation_id != operation_id:
            raise ReleaseError("deployment operation lost current target resolution ownership")
        verify_runtime(record.intent, evidence)
        if self.target.pending_artifact_identity != record.intent.artifact.canonical:
            raise ReleaseError("pending target artifact differs from verified deployment intent")
        if self.target.pending_configuration_generation != record.intent.configuration.generation:
            raise ReleaseError("pending target configuration differs from verified deployment intent")
        self.target.current_artifact_identity = self.target.pending_artifact_identity
        self.target.current_configuration_generation = self.target.pending_configuration_generation
        self._clear_pending(operation_id)
        updated = DeploymentRecord(record.intent, PromotionState.COMPLETED, record.resulting_release_target_state_version_or_pending)
        self._records[operation_id] = updated
        return updated

    def _clear_pending(self, operation_id: str) -> None:
        if self.target.unresolved_operation_id == operation_id:
            self.target.unresolved_operation_id = None
        self.target.pending_artifact_identity = None
        self.target.pending_configuration_generation = None


def require_trusted_build_source(source_trust_class: SourceTrustClass, *, exact_source_state_proven: bool, accepted_change_authority_proven: bool) -> None:
    if source_trust_class is not SourceTrustClass.ACCEPTED_REVIEW_STATE:
        raise ReleaseError("untrusted candidate source cannot enter trusted build authority")
    if not exact_source_state_proven or not accepted_change_authority_proven:
        raise ReleaseError("accepted source requires exact state and change-authority evidence")
