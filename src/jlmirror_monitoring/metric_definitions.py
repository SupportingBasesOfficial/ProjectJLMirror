from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, Sequence

from .source import (
    ConfiguredProviderScope,
    OperationalEvidenceState,
    SyncOperationState,
    ZabbixProviderConfiguration,
    _canonical_explicit_text,
    opaque_token,
)
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
    ZabbixHostGroup,
)

MAX_ITEMS_PER_SNAPSHOT = 200_000
MAX_ITEM_NAME_LENGTH = 1024
MAX_ITEM_KEY_LENGTH = 2048
MAX_ITEM_UNIT_LENGTH = 255


class MetricValueKind(StrEnum):
    NUMBER = "number"
    INTEGER = "integer"
    STRING = "string"
    TEXT = "text"
    LOG = "log"


class ZabbixNativeValueType(StrEnum):
    FLOAT = "float"
    UNSIGNED = "unsigned"
    CHARACTER = "character"
    TEXT = "text"
    LOG = "log"


class ZabbixItemOperationalState(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    UNSUPPORTED = "unsupported"


class MetricDefinitionFailureClass(StrEnum):
    CREDENTIAL_UNAVAILABLE = "credential.unavailable"
    PROVIDER_AUTHENTICATION_REJECTED = "provider.authentication_rejected"
    EGRESS_NOT_ADMITTED = "provider.egress_not_admitted"
    PROVIDER_UNAVAILABLE = "provider.unavailable"
    PROVIDER_PROTOCOL_INVALID = "provider.protocol_invalid"
    SNAPSHOT_TRUNCATED = "provider.snapshot_truncated"
    SCOPE_ANCHOR_INACCESSIBLE = "provider.scope_anchor_inaccessible"
    HOST_ASSOCIATION_INVALID = "provider.host_association_invalid"
    VALUE_KIND_DRIFT = "provider.value_kind_drift"


def canonical_value_kind(native_value_type: ZabbixNativeValueType) -> MetricValueKind:
    mapping = {
        ZabbixNativeValueType.FLOAT: MetricValueKind.NUMBER,
        ZabbixNativeValueType.UNSIGNED: MetricValueKind.INTEGER,
        ZabbixNativeValueType.CHARACTER: MetricValueKind.STRING,
        ZabbixNativeValueType.TEXT: MetricValueKind.TEXT,
        ZabbixNativeValueType.LOG: MetricValueKind.LOG,
    }
    try:
        return mapping[native_value_type]
    except KeyError as exc:
        raise ValueError("unsupported normalized Zabbix native value type") from exc


@dataclass(frozen=True)
class ZabbixItemEvidence:
    itemid: str
    hostid: str
    name: str
    key: str
    unit: str
    native_value_type: ZabbixNativeValueType
    operational_state: ZabbixItemOperationalState

    def __post_init__(self) -> None:
        _canonical_explicit_text(self.itemid, "itemid", max_len=256)
        _canonical_explicit_text(self.hostid, "hostid", max_len=256)
        _canonical_explicit_text(self.name, "item_name", max_len=MAX_ITEM_NAME_LENGTH)
        _canonical_explicit_text(self.key, "item_key", max_len=MAX_ITEM_KEY_LENGTH)
        if not isinstance(self.unit, str) or len(self.unit) > MAX_ITEM_UNIT_LENGTH:
            raise ValueError("item unit must be bounded text")
        if any(ord(char) < 0x20 or ord(char) == 0x7F for char in self.unit):
            raise ValueError("item unit must not contain control characters")
        if not isinstance(self.native_value_type, ZabbixNativeValueType):
            raise ValueError("native_value_type must be normalized before entering Monitoring")
        if not isinstance(self.operational_state, ZabbixItemOperationalState):
            raise ValueError("operational_state must be normalized provider evidence")

    @property
    def value_kind(self) -> MetricValueKind:
        return canonical_value_kind(self.native_value_type)


@dataclass(frozen=True)
class ZabbixItemSnapshot:
    items: tuple[ZabbixItemEvidence, ...]
    complete: bool

    def __post_init__(self) -> None:
        if not isinstance(self.complete, bool):
            raise ValueError("snapshot completeness must be a canonical boolean")
        if not isinstance(self.items, tuple) or len(self.items) > MAX_ITEMS_PER_SNAPSHOT:
            raise ValueError("items must be an immutable bounded tuple")
        if any(not isinstance(item, ZabbixItemEvidence) for item in self.items):
            raise ValueError("snapshot contains non-normalized item evidence")
        if len({item.itemid for item in self.items}) != len(self.items):
            raise ValueError("snapshot must not contain duplicate itemid")


@dataclass(frozen=True)
class MetricDefinitionClaim:
    claim_token: str
    tenant_id: str
    monitoring_sync_operation_id: str
    monitoring_source_id: str
    provider_scope_tenant_binding_id: str
    source_instance_generation: str
    configuration_revision: int
    scope_revision: int
    item_definition_poll_epoch: int
    item_definition_poll_generation: int
    provider_instance_ref: str
    provider_configuration: ZabbixProviderConfiguration
    credential_binding_ref: str
    configured_provider_scope: ConfiguredProviderScope


@dataclass(frozen=True)
class MetricDefinitionResult:
    operational_evidence_state: OperationalEvidenceState
    operation_state: SyncOperationState
    items: tuple[ZabbixItemEvidence, ...]
    snapshot_complete: bool
    failure_class: MetricDefinitionFailureClass | None
    egress_decision_ref: str | None
    credential_generation_ref: str | None

    @property
    def succeeded(self) -> bool:
        return self.operation_state is SyncOperationState.SUCCEEDED


class MonitoringMetricDefinitionRepository(Protocol):
    def claim_metric_definitions(
        self,
        monitoring_sync_operation_id: str,
        *,
        claim_token: str,
    ) -> MetricDefinitionClaim:
        ...

    def complete_metric_definitions(
        self,
        claim: MetricDefinitionClaim,
        result: MetricDefinitionResult,
        *,
        snapshot_evidence_id: str,
    ) -> MetricDefinitionResult:
        ...


class ZabbixItemReader(Protocol):
    def hostgroup_get(
        self,
        endpoint: AdmittedProviderEndpoint,
        credential: ResolvedZabbixCredential,
        host_group_refs: Sequence[str],
    ) -> Sequence[ZabbixHostGroup]:
        ...

    def item_get(
        self,
        endpoint: AdmittedProviderEndpoint,
        credential: ResolvedZabbixCredential,
        host_group_refs: Sequence[str],
        *,
        max_items: int,
    ) -> ZabbixItemSnapshot:
        ...


def _degraded(
    failure_class: MetricDefinitionFailureClass,
    *,
    evidence_state: OperationalEvidenceState,
    items: tuple[ZabbixItemEvidence, ...] = (),
    egress_decision_ref: str | None = None,
    credential_generation_ref: str | None = None,
) -> MetricDefinitionResult:
    return MetricDefinitionResult(
        evidence_state,
        SyncOperationState.RECONCILIATION_REQUIRED,
        items,
        False,
        failure_class,
        egress_decision_ref,
        credential_generation_ref,
    )


def collect_metric_definitions(
    claim: MetricDefinitionClaim,
    *,
    credential_resolver: CredentialResolver,
    outbound_admission: OutboundAdmission,
    item_reader: ZabbixItemReader,
) -> MetricDefinitionResult:
    try:
        credential = credential_resolver.resolve_zabbix_api_token(claim.credential_binding_ref)
    except CredentialResolutionError:
        return _degraded(
            MetricDefinitionFailureClass.CREDENTIAL_UNAVAILABLE,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
        )

    try:
        endpoint = outbound_admission.admit_zabbix_api(claim.provider_configuration)
    except EgressAdmissionError:
        return _degraded(
            MetricDefinitionFailureClass.EGRESS_NOT_ADMITTED,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
            credential_generation_ref=credential.credential_generation_ref,
        )

    configured_refs = claim.configured_provider_scope.host_group_refs
    try:
        visible_groups = tuple(item_reader.hostgroup_get(endpoint, credential, configured_refs))
    except ProviderAuthenticationError:
        return _degraded(
            MetricDefinitionFailureClass.PROVIDER_AUTHENTICATION_REJECTED,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
            egress_decision_ref=endpoint.egress_decision_ref,
            credential_generation_ref=credential.credential_generation_ref,
        )
    except ProviderUnavailableError:
        return _degraded(
            MetricDefinitionFailureClass.PROVIDER_UNAVAILABLE,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
            egress_decision_ref=endpoint.egress_decision_ref,
            credential_generation_ref=credential.credential_generation_ref,
        )
    except (ProviderProtocolError, ValueError, TypeError):
        return _degraded(
            MetricDefinitionFailureClass.PROVIDER_PROTOCOL_INVALID,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
            egress_decision_ref=endpoint.egress_decision_ref,
            credential_generation_ref=credential.credential_generation_ref,
        )

    returned_refs = tuple(group.groupid for group in visible_groups if isinstance(group, ZabbixHostGroup))
    if len(returned_refs) != len(visible_groups) or len(returned_refs) != len(set(returned_refs)):
        return _degraded(
            MetricDefinitionFailureClass.PROVIDER_PROTOCOL_INVALID,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
            egress_decision_ref=endpoint.egress_decision_ref,
            credential_generation_ref=credential.credential_generation_ref,
        )
    if any(ref not in set(returned_refs) for ref in configured_refs):
        return _degraded(
            MetricDefinitionFailureClass.SCOPE_ANCHOR_INACCESSIBLE,
            evidence_state=OperationalEvidenceState.INCOMPLETE,
            egress_decision_ref=endpoint.egress_decision_ref,
            credential_generation_ref=credential.credential_generation_ref,
        )

    try:
        snapshot = item_reader.item_get(
            endpoint,
            credential,
            configured_refs,
            max_items=MAX_ITEMS_PER_SNAPSHOT,
        )
    except ProviderAuthenticationError:
        return _degraded(
            MetricDefinitionFailureClass.PROVIDER_AUTHENTICATION_REJECTED,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
            egress_decision_ref=endpoint.egress_decision_ref,
            credential_generation_ref=credential.credential_generation_ref,
        )
    except ProviderUnavailableError:
        return _degraded(
            MetricDefinitionFailureClass.PROVIDER_UNAVAILABLE,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
            egress_decision_ref=endpoint.egress_decision_ref,
            credential_generation_ref=credential.credential_generation_ref,
        )
    except (ProviderProtocolError, ValueError, TypeError):
        return _degraded(
            MetricDefinitionFailureClass.PROVIDER_PROTOCOL_INVALID,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
            egress_decision_ref=endpoint.egress_decision_ref,
            credential_generation_ref=credential.credential_generation_ref,
        )

    if not isinstance(snapshot, ZabbixItemSnapshot):
        return _degraded(
            MetricDefinitionFailureClass.PROVIDER_PROTOCOL_INVALID,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
            egress_decision_ref=endpoint.egress_decision_ref,
            credential_generation_ref=credential.credential_generation_ref,
        )
    if not snapshot.complete:
        return _degraded(
            MetricDefinitionFailureClass.SNAPSHOT_TRUNCATED,
            evidence_state=OperationalEvidenceState.INCOMPLETE,
            items=snapshot.items,
            egress_decision_ref=endpoint.egress_decision_ref,
            credential_generation_ref=credential.credential_generation_ref,
        )

    return MetricDefinitionResult(
        OperationalEvidenceState.CURRENT,
        SyncOperationState.SUCCEEDED,
        snapshot.items,
        True,
        None,
        endpoint.egress_decision_ref,
        credential.credential_generation_ref,
    )


class MetricDefinitionWorker:
    def __init__(
        self,
        *,
        repository: MonitoringMetricDefinitionRepository,
        credential_resolver: CredentialResolver,
        outbound_admission: OutboundAdmission,
        item_reader: ZabbixItemReader,
    ) -> None:
        self._repository = repository
        self._credential_resolver = credential_resolver
        self._outbound_admission = outbound_admission
        self._item_reader = item_reader

    def run(self, monitoring_sync_operation_id: str) -> MetricDefinitionResult:
        claim = self._repository.claim_metric_definitions(
            monitoring_sync_operation_id,
            claim_token=opaque_token("mon-item-claim"),
        )
        collected = collect_metric_definitions(
            claim,
            credential_resolver=self._credential_resolver,
            outbound_admission=self._outbound_admission,
            item_reader=self._item_reader,
        )
        persisted = self._repository.complete_metric_definitions(
            claim,
            collected,
            snapshot_evidence_id=opaque_token("mon-item-snapshot"),
        )
        if not isinstance(persisted, MetricDefinitionResult):
            raise TypeError("complete_metric_definitions must return authoritative persisted MetricDefinitionResult")
        return persisted
