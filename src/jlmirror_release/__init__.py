"""Wave 3 vendor-neutral release and deployment authority primitives."""

from .authority import (
    CurrentAuthorityEvidence,
    DeploymentAdmissionEvidence,
    DeploymentAuthority,
    DeploymentObservation,
    DeploymentRecord,
    ReleaseTargetState,
    require_deployment_admission,
)
from .compatibility import (
    CellCompatibilityEvidence,
    MixedVersionMatrix,
    NoApplicableCaseEvidence,
    RolloutCompatibilityEvidence,
    require_rollout_compatibility,
)
from .configuration import ConfigurationValidationEvidence, require_validation_for_target
from .model import (
    ArtifactIdentity, DeploymentIntent, OutcomeClass, PromotionState, ReleaseError,
    SourceTrustClass, TargetConfiguration, ValidationScope,
)
from .provenance import (
    AcceptedSourceEvidence,
    BuildProvenanceEvidence,
    PromotionEvidence,
    require_promotion_authority,
    require_trusted_build_source,
    validate_build_provenance,
)
from .recovery import RecoveryClassificationEvidence, classify_change_outcome
from .verification import (
    EMPTY_RELIABILITY_FLOOR_AUTHORITY_PROFILE,
    RUNTIME_REQUIREMENTS_PRINCIPAL,
    EmptyReliabilityFloorJustification,
    HealthGateEvidence,
    RuntimeVerificationEvidence,
    RuntimeVerificationRequirements,
    verify_runtime,
)

__all__ = [
    "AcceptedSourceEvidence", "ArtifactIdentity", "BuildProvenanceEvidence", "CellCompatibilityEvidence",
    "ConfigurationValidationEvidence", "CurrentAuthorityEvidence", "DeploymentAdmissionEvidence",
    "DeploymentAuthority", "DeploymentIntent", "DeploymentObservation", "DeploymentRecord",
    "EMPTY_RELIABILITY_FLOOR_AUTHORITY_PROFILE", "EmptyReliabilityFloorJustification",
    "HealthGateEvidence", "MixedVersionMatrix", "NoApplicableCaseEvidence", "OutcomeClass",
    "PromotionEvidence", "PromotionState", "RUNTIME_REQUIREMENTS_PRINCIPAL",
    "RecoveryClassificationEvidence", "ReleaseError",
    "ReleaseTargetState", "RolloutCompatibilityEvidence", "RuntimeVerificationEvidence",
    "RuntimeVerificationRequirements", "SourceTrustClass", "TargetConfiguration", "ValidationScope",
    "classify_change_outcome", "require_deployment_admission", "require_promotion_authority",
    "require_rollout_compatibility", "require_trusted_build_source", "require_validation_for_target",
    "validate_build_provenance", "verify_runtime",
]
