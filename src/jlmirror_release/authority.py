from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .model import DeploymentIntent, PromotionState, ReleaseError, SourceTrustClass


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


@dataclass(frozen=True)
class DeploymentRecord:
    intent: DeploymentIntent
    state: PromotionState
    resulting_release_target_state_version_or_pending: int | None = None


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

    def observe_effect(
        self,
        operation_id: str,
        observation: DeploymentObservation,
        *,
        observed_artifact_identity: str | None = None,
        observed_configuration_generation: str | None = None,
    ) -> DeploymentRecord:
        record = self._records[operation_id]

        if observation is DeploymentObservation.AMBIGUOUS:
            updated = DeploymentRecord(record.intent, PromotionState.RECONCILIATION_REQUIRED)
            self._records[operation_id] = updated
            return updated

        if observation is DeploymentObservation.NOT_OBSERVED:
            # Lack of evidence is not proof of absence.
            updated = DeploymentRecord(record.intent, PromotionState.RECONCILIATION_REQUIRED)
            self._records[operation_id] = updated
            return updated

        if observation is DeploymentObservation.EFFECT_ABSENT_PROVEN:
            self.target.unresolved_operation_id = None
            updated = DeploymentRecord(record.intent, PromotionState.ABORTED)
            self._records[operation_id] = updated
            return updated

        if observed_artifact_identity != record.intent.artifact.canonical:
            raise ReleaseError("runtime artifact identity does not match deployment intent")
        if observed_configuration_generation != record.intent.configuration.generation:
            raise ReleaseError("runtime configuration generation does not match deployment intent")

        next_version = self.target.release_target_state_version + 1
        self.target.release_target_state_version = next_version
        self.target.current_artifact_identity = observed_artifact_identity
        self.target.current_configuration_generation = observed_configuration_generation
        self.target.unresolved_operation_id = None
        updated = DeploymentRecord(
            record.intent,
            PromotionState.RUNTIME_VERIFICATION,
            resulting_release_target_state_version_or_pending=next_version,
        )
        self._records[operation_id] = updated
        return updated


def require_trusted_build_source(
    source_trust_class: SourceTrustClass,
    *,
    exact_source_state_proven: bool,
    accepted_change_authority_proven: bool,
) -> None:
    if source_trust_class is not SourceTrustClass.ACCEPTED_REVIEW_STATE:
        raise ReleaseError("untrusted candidate source cannot enter trusted build authority")
    if not exact_source_state_proven or not accepted_change_authority_proven:
        raise ReleaseError("accepted source requires exact state and change-authority evidence")
