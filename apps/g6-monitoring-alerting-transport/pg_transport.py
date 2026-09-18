from __future__ import annotations

from datetime import datetime
import json
from typing import Protocol

from consumer import ClaimEvidence, MonitoringEnvelope, ReceiptIdentity


class PgQueryPort(Protocol):
    def query(self, sql: str, **variables: str) -> str: ...


class PgMonitoringAlertingTransportPort:
    def __init__(self, pg: PgQueryPort) -> None:
        self._pg = pg

    def admit(self, envelope: MonitoringEnvelope) -> tuple[ReceiptIdentity, str]:
        raw = self._pg.query(
            """
SELECT system.g6_admit_monitoring_alerting_message(
  :'producer_message_scope', :'message_id', :'message_class', :'contract_name',
  :'contract_version', :'producer', NULLIF(:'producer_generation',''),
  :'scope_class', :'tenant_id', :'subject_type', :'subject_id',
  :'occurred_at'::timestamptz, NULLIF(:'created_at','')::timestamptz,
  NULLIF(:'operation_id',''), NULLIF(:'not_before','')::timestamptz,
  NULLIF(:'deadline','')::timestamptz, :'correlation_id',
  NULLIF(:'causation_id',''), :'data_classification',
  :'serialization_profile_id', decode(:'encoded_payload_hex','hex')
)::text;
""",
            producer_message_scope=envelope.producer_message_scope,
            message_id=envelope.message_id,
            message_class=envelope.message_class,
            contract_name=envelope.contract_name,
            contract_version=envelope.contract_version,
            producer=envelope.producer,
            producer_generation=envelope.producer_generation or "",
            scope_class=envelope.scope_class,
            tenant_id=envelope.tenant_id,
            subject_type=envelope.subject_type,
            subject_id=envelope.subject_id,
            occurred_at=envelope.occurred_at.isoformat(),
            created_at="" if envelope.created_at is None else envelope.created_at.isoformat(),
            operation_id=envelope.operation_id or "",
            not_before="" if envelope.not_before is None else envelope.not_before.isoformat(),
            deadline="" if envelope.deadline is None else envelope.deadline.isoformat(),
            correlation_id=envelope.correlation_id,
            causation_id=envelope.causation_id,
            data_classification=envelope.data_classification,
            serialization_profile_id=envelope.serialization_profile_id,
            encoded_payload_hex=envelope.encoded_payload.hex(),
        )
        value = json.loads(raw)
        expected = {
            "consumer_contract",
            "message_identity_scope",
            "message_id",
            "tenant_id",
            "receipt_state",
            "duplicate",
        }
        if set(value) != expected:
            raise RuntimeError("G6 admit response shape is invalid")
        identity = ReceiptIdentity(
            message_identity_scope=value["message_identity_scope"],
            message_id=value["message_id"],
            tenant_id=value["tenant_id"],
        )
        return identity, value["receipt_state"]

    def claim(
        self,
        identity: ReceiptIdentity,
        *,
        executor_id: str,
        claim_seconds: int,
        admission,
    ) -> tuple[str, ClaimEvidence | None]:
        context = admission.tenant_context
        if context is None or context.tenant_id != identity.tenant_id:
            raise RuntimeError("G6 claim requires exact tenant execution context")

        raw = self._pg.query(
            """
SELECT system.g6_claim_monitoring_alerting_receipt(
  :'scope', :'message_id', :'executor_id', :'claim_seconds'::integer,
  :'admission_revision', :'authorization_revision', :'principal_id',
  :'principal_credential_generation', :'runtime_generation',
  :'environment_class', :'placement_version', :'fence_scope_id',
  :'fence_epoch'::bigint
)::text;
""",
            scope=identity.message_identity_scope,
            message_id=identity.message_id,
            executor_id=executor_id,
            claim_seconds=str(claim_seconds),
            admission_revision=admission.admission_revision,
            authorization_revision=admission.authorization_revision,
            principal_id=admission.principal_id,
            principal_credential_generation=admission.principal_credential_generation,
            runtime_generation=admission.runtime_generation,
            environment_class=admission.environment_class.value,
            placement_version=context.placement_version,
            fence_scope_id=context.fence_scope_id,
            fence_epoch=str(context.fence_epoch),
        )
        value = json.loads(raw)
        state = value.get("receipt_state")
        if state == "processing":
            generation = value.get("execution_generation")
            if not isinstance(generation, int) or generation <= 0:
                raise RuntimeError("G6 processing claim generation is invalid")
            return state, ClaimEvidence(
                executor_id=executor_id,
                execution_generation=generation,
            )
        if state in {
            "completed",
            "reconciliation_required",
            "quarantined",
            "failed_terminal",
            "processing",
        }:
            return state, None
        raise RuntimeError("G6 claim response state is invalid")

    def complete(self, identity: ReceiptIdentity, claim: ClaimEvidence) -> dict:
        raw = self._pg.query(
            """
SELECT system.g6_complete_monitoring_alerting_resync(
  :'scope', :'message_id', :'executor_id', :'execution_generation'::bigint
)::text;
""",
            scope=identity.message_identity_scope,
            message_id=identity.message_id,
            executor_id=claim.executor_id,
            execution_generation=str(claim.execution_generation),
        )
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise RuntimeError("G6 completion response is invalid")
        allowed = {"completed", "reconciliation_required"}
        if value.get("receipt_state") not in allowed:
            raise RuntimeError("G6 completion state is invalid")
        return value
