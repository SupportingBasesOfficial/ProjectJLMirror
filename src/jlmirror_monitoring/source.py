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


def _canonical_explicit_text(value: object, field: str, *, max_len: int) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > max_len
        or any(ord(char) < 0x20 or ord(char) == 0x7F for char in value)
    ):
        raise ValueError(f"{field} must be a bounded canonical non-empty string")
    return value


@dataclass(frozen=True)
class ZabbixProviderConfiguration:
    base_url: str

    def __post_init__(self) -> None:
        raw = _canonical_explicit_text(self.base_url, "base_url", max_len=2048)
        if "\\" in raw:
            raise ValueError("Zabbix base_url must not contain backslashes")
        try:
            raw.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError("Zabbix base_url must use an ASCII canonical URI representation") from exc
        try:
            parsed = urlsplit(raw)
            username = parsed.username
            password = parsed.password
            port = parsed.port
            hostname = parsed.hostname
        except (TypeError, ValueError) as exc:
            raise ValueError("Zabbix base_url is malformed") from exc
        if parsed.scheme != "https":
            raise ValueError("Zabbix base_url must use https")
        if not parsed.netloc or not hostname:
            raise ValueError("Zabbix base_url requires a host")
        if username is not None or password is not None:
            raise ValueError("Zabbix base_url must not contain userinfo")
        if parsed.query or parsed.fragment:
            raise ValueError("Zabbix base_url must not contain query or fragment")
        host = hostname.lower()
        if host.endswith("."):
            raise ValueError("Zabbix base_url host must not use a trailing-dot alternate form")
        netloc = f"[{host}]" if ":" in host else host
        if port is not None:
            netloc = f"{netloc}:{port}"
        path = parsed.path or ""
        segments = path.split("/")
        if any(segment in (".", "..") for segment in segments):
            raise ValueError("Zabbix base_url path must not contain dot segments")
        canonical = urlunsplit(("https", netloc, path, "", ""))
        if canonical != raw:
            raise ValueError("Zabbix base_url is not canonical")


@dataclass(frozen=True)
class ConfiguredProviderScope:
    host_group_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.host_group_refs, tuple):
            raise ValueError("host_group_refs must be an immutable tuple")
        if len(self.host_group_refs) > 256:
            raise ValueError("host_group_refs exceeds bounded cardinality")
        seen: set[str] = set()
        for value in self.host_group_refs:
            text = _canonical_explicit_text(value, "host_group_ref", max_len=256)
            if text in seen:
                raise ValueError("host_group_refs must not contain duplicates")
            seen.add(text)

    @classmethod
    def from_refs(cls, refs: Iterable[str]) -> "ConfiguredProviderScope":
        return cls(tuple(refs))

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
        _canonical_explicit_text(self.tenant_id, "tenant_id", max_len=256)
        _canonical_explicit_text(self.display_name, "display_name", max_len=512)
        _canonical_explicit_text(self.credential_binding_ref, "credential_binding_ref", max_len=512)
        if not isinstance(self.provider_configuration, ZabbixProviderConfiguration):
            raise ValueError("provider_configuration must be canonical Zabbix configuration")
        if not isinstance(self.configured_provider_scope, ConfiguredProviderScope):
            raise ValueError("configured_provider_scope must be canonical Zabbix scope")

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
    audit_evidence_id: str
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
    audit_evidence_id_factory: Callable[[], str] = lambda: opaque_token("mon-audit"),
    now: Callable[[], datetime] = utc_now,
) -> SourceCreationPlan:
    if not isinstance(command, CreateMonitoringSourceCommand):
        raise ValueError("command must be canonical Monitoring source creation input")
    created_at = now()
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("creation clock must return an aware timestamp")
    created_at = created_at.astimezone(timezone.utc)

    source_id = source_id_factory()
    generation = generation_factory()
    operation_id = operation_id_factory()
    audit_evidence_id = audit_evidence_id_factory()
    generated = (
        ("monitoring_source_id", source_id),
        ("source_instance_generation", generation),
        ("monitoring_sync_operation_id", operation_id),
        ("audit_evidence_id", audit_evidence_id),
    )
    for field, value in generated:
        _canonical_explicit_text(value, field, max_len=512)
    if len({value for _, value in generated}) != len(generated):
        raise ValueError("generated identities must be distinct")

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
        audit_evidence_id=audit_evidence_id,
        canonical_request_fingerprint=command.canonical_fingerprint(),
    )
