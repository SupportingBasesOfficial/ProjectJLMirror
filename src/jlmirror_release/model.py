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
    "principal.release-untrusted-validation@1",
    "principal.release-build@1",
    "principal.release-publish@1",
    "principal.release-promote@1",
    "principal.release-deploy@1",
    "principal.release-migrate@1",
    "principal.release-verify@1",
    "principal.release-emergency@1",
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

    def __post_init__(self) -> None:
        if not self.deployment_operation_id or not self.target_id:
            raise ReleaseError("stable deployment operation and target identity are required")
        if self.expected_release_target_state_version < 0:
            raise ReleaseError("expected target state version cannot be negative")
        if not self.runtime_profile_set:
            raise ReleaseError("runtime_profile_set cannot be empty")
