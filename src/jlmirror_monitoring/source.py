from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import json
import secrets
from typing import Callable, Iterable
from urllib.parse import urlsplit, urlunsplit


class OperationalEvidenceState(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    INCOMPLETE = "incomplete"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    UNAVAILABLE = "unavailable"


class SyncOperationState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    FAILED_TERMINAL = "failed_terminal"


@dataclass(frozen=True)
class ZabbixProviderConfiguration:
    base_url: str

    def __post_init__(self) -> None:
        raw = self.base_url.strip()
        if raw != self.base_url or not raw:
            raise ValueError("base_url must be a canonical non-empty HTTPS URL")
        parsed = urlsplit(raw)
        if parsed.scheme != "https":
            raise ValueError("Zabbix base_url must use https")
        if not parsed.hostname:
            raise ValueError("Zabbix base_url requires a host")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("Zabbix base_url must not contain userinfo")
        if parsed.query or parsed.fragment:
            raise ValueError("Zabbix base_url must not contain query or fragment")
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("Zabbix base_url contains an invalid port") from exc
        host = parsed.hostname.lower()
        netloc = f"[{host}]" if ":" in host else host
        if port is not None:
            netloc = f"{netloc}:{port}"
        path = parsed.path or ""
        canonical = urlunsplit(("https", netloc, path, "", ""))
        if canonical != raw:
            raise ValueError("Zabbix base_url is not canonical")
        if len(raw) > 2048:
            raise ValueError("Zabbix base_url exceeds bounded length")


@dataclass(frozen=True)
class ConfiguredProviderScope:
    host_group_refs: tuple[str, ...]

    @classmethod
    def from_refs(cls, refs: Iterable[str]) -> "ConfiguredProviderScope":
        values = tuple(refs)
        if len(values) > 256:
            raise ValueError("host_group_refs exceeds bounded cardinality")
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not isinstance(value, str) or value != value.strip() or not value:
                raise ValueError("host_group_ref must be a bounded non-empty canonical string")
            if len(value) > 256:
                raise ValueError("host_group_ref exceeds bounded length")
            if value in seen:
                raise ValueError("host_group_refs must not contain duplicates")
            seen.add(value)
            normalized.append(value)
        return cls(tuple(normalized))

    def canonical_json(self) -> str:
        return json.dumps({"host_group_refs": list(self.host_group_refs)}, separators=(",", ":"), sort_keys=True)


@dataclass(frozen=True)
class CreateMonitoringSourceCommand:
    tenant_id: str
    display_name: str
    provider_configuration: ZabbixProviderConfiguration
    credential_binding_ref: str
    configured_provider_scope: ConfiguredProviderScope

    def __post_init__(self) -> None:
        for field_name, value, max_len in (
            ("tenant_id", self.tenant_id, 256),
            ("display_name", self.display_name, 512),
            ("credential_binding_ref", self.credential_binding_ref, 512),
        ):
            if not isinstance(value, str) or value != value.strip() or not value:
                raise ValueError(f"{field_name} must be a canonical non-empty string")
            if len(value) > max_len:
                raise ValueError(f"{field_name} exceeds bounded length")

    def canonical_fingerprint(self) -> str:
        body = {
            "provider_profile": "zabbix",
            "display_name": self.display_name,
            "provider_configuration": {"base_url": self.provider_configuration.base_url},
            "credential_binding_ref": self.credential_binding_ref,
            "configured_provider_scope": {"host_group_refs": list(self.configured_provider_scope.host_group_refs)},
        }
        encoded = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class MonitoringSource:
    tenant_id: str
    monitoring_source_id: str
    provider_profile: str
    active_source_instance_generation: str
    configuration_revision: int
    scope_revision: int
    display_name: str
    provider_configuration: ZabbixProviderConfiguration
    credential_binding_ref: str
    configured_provider_scope: ConfiguredProviderScope
    operational_evidence_state: OperationalEvidenceState
    replacement_candidate_ref: str | None
    last_successful_sync_at: datetime | None
    last_attempt_at: datetime | None
    last_sync_operation_id: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class MonitoringSyncOperation:
    tenant_id: str
    monitoring_sync_operation_id: str
    monitoring_source_id: str
    source_instance_generation: str
    configuration_revision: int
    scope_revision: int
    responsibility_kind: str
    state: SyncOperationState
    created_at: datetime


@dataclass(frozen=True)
class SourceCreationPlan:
    source: MonitoringSource
    sync_operation: MonitoringSyncOperation
    canonical_request_fingerprint: str


def opaque_token(prefix: str) -> str:
    if not prefix or not prefix.replace("-", "").isalnum():
        raise ValueError("token prefix must be bounded ASCII identifier text")
    return f"{prefix}_{secrets.token_urlsafe(32)}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def plan_source_creation(
    command: CreateMonitoringSourceCommand,
    *,
    source_id_factory: Callable[[], str] = lambda: opaque_token("mon-src"),
    generation_factory: Callable[[], str] = lambda: opaque_token("mon-gen"),
    operation_id_factory: Callable[[], str] = lambda: opaque_token("mon-sync"),
    now: Callable[[], datetime] = utc_now,
) -> SourceCreationPlan:
    created_at = now()
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("creation clock must return an aware timestamp")

    source_id = source_id_factory()
    generation = generation_factory()
    operation_id = operation_id_factory()
    if len({source_id, generation, operation_id}) != 3:
        raise ValueError("generated identities must be distinct")
    if not source_id or not generation or not operation_id:
        raise ValueError("generated identities must be non-empty")

    source = MonitoringSource(
        tenant_id=command.tenant_id,
        monitoring_source_id=source_id,
        provider_profile="zabbix",
        active_source_instance_generation=generation,
        configuration_revision=1,
        scope_revision=1,
        display_name=command.display_name,
        provider_configuration=command.provider_configuration,
        credential_binding_ref=command.credential_binding_ref,
        configured_provider_scope=command.configured_provider_scope,
        operational_evidence_state=OperationalEvidenceState.RECONCILIATION_REQUIRED,
        replacement_candidate_ref=None,
        last_successful_sync_at=None,
        last_attempt_at=None,
        last_sync_operation_id=operation_id,
        created_at=created_at,
        updated_at=created_at,
    )
    sync_operation = MonitoringSyncOperation(
        tenant_id=command.tenant_id,
        monitoring_sync_operation_id=operation_id,
        monitoring_source_id=source_id,
        source_instance_generation=generation,
        configuration_revision=1,
        scope_revision=1,
        responsibility_kind="validation_and_initial_sync",
        state=SyncOperationState.PENDING,
        created_at=created_at,
    )
    return SourceCreationPlan(
        source=source,
        sync_operation=sync_operation,
        canonical_request_fingerprint=command.canonical_fingerprint(),
    )
