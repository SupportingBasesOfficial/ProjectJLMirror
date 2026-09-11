from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, Sequence

from .metric_definitions import MetricValueKind
from .source import OperationalEvidenceState, SyncOperationState, opaque_token

MAX_CURRENT_SAMPLES_PER_BATCH = 200_000
MAX_RAW_CURRENT_VALUE_LENGTH = 65_536


class CurrentStateFailureClass(StrEnum):
    PROVIDER_PROTOCOL_INVALID = "provider.protocol_invalid"
    PROVIDER_SAMPLE_TIME_INVALID = "provider.sample_time_invalid"
    VALUE_PARSE_INVALID = "provider.value_parse_invalid"
    DEFINITION_NOT_CURRENT = "monitoring.definition_not_current"
    SCOPE_NOT_CURRENT = "monitoring.scope_not_current"
    BINDING_RECONCILIATION_REQUIRED = "monitoring.binding_reconciliation_required"
    POLL_SUPERSEDED = "monitoring.poll_superseded"


@dataclass(frozen=True)
class ZabbixCurrentValueEvidence:
    itemid: str
    raw_value: str
    lastclock: int
    lastns: int

    def __post_init__(self) -> None:
        if not isinstance(self.itemid, str) or not self.itemid or len(self.itemid) > 256:
            raise ValueError("itemid must be bounded non-empty text")
        if not isinstance(self.raw_value, str) or len(self.raw_value) > MAX_RAW_CURRENT_VALUE_LENGTH:
            raise ValueError("raw_value must be bounded text")
        if not isinstance(self.lastclock, int) or self.lastclock <= 0:
            raise ValueError("lastclock must be a positive provider sample timestamp")
        if not isinstance(self.lastns, int) or not 0 <= self.lastns <= 999_999_999:
            raise ValueError("lastns must be a valid nanosecond component")


@dataclass(frozen=True)
class CurrentMetricTarget:
    metric_definition_id: str
    monitoring_resource_id: str
    provider_external_ref: str
    value_kind: MetricValueKind


@dataclass(frozen=True)
class MetricCurrentStateClaim:
    claim_token: str
    tenant_id: str
    monitoring_sync_operation_id: str
    monitoring_source_id: str
    source_instance_generation: str
    configuration_revision: int
    scope_revision: int
    current_state_poll_epoch: int
    current_state_poll_generation: int
    targets: tuple[CurrentMetricTarget, ...]


@dataclass(frozen=True)
class AcceptedCurrentObservation:
    metric_definition_id: str
    monitoring_resource_id: str
    provider_external_ref: str
    observation_id: str
    observed_at_epoch_seconds: int
    observed_at_nanoseconds: int
    value_kind: MetricValueKind
    canonical_value: int | float | str | bool


@dataclass(frozen=True)
class MetricCurrentStateResult:
    operation_state: SyncOperationState
    operational_evidence_state: OperationalEvidenceState
    accepted_observations: tuple[AcceptedCurrentObservation, ...]
    failure_class: CurrentStateFailureClass | None

    @property
    def succeeded(self) -> bool:
        return self.operation_state is SyncOperationState.SUCCEEDED


class MonitoringMetricCurrentStateRepository(Protocol):
    def claim_metric_current_state(
        self,
        monitoring_sync_operation_id: str,
        *,
        claim_token: str,
    ) -> MetricCurrentStateClaim:
        ...

    def complete_metric_current_state(
        self,
        claim: MetricCurrentStateClaim,
        result: MetricCurrentStateResult,
    ) -> MetricCurrentStateResult:
        ...


class ZabbixCurrentValueReader(Protocol):
    def read_current_values(
        self,
        itemids: Sequence[str],
        *,
        max_items: int,
    ) -> Sequence[ZabbixCurrentValueEvidence]:
        ...


def parse_canonical_value(kind: MetricValueKind, raw: str) -> int | float | str | bool:
    if kind is MetricValueKind.NUMBER:
        value = float(raw)
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("number must be finite")
        return value
    if kind is MetricValueKind.INTEGER:
        if raw.strip() != raw or not raw or any(c not in "0123456789" for c in raw):
            raise ValueError("integer current value must be canonical unsigned decimal")
        return int(raw)
    if kind in (MetricValueKind.STRING, MetricValueKind.TEXT, MetricValueKind.LOG):
        return raw
    if kind is MetricValueKind.BOOLEAN:
        if raw == "1":
            return True
        if raw == "0":
            return False
        raise ValueError("boolean current value requires explicit 0/1 mapping")
    raise ValueError("unsupported canonical value kind")


def collect_metric_current_state(
    claim: MetricCurrentStateClaim,
    *,
    reader: ZabbixCurrentValueReader,
) -> MetricCurrentStateResult:
    if len(claim.targets) > MAX_CURRENT_SAMPLES_PER_BATCH:
        return MetricCurrentStateResult(
            SyncOperationState.RECONCILIATION_REQUIRED,
            OperationalEvidenceState.RECONCILIATION_REQUIRED,
            (),
            CurrentStateFailureClass.PROVIDER_PROTOCOL_INVALID,
        )

    by_itemid = {target.provider_external_ref: target for target in claim.targets}
    if len(by_itemid) != len(claim.targets):
        return MetricCurrentStateResult(
            SyncOperationState.RECONCILIATION_REQUIRED,
            OperationalEvidenceState.RECONCILIATION_REQUIRED,
            (),
            CurrentStateFailureClass.PROVIDER_PROTOCOL_INVALID,
        )

    try:
        returned = tuple(
            reader.read_current_values(tuple(by_itemid), max_items=MAX_CURRENT_SAMPLES_PER_BATCH)
        )
    except (TypeError, ValueError):
        return MetricCurrentStateResult(
            SyncOperationState.RECONCILIATION_REQUIRED,
            OperationalEvidenceState.UNAVAILABLE,
            (),
            CurrentStateFailureClass.PROVIDER_PROTOCOL_INVALID,
        )

    if len(returned) > MAX_CURRENT_SAMPLES_PER_BATCH or len({row.itemid for row in returned}) != len(returned):
        return MetricCurrentStateResult(
            SyncOperationState.RECONCILIATION_REQUIRED,
            OperationalEvidenceState.RECONCILIATION_REQUIRED,
            (),
            CurrentStateFailureClass.PROVIDER_PROTOCOL_INVALID,
        )

    accepted: list[AcceptedCurrentObservation] = []
    for row in returned:
        target = by_itemid.get(row.itemid)
        if target is None:
            return MetricCurrentStateResult(
                SyncOperationState.RECONCILIATION_REQUIRED,
                OperationalEvidenceState.RECONCILIATION_REQUIRED,
                (),
                CurrentStateFailureClass.PROVIDER_PROTOCOL_INVALID,
            )
        try:
            canonical_value = parse_canonical_value(target.value_kind, row.raw_value)
        except (TypeError, ValueError, OverflowError):
            return MetricCurrentStateResult(
                SyncOperationState.RECONCILIATION_REQUIRED,
                OperationalEvidenceState.RECONCILIATION_REQUIRED,
                (),
                CurrentStateFailureClass.VALUE_PARSE_INVALID,
            )
        accepted.append(
            AcceptedCurrentObservation(
                metric_definition_id=target.metric_definition_id,
                monitoring_resource_id=target.monitoring_resource_id,
                provider_external_ref=target.provider_external_ref,
                observation_id=opaque_token("mon-current-observation"),
                observed_at_epoch_seconds=row.lastclock,
                observed_at_nanoseconds=row.lastns,
                value_kind=target.value_kind,
                canonical_value=canonical_value,
            )
        )

    # Missing targets are not negative evidence here. Positive object evidence remains admissible;
    # coverage-aware degradation is decided by the repository under current poll authority.
    return MetricCurrentStateResult(
        SyncOperationState.SUCCEEDED,
        OperationalEvidenceState.CURRENT,
        tuple(accepted),
        None,
    )


class MetricCurrentStateWorker:
    def __init__(self, *, repository: MonitoringMetricCurrentStateRepository, reader: ZabbixCurrentValueReader) -> None:
        self._repository = repository
        self._reader = reader

    def run(self, monitoring_sync_operation_id: str) -> MetricCurrentStateResult:
        claim = self._repository.claim_metric_current_state(
            monitoring_sync_operation_id,
            claim_token=opaque_token("mon-current-claim"),
        )
        collected = collect_metric_current_state(claim, reader=self._reader)
        persisted = self._repository.complete_metric_current_state(claim, collected)
        if not isinstance(persisted, MetricCurrentStateResult):
            raise TypeError("complete_metric_current_state must return authoritative persisted result")
        return persisted
