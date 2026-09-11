from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, Sequence

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

MAX_PROBLEMS_PER_POLL = 20_000
MAX_RECOVERY_EVENTS_PER_WINDOW = 20_000
MAX_TRIGGER_METADATA_PER_REQUEST = 5_000
MAX_PROBLEM_SUMMARY_LENGTH = 8_192
MAX_PROVIDER_TAGS_PER_PROBLEM = 128
MAX_PROVIDER_TAG_KEY_LENGTH = 255
MAX_PROVIDER_TAG_VALUE_LENGTH = 2_048


class ProblemStateFailureClass(StrEnum):
    CREDENTIAL_UNAVAILABLE = "credential.unavailable"
    PROVIDER_AUTHENTICATION_REJECTED = "provider.authentication_rejected"
    EGRESS_NOT_ADMITTED = "provider.egress_not_admitted"
    PROVIDER_UNAVAILABLE = "provider.unavailable"
    PROVIDER_PROTOCOL_INVALID = "provider.protocol_invalid"
    PROVIDER_RESULT_TRUNCATED = "monitoring.problem_result_truncated"
    ASSOCIATION_RECONCILIATION_REQUIRED = "monitoring.problem_association_reconciliation_required"
    POLL_SUPERSEDED = "monitoring.problem_poll_superseded"


class ProblemSeverityClass(StrEnum):
    UNKNOWN = "unknown"
    INFORMATIONAL = "informational"
    WARNING = "warning"
    DEGRADED = "degraded"
    CRITICAL = "critical"


class CanonicalProblemState(StrEnum):
    ACTIVE = "active"
    RESOLVED = "resolved"


@dataclass(frozen=True)
class ProviderTag:
    key: str
    value: str

    def __post_init__(self) -> None:
        if not self.key or len(self.key) > MAX_PROVIDER_TAG_KEY_LENGTH:
            raise ValueError("provider tag key must be bounded non-empty text")
        if len(self.value) > MAX_PROVIDER_TAG_VALUE_LENGTH:
            raise ValueError("provider tag value exceeds bounded ceiling")


@dataclass(frozen=True)
class ZabbixProblemEvidence:
    eventid: str
    objectid: str
    clock: int
    name: str
    severity: int
    acknowledged: bool
    tags: tuple[ProviderTag, ...] = ()

    def __post_init__(self) -> None:
        if not self.eventid or len(self.eventid) > 256:
            raise ValueError("eventid must be bounded non-empty text")
        if not self.objectid or len(self.objectid) > 256:
            raise ValueError("objectid must be bounded non-empty text")
        if self.clock <= 0:
            raise ValueError("provider clock must be positive")
        if not self.name or len(self.name) > MAX_PROBLEM_SUMMARY_LENGTH:
            raise ValueError("problem name must be bounded non-empty text")
        if self.severity not in (0, 1, 2, 3, 4, 5):
            raise ValueError("unsupported Zabbix severity")
        if len(self.tags) > MAX_PROVIDER_TAGS_PER_PROBLEM:
            raise ValueError("provider tag count exceeds bounded ceiling")


@dataclass(frozen=True)
class ZabbixRecoveryEvidence:
    problem_eventid: str
    recovery_eventid: str
    clock: int

    def __post_init__(self) -> None:
        if not self.problem_eventid or not self.recovery_eventid:
            raise ValueError("problem and recovery event identity are required")
        if len(self.problem_eventid) > 256 or len(self.recovery_eventid) > 256:
            raise ValueError("provider event identity exceeds bounded ceiling")
        if self.clock <= 0:
            raise ValueError("recovery clock must be positive")


@dataclass(frozen=True)
class ProblemAssociationTarget:
    provider_trigger_ref: str
    monitoring_resource_id: str

    def __post_init__(self) -> None:
        if not self.provider_trigger_ref or len(self.provider_trigger_ref) > 256:
            raise ValueError("provider trigger ref must be bounded non-empty text")
        if not self.monitoring_resource_id:
            raise ValueError("canonical resource identity is required")


@dataclass(frozen=True)
class ProblemStateClaim:
    claim_token: str
    tenant_id: str
    monitoring_sync_operation_id: str
    monitoring_source_id: str
    source_instance_generation: str
    configuration_revision: int
    scope_revision: int
    problem_poll_epoch: int
    problem_poll_generation: int
    provider_instance_ref: str
    provider_configuration: ZabbixProviderConfiguration
    credential_binding_ref: str
    associations: tuple[ProblemAssociationTarget, ...]


@dataclass(frozen=True)
class CanonicalProblemEvidence:
    provider_eventid: str
    monitoring_resource_id: str
    state: CanonicalProblemState
    severity_class: ProblemSeverityClass
    summary: str
    opened_at_epoch_seconds: int
    resolved_at_epoch_seconds: int | None
    provider_acknowledged: bool
    tags: tuple[ProviderTag, ...]


@dataclass(frozen=True)
class ProblemStateResult:
    operation_state: SyncOperationState
    operational_evidence_state: OperationalEvidenceState
    problems: tuple[CanonicalProblemEvidence, ...]
    failure_class: ProblemStateFailureClass | None
    complete_snapshot: bool
    egress_decision_ref: str | None = None
    credential_generation_ref: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.operation_state is SyncOperationState.SUCCEEDED


class ZabbixProblemReader(Protocol):
    def read_active_problems(
        self,
        endpoint: AdmittedProviderEndpoint,
        credential: ResolvedZabbixCredential,
        *,
        max_rows: int,
    ) -> tuple[Sequence[ZabbixProblemEvidence], bool]:
        ...

    def read_recovery_events(
        self,
        endpoint: AdmittedProviderEndpoint,
        credential: ResolvedZabbixCredential,
        problem_eventids: Sequence[str],
        *,
        max_rows: int,
    ) -> Sequence[ZabbixRecoveryEvidence]:
        ...


class MonitoringProblemStateRepository(Protocol):
    def claim_problem_state(
        self,
        monitoring_sync_operation_id: str,
        *,
        claim_token: str,
    ) -> ProblemStateClaim:
        ...

    def complete_problem_state(
        self,
        claim: ProblemStateClaim,
        result: ProblemStateResult,
    ) -> ProblemStateResult:
        ...


def normalize_zabbix_severity(value: int) -> ProblemSeverityClass:
    mapping = {
        0: ProblemSeverityClass.UNKNOWN,
        1: ProblemSeverityClass.INFORMATIONAL,
        2: ProblemSeverityClass.WARNING,
        3: ProblemSeverityClass.DEGRADED,
        4: ProblemSeverityClass.CRITICAL,
        5: ProblemSeverityClass.CRITICAL,
    }
    try:
        return mapping[value]
    except KeyError as exc:
        raise ValueError("unsupported Zabbix severity") from exc


def _degraded(
    failure_class: ProblemStateFailureClass,
    *,
    evidence_state: OperationalEvidenceState,
    egress_decision_ref: str | None = None,
    credential_generation_ref: str | None = None,
) -> ProblemStateResult:
    return ProblemStateResult(
        SyncOperationState.RECONCILIATION_REQUIRED,
        evidence_state,
        (),
        failure_class,
        False,
        egress_decision_ref,
        credential_generation_ref,
    )


def collect_problem_state(
    claim: ProblemStateClaim,
    *,
    credential_resolver: CredentialResolver,
    outbound_admission: OutboundAdmission,
    reader: ZabbixProblemReader,
) -> ProblemStateResult:
    association_by_trigger = {item.provider_trigger_ref: item for item in claim.associations}
    if len(association_by_trigger) != len(claim.associations) or len(claim.associations) > MAX_TRIGGER_METADATA_PER_REQUEST:
        return _degraded(
            ProblemStateFailureClass.PROVIDER_PROTOCOL_INVALID,
            evidence_state=OperationalEvidenceState.RECONCILIATION_REQUIRED,
        )

    try:
        credential = credential_resolver.resolve_zabbix_api_token(claim.credential_binding_ref)
    except CredentialResolutionError:
        return _degraded(
            ProblemStateFailureClass.CREDENTIAL_UNAVAILABLE,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
        )

    try:
        endpoint = outbound_admission.admit_zabbix_api(claim.provider_configuration)
    except EgressAdmissionError:
        return _degraded(
            ProblemStateFailureClass.EGRESS_NOT_ADMITTED,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
            credential_generation_ref=credential.credential_generation_ref,
        )

    try:
        rows, complete_snapshot = reader.read_active_problems(
            endpoint,
            credential,
            max_rows=MAX_PROBLEMS_PER_POLL,
        )
        rows = tuple(rows)
        if len(rows) >= MAX_PROBLEMS_PER_POLL:
            return _degraded(
                ProblemStateFailureClass.PROVIDER_RESULT_TRUNCATED,
                evidence_state=OperationalEvidenceState.RECONCILIATION_REQUIRED,
                egress_decision_ref=endpoint.egress_decision_ref,
                credential_generation_ref=credential.credential_generation_ref,
            )
        if len({row.eventid for row in rows}) != len(rows):
            return _degraded(
                ProblemStateFailureClass.PROVIDER_PROTOCOL_INVALID,
                evidence_state=OperationalEvidenceState.RECONCILIATION_REQUIRED,
                egress_decision_ref=endpoint.egress_decision_ref,
                credential_generation_ref=credential.credential_generation_ref,
            )

        accepted: list[CanonicalProblemEvidence] = []
        for row in rows:
            association = association_by_trigger.get(row.objectid)
            if association is None:
                return _degraded(
                    ProblemStateFailureClass.ASSOCIATION_RECONCILIATION_REQUIRED,
                    evidence_state=OperationalEvidenceState.RECONCILIATION_REQUIRED,
                    egress_decision_ref=endpoint.egress_decision_ref,
                    credential_generation_ref=credential.credential_generation_ref,
                )
            accepted.append(
                CanonicalProblemEvidence(
                    provider_eventid=row.eventid,
                    monitoring_resource_id=association.monitoring_resource_id,
                    state=CanonicalProblemState.ACTIVE,
                    severity_class=normalize_zabbix_severity(row.severity),
                    summary=row.name,
                    opened_at_epoch_seconds=row.clock,
                    resolved_at_epoch_seconds=None,
                    provider_acknowledged=row.acknowledged,
                    tags=row.tags,
                )
            )
    except ProviderAuthenticationError:
        return _degraded(
            ProblemStateFailureClass.PROVIDER_AUTHENTICATION_REJECTED,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
            egress_decision_ref=endpoint.egress_decision_ref,
            credential_generation_ref=credential.credential_generation_ref,
        )
    except ProviderUnavailableError:
        return _degraded(
            ProblemStateFailureClass.PROVIDER_UNAVAILABLE,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
            egress_decision_ref=endpoint.egress_decision_ref,
            credential_generation_ref=credential.credential_generation_ref,
        )
    except (ProviderProtocolError, TypeError, ValueError):
        return _degraded(
            ProblemStateFailureClass.PROVIDER_PROTOCOL_INVALID,
            evidence_state=OperationalEvidenceState.UNAVAILABLE,
            egress_decision_ref=endpoint.egress_decision_ref,
            credential_generation_ref=credential.credential_generation_ref,
        )

    # Omission has negative authority only when the adapter explicitly proves the
    # active-problem snapshot complete. Recovery-event reconciliation is persisted
    # separately by the repository and must bind to the same scoped event identity.
    return ProblemStateResult(
        SyncOperationState.SUCCEEDED,
        OperationalEvidenceState.CURRENT if complete_snapshot else OperationalEvidenceState.RECONCILIATION_REQUIRED,
        tuple(accepted),
        None,
        complete_snapshot,
        endpoint.egress_decision_ref,
        credential.credential_generation_ref,
    )
