"""Wave 3 vendor-neutral observability evidence primitives.

This package creates evidence records only. It is not a business, security,
placement, recovery, or release authority.
"""

from .catalog import (
    ApplicabilityResolution,
    EXPECTED_RELIABILITY_PROFILE_IDS,
    RELIABILITY_OBSERVABILITY_JOINS,
    ReliabilityObservabilityJoin,
    join_for,
)
from .model import (
    ComparisonOutcomeClass,
    CorrelationContext,
    EvidencePlane,
    HealthAssessment,
    HealthState,
    ObservationError,
    SignalFamily,
    SignalRecord,
    missing_health,
)
from .pipeline import ObservabilityPipelineEvidence
from .policy import ObservabilityBinding, binding_for_reliability_profile, require_product_applicability

__all__ = [
    "ApplicabilityResolution", "ComparisonOutcomeClass", "CorrelationContext",
    "EXPECTED_RELIABILITY_PROFILE_IDS", "EvidencePlane", "HealthAssessment",
    "HealthState", "ObservationError", "ObservabilityBinding", "ObservabilityPipelineEvidence",
    "RELIABILITY_OBSERVABILITY_JOINS", "ReliabilityObservabilityJoin", "SignalFamily",
    "SignalRecord", "binding_for_reliability_profile", "join_for", "missing_health",
    "require_product_applicability",
]
