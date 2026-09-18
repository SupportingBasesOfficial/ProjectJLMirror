from __future__ import annotations

import json
import subprocess

from consumer import ClaimEvidence, MonitoringEnvelope, ReceiptIdentity


class Pg:
    def __init__(self, *, container: str, database: str) -> None:
        self.container = container
        self.database = database

    def query(self, sql: str, **variables: str) -> str:
        command = [
            "docker", "exec", "-i", self.container,
            "psql", "-Atq", "-v", "ON_ERROR_STOP=1",
            "-U", "postgres", "-d", self.database,
        ]
        for key, value in variables.items():
            command.extend(["-v", f"{key}={value}"])
        completed = subprocess.run(
            command,
            input=sql,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip()[-3000:])
        return completed.stdout.strip()


class PgTransportPort:
    def __init__(self, pg: Pg) -> None:
        self.pg = pg

    def admit(self, envelope: MonitoringEnvelope) -> tuple[ReceiptIdentity, str]:
        raw = self.pg.query(
            """
BEGIN;
SET LOCAL ROLE jlmirror_g6_alerting_transport_invoker;
SELECT system.g6_admit_monitoring_alerting_message(
    :'producer_scope', :'message_id', :'message_class', :'contract_name',
    :'contract_version', :'producer', NULLIF(:'producer_generation',''),
    :'scope_class', :'tenant_id', :'subject_type', :'subject_id',
    :'occurred_at'::timestamptz, NULLIF(:'created_at','')::timestamptz,
    NULLIF(:'operation_id',''), NULLIF(:'not_before','')::timestamptz,
    NULLIF(:'deadline','')::timestamptz, :'correlation_id',
    NULLIF(:'causation_id',''), :'data_classification',
    :'serialization_profile_id', decode(:'payload_hex','hex')
)::text;
COMMIT;
""",
            producer_scope=envelope.producer_message_scope,
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
            created_at=envelope.created_at.isoformat() if envelope.created_at else "",
            operation_id=envelope.operation_id or "",
            not_before=envelope.not_before.isoformat() if envelope.not_before else "",
            deadline=envelope.deadline.isoformat() if envelope.deadline else "",
            correlation_id=envelope.correlation_id,
            causation_id=envelope.causation_id,
            data_classification=envelope.data_classification,
            serialization_profile_id=envelope.serialization_profile_id,
            payload_hex=envelope.encoded_payload.hex(),
        )
        payload = json.loads(raw)
        expected = {
            "consumer_contract", "message_identity_scope", "message_id",
            "tenant_id", "receipt_state", "duplicate",
        }
        if set(payload) != expected:
            raise RuntimeError("G6 admission response shape is invalid")
        identity = ReceiptIdentity(
            message_identity_scope=payload["message_identity_scope"],
            message_id=payload["message_id"],
            tenant_id=payload["tenant_id"],
        )
        return identity, payload["receipt_state"]

    def claim(
        self,
        identity: ReceiptIdentity,
        *,
        executor_id: str,
        claim_seconds: int,
        admission,
    ) -> tuple[str, ClaimEvidence | None]:
        context = admission.tenant_context
        if context is None:
            raise RuntimeError("tenant claim requires TenantContext")
        raw = self.pg.query(
            """
BEGIN;
SET LOCAL ROLE jlmirror_g6_alerting_transport_invoker;
SELECT system.g6_claim_monitoring_alerting_receipt(
    :'identity_scope', :'message_id', :'executor_id', :'claim_seconds'::integer,
    :'admission_revision', :'authorization_revision', :'principal_id',
    :'principal_credential_generation', :'runtime_generation',
    :'environment_class', :'placement_version', :'fence_scope_id',
    :'fence_epoch'::bigint
)::text;
COMMIT;
""",
            identity_scope=identity.message_identity_scope,
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
        payload = json.loads(raw)
        state = payload.get("receipt_state")
        generation = payload.get("execution_generation")
        if state == "processing":
            if type(generation) is not int or generation < 1:
                raise RuntimeError("G6 processing claim lacks execution generation")
            return state, ClaimEvidence(executor_id=executor_id, execution_generation=generation)
        return str(state), None

    def complete(self, identity: ReceiptIdentity, claim: ClaimEvidence) -> dict:
        raw = self.pg.query(
            """
BEGIN;
SET LOCAL ROLE jlmirror_g6_alerting_transport_invoker;
SELECT system.g6_complete_monitoring_alerting_resync(
    :'identity_scope', :'message_id', :'executor_id', :'execution_generation'::bigint
)::text;
COMMIT;
""",
            identity_scope=identity.message_identity_scope,
            message_id=identity.message_id,
            executor_id=claim.executor_id,
            execution_generation=str(claim.execution_generation),
        )
        payload = json.loads(raw)
        if payload.get("receipt_state") not in {"completed", "reconciliation_required"}:
            raise RuntimeError("G6 completion response shape is invalid")
        return payload
