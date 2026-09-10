from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
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
)

MAX_HOSTS_PER_SNAPSHOT = 50_000
MAX_INTERFACES_PER_HOST = 32
MAX_GROUPS_PER_HOST = 256
MAX_TEMPLATES_PER_HOST = 256
MAX_TAGS_PER_HOST = 128


class InventoryFailureClass(StrEnum):
    CREDENTIAL_UNAVAILABLE = "credential.unavailable"
    PROVIDER_AUTHENTICATION_REJECTED = "provider.authentication_rejected"
    EGRESS_NOT_ADMITTED = "provider.egress_not_admitted"
    PROVIDER_UNAVAILABLE = "provider.unavailable"
    PROVIDER_PROTOCOL_INVALID = "provider.protocol_invalid"
    SNAPSHOT_TRUNCATED = "provider.snapshot_truncated"
    SCOPE_EVIDENCE_INVALID = "provider.scope_evidence_invalid"


@dataclass(frozen=True)
class ZabbixHostInterfaceEvidence:
    interfaceid: str
    interface_type: str
    main: bool
    use_ip: bool
    ip: str | None
    dns: str | None
    port: str | None

    def __post_init__(self) -> None:
        _canonical_explicit_text(self.interfaceid, "interfaceid", max_len=256)
        if self.interface_type not in {"agent", "snmp", "ipmi", "jmx", "unknown"}:
            raise ValueError("interface_type must be an allowed normalized Zabbix interface kind")
        for field_name, value, max_len in (("ip", self.ip, 255), ("dns", self.dns, 255), ("port", self.port, 32)):
            if value is not None:
                _canonical_explicit_text(value, field_name, max_len=max_len)


@dataclass(frozen=True)
class ZabbixNamedRefEvidence:
    ref: str
    name: str | None = None

    def __post_init__(self) -> None:
        _canonical_explicit_text(self.ref, "provider_ref", max_len=256)
        if self.name is not None:
            _canonical_explicit_text(self.name, "provider_ref_name", max_len=512)


@dataclass(frozen=True)
class ZabbixTagEvidence:
    tag: str
    value: str

    def __post_init__(self) -> None:
        _canonical_explicit_text(self.tag, "tag", max_len=255)
        if not isinstance(self.value, str) or len(self.value) > 1024:
            raise ValueError("tag value must be bounded text")
        if any(ord(char) < 0x20 or ord(char) == 0x7F for char in self.value):
            raise ValueError("tag value must not contain control characters")


@dataclass(frozen=True)
class ZabbixInventoryEvidence:
    device_type: str | None = None
    device_type_full: str | None = None
    os: str | None = None
    os_full: str | None = None
    vendor: str | None = None
    model: str | None = None
    serial_primary: str | None = None
    serial_secondary: str | None = None
    asset_tag: str | None = None
    hardware: str | None = None
    software: str | None = None
    location: str | None = None

    def __post_init__(self) -> None:
        for field_name, value, max_len in (
            ("device_type", self.device_type, 512),
            ("device_type_full", self.device_type_full, 2048),
            ("os", self.os, 512),
            ("os_full", self.os_full, 2048),
            ("vendor", self.vendor, 512),
            ("model", self.model, 512),
            ("serial_primary", self.serial_primary, 512),
            ("serial_secondary", self.serial_secondary, 512),
            ("asset_tag", self.asset_tag, 512),
            ("hardware", self.hardware, 2048),
            ("software", self.software, 2048),
            ("location", self.location, 1024),
        ):
            if value is not None:
                _canonical_explicit_text(value, field_name, max_len=max_len)


@dataclass(frozen=True)
class ZabbixHostEvidence:
    hostid: str
    technical_name: str
    display_name: str
    inventory: ZabbixInventoryEvidence
    interfaces: tuple[ZabbixHostInterfaceEvidence, ...]
    groups: tuple[ZabbixNamedRefEvidence, ...]
    templates: tuple[ZabbixNamedRefEvidence, ...]
    tags: tuple[ZabbixTagEvidence, ...]

    def __post_init__(self) -> None:
        _canonical_explicit_text(self.hostid, "hostid", max_len=256)
        _canonical_explicit_text(self.technical_name, "technical_name", max_len=512)
        _canonical_explicit_text(self.display_name, "display_name", max_len=512)
        if not isinstance(self.inventory, ZabbixInventoryEvidence):
            raise ValueError("inventory must be normalized Zabbix inventory evidence")
        for name, values, maximum in (
            ("interfaces", self.interfaces, MAX_INTERFACES_PER_HOST),
            ("groups", self.groups, MAX_GROUPS_PER_HOST),
            ("templates", self.templates, MAX_TEMPLATES_PER_HOST),
            ("tags", self.tags, MAX_TAGS_PER_HOST),
        ):
            if not isinstance(values, tuple) or len(values) > maximum:
                raise ValueError(f"{name} must be an immutable bounded tuple")
        if len({value.interfaceid for value in self.interfaces}) != len(self.interfaces):
            raise ValueError("duplicate interfaceid in host evidence")
        if len({value.ref for value in self.groups}) != len(self.groups):
            raise ValueError("duplicate group ref in host evidence")
        if len({value.ref for value in self.templates}) != len(self.templates):
            raise ValueError("duplicate template ref in host evidence")
        if len({(value.tag, value.value) for value in self.tags}) != len(self.tags):
            raise ValueError("duplicate tag/value pair in host evidence")

    def canonical_evidence(self) -> dict[str, object]:
        inventory = {key: value for key, value in (
            ("device_type", self.inventory.device_type),
            ("device_type_full", self.inventory.device_type_full),
            ("os", self.inventory.os),
            ("os_full", self.inventory.os_full),
            ("vendor", self.inventory.vendor),
            ("model", self.inventory.model),
            ("serial_primary", self.inventory.serial_primary),
            ("serial_secondary", self.inventory.serial_secondary),
            ("asset_tag", self.inventory.asset_tag),
            ("hardware", self.inventory.hardware),
            ("software", self.inventory.software),
            ("location", self.inventory.location),
        ) if value is not None}
        return {
            "technical_name": self.technical_name,
            "display_name": self.display_name,
            "inventory": inventory,
            "interfaces": [{"interfaceid": i.interfaceid, "interface_type": i.interface_type, "main": i.main, "use_ip": i.use_ip, **({"ip": i.ip} if i.ip is not None else {}), **({"dns": i.dns} if i.dns is not None else {}), **({"port": i.port} if i.port is not None else {})} for i in self.interfaces],
            "groups": [{"ref": i.ref, **({"name": i.name} if i.name is not None else {})} for i in self.groups],
            "templates": [{"ref": i.ref, **({"name": i.name} if i.name is not None else {})} for i in self.templates],
            "tags": [{"tag": i.tag, "value": i.value} for i in self.tags],
        }

    def evidence_fingerprint(self) -> str:
        encoded = json.dumps(self.canonical_evidence(), separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ZabbixHostSnapshot:
    hosts: tuple[ZabbixHostEvidence, ...]
    complete: bool

    def __post_init__(self) -> None:
        if not isinstance(self.hosts, tuple) or len(self.hosts) > MAX_HOSTS_PER_SNAPSHOT:
            raise ValueError("hosts must be an immutable bounded tuple")
        if len({host.hostid for host in self.hosts}) != len(self.hosts):
            raise ValueError("snapshot must not contain duplicate hostid")


@dataclass(frozen=True)
class HostInventoryClaim:
    claim_token: str
    tenant_id: str
    monitoring_sync_operation_id: str
    monitoring_source_id: str
    provider_scope_tenant_binding_id: str
    source_instance_generation: str
    configuration_revision: int
    scope_revision: int
    provider_instance_ref: str
    provider_configuration: ZabbixProviderConfiguration
    credential_binding_ref: str
    configured_provider_scope: ConfiguredProviderScope


@dataclass(frozen=True)
class HostInventoryResult:
    operational_evidence_state: OperationalEvidenceState
    operation_state: SyncOperationState
    hosts: tuple[ZabbixHostEvidence, ...]
    snapshot_complete: bool
    failure_class: InventoryFailureClass | None
    egress_decision_ref: str | None
    credential_generation_ref: str | None

    @property
    def succeeded(self) -> bool:
        return self.operation_state is SyncOperationState.SUCCEEDED


class MonitoringHostInventoryRepository(Protocol):
    def claim_host_inventory(self, monitoring_sync_operation_id: str, *, claim_token: str) -> HostInventoryClaim: ...
    def complete_host_inventory(self, claim: HostInventoryClaim, result: HostInventoryResult, *, snapshot_evidence_id: str) -> None: ...


class ZabbixHostReader(Protocol):
    def host_get(self, endpoint: AdmittedProviderEndpoint, credential: ResolvedZabbixCredential, host_group_refs: Sequence[str], *, max_hosts: int) -> ZabbixHostSnapshot: ...


def _degraded(failure_class: InventoryFailureClass, *, evidence_state: OperationalEvidenceState, hosts: tuple[ZabbixHostEvidence, ...] = (), egress_decision_ref: str | None = None, credential_generation_ref: str | None = None) -> HostInventoryResult:
    return HostInventoryResult(evidence_state, SyncOperationState.RECONCILIATION_REQUIRED, hosts, False, failure_class, egress_decision_ref, credential_generation_ref)


def collect_host_inventory(claim: HostInventoryClaim, *, credential_resolver: CredentialResolver, outbound_admission: OutboundAdmission, host_reader: ZabbixHostReader) -> HostInventoryResult:
    try:
        credential = credential_resolver.resolve_zabbix_api_token(claim.credential_binding_ref)
    except CredentialResolutionError:
        return _degraded(InventoryFailureClass.CREDENTIAL_UNAVAILABLE, evidence_state=OperationalEvidenceState.UNAVAILABLE)
    try:
        endpoint = outbound_admission.admit_zabbix_api(claim.provider_configuration)
    except EgressAdmissionError:
        return _degraded(InventoryFailureClass.EGRESS_NOT_ADMITTED, evidence_state=OperationalEvidenceState.UNAVAILABLE, credential_generation_ref=credential.credential_generation_ref)
    try:
        snapshot = host_reader.host_get(endpoint, credential, claim.configured_provider_scope.host_group_refs, max_hosts=MAX_HOSTS_PER_SNAPSHOT)
    except ProviderAuthenticationError:
        return _degraded(InventoryFailureClass.PROVIDER_AUTHENTICATION_REJECTED, evidence_state=OperationalEvidenceState.UNAVAILABLE, egress_decision_ref=endpoint.egress_decision_ref, credential_generation_ref=credential.credential_generation_ref)
    except ProviderUnavailableError:
        return _degraded(InventoryFailureClass.PROVIDER_UNAVAILABLE, evidence_state=OperationalEvidenceState.UNAVAILABLE, egress_decision_ref=endpoint.egress_decision_ref, credential_generation_ref=credential.credential_generation_ref)
    except (ProviderProtocolError, ValueError):
        return _degraded(InventoryFailureClass.PROVIDER_PROTOCOL_INVALID, evidence_state=OperationalEvidenceState.UNAVAILABLE, egress_decision_ref=endpoint.egress_decision_ref, credential_generation_ref=credential.credential_generation_ref)

    configured = set(claim.configured_provider_scope.host_group_refs)
    for host in snapshot.hosts:
        if not {group.ref for group in host.groups}.intersection(configured):
            return _degraded(InventoryFailureClass.SCOPE_EVIDENCE_INVALID, evidence_state=OperationalEvidenceState.INCOMPLETE, egress_decision_ref=endpoint.egress_decision_ref, credential_generation_ref=credential.credential_generation_ref)
    if not snapshot.complete:
        return _degraded(InventoryFailureClass.SNAPSHOT_TRUNCATED, evidence_state=OperationalEvidenceState.INCOMPLETE, hosts=snapshot.hosts, egress_decision_ref=endpoint.egress_decision_ref, credential_generation_ref=credential.credential_generation_ref)
    return HostInventoryResult(OperationalEvidenceState.CURRENT, SyncOperationState.SUCCEEDED, snapshot.hosts, True, None, endpoint.egress_decision_ref, credential.credential_generation_ref)


class HostInventoryWorker:
    def __init__(self, *, repository: MonitoringHostInventoryRepository, credential_resolver: CredentialResolver, outbound_admission: OutboundAdmission, host_reader: ZabbixHostReader) -> None:
        self._repository = repository
        self._credential_resolver = credential_resolver
        self._outbound_admission = outbound_admission
        self._host_reader = host_reader

    def run(self, monitoring_sync_operation_id: str) -> HostInventoryResult:
        claim = self._repository.claim_host_inventory(monitoring_sync_operation_id, claim_token=opaque_token("mon-host-claim"))
        result = collect_host_inventory(claim, credential_resolver=self._credential_resolver, outbound_admission=self._outbound_admission, host_reader=self._host_reader)
        self._repository.complete_host_inventory(claim, result, snapshot_evidence_id=opaque_token("mon-host-snapshot"))
        return result
