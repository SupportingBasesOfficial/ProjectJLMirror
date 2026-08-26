"""Wave 3 vendor-neutral observability evidence primitives.

This package creates evidence records only. It is not a business, security,
placement, recovery, or release authority.
"""

from .model import (
    ComparisonOutcomeClass,
    CorrelationContext,
    HealthAssessment,
    HealthState,
    ObservationError,
    SignalFamily,
    SignalRecord,
    missing_health,
)
from .policy import ObservabilityBinding, require_product_applicability

__all__ = [
    "ComparisonOutcomeClass",
    "CorrelationContext",
    "HealthAssessment",
    "HealthState",
    "ObservationError",
    "SignalFamily",
    "SignalRecord",
    "missing_health",
    "ObservabilityBinding",
    "require_product_applicability",
]
