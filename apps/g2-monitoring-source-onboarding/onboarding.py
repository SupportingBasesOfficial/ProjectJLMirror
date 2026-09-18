from __future__ import annotations

from dataclasses import dataclass
import secrets
from typing import Mapping, Protocol

from jlmirror_monitoring import (
    ConfiguredProviderScope,
    CreateMonitoringSourceCommand,
    OperationalEvidenceState,
    SourceCreationPlan,
    SyncOperationState,
    ZabbixProviderConfiguration,
    plan_source_creation,
)


MANAGE_ACTION = "monitoring.source.manage"
READ_ACTION = "monitoring.source.read"
SYNC_READ_ACTION = "monitoring.sync.read"
PROVIDER_PROFILE = "zabbix"


@dataclass(frozen=True)
class CurrentAuthorizationEvidence:
    actor_principal_id: str
    actor_principal_kind: str
    actor_generation_ref: str
    authorization_decision_ref: str


class CurrentAuthorizationPort(Protocol):
    def require(
        self,
        *,
        actor_ref: str,
        tenant_id: str,
        action: str,
    ) -> CurrentAuthorizationEvidence: ...


class ProviderBindingPort(Protocol):
    def current_instance_ref(self, *, tenant_id: str, provider_profile: str) -> str: ...


@dataclass(frozen=True)
class SourceSnapshot:
    monitoring_source_id: str
    monitoring_sync_operation_id: str
    operational_evidence_state: OperationalEvidenceState
    sync_operation_state: SyncOperationState


class MonitoringSourcePort(Protocol):
    def create_initial(
        self,
        *,
        plan: SourceCreationPlan,
        idempotency_key: str,
        actor_principal_id: str,
        actor_principal_kind: str,
        actor_generation_ref: str,
        authorization_decision_ref: str,
        request_correlation_id: str,
    ) -> SourceSnapshot: ...

    def read_source(self, *, tenant_id: str, monitoring_source_id: str) -> SourceSnapshot: ...


class ValidationResponsibilityPort(Protocol):
    def make_ready(self, *, tenant_id: str, monitoring_sync_operation_id: str) -> None: ...


@dataclass(frozen=True)
class CreateSourceRequest:
    display_name: str
    provider_configuration_base_url: str
    credential_binding_ref: str
    host_group_refs: tuple[str, ...]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "CreateSourceRequest":
        expected = {
            "provider_profile",
            "display_name",
            "provider_configuration",
            "credential_binding_ref",
            "configured_provider_scope",
        }
        if set(payload) != expected:
            raise ValueError("create source request shape is not canonical")
        if payload.get("provider_profile") != PROVIDER_PROFILE:
            raise ValueError("provider_profile must be zabbix")

        configuration = payload.get("provider_configuration")
        if not isinstance(configuration, Mapping) or set(configuration) != {"base_url"}:
            raise ValueError("provider_configuration shape is not canonical")
        base_url = configuration.get("base_url")

        scope = payload.get("configured_provider_scope")
        if not isinstance(scope, Mapping) or set(scope) != {"host_group_refs"}:
            raise ValueError("configured_provider_scope shape is not canonical")
        refs = scope.get("host_group_refs")
        if not isinstance(refs, list) or not all(isinstance(item, str) for item in refs):
            raise ValueError("host_group_refs must be a list of strings")

        display_name = payload.get("display_name")
        binding_ref = payload.get("credential_binding_ref")
        if not isinstance(display_name, str) or not isinstance(binding_ref, str) or not isinstance(base_url, str):
            raise ValueError("create source scalar fields must be strings")

        return cls(
            display_name=display_name,
            provider_configuration_base_url=base_url,
            credential_binding_ref=binding_ref,
            host_group_refs=tuple(refs),
        )


@dataclass(frozen=True)
class OnboardingView:
    monitoring_source_id: str
    monitoring_sync_operation_id: str
    state: str
    provider_connection_confirmed: bool
    can_recheck: bool


def _bounded_idempotency_key(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 256
        or any(ord(char) < 0x20 or ord(char) == 0x7F for char in value)
    ):
        raise ValueError("Idempotency-Key is not canonical")
    return value


def present(snapshot: SourceSnapshot) -> OnboardingView:
    evidence = snapshot.operational_evidence_state
    operation = snapshot.sync_operation_state

    if evidence is OperationalEvidenceState.CURRENT and operation is SyncOperationState.SUCCEEDED:
        state = "current"
        confirmed = True
        can_recheck = False
    elif operation in (SyncOperationState.PENDING, SyncOperationState.RUNNING):
        state = "validation_pending"
        confirmed = False
        can_recheck = False
    elif evidence is OperationalEvidenceState.INCOMPLETE:
        state = "incomplete"
        confirmed = False
        can_recheck = True
    elif evidence is OperationalEvidenceState.UNAVAILABLE:
        state = "unavailable"
        confirmed = False
        can_recheck = True
    else:
        state = "reconciliation_required"
        confirmed = False
        can_recheck = True

    return OnboardingView(
        monitoring_source_id=snapshot.monitoring_source_id,
        monitoring_sync_operation_id=snapshot.monitoring_sync_operation_id,
        state=state,
        provider_connection_confirmed=confirmed,
        can_recheck=can_recheck,
    )


class MonitoringSourceOnboarding:
    def __init__(
        self,
        *,
        authorization: CurrentAuthorizationPort,
        provider_binding: ProviderBindingPort,
        source_port: MonitoringSourcePort,
        validation_responsibility: ValidationResponsibilityPort,
    ) -> None:
        self._authorization = authorization
        self._provider_binding = provider_binding
        self._source_port = source_port
        self._validation_responsibility = validation_responsibility

    def create(
        self,
        *,
        actor_ref: str,
        tenant_id: str,
        idempotency_key: str,
        payload: Mapping[str, object],
    ) -> OnboardingView:
        key = _bounded_idempotency_key(idempotency_key)
        self._authorization.require(
            actor_ref=actor_ref,
            tenant_id=tenant_id,
            action=MANAGE_ACTION,
        )
        request = CreateSourceRequest.from_mapping(payload)
        provider_instance_ref = self._provider_binding.current_instance_ref(
            tenant_id=tenant_id,
            provider_profile=PROVIDER_PROFILE,
        )

        command = CreateMonitoringSourceCommand(
            tenant_id=tenant_id,
            display_name=request.display_name,
            provider_instance_ref=provider_instance_ref,
            provider_configuration=ZabbixProviderConfiguration(request.provider_configuration_base_url),
            credential_binding_ref=request.credential_binding_ref,
            configured_provider_scope=ConfiguredProviderScope.from_refs(request.host_group_refs),
        )
        admission = self._authorization.require(
            actor_ref=actor_ref,
            tenant_id=tenant_id,
            action=MANAGE_ACTION,
        )
        committed = self._source_port.create_initial(
            plan=plan_source_creation(command),
            idempotency_key=key,
            actor_principal_id=admission.actor_principal_id,
            actor_principal_kind=admission.actor_principal_kind,
            actor_generation_ref=admission.actor_generation_ref,
            authorization_decision_ref=admission.authorization_decision_ref,
            request_correlation_id="g2-request:" + secrets.token_urlsafe(24),
        )

        if committed.sync_operation_state is SyncOperationState.PENDING:
            self._validation_responsibility.make_ready(
                tenant_id=tenant_id,
                monitoring_sync_operation_id=committed.monitoring_sync_operation_id,
            )
        return present(committed)

    def read(
        self,
        *,
        actor_ref: str,
        tenant_id: str,
        monitoring_source_id: str,
    ) -> OnboardingView:
        self._authorization.require(actor_ref=actor_ref, tenant_id=tenant_id, action=READ_ACTION)
        snapshot = self._source_port.read_source(
            tenant_id=tenant_id,
            monitoring_source_id=monitoring_source_id,
        )
        self._authorization.require(actor_ref=actor_ref, tenant_id=tenant_id, action=READ_ACTION)
        self._authorization.require(actor_ref=actor_ref, tenant_id=tenant_id, action=SYNC_READ_ACTION)
        return present(snapshot)
