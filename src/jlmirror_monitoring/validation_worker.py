from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, Sequence

from .source import ConfiguredProviderScope, OperationalEvidenceState, SyncOperationState, ZabbixProviderConfiguration, opaque_token


class ValidationFailureClass(StrEnum):
    CREDENTIAL_UNAVAILABLE = "credential.unavailable"
    PROVIDER_AUTHENTICATION_REJECTED = "provider.authentication_rejected"
    EGRESS_NOT_ADMITTED = "provider.egress_not_admitted"
    PROVIDER_UNAVAILABLE = "provider.unavailable"
    PROVIDER_PROTOCOL_INVALID = "provider.protocol_invalid"
    SCOPE_ANCHOR_INACCESSIBLE = "provider.scope_anchor_inaccessible"


class CredentialResolutionError(RuntimeError):
    pass


class EgressAdmissionError(RuntimeError):
    pass


class ProviderAuthenticationError(RuntimeError):
    pass


class ProviderUnavailableError(RuntimeError):
    pass


class ProviderProtocolError(RuntimeError):
    pass


@dataclass(frozen=True, repr=False)
class ResolvedZabbixCredential:
    api_token: str = field(repr=False)
    credential_generation_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.api_token, str) or not self.api_token:
            raise ValueError("api_token must be non-empty in-memory secret material")
        if not isinstance(self.credential_generation_ref, str) or not self.credential_generation_ref:
            raise ValueError("credential_generation_ref must be non-empty")


@dataclass(frozen=True)
class AdmittedProviderEndpoint:
    api_url: str
    egress_decision_ref: str

    def __post_init__(self) -> None:
        if not self.api_url.endswith("/api_jsonrpc.php"):
            raise ValueError("admitted Zabbix endpoint must target api_jsonrpc.php")
        if not self.egress_decision_ref:
            raise ValueError("egress_decision_ref must be non-empty")


@dataclass(frozen=True)
class ZabbixHostGroup:
    groupid: str
    name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.groupid, str) or not self.groupid:
            raise ValueError("groupid must be non-empty")


@dataclass(frozen=True)
class InitialValidationClaim:
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
class InitialValidationResult:
    operational_evidence_state: OperationalEvidenceState
    operation_state: SyncOperationState
    visible_host_group_refs: tuple[str, ...]
    missing_host_group_refs: tuple[str, ...]
    failure_class: ValidationFailureClass | None
    egress_decision_ref: str | None
    credential_generation_ref: str | None

    @property
    def succeeded(self) -> bool:
        return self.operation_state is SyncOperationState.SUCCEEDED


class MonitoringValidationRepository(Protocol):
    def claim_initial_validation(self, monitoring_sync_operation_id: str, *, claim_token: str) -> InitialValidationClaim:
        ...

    def complete_initial_validation(self, claim: InitialValidationClaim, result: InitialValidationResult, *, validation_evidence_id: str) -> None:
        ...


class CredentialResolver(Protocol):
    def resolve_zabbix_api_token(self, credential_binding_ref: str) -> ResolvedZabbixCredential:
        ...


class OutboundAdmission(Protocol):
    def admit_zabbix_api(self, provider_configuration: ZabbixProviderConfiguration) -> AdmittedProviderEndpoint:
        ...


class ZabbixHostGroupReader(Protocol):
    def hostgroup_get(
        self,
        endpoint: AdmittedProviderEndpoint,
        credential: ResolvedZabbixCredential,
        host_group_refs: Sequence[str],
    ) -> Sequence[ZabbixHostGroup]:
        ...


def _reconciliation_result(
    failure_class: ValidationFailureClass,
    *,
    evidence_state: OperationalEvidenceState,
    egress_decision_ref: str | None = None,
    credential_generation_ref: str | None = None,
    visible: tuple[str, ...] = (),
    missing: tuple[str, ...] = (),
) -> InitialValidationResult:
    return InitialValidationResult(
        operational_evidence_state=evidence_state,
        operation_state=SyncOperationState.RECONCILIATION_REQUIRED,
        visible_host_group_refs=visible,
        missing_host_group_refs=missing,
        failure_class=failure_class,
        egress_decision_ref=egress_decision_ref,
        credential_generation_ref=credential_generation_ref,
    )


def validate_host_group_scope(
    claim: InitialValidationClaim,
    *,
    credential_resolver: CredentialResolver,
    outbound_admission: OutboundAdmission,
    host_group_reader: ZabbixHostGroupReader,
) -> InitialValidationResult:
    credential: ResolvedZabbixCredential | None = None
    endpoint: AdmittedProviderEndpoint | None = None
    try:
        credential = credential_resolver.resolve_zabbix_api_token(claim.credential_binding_ref)
    except CredentialResolutionError:
        return _reconciliation_result(
            ValidationFailureClass.CREDENTIAL_UNAVAILABLE,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
        )

    try:
        endpoint = outbound_admission.admit_zabbix_api(claim.provider_configuration)
    except EgressAdmissionError:
        return _reconciliation_result(
            ValidationFailureClass.EGRESS_NOT_ADMITTED,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
            credential_generation_ref=credential.credential_generation_ref,
        )

    try:
        groups = tuple(
            host_group_reader.hostgroup_get(
                endpoint,
                credential,
                claim.configured_provider_scope.host_group_refs,
            )
        )
    except ProviderAuthenticationError:
        return _reconciliation_result(
            ValidationFailureClass.PROVIDER_AUTHENTICATION_REJECTED,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
            egress_decision_ref=endpoint.egress_decision_ref,
            credential_generation_ref=credential.credential_generation_ref,
        )
    except ProviderUnavailableError:
        return _reconciliation_result(
            ValidationFailureClass.PROVIDER_UNAVAILABLE,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
            egress_decision_ref=endpoint.egress_decision_ref,
            credential_generation_ref=credential.credential_generation_ref,
        )
    except ProviderProtocolError:
        return _reconciliation_result(
            ValidationFailureClass.PROVIDER_PROTOCOL_INVALID,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
            egress_decision_ref=endpoint.egress_decision_ref,
            credential_generation_ref=credential.credential_generation_ref,
        )

    returned = [group.groupid for group in groups]
    if len(returned) != len(set(returned)):
        return _reconciliation_result(
            ValidationFailureClass.PROVIDER_PROTOCOL_INVALID,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
            egress_decision_ref=endpoint.egress_decision_ref,
            credential_generation_ref=credential.credential_generation_ref,
        )

    configured = claim.configured_provider_scope.host_group_refs
    configured_set = set(configured)
    if any(groupid not in configured_set for groupid in returned):
        return _reconciliation_result(
            ValidationFailureClass.PROVIDER_PROTOCOL_INVALID,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
            egress_decision_ref=endpoint.egress_decision_ref,
            credential_generation_ref=credential.credential_generation_ref,
        )

    visible = tuple(ref for ref in configured if ref in set(returned))
    missing = tuple(ref for ref in configured if ref not in set(returned))
    if missing:
        return _reconciliation_result(
            ValidationFailureClass.SCOPE_ANCHOR_INACCESSIBLE,
            evidence_state=OperationalEvidenceState.INCOMPLETE,
            egress_decision_ref=endpoint.egress_decision_ref,
            credential_generation_ref=credential.credential_generation_ref,
            visible=visible,
            missing=missing,
        )

    return InitialValidationResult(
        operational_evidence_state=OperationalEvidenceState.CURRENT,
        operation_state=SyncOperationState.SUCCEEDED,
        visible_host_group_refs=visible,
        missing_host_group_refs=(),
        failure_class=None,
        egress_decision_ref=endpoint.egress_decision_ref,
        credential_generation_ref=credential.credential_generation_ref,
    )


class InitialValidationWorker:
    def __init__(
        self,
        *,
        repository: MonitoringValidationRepository,
        credential_resolver: CredentialResolver,
        outbound_admission: OutboundAdmission,
        host_group_reader: ZabbixHostGroupReader,
    ) -> None:
        self._repository = repository
        self._credential_resolver = credential_resolver
        self._outbound_admission = outbound_admission
        self._host_group_reader = host_group_reader

    def run(self, monitoring_sync_operation_id: str) -> InitialValidationResult:
        claim = self._repository.claim_initial_validation(
            monitoring_sync_operation_id,
            claim_token=opaque_token("mon-claim"),
        )
        result = validate_host_group_scope(
            claim,
            credential_resolver=self._credential_resolver,
            outbound_admission=self._outbound_admission,
            host_group_reader=self._host_group_reader,
        )
        self._repository.complete_initial_validation(
            claim,
            result,
            validation_evidence_id=opaque_token("mon-validation"),
        )
        return result
