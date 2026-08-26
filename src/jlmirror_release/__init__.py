"""Wave 3 vendor-neutral release and deployment authority primitives."""

from .authority import DeploymentAuthority, DeploymentObservation, DeploymentRecord, ReleaseTargetState, require_trusted_build_source
from .compatibility import CellCompatibilityEvidence, MixedVersionMatrix, RolloutCompatibilityEvidence, require_rollout_compatibility
from .configuration import ConfigurationValidationEvidence, require_validation_for_target
from .model import ArtifactIdentity, DeploymentIntent, OutcomeClass, PromotionState, ReleaseError, SourceTrustClass, TargetConfiguration, ValidationScope
from .provenance import BuildProvenanceEvidence, PromotionEvidence, require_promotion_authority, validate_build_provenance
from .recovery import RecoveryClassificationEvidence, classify_change_outcome
from .verification import RuntimeVerificationEvidence, verify_runtime

__all__ = [
    "ArtifactIdentity", "BuildProvenanceEvidence", "CellCompatibilityEvidence",
    "ConfigurationValidationEvidence", "DeploymentAuthority", "DeploymentIntent",
    "DeploymentObservation", "DeploymentRecord", "MixedVersionMatrix", "OutcomeClass",
    "PromotionEvidence", "PromotionState", "RecoveryClassificationEvidence", "ReleaseError",
    "ReleaseTargetState", "RolloutCompatibilityEvidence", "RuntimeVerificationEvidence",
    "SourceTrustClass", "TargetConfiguration", "ValidationScope", "classify_change_outcome",
    "require_promotion_authority", "require_rollout_compatibility", "require_trusted_build_source",
    "require_validation_for_target", "validate_build_provenance", "verify_runtime",
]
