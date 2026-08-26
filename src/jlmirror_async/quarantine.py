from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from .model import (
    LogicalMessage,
    ReconciliationBlocked,
    ScopedMessageIdentity,
    aware,
    contract_name,
    identifier,
    optional_identifier,
)


class QuarantineSource(str, Enum):
    OUTBOX_PUBLICATION = "outbox_publication"
    CONSUMER_INBOX = "consumer_inbox"
    REPLAY_CONSUME = "replay_consume"


_RELIABILITY_PROFILE_BY_SOURCE = {
    QuarantineSource.OUTBOX_PUBLICATION: "rel.outbox-publication@1",
    QuarantineSource.CONSUMER_INBOX: "rel.consumer-inbox-effect@1",
    QuarantineSource.REPLAY_CONSUME: "rel.replay-consume-state@1",
}


@dataclass(frozen=True)
class QuarantineSubject:
    """Stable, non-payload quarantine identity presented to redrive authority.

    This is a request scope, never proof that the subject is currently quarantined.
    Phase 15 owns `ops.redrive-operation@1`; Wave 2 supplies the exact correctness
    scope a future operations implementation must re-resolve and authorize before
    any redrive state transition.
    """

    source: QuarantineSource
    owner_contract: str
    identity_scope: str
    message_id: str
    quarantine_generation: int
    quarantine_reason_class: str
    correlation_id: str
    reliability_profile_id: str
    tenant_id: str | None = None
    operation_id: str | None = None
    source_generation: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source, QuarantineSource):
            raise ValueError("source must be a canonical QuarantineSource")
        contract_name(self.owner_contract, "owner_contract")
        identifier(self.identity_scope, "identity_scope")
        identifier(self.message_id, "message_id")
        if isinstance(self.quarantine_generation, bool) or not isinstance(
            self.quarantine_generation, int
        ):
            raise ValueError("quarantine_generation must be an integer")
        if self.quarantine_generation < 0:
            raise ValueError("quarantine_generation must be non-negative")
        identifier(self.quarantine_reason_class, "quarantine_reason_class")
        identifier(self.correlation_id, "correlation_id")
        identifier(self.reliability_profile_id, "reliability_profile_id")
        optional_identifier(self.tenant_id, "tenant_id")
        optional_identifier(self.operation_id, "operation_id")
        optional_identifier(self.source_generation, "source_generation")
        expected_profile = _RELIABILITY_PROFILE_BY_SOURCE[self.source]
        if self.reliability_profile_id != expected_profile:
            raise ValueError("quarantine source must bind its exact accepted reliability profile")


@dataclass(frozen=True)
class RedriveRequest:
    redrive_operation_id: str
    subject: QuarantineSubject

    def __post_init__(self) -> None:
        identifier(self.redrive_operation_id, "redrive_operation_id")
        if not isinstance(self.subject, QuarantineSubject):
            raise ValueError("redrive request requires canonical QuarantineSubject")


@dataclass(frozen=True)
class RedriveAdmission:
    """Current privileged eligibility evidence for one exact quarantine subject.

    Concrete operator tooling, IAM, compatibility evaluation, placement resolution,
    comparison/KMS checks and capacity products remain replaceable C2/operations
    choices. The trusted adapter must independently re-establish the durable current
    quarantine state and collapse all required authorities into one exact
    request-bound decision. This object is not a bearer capability for another
    message, state generation or quarantine reason.
    """

    request: RedriveRequest
    quarantine_state_revision: str
    authorizing_principal_id: str
    privileged_authority_revision: str
    compatibility_revision: str
    effect_safety_revision: str
    capacity_admission_revision: str
    audit_revision: str
    observed_at: datetime
    current: bool
    eligible: bool
    placement_version: str | None = None
    reconciliation_revision: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.request, RedriveRequest):
            raise ValueError("redrive admission requires exact canonical request")
        for field in (
            "quarantine_state_revision",
            "authorizing_principal_id",
            "privileged_authority_revision",
            "compatibility_revision",
            "effect_safety_revision",
            "capacity_admission_revision",
            "audit_revision",
        ):
            identifier(getattr(self, field), field)
        aware(self.observed_at, "observed_at")
        if type(self.current) is not bool or type(self.eligible) is not bool:
            raise ValueError("current and eligible must be explicit booleans")
        optional_identifier(self.placement_version, "placement_version")
        optional_identifier(self.reconciliation_revision, "reconciliation_revision")
        if self.request.subject.tenant_id is not None and self.placement_version is None:
            raise ValueError("tenant-scoped redrive admission requires current placement evidence")
        if self.request.subject.tenant_id is None and self.placement_version is not None:
            raise ValueError("global redrive admission must not manufacture tenant placement")


class CurrentRedriveAuthorityPort(Protocol):
    def authorize_redrive(self, *, request: RedriveRequest) -> RedriveAdmission:
        """Return one current decision for the exact quarantined subject.

        Implementations must independently re-resolve the current durable quarantine
        record/state generation/reason, then establish current privileged authority,
        owning-contract compatibility/eligibility, tenant placement where applicable,
        duplicate/effect safety/reconciliation, capacity admission and audit
        responsibility. The caller-provided request is scope to check, never proof of
        current quarantine. Queue age, operator desire, broker DLQ state or time in
        quarantine are never sufficient authority.
        """


def require_current_redrive(
    authority: CurrentRedriveAuthorityPort,
    request: RedriveRequest,
) -> RedriveAdmission:
    if authority is None or not hasattr(authority, "authorize_redrive"):
        raise ReconciliationBlocked("current privileged redrive authority is unavailable")
    try:
        admission = authority.authorize_redrive(request=request)
    except Exception as exc:
        raise ReconciliationBlocked("redrive authority failed closed") from exc
    if not isinstance(admission, RedriveAdmission):
        raise ReconciliationBlocked("redrive authority returned malformed evidence")
    if admission.request != request:
        raise ReconciliationBlocked("redrive admission is bound to another quarantine subject")
    if admission.current is not True:
        raise ReconciliationBlocked("redrive privileged authority is not current")
    if admission.eligible is not True:
        raise ReconciliationBlocked("owning contract does not currently admit redrive")
    return admission


def outbox_redrive_request(
    message: LogicalMessage,
    *,
    claim_generation: int,
    quarantine_reason_class: str,
    redrive_operation_id: str,
) -> RedriveRequest:
    """Build redrive scope from immutable message authority, never operator payload."""

    if not isinstance(message, LogicalMessage):
        raise ValueError("outbox redrive requires canonical immutable LogicalMessage")
    return RedriveRequest(
        redrive_operation_id=redrive_operation_id,
        subject=QuarantineSubject(
            source=QuarantineSource.OUTBOX_PUBLICATION,
            owner_contract=message.contract_name,
            identity_scope=message.producer_message_scope,
            message_id=message.message_id,
            quarantine_generation=claim_generation,
            quarantine_reason_class=quarantine_reason_class,
            correlation_id=message.correlation_id,
            reliability_profile_id="rel.outbox-publication@1",
            tenant_id=message.tenant_id,
            operation_id=message.operation_id,
            source_generation=message.producer_generation,
        ),
    )


def inbox_redrive_request(
    identity: ScopedMessageIdentity,
    *,
    execution_generation: int,
    quarantine_reason_class: str,
    correlation_id: str,
    redrive_operation_id: str,
    operation_id: str | None = None,
    source_generation: str | None = None,
) -> RedriveRequest:
    """Build consumer redrive scope from trusted inbox identity and state generation."""

    if not isinstance(identity, ScopedMessageIdentity):
        raise ValueError("inbox redrive requires canonical ScopedMessageIdentity")
    return RedriveRequest(
        redrive_operation_id=redrive_operation_id,
        subject=QuarantineSubject(
            source=QuarantineSource.CONSUMER_INBOX,
            owner_contract=identity.consumer_contract,
            identity_scope=identity.message_identity_scope,
            message_id=identity.message_id,
            quarantine_generation=execution_generation,
            quarantine_reason_class=quarantine_reason_class,
            correlation_id=correlation_id,
            reliability_profile_id="rel.consumer-inbox-effect@1",
            tenant_id=identity.tenant_id,
            operation_id=operation_id,
            source_generation=source_generation,
        ),
    )
