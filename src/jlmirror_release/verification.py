from __future__ import annotations

from dataclasses import dataclass

from .model import DeploymentIntent, ReleaseError


@dataclass(frozen=True)
class RuntimeVerificationEvidence:
    observed_artifact_identity: str | None
    observed_configuration_generation: str | None
    runtime_profile_set: tuple[str, ...]
    runtime_admission_current: bool
    health_evidence_present: bool
    vendor_controller_green: bool = False


def verify_runtime(intent: DeploymentIntent, evidence: RuntimeVerificationEvidence) -> None:
    """Verify actual runtime state; vendor/controller green is intentionally insufficient."""
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
    if not evidence.health_evidence_present:
        raise ReleaseError("required Phase 12 health evidence is missing")
    # vendor_controller_green is deliberately ignored as an authority input.
