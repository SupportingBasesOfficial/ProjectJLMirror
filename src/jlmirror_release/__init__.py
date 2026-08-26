"""Wave 3 vendor-neutral release and deployment authority primitives."""

from .authority import (
    DeploymentAuthority,
    DeploymentObservation,
    DeploymentRecord,
    ReleaseTargetState,
    require_trusted_build_source,
)
from .configuration import ConfigurationValidationEvidence, require_validation_for_target
from .model import (
    ArtifactIdentity,
    DeploymentIntent,
    OutcomeClass,
    PromotionState,
    ReleaseError,
    SourceTrustClass,
    TargetConfiguration,
    ValidationScope,
)
from .verification import RuntimeVerificationEvidence, verify_runtime

__all__ = [
    "ArtifactIdentity",
    "ConfigurationValidationEvidence",
    "DeploymentAuthority",
    "DeploymentIntent",
    "DeploymentObservation",
    "DeploymentRecord",
    "OutcomeClass",
    "PromotionState",
    "ReleaseError",
    "ReleaseTargetState",
    "RuntimeVerificationEvidence",
    "SourceTrustClass",
    "TargetConfiguration",
    "ValidationScope",
    "require_trusted_build_source",
    "require_validation_for_target",
    "verify_runtime",
]
