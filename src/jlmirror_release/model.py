from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReleaseError(ValueError):
    """Raised when a release record attempts an unauthorized substitution."""


class SourceTrustClass(str, Enum):
    UNTRUSTED_CANDIDATE = "source.untrusted-candidate@1"
    ACCEPTED_REVIEW_STATE = "source.accepted-review-state@1"


class ValidationScope(str, Enum):
    GENERAL = "validation.general@1"
    REFERENCE_CELL = "validation.reference-cell@1"


class PromotionState(str, Enum):
    PROPOSED = "proposed"
    VALIDATING = "validating"
    ELIGIBLE = "eligible"
    APPROVED = "approved"
    DEPLOYING = "deploying"
    RUNTIME_VERIFICATION = "runtime_verification"
    COMPLETED = "completed"
    PAUSED = "paused"
    REJECTED = "rejected"
    ABORTED = "aborted"
    SUPERSEDED = "superseded"
    RECONCILIATION_REQUIRED = "reconciliation_required"


class OutcomeClass(str, Enum):
    ROLLBACK_ELIGIBLE = "rollback_eligible"
    FORWARD_RECOVERY_REQUIRED = "forward_recovery_required"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    IRREVERSIBLE_WITHOUT_GOVERNED_MIGRATION = "irreversible_without_governed_migration"


RELEASE_PRINCIPALS = frozenset({
    "principal.release-untrusted-validation@1", "principal.release-build@1",
    "principal.release-publish@1", "principal.release-promote@1",
    "principal.release-deploy@1", "principal.release-migrate@1",
    "principal.release-verify@1", "principal.release-emergency@1",
})
ALLOWED_ENVIRONMENT_CLASSES = frozenset({
    "environment.development@1", "environment.validation@1",
    "environment.production@1", "environment.recovery@1",
})
CANONICAL_RUNTIME_PROFILES = frozenset({
    "runtime.web-bff@1", "runtime.api@1", "runtime.worker@1", "runtime.realtime@1",
    "runtime.control-plane@1", "runtime.automation@1", "runtime.untrusted-parser@1",
    "runtime.migration-admin@1", "runtime.recovery@1", "runtime.edge-optional@1",
})


@dataclass(frozen=True)
class ArtifactIdentity:
    algorithm: str
    digest: str

    def __post_init__(self) -> None:
        if self.algorithm not in {"sha256", "sha512"}:
            raise ReleaseError("artifact identity must use an accepted cryptographic digest")
        expected_len = 64 if self.algorithm == "sha256" else 128
        if len(self.digest) != expected_len:
            raise ReleaseError("artifact digest length does not match algorithm")
        try:
            int(self.digest, 16)
        except ValueError as exc:
            raise ReleaseError("artifact digest must be hexadecimal") from exc

    @property
    def canonical(self) -> str:
        return f"{self.algorithm}:{self.digest.lower()}"


@dataclass(frozen=True)
class TargetConfiguration:
    identity: str
    generation: str
    semantic_profile: str

    def __post_init__(self) -> None:
        if not all((self.identity, self.generation, self.semantic_profile)):
            raise ReleaseError("target configuration identity/generation/profile are required")


@dataclass(frozen=True)
class DeploymentIntent:
    deployment_operation_id: str
    target_id: str
    expected_release_target_state_version: int
    artifact: ArtifactIdentity
    configuration: TargetConfiguration
    target_environment_class: str
    runtime_profile_set: tuple[str, ...]
    promotion_id: str
    release_policy_profile_and_version: str
    validation_scope: ValidationScope
    rollout_scope: str
    schema_state: str
    api_compatibility_family: str
    event_compatibility_set: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.deployment_operation_id or not self.target_id or not self.promotion_id:
            raise ReleaseError("stable deployment operation, promotion and target identity are required")
        if self.expected_release_target_state_version < 0:
            raise ReleaseError("expected target state version cannot be negative")
        if self.target_environment_class not in ALLOWED_ENVIRONMENT_CLASSES:
            raise ReleaseError("unknown logical target environment class")
        if not self.runtime_profile_set:
            raise ReleaseError("runtime_profile_set cannot be empty")
        if len(set(self.runtime_profile_set)) != len(self.runtime_profile_set):
            raise ReleaseError("runtime_profile_set cannot contain duplicate runtime profiles")
        unknown_runtime_profiles = set(self.runtime_profile_set) - CANONICAL_RUNTIME_PROFILES
        if unknown_runtime_profiles:
            raise ReleaseError(
                "runtime_profile_set contains unknown Phase 13 runtime profiles: "
                + ",".join(sorted(unknown_runtime_profiles))
            )
        if not self.release_policy_profile_and_version or not self.rollout_scope:
            raise ReleaseError("release policy and rollout scope are required")
        if not self.schema_state or not self.api_compatibility_family or not self.event_compatibility_set:
            raise ReleaseError("schema/API/event compatibility state is required")
