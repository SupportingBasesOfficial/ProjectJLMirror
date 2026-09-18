from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from jlmirror_async import (
    AsyncExecutionRequest,
    CurrentAsyncExecutionAuthorityPort,
    ScopedMessageIdentity,
    require_current_execution,
)

CONSUMER_CONTRACT = "alerting.monitoring-resync@1"
PROBLEM_CONTRACT = "monitoring.problem-state.changed"
HEALTH_CONTRACT = "monitoring.health-projection.changed"


@dataclass(frozen=True)
class MonitoringEnvelope:
    producer_message_scope: str
    message_id: str
    message_class: str
    contract_name: str
    contract_version: str
    producer: str
    producer_generation: str | None
    scope_class: str
    tenant_id: str
    subject_type: str
    subject_id: str
    occurred_at: datetime
    created_at: datetime | None
    operation_id: str | None
    not_before: datetime | None
    deadline: datetime | None
    correlation_id: str
    causation_id: str
    data_classification: str
    serialization_profile_id: str
    encoded_payload: bytes

    def validate(self) -> None:
        if self.contract_name not in {PROBLEM_CONTRACT, HEALTH_CONTRACT}:
            raise ValueError("unsupported Monitoring integration contract")
        if (
            self.message_class != "integration_event"
            or self.contract_version != "1"
            or self.producer != "Monitoring"
            or self.producer_generation is not None
            or self.scope_class != "tenant"
            or self.data_classification != "confidential_tenant"
            or self.serialization_profile_id != "jsonb-text-utf8@1"
            or self.created_at is not None
            or self.operation_id is not None
            or self.not_before is not None
            or self.deadline is not None
        ):
            raise ValueError("Monitoring integration envelope is not canonical")
        for value, field, bound in (
            (self.producer_message_scope, "producer_message_scope", 512),
            (self.message_id, "message_id", 1024),
            (self.tenant_id, "tenant_id", 512),
            (self.subject_type, "subject_type", 128),
            (self.subject_id, "subject_id", 1024),
            (self.correlation_id, "correlation_id", 1024),
            (self.causation_id, "causation_id", 1024),
        ):
            if not value or len(value) > bound:
                raise ValueError(f"{field} is invalid")
        if len(self.encoded_payload) > 16384:
            raise ValueError("Monitoring integration payload exceeds accepted bound")
        if self.contract_name == PROBLEM_CONTRACT and self.subject_type != "monitoring_problem":
            raise ValueError("Problem event subject type is invalid")
        if self.contract_name == HEALTH_CONTRACT and self.subject_type != "monitoring_resource":
            raise ValueError("Health event subject type is invalid")


@dataclass(frozen=True)
class ReceiptIdentity:
    message_identity_scope: str
    message_id: str
    tenant_id: str

    def scoped(self) -> ScopedMessageIdentity:
        return ScopedMessageIdentity(
            consumer_contract=CONSUMER_CONTRACT,
            message_identity_scope=self.message_identity_scope,
            message_id=self.message_id,
            tenant_id=self.tenant_id,
        )


@dataclass(frozen=True)
class ClaimEvidence:
    executor_id: str
    execution_generation: int


class TransportPort(Protocol):
    def admit(self, envelope: MonitoringEnvelope) -> tuple[ReceiptIdentity, str]: ...
    def claim(
        self,
        identity: ReceiptIdentity,
        *,
        executor_id: str,
        claim_seconds: int,
        admission,
    ) -> tuple[str, ClaimEvidence | None]: ...
    def complete(self, identity: ReceiptIdentity, claim: ClaimEvidence) -> dict: ...


class MonitoringAlertingTransport:
    def __init__(
        self,
        *,
        port: TransportPort,
        execution_authority: CurrentAsyncExecutionAuthorityPort,
        executor_id: str,
        claim_seconds: int = 30,
    ) -> None:
        if not executor_id or len(executor_id) > 512:
            raise ValueError("executor_id is invalid")
        if claim_seconds < 1 or claim_seconds > 300:
            raise ValueError("claim_seconds is invalid")
        self._port = port
        self._execution_authority = execution_authority
        self._executor_id = executor_id
        self._claim_seconds = claim_seconds

    def consume(self, envelope: MonitoringEnvelope) -> dict:
        envelope.validate()
        identity, state = self._port.admit(envelope)
        if (
            identity.message_identity_scope != envelope.producer_message_scope
            or identity.message_id != envelope.message_id
            or identity.tenant_id != envelope.tenant_id
        ):
            raise RuntimeError("durable receipt identity does not match validated envelope")

        if state == "completed":
            return {"receipt_state": "completed", "duplicate": True}
        if state in {"reconciliation_required", "quarantined", "failed_terminal"}:
            return {"receipt_state": state, "duplicate": True}
        if state == "processing":
            return {"receipt_state": "processing", "duplicate": True}
        if state != "admitted":
            raise RuntimeError("durable receipt state is unsupported")

        request = AsyncExecutionRequest(
            authority_contract=CONSUMER_CONTRACT,
            runtime_profile_id="runtime.worker@1",
            tenant_id=identity.tenant_id,
            message_identity=identity.scoped(),
        )
        admission = require_current_execution(self._execution_authority, request)
        context = admission.tenant_context
        if context is None:
            raise RuntimeError("tenant-scoped consumer requires TenantContext")

        claim_state, claim = self._port.claim(
            identity,
            executor_id=self._executor_id,
            claim_seconds=self._claim_seconds,
            admission=admission,
        )
        if claim_state != "processing" or claim is None:
            return {"receipt_state": claim_state, "duplicate": True}

        result = self._port.complete(identity, claim)
        if result.get("receipt_state") not in {"completed", "reconciliation_required"}:
            raise RuntimeError("G6 completion returned unsupported state")
        return result
