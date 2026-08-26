from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Optional


class ObservationError(ValueError):
    """Raised when evidence violates the accepted observability boundary."""


class SignalFamily(str, Enum):
    METRIC = "metric"
    LOG = "log"
    TRACE = "trace"
    EVENT = "event"
    HEALTH = "health"


class EvidencePlane(str, Enum):
    OPERATIONAL_OBSERVABILITY = "operational_observability"
    CUSTOMER_MONITORING = "customer_monitoring"
    AUDIT_RESPONSIBILITY = "audit_responsibility"


class HealthState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"
    DRAINING = "draining"
    QUARANTINED = "quarantined"


class ComparisonOutcomeClass(str, Enum):
    EQUIVALENT_DUPLICATE_PROVEN = "equivalent_duplicate_proven"
    IDENTITY_CONFLICT = "identity_conflict"
    EQUIVALENCE_UNKNOWN = "equivalence_unknown"
    VERIFIER_TEMPORARILY_UNAVAILABLE = "verifier_temporarily_unavailable"
    HISTORICAL_COMPARISON_CONTINUITY_BLOCKED = "historical_comparison_continuity_blocked"
    COMPARISON_AUTHORITY_COMPROMISED_OR_UNTRUSTED = "comparison_authority_compromised_or_untrusted"
    POISON_OR_CONTRACT_INVALID = "poison_or_contract_invalid"


CORE_SIGNAL_PROFILES = frozenset({
    "obs.request.outcome@1", "obs.operation.state@1", "obs.async.progress@1",
    "obs.async.transport@1", "obs.provider.operation@1", "obs.realtime.lifecycle@1",
    "obs.webhook.delivery@1", "obs.telemetry.acceptance@1", "obs.observability.pipeline@1",
    "obs.recovery.reconciliation@1", "obs.security.authority-freshness@1",
    "obs.message-equivalence.admission@1", "obs.message-equivalence.verifier@1",
    "obs.configuration.generation@1", "obs.audit.responsibility-health@1",
    "obs.artifact.lifecycle@1",
})

CORE_HEALTH_PROFILES = frozenset({
    "health.api-bff@1", "health.async-worker@1", "health.provider-adapter@1",
    "health.realtime@1", "health.webhook-delivery@1", "health.control-plane@1",
    "health.cell@1", "health.security-authority@1", "health.message-equivalence@1",
    "health.customer-telemetry@1", "health.audit-plane@1", "health.artifact@1",
    "health.observability-pipeline@1", "health.recovery@1",
})

CORE_SLI_PROFILES = frozenset({
    "sli.api.outcome@1", "sli.api.latency@1", "sli.async.progress@1",
    "sli.provider.outcome@1", "sli.realtime.delivery@1", "sli.webhook.convergence@1",
    "sli.customer-telemetry.acceptance@1", "sli.observability.integrity@1",
    "sli.control-plane.admission@1", "sli.cell.admission@1", "sli.artifact.delivery@1",
    "sli.recovery.convergence@1",
})

CORE_ALERT_PROFILES = frozenset({
    "alert.customer-impact@1", "alert.durable-progress@1", "alert.capacity-saturation@1",
    "alert.security-trust@1", "alert.recovery-continuity@1", "alert.telemetry-integrity@1",
})

SIGNAL_ALLOWED_FAMILIES: Mapping[str, frozenset[SignalFamily]] = MappingProxyType({
    "obs.request.outcome@1": frozenset({SignalFamily.METRIC, SignalFamily.LOG, SignalFamily.TRACE}),
    "obs.operation.state@1": frozenset({SignalFamily.EVENT, SignalFamily.METRIC, SignalFamily.LOG}),
    "obs.async.progress@1": frozenset({SignalFamily.METRIC, SignalFamily.EVENT}),
    "obs.async.transport@1": frozenset({SignalFamily.METRIC, SignalFamily.EVENT, SignalFamily.HEALTH}),
    "obs.provider.operation@1": frozenset({SignalFamily.METRIC, SignalFamily.TRACE, SignalFamily.LOG}),
    "obs.realtime.lifecycle@1": frozenset({SignalFamily.METRIC, SignalFamily.EVENT, SignalFamily.LOG}),
    "obs.webhook.delivery@1": frozenset({SignalFamily.METRIC, SignalFamily.EVENT, SignalFamily.LOG}),
    "obs.telemetry.acceptance@1": frozenset({SignalFamily.METRIC, SignalFamily.EVENT}),
    "obs.observability.pipeline@1": frozenset({SignalFamily.METRIC, SignalFamily.HEALTH, SignalFamily.EVENT}),
    "obs.recovery.reconciliation@1": frozenset({SignalFamily.METRIC, SignalFamily.EVENT, SignalFamily.HEALTH}),
    "obs.security.authority-freshness@1": frozenset({SignalFamily.HEALTH, SignalFamily.EVENT}),
    "obs.message-equivalence.admission@1": frozenset({SignalFamily.METRIC, SignalFamily.EVENT, SignalFamily.LOG}),
    "obs.message-equivalence.verifier@1": frozenset({SignalFamily.METRIC, SignalFamily.HEALTH, SignalFamily.EVENT}),
    "obs.configuration.generation@1": frozenset({SignalFamily.EVENT, SignalFamily.HEALTH}),
    "obs.audit.responsibility-health@1": frozenset({SignalFamily.HEALTH, SignalFamily.EVENT}),
    "obs.artifact.lifecycle@1": frozenset({SignalFamily.EVENT, SignalFamily.HEALTH, SignalFamily.METRIC}),
})

SIGNAL_EVIDENCE_PLANE: Mapping[str, EvidencePlane] = MappingProxyType({
    **{profile: EvidencePlane.OPERATIONAL_OBSERVABILITY for profile in CORE_SIGNAL_PROFILES},
    "obs.telemetry.acceptance@1": EvidencePlane.CUSTOMER_MONITORING,
    "obs.audit.responsibility-health@1": EvidencePlane.AUDIT_RESPONSIBILITY,
})

FORBIDDEN_METRIC_DIMENSIONS = frozenset({
    "request_id", "operation_id", "message_id", "connection_id", "artifact_id",
    "raw_url", "url", "query", "query_string", "token", "session_id", "secret",
    "signature", "authorization",
})
FORBIDDEN_PAYLOAD_KEY_FRAGMENTS = (
    "password", "private_key", "refresh_token", "access_token", "authorization_code",
    "session_handle", "client_secret",
)


def _frozen_map(value: Mapping[str, str]) -> Mapping[str, str]:
    return MappingProxyType(dict(value))


@dataclass(frozen=True)
class CorrelationContext:
    request_id: Optional[str] = None
    operation_id: Optional[str] = None
    trace_id: Optional[str] = None
    message_id: Optional[str] = None

    def as_diagnostic(self) -> Mapping[str, str]:
        return MappingProxyType({k: v for k, v in {
            "request_id": self.request_id, "operation_id": self.operation_id,
            "trace_id": self.trace_id, "message_id": self.message_id,
        }.items() if v is not None})


@dataclass(frozen=True)
class SignalRecord:
    profile_id: str
    family: SignalFamily
    operation_class: str
    classification: str
    tenant_scope_class: str
    metric_dimensions: Mapping[str, str] = field(default_factory=dict)
    diagnostic_fields: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.profile_id not in CORE_SIGNAL_PROFILES:
            raise ObservationError(f"unknown signal profile: {self.profile_id}")
        if self.family not in SIGNAL_ALLOWED_FAMILIES[self.profile_id]:
            raise ObservationError(f"signal family {self.family.value} is not allowed for {self.profile_id}")
        if not self.operation_class or not self.classification or not self.tenant_scope_class:
            raise ObservationError("operation_class, classification and tenant_scope_class are required")
        bad = set(self.metric_dimensions) & FORBIDDEN_METRIC_DIMENSIONS
        if bad:
            raise ObservationError("unbounded/sensitive evidence cannot be a metric dimension: " + ",".join(sorted(bad)))
        for key in list(self.metric_dimensions) + list(self.diagnostic_fields):
            lower = key.lower()
            if any(fragment in lower for fragment in FORBIDDEN_PAYLOAD_KEY_FRAGMENTS):
                raise ObservationError(f"secret-bearing field forbidden in ordinary telemetry: {key}")
        object.__setattr__(self, "metric_dimensions", _frozen_map(self.metric_dimensions))
        object.__setattr__(self, "diagnostic_fields", _frozen_map(self.diagnostic_fields))

    @property
    def evidence_plane(self) -> EvidencePlane:
        return SIGNAL_EVIDENCE_PLANE[self.profile_id]

    @property
    def grants_authority(self) -> bool:
        return False


@dataclass(frozen=True)
class HealthAssessment:
    profile_id: str
    state: HealthState
    reason_class: str
    evidence_complete: bool

    def __post_init__(self) -> None:
        if self.profile_id not in CORE_HEALTH_PROFILES:
            raise ObservationError(f"unknown health profile: {self.profile_id}")
        if not self.reason_class:
            raise ObservationError("reason_class is required")
        if not self.evidence_complete and self.state is not HealthState.UNKNOWN:
            raise ObservationError("incomplete evidence must be represented as health=unknown")

    @property
    def grants_authority(self) -> bool:
        return False


def missing_health(profile_id: str, reason_class: str = "telemetry_missing") -> HealthAssessment:
    return HealthAssessment(profile_id, HealthState.UNKNOWN, reason_class, False)
