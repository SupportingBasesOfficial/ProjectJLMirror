from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, Sequence

from .metric_current_state import CanonicalMetricValue
from .metric_definitions import MetricValueKind
from .source import OperationalEvidenceState, SyncOperationState, ZabbixProviderConfiguration
from .validation_worker import (
    AdmittedProviderEndpoint,
    CredentialResolutionError,
    CredentialResolver,
    EgressAdmissionError,
    OutboundAdmission,
    ProviderAuthenticationError,
    ProviderProtocolError,
    ProviderUnavailableError,
    ResolvedZabbixCredential,
)

MAX_HISTORY_ITEMS_PER_REQUEST = 512
MAX_HISTORY_ROWS_PER_REQUEST = 20_000
MAX_HISTORY_WINDOW_SECONDS = 86_400


class MetricHistoryFailureClass(StrEnum):
    CREDENTIAL_UNAVAILABLE = "credential.unavailable"
    PROVIDER_AUTHENTICATION_REJECTED = "provider.authentication_rejected"
    EGRESS_NOT_ADMITTED = "provider.egress_not_admitted"
    PROVIDER_UNAVAILABLE = "provider.unavailable"
    PROVIDER_PROTOCOL_INVALID = "provider.protocol_invalid"
    WINDOW_INVALID = "monitoring.history_window_invalid"
    PAGE_TRUNCATED = "monitoring.history_page_truncated"
    STREAM_NOT_CURRENT = "monitoring.history_stream_not_current"
    BINDING_RECONCILIATION_REQUIRED = "monitoring.binding_reconciliation_required"


class HistoryCoverageState(StrEnum):
    OPEN = "open"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    GAP = "gap"
    FINALIZED = "finalized"


@dataclass(frozen=True)
class HistoryMetricTarget:
    metric_definition_id: str
    monitoring_resource_id: str
    provider_external_ref: str
    value_kind: MetricValueKind
    history_value_type: int

    def __post_init__(self) -> None:
        if not self.metric_definition_id or not self.monitoring_resource_id:
            raise ValueError("canonical metric/resource identity is required")
        if not self.provider_external_ref or len(self.provider_external_ref) > 256:
            raise ValueError("provider_external_ref must be bounded non-empty text")
        if self.history_value_type not in (0, 1, 2, 3, 4, 5):
            raise ValueError("history_value_type must be a supported bounded Zabbix history type")


@dataclass(frozen=True)
class MetricHistoryWindow:
    time_from: int
    time_till: int

    def __post_init__(self) -> None:
        if self.time_from <= 0 or self.time_till < self.time_from:
            raise ValueError("history window must be positive and ordered")
        if self.time_till - self.time_from > MAX_HISTORY_WINDOW_SECONDS:
            raise ValueError("history window exceeds bounded implementation ceiling")


@dataclass(frozen=True)
class MetricHistoryClaim:
    claim_token: str
    tenant_id: str
    monitoring_sync_operation_id: str
    monitoring_source_id: str
    source_instance_generation: str
    configuration_revision: int
    scope_revision: int
    provider_instance_ref: str
    provider_configuration: ZabbixProviderConfiguration
    credential_binding_ref: str
    targets: tuple[HistoryMetricTarget, ...]
    window: MetricHistoryWindow


@dataclass(frozen=True)
class ZabbixHistoryEvidence:
    itemid: str
    clock: int
    ns: int
    raw_value: str

    def __post_init__(self) -> None:
        if not self.itemid or len(self.itemid) > 256:
            raise ValueError("itemid must be bounded non-empty text")
        if self.clock <= 0:
            raise ValueError("clock must be positive")
        if not 0 <= self.ns <= 999_999_999:
            raise ValueError("ns must be a valid nanosecond component")
        if len(self.raw_value) > 65_536:
            raise ValueError("raw history value exceeds bounded input ceiling")


@dataclass(frozen=True)
class AcceptedHistoryObservation:
    observation_id: str
    metric_definition_id: str
    monitoring_resource_id: str
    provider_external_ref: str
    provider_clock: int
    provider_ns: int
    value_kind: MetricValueKind
    canonical_value: CanonicalMetricValue


@dataclass(frozen=True)
class MetricHistoryResult:
    operation_state: SyncOperationState
    operational_evidence_state: OperationalEvidenceState
    coverage_state: HistoryCoverageState
    observations: tuple[AcceptedHistoryObservation, ...]
    failure_class: MetricHistoryFailureClass | None
    request_exhausted: bool
    egress_decision_ref: str | None = None
    credential_generation_ref: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.operation_state is SyncOperationState.SUCCEEDED


class ZabbixHistoryReader(Protocol):
    def read_history(
        self,
        endpoint: AdmittedProviderEndpoint,
        credential: ResolvedZabbixCredential,
        *,
        history_value_type: int,
        itemids: Sequence[str],
        time_from: int,
        time_till: int,
        max_rows: int,
    ) -> Sequence[ZabbixHistoryEvidence]:
        ...


class MonitoringMetricHistoryRepository(Protocol):
    def claim_metric_history(
        self,
        monitoring_sync_operation_id: str,
        *,
        claim_token: str,
    ) -> MetricHistoryClaim:
        ...

    def complete_metric_history(
        self,
        claim: MetricHistoryClaim,
        result: MetricHistoryResult,
    ) -> MetricHistoryResult:
        ...


def _degraded(
    failure_class: MetricHistoryFailureClass,
    *,
    evidence_state: OperationalEvidenceState,
    coverage_state: HistoryCoverageState = HistoryCoverageState.RECONCILIATION_REQUIRED,
    egress_decision_ref: str | None = None,
    credential_generation_ref: str | None = None,
) -> MetricHistoryResult:
    return MetricHistoryResult(
        SyncOperationState.RECONCILIATION_REQUIRED,
        evidence_state,
        coverage_state,
        (),
        failure_class,
        False,
        egress_decision_ref,
        credential_generation_ref,
    )


def read_metric_history_window(
    claim: MetricHistoryClaim,
    *,
    credential_resolver: CredentialResolver,
    outbound_admission: OutboundAdmission,
    reader: ZabbixHistoryReader,
) -> MetricHistoryResult:
    if not claim.targets or len(claim.targets) > MAX_HISTORY_ITEMS_PER_REQUEST:
        return _degraded(
            MetricHistoryFailureClass.PROVIDER_PROTOCOL_INVALID,
            evidence_state=OperationalEvidenceState.RECONCILIATION_REQUIRED,
        )

    by_type: dict[int, list[HistoryMetricTarget]] = {}
    identities: set[tuple[str, int]] = set()
    for target in claim.targets:
        identity = (target.provider_external_ref, target.history_value_type)
        if identity in identities:
            return _degraded(
                MetricHistoryFailureClass.PROVIDER_PROTOCOL_INVALID,
                evidence_state=OperationalEvidenceState.RECONCILIATION_REQUIRED,
            )
        identities.add(identity)
        by_type.setdefault(target.history_value_type, []).append(target)

    try:
        credential = credential_resolver.resolve_zabbix_api_token(claim.credential_binding_ref)
    except CredentialResolutionError:
        return _degraded(
            MetricHistoryFailureClass.CREDENTIAL_UNAVAILABLE,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
        )

    try:
        endpoint = outbound_admission.admit_zabbix_api(claim.provider_configuration)
    except EgressAdmissionError:
        return _degraded(
            MetricHistoryFailureClass.EGRESS_NOT_ADMITTED,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
            credential_generation_ref=credential.credential_generation_ref,
        )

    returned: list[ZabbixHistoryEvidence] = []
    try:
        for history_value_type, targets in sorted(by_type.items()):
            rows = tuple(
                reader.read_history(
                    endpoint,
                    credential,
                    history_value_type=history_value_type,
                    itemids=tuple(target.provider_external_ref for target in targets),
                    time_from=claim.window.time_from,
                    time_till=claim.window.time_till,
                    max_rows=MAX_HISTORY_ROWS_PER_REQUEST,
                )
            )
            if len(rows) >= MAX_HISTORY_ROWS_PER_REQUEST:
                return _degraded(
                    MetricHistoryFailureClass.PAGE_TRUNCATED,
                    evidence_state=OperationalEvidenceState.RECONCILIATION_REQUIRED,
                    egress_decision_ref=endpoint.egress_decision_ref,
                    credential_generation_ref=credential.credential_generation_ref,
                )
            allowed = {target.provider_external_ref for target in targets}
            if any(row.itemid not in allowed for row in rows):
                return _degraded(
                    MetricHistoryFailureClass.PROVIDER_PROTOCOL_INVALID,
                    evidence_state=OperationalEvidenceState.RECONCILIATION_REQUIRED,
                    egress_decision_ref=endpoint.egress_decision_ref,
                    credential_generation_ref=credential.credential_generation_ref,
                )
            returned.extend(rows)
    except ProviderAuthenticationError:
        return _degraded(
            MetricHistoryFailureClass.PROVIDER_AUTHENTICATION_REJECTED,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
            egress_decision_ref=endpoint.egress_decision_ref,
            credential_generation_ref=credential.credential_generation_ref,
        )
    except ProviderUnavailableError:
        return _degraded(
            MetricHistoryFailureClass.PROVIDER_UNAVAILABLE,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
            egress_decision_ref=endpoint.egress_decision_ref,
            credential_generation_ref=credential.credential_generation_ref,
        )
    except (ProviderProtocolError, TypeError, ValueError):
        return _degraded(
            MetricHistoryFailureClass.PROVIDER_PROTOCOL_INVALID,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
            egress_decision_ref=endpoint.egress_decision_ref,
            credential_generation_ref=credential.credential_generation_ref,
        )

    # Durable acceptance identity and canonical value parsing are repository-bound so
    # Current-first and History-first discovery converge under one authoritative tuple.
    return MetricHistoryResult(
        SyncOperationState.SUCCEEDED,
        OperationalEvidenceState.CURRENT,
        HistoryCoverageState.OPEN,
        (),
        None,
        True,
        endpoint.egress_decision_ref,
        credential.credential_generation_ref,
    )
