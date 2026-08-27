from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Optional
import re


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

PROFILE_ALLOWED_METRIC_DIMENSIONS: Mapping[str, frozenset[str]] = MappingProxyType({
    "obs.request.outcome@1": frozenset({"outcome_class", "operation_class"}),
    "obs.operation.state@1": frozenset({"state_class", "operation_class"}),
    "obs.async.progress@1": frozenset({"state_class", "workload_class", "saturation_class"}),
    "obs.async.transport@1": frozenset({"state_class", "workload_class", "saturation_class"}),
    "obs.provider.operation@1": frozenset({"outcome_class", "provider_class", "saturation_class"}),
    "obs.realtime.lifecycle@1": frozenset({"state_class", "saturation_class"}),
    "obs.webhook.delivery@1": frozenset({"outcome_class", "state_class", "saturation_class"}),
    "obs.telemetry.acceptance@1": frozenset({"outcome_class", "state_class", "saturation_class"}),
    "obs.observability.pipeline@1": frozenset({"state_class", "saturation_class"}),
    "obs.recovery.reconciliation@1": frozenset({"state_class", "failure_class"}),
    "obs.security.authority-freshness@1": frozenset({"state_class", "failure_class"}),
    "obs.message-equivalence.admission@1": frozenset({"comparison_outcome_class", "reliability_failure_class", "reliability_degradation_mode"}),
    "obs.message-equivalence.verifier@1": frozenset({"state_class", "saturation_class"}),
    "obs.configuration.generation@1": frozenset({"state_class"}),
    "obs.audit.responsibility-health@1": frozenset({"state_class"}),
    "obs.artifact.lifecycle@1": frozenset({"state_class", "saturation_class"}),
})

PROFILE_ALLOWED_DIAGNOSTIC_FIELDS: Mapping[str, frozenset[str]] = MappingProxyType({
    "obs.request.outcome@1": frozenset({"request_id", "trace_id"}),
    "obs.operation.state@1": frozenset({"operation_id", "trace_id"}),
    "obs.async.progress@1": frozenset({"operation_id", "message_id", "trace_id"}),
    "obs.async.transport@1": frozenset({"message_id", "trace_id"}),
    "obs.provider.operation@1": frozenset({"operation_id", "trace_id"}),
    "obs.realtime.lifecycle@1": frozenset({"connection_id", "trace_id"}),
    "obs.webhook.delivery@1": frozenset({"operation_id", "trace_id"}),
    "obs.telemetry.acceptance@1": frozenset({"operation_id", "trace_id"}),
    "obs.observability.pipeline@1": frozenset({"trace_id"}),
    "obs.recovery.reconciliation@1": frozenset({"operation_id", "trace_id"}),
    "obs.security.authority-freshness@1": frozenset({"trace_id", "authority_generation_ref"}),
    "obs.message-equivalence.admission@1": frozenset({"message_id", "trace_id", "comparison_generation_ref"}),
    "obs.message-equivalence.verifier@1": frozenset({"trace_id", "comparison_generation_ref"}),
    "obs.configuration.generation@1": frozenset({"configuration_generation", "trace_id"}),
    "obs.audit.responsibility-health@1": frozenset({"accountability_reference", "trace_id"}),
    "obs.artifact.lifecycle@1": frozenset({"artifact_id", "operation_id", "trace_id"}),
})

# Wave 3 intentionally keeps these implementation mapping classes finite. Extending them is a
# reviewed compatibility change, not an untrusted runtime/input decision.
ALLOWED_SIGNAL_CLASSIFICATIONS = frozenset({"internal", "protected"})
ALLOWED_TENANT_SCOPE_CLASSES = frozenset({
    "none", "bounded", "tenant_scoped_bounded", "cross_tenant_aggregate", "platform_bounded",
})
CANONICAL_OUTCOME_CLASSES = frozenset({
    "success", "denied", "invalid", "not_found_or_concealed", "throttled", "unavailable",
    "timed_out", "cancelled", "ambiguous_external_outcome", "reconciliation_required",
    "quarantined", "recovery_blocked", "compromised_or_untrusted", "internal_failure",
})
CANONICAL_FAILURE_CLASSES = frozenset({
    "unavailable", "slow_or_timed_out", "throttled", "saturated", "partitioned", "stale",
    "duplicate", "identity_conflict", "out_of_order_or_gap", "contract_permanent", "policy_denied",
    "poison_or_unknown", "external_outcome_ambiguous", "recovery_continuity_blocked",
    "compromised_or_untrusted", "governance_blocked",
})
CANONICAL_DEGRADATION_MODES = frozenset({
    "fail_closed", "fail_fast", "stale_tolerant", "queued_or_deferred", "shed_or_reject",
    "reconciliation_blocked", "resync_required", "capability_unavailable",
})
CANONICAL_HEALTH_REASON_CLASSES = frozenset({
    "healthy_or_eligible",
    "dependency_unavailable",
    "dependency_slow_or_saturated",
    "throttled_or_shed",
    "configuration_unavailable_or_stale",
    "current_authority_unprovable",
    "compromised_or_untrusted",
    "reconciliation_required",
    "recovery_continuity_blocked",
    "draining",
    "startup_or_warmup",
    "internal_failure",
})
# Phase 12 fixes the semantic reason classes above. `telemetry_missing` is the finite Wave 3
# mapping for the same phase's missing-data=unknown condition; it is not caller-defined taxonomy.
WAVE3_HEALTH_REASON_EXTENSIONS = frozenset({"telemetry_missing"})
REVIEWED_HEALTH_REASON_CLASSES = CANONICAL_HEALTH_REASON_CLASSES | WAVE3_HEALTH_REASON_EXTENSIONS
REVIEWED_OPERATION_CLASSES = frozenset({
    "api.read", "monitoring.accept", "audit.responsibility", "security.currentness",
    "message.equivalence",
})
# Dimensions with no accepted finite value registry remain unusable for metric emission until a
# later reviewed implementation mapping adds bounded values. A known key is not permission to emit
# arbitrary safe-looking tokens.
REVIEWED_METRIC_DIMENSION_VALUES: Mapping[str, frozenset[str]] = MappingProxyType({
    "failure_class": CANONICAL_FAILURE_CLASSES,
    "reliability_failure_class": CANONICAL_FAILURE_CLASSES,
    "reliability_degradation_mode": CANONICAL_DEGRADATION_MODES,
    "state_class": frozenset(),
    "workload_class": frozenset(),
    "provider_class": frozenset(),
    "saturation_class": frozenset(),
})

_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,95}$")
_OPERATION_CLASS_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}(?:\.[a-z][a-z0-9_-]{0,31})+$")
_DIAGNOSTIC_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_:@/-]{0,191}$")
FORBIDDEN_VALUE_PREFIXES = ("bearer ", "basic ")
FORBIDDEN_PAYLOAD_KEY_FRAGMENTS = (
    "password", "private_key", "refresh_token", "access_token", "authorization_code",
    "session_handle", "client_secret", "cookie", "authorization",
)


def _frozen_map(value: Mapping[str, str]) -> Mapping[str, str]:
    return MappingProxyType(dict(value))


def _validate_safe_token(name: str, value: str) -> None:
    if not isinstance(value, str) or not _SAFE_TOKEN_RE.fullmatch(value):
        raise ObservationError(f"metric dimension {name} must be a bounded semantic token")


def _validate_operation_class(value: str) -> None:
    if not isinstance(value, str) or not _OPERATION_CLASS_RE.fullmatch(value):
        raise ObservationError("operation_class must be a bounded namespaced semantic class")
    if value not in REVIEWED_OPERATION_CLASSES:
        raise ObservationError("operation_class is not in the reviewed finite Wave 3 registry")


def _validate_metric_dimension_value(name: str, value: str, *, operation_class: str) -> None:
    _validate_safe_token(name, value)
    if name == "operation_class":
        if value != operation_class:
            raise ObservationError("metric operation_class must equal the record's stable operation_class")
        return
    if name == "outcome_class":
        if value not in CANONICAL_OUTCOME_CLASSES:
            raise ObservationError("outcome_class is outside the accepted Phase 12 taxonomy")
        return
    if name == "comparison_outcome_class":
        if value not in {item.value for item in ComparisonOutcomeClass}:
            raise ObservationError("comparison_outcome_class is outside the accepted Phase 12 taxonomy")
        return
    allowed = REVIEWED_METRIC_DIMENSION_VALUES.get(name)
    if allowed is None or value not in allowed:
        raise ObservationError(f"metric dimension {name} value is not in a reviewed finite semantic registry")


def _validate_diagnostic_identifier(name: str, value: str) -> None:
    if not isinstance(value, str) or not _DIAGNOSTIC_ID_RE.fullmatch(value):
        raise ObservationError(f"diagnostic field {name} must be an opaque bounded identifier")
    if value.lower().startswith(FORBIDDEN_VALUE_PREFIXES):
        raise ObservationError(f"credential-shaped value forbidden in ordinary telemetry: {name}")


@dataclass(frozen=True)
class CorrelationContext:
    request_id: Optional[str] = None
    operation_id: Optional[str] = None
    trace_id: Optional[str] = None
    message_id: Optional[str] = None

    def as_diagnostic(self) -> Mapping[str, str]:
        result = {k: v for k, v in {
            "request_id": self.request_id, "operation_id": self.operation_id,
            "trace_id": self.trace_id, "message_id": self.message_id,
        }.items() if v is not None}
        for key, value in result.items():
            _validate_diagnostic_identifier(key, value)
        return MappingProxyType(result)


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
        _validate_operation_class(self.operation_class)
        if self.classification not in ALLOWED_SIGNAL_CLASSIFICATIONS:
            raise ObservationError("signal classification is not in the reviewed bounded Wave 3 mapping")
        if self.tenant_scope_class not in ALLOWED_TENANT_SCOPE_CLASSES:
            raise ObservationError("tenant_scope_class is not in the reviewed bounded Wave 3 mapping")

        unknown_dimensions = set(self.metric_dimensions) - PROFILE_ALLOWED_METRIC_DIMENSIONS[self.profile_id]
        if unknown_dimensions:
            raise ObservationError("metric dimension is not declared by profile: " + ",".join(sorted(unknown_dimensions)))
        for key, value in self.metric_dimensions.items():
            if any(fragment in key.lower() for fragment in FORBIDDEN_PAYLOAD_KEY_FRAGMENTS):
                raise ObservationError(f"secret-bearing metric field forbidden: {key}")
            _validate_metric_dimension_value(key, value, operation_class=self.operation_class)

        unknown_diagnostics = set(self.diagnostic_fields) - PROFILE_ALLOWED_DIAGNOSTIC_FIELDS[self.profile_id]
        if unknown_diagnostics:
            raise ObservationError("diagnostic field is not declared by profile: " + ",".join(sorted(unknown_diagnostics)))
        for key, value in self.diagnostic_fields.items():
            if any(fragment in key.lower() for fragment in FORBIDDEN_PAYLOAD_KEY_FRAGMENTS):
                raise ObservationError(f"secret-bearing field forbidden in ordinary telemetry: {key}")
            _validate_diagnostic_identifier(key, value)

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
        # A dataclass type hint is not runtime-enforced: without this explicit membership
        # check, any string (e.g. a caller/producer-supplied token) would silently pass
        # through as `state` and only fail to match the HealthState.UNKNOWN identity check
        # below on the evidence_complete=True path -- never actually being validated as one
        # of the six reviewed HealthState values. Sibling fields (profile_id, reason_class)
        # are already exact-membership checked; state was not, which is the gap this closes.
        if not isinstance(self.state, HealthState):
            raise ObservationError("health state must be a member of the reviewed HealthState enum")
        if self.reason_class not in REVIEWED_HEALTH_REASON_CLASSES:
            raise ObservationError("health reason_class is not in the reviewed finite Phase 12/Wave 3 registry")
        if not self.evidence_complete and self.state is not HealthState.UNKNOWN:
            raise ObservationError("incomplete evidence must be represented as health=unknown")

    @property
    def grants_authority(self) -> bool:
        return False


def missing_health(profile_id: str, reason_class: str = "telemetry_missing") -> HealthAssessment:
    return HealthAssessment(profile_id, HealthState.UNKNOWN, reason_class, False)
