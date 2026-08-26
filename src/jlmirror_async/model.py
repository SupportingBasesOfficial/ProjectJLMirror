from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hmac
import re

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$")
_CONTRACT_RE = re.compile(r"^[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)+$")


class AsyncCorrectnessError(RuntimeError):
    """Base error for fail-closed Wave 2 correctness boundaries."""


class IntegrityConflict(AsyncCorrectnessError):
    """Same trusted scoped identity was presented with conflicting meaning."""


class ReconciliationBlocked(AsyncCorrectnessError):
    """A protected effect cannot continue until ambiguity/continuity is reconciled."""


class InvalidTransition(AsyncCorrectnessError):
    """A caller attempted an invalid correctness-state transition."""


class MessageClass(str, Enum):
    DOMAIN_EVENT = "domain_event"
    INTEGRATION_EVENT = "integration_event"
    JOB_COMMAND = "job_command"
    PROCESS_SIGNAL = "process_signal"
    REALTIME_PROJECTION = "realtime_projection"
    OUTBOUND_WEBHOOK_DELIVERY = "outbound_webhook_delivery"


class MessageScope(str, Enum):
    TENANT = "tenant"
    GLOBAL = "global"


class EquivalenceRelation(str, Enum):
    EQUIVALENT = "equivalent"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"


class InboxState(str, Enum):
    ADMITTED = "admitted"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED_TERMINAL = "failed_terminal"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    QUARANTINED = "quarantined"


class OutboxDispatchState(str, Enum):
    PENDING = "pending"
    CLAIMED = "claimed"
    PUBLISHED = "published"
    QUARANTINED = "quarantined"


class OperationState(str, Enum):
    PREPARED = "prepared"
    ATTEMPTING = "attempting"
    COMPLETED = "completed"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    FAILED_TERMINAL = "failed_terminal"


class ReconciliationResolution(str, Enum):
    EFFECT_CONFIRMED = "effect_confirmed"
    EFFECT_PROVEN_ABSENT = "effect_proven_absent"
    STILL_UNKNOWN = "still_unknown"


def aware(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def identifier(value: str, field: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise ValueError(f"invalid {field}")
    return value


def contract_name(value: str, field: str) -> str:
    if not isinstance(value, str) or not _CONTRACT_RE.fullmatch(value):
        raise ValueError(f"invalid {field}")
    return value


def optional_identifier(value: str | None, field: str) -> str | None:
    if value is not None:
        identifier(value, field)
    return value


@dataclass(frozen=True)
class ComparisonEvidence:
    """Opaque durable equality evidence under an accepted comparison profile.

    Wave 2 intentionally does not choose digest/MAC/retained-content/KMS mechanics.
    `evidence` is adapter-produced opaque bytes. Equality is meaningful only when
    profile, profile version, evidence form and historical verifier generation are
    identical. Otherwise equality is unknown and must fail closed/reconcile.
    """

    comparison_profile_id: str
    comparison_profile_version: str
    evidence_form: str
    evidence: bytes
    verifier_generation: str | None = None

    def __post_init__(self) -> None:
        identifier(self.comparison_profile_id, "comparison_profile_id")
        identifier(self.comparison_profile_version, "comparison_profile_version")
        identifier(self.evidence_form, "evidence_form")
        optional_identifier(self.verifier_generation, "verifier_generation")
        if not isinstance(self.evidence, bytes) or not self.evidence:
            raise ValueError("comparison evidence must be non-empty opaque bytes")

    def relation_to(self, other: "ComparisonEvidence") -> EquivalenceRelation:
        if not isinstance(other, ComparisonEvidence):
            return EquivalenceRelation.UNKNOWN
        if (
            self.comparison_profile_id != other.comparison_profile_id
            or self.comparison_profile_version != other.comparison_profile_version
            or self.evidence_form != other.evidence_form
            or self.verifier_generation != other.verifier_generation
        ):
            return EquivalenceRelation.UNKNOWN
        return (
            EquivalenceRelation.EQUIVALENT
            if hmac.compare_digest(self.evidence, other.evidence)
            else EquivalenceRelation.MISMATCH
        )


@dataclass(frozen=True)
class MessageSubject:
    subject_type: str
    subject_id: str

    def __post_init__(self) -> None:
        identifier(self.subject_type, "subject_type")
        identifier(self.subject_id, "subject_id")


@dataclass(frozen=True)
class LogicalMessage:
    """Transport-independent logical message plus adapter-owned payload encoding.

    Timestamp fields follow the accepted Phase 10 class semantics. Event/fact
    classes use `occurred_at`; work/process classes use `created_at`. A job command
    is additionally bound to its stable durable `operation_id`.
    """

    message_id: str
    producer_message_scope: str
    message_class: MessageClass
    contract_name: str
    contract_version: str
    producer: str
    scope: MessageScope
    correlation_id: str
    data_classification: str
    serialization_profile_id: str
    encoded_payload: bytes
    comparison_evidence: ComparisonEvidence
    tenant_id: str | None = None
    producer_generation: str | None = None
    causation_id: str | None = None
    subject: MessageSubject | None = None
    occurred_at: datetime | None = None
    created_at: datetime | None = None
    operation_id: str | None = None
    not_before: datetime | None = None
    deadline: datetime | None = None

    def __post_init__(self) -> None:
        identifier(self.message_id, "message_id")
        identifier(self.producer_message_scope, "producer_message_scope")
        if not isinstance(self.message_class, MessageClass):
            raise ValueError("message_class must be a canonical MessageClass")
        contract_name(self.contract_name, "contract_name")
        identifier(self.contract_version, "contract_version")
        identifier(self.producer, "producer")
        if not isinstance(self.scope, MessageScope):
            raise ValueError("scope must be a canonical MessageScope")
        identifier(self.correlation_id, "correlation_id")
        identifier(self.data_classification, "data_classification")
        identifier(self.serialization_profile_id, "serialization_profile_id")
        if not isinstance(self.encoded_payload, bytes):
            raise ValueError("encoded_payload must be bytes from the selected adapter profile")
        if not isinstance(self.comparison_evidence, ComparisonEvidence):
            raise ValueError("comparison_evidence must be explicit")
        optional_identifier(self.producer_generation, "producer_generation")
        optional_identifier(self.causation_id, "causation_id")
        optional_identifier(self.operation_id, "operation_id")
        if self.subject is not None and not isinstance(self.subject, MessageSubject):
            raise ValueError("subject must be MessageSubject when present")
        if self.scope is MessageScope.TENANT:
            identifier(self.tenant_id or "", "tenant_id")
        elif self.tenant_id is not None:
            raise ValueError("explicit global message must not carry tenant_id")

        fact_classes = {
            MessageClass.DOMAIN_EVENT,
            MessageClass.INTEGRATION_EVENT,
            MessageClass.REALTIME_PROJECTION,
        }
        work_classes = {
            MessageClass.JOB_COMMAND,
            MessageClass.PROCESS_SIGNAL,
            MessageClass.OUTBOUND_WEBHOOK_DELIVERY,
        }
        if self.message_class in fact_classes:
            if self.occurred_at is None or self.created_at is not None:
                raise ValueError("event/projection class requires occurred_at and forbids created_at")
            aware(self.occurred_at, "occurred_at")
        elif self.message_class in work_classes:
            if self.created_at is None or self.occurred_at is not None:
                raise ValueError("work/process class requires created_at and forbids occurred_at")
            created = aware(self.created_at, "created_at")
            if self.message_class is MessageClass.JOB_COMMAND and self.operation_id is None:
                raise ValueError("job_command requires stable durable operation_id")
            if self.message_class is not MessageClass.JOB_COMMAND and (
                self.not_before is not None or self.deadline is not None
            ):
                raise ValueError("not_before/deadline are valid only for job_command")
            if self.not_before is not None:
                not_before = aware(self.not_before, "not_before")
                if not_before < created:
                    raise ValueError("not_before cannot precede job created_at")
            else:
                not_before = None
            if self.deadline is not None:
                deadline = aware(self.deadline, "deadline")
                if deadline < created:
                    raise ValueError("deadline cannot precede job created_at")
                if not_before is not None and deadline < not_before:
                    raise ValueError("deadline cannot precede not_before")
        else:  # pragma: no cover - enum exhaustiveness guard
            raise ValueError("unsupported message_class")

    @property
    def outbox_identity(self) -> tuple[str, str]:
        return (self.producer_message_scope, self.message_id)


@dataclass(frozen=True)
class ScopedMessageIdentity:
    consumer_contract: str
    message_identity_scope: str
    message_id: str
    tenant_id: str | None = None

    def __post_init__(self) -> None:
        contract_name(self.consumer_contract, "consumer_contract")
        identifier(self.message_identity_scope, "message_identity_scope")
        identifier(self.message_id, "message_id")
        optional_identifier(self.tenant_id, "tenant_id")

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.consumer_contract, self.message_identity_scope, self.message_id)


@dataclass(frozen=True)
class EffectResultLink:
    result_id: str
    result_kind: str

    def __post_init__(self) -> None:
        identifier(self.result_id, "result_id")
        identifier(self.result_kind, "result_kind")


@dataclass(frozen=True)
class CrossAuthorityOperationSnapshot:
    """One coherent authority observation for a stable cross-authority operation."""

    operation_id: str
    state: OperationState
    attempt_generation: int
    outcome: EffectResultLink | None = None
    reconciliation_resolution: ReconciliationResolution | None = None
    reconciliation_revision: str | None = None

    def __post_init__(self) -> None:
        identifier(self.operation_id, "operation_id")
        if not isinstance(self.state, OperationState):
            raise ValueError("state must be canonical OperationState")
        if isinstance(self.attempt_generation, bool) or not isinstance(self.attempt_generation, int):
            raise ValueError("attempt_generation must be an integer")
        if self.attempt_generation < 0:
            raise ValueError("attempt_generation must be non-negative")
        if self.outcome is not None and not isinstance(self.outcome, EffectResultLink):
            raise ValueError("outcome must be EffectResultLink when present")
        if self.reconciliation_resolution is not None and not isinstance(
            self.reconciliation_resolution,
            ReconciliationResolution,
        ):
            raise ValueError("reconciliation_resolution must be canonical")
        optional_identifier(self.reconciliation_revision, "reconciliation_revision")
        if (self.reconciliation_resolution is None) != (self.reconciliation_revision is None):
            raise ValueError("reconciliation resolution and revision must be present together")
        if self.state is OperationState.COMPLETED and self.outcome is None:
            raise ValueError("completed operation snapshot requires durable outcome")
        if self.state is not OperationState.COMPLETED and self.outcome is not None:
            raise ValueError("non-completed operation snapshot cannot carry durable outcome")
        if self.reconciliation_resolution is ReconciliationResolution.EFFECT_CONFIRMED:
            if self.state is not OperationState.COMPLETED or self.outcome is None:
                raise ValueError("effect_confirmed snapshot must be completed with outcome")
        elif self.reconciliation_resolution is ReconciliationResolution.EFFECT_PROVEN_ABSENT:
            if self.state is not OperationState.PREPARED or self.outcome is not None:
                raise ValueError("effect_proven_absent snapshot must be prepared without outcome")
        elif self.reconciliation_resolution is ReconciliationResolution.STILL_UNKNOWN:
            if self.state is not OperationState.RECONCILIATION_REQUIRED or self.outcome is not None:
                raise ValueError("still_unknown snapshot must remain reconciliation_required")


@dataclass(frozen=True)
class BrokerPublicationReceipt:
    receipt_id: str
    observed_at: datetime

    def __post_init__(self) -> None:
        identifier(self.receipt_id, "receipt_id")
        aware(self.observed_at, "observed_at")