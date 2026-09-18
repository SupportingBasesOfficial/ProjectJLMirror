from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"apps/g6-monitoring-alerting-transport"))

from consumer import MonitoringAlertingTransport, MonitoringEnvelope, ReceiptIdentity, ClaimEvidence  # noqa: E402
from jlmirror_async import AsyncExecutionAdmission, AsyncExecutionRequest  # noqa: E402
from jlmirror_authority import EnvironmentClass, PrincipalKind, TenantContext  # noqa: E402

NOW=datetime(2026,9,18,12,0,tzinfo=timezone.utc)


class Authority:
    def finalize_current_execution(self, *, request: AsyncExecutionRequest):
        context=TenantContext(
            tenant_id="tenant-a",
            principal_id="service-alerting-worker",
            principal_kind=PrincipalKind.SERVICE_WORKLOAD,
            principal_credential_generation="cred-1",
            cell_id="cell-a",
            placement_version="placement-1",
            runtime_generation="runtime-1",
            runtime_profile_id="runtime.worker@1",
            runtime_isolation_class="isolation.application-serving@1",
            configuration_generation="config-1",
            workload_credential_generation="workload-1",
            network_policy_generation="network-1",
            environment_class=EnvironmentClass.PRODUCTION,
            isolation_class="pooled",
            fence_scope_id="tenant-a-worker",
            fence_epoch=7,
            constructed_at=NOW,
        )
        return AsyncExecutionAdmission(
            request=request,
            principal_id=context.principal_id,
            principal_credential_generation=context.principal_credential_generation,
            authorization_revision="authz-1",
            admission_revision="admission-1",
            runtime_generation=context.runtime_generation,
            environment_class=context.environment_class,
            observed_at=NOW,
            current=True,
            tenant_context=context,
        )


class Port:
    def admit(self,envelope):
        return ReceiptIdentity(envelope.producer_message_scope,envelope.message_id,envelope.tenant_id),"admitted"
    def claim(self,identity,*,executor_id,claim_seconds,admission):
        if admission.request.tenant_id!=identity.tenant_id:
            raise RuntimeError("tenant binding drift")
        return "processing",ClaimEvidence(executor_id,1)
    def complete(self,identity,claim):
        return {
            "receipt_state":"completed",
            "effect_result_id":"g6-resync:smoke",
            "effect_result_kind":"monitoring_problem_owner_reread_current",
        }


def main()->int:
    payload={
        "monitoring_resource_id":"resource-1",
        "monitoring_source_id":"source-1",
        "problem_id":"problem-1",
        "problem_transition_id":"problem-transition-1",
        "projection_revision":7,
        "source_instance_generation":"generation-1",
    }
    import hashlib
    sep=chr(31)
    contract="monitoring.problem-state.changed"
    transition="problem-transition-1"
    tenant="tenant-a"
    envelope=MonitoringEnvelope(
        producer_message_scope="monitoring:tenant:"+hashlib.md5(tenant.encode()).hexdigest(),
        message_id=contract+"@1:"+hashlib.md5((tenant+sep+transition).encode()).hexdigest(),
        message_class="integration_event",
        contract_name=contract,
        contract_version="1",
        producer="Monitoring",
        producer_generation=None,
        scope_class="tenant",
        tenant_id=tenant,
        subject_type="monitoring_problem",
        subject_id="problem-1",
        occurred_at=NOW,
        created_at=None,
        operation_id=None,
        not_before=None,
        deadline=None,
        correlation_id="monitoring-correlation:"+hashlib.md5((tenant+sep+transition).encode()).hexdigest(),
        causation_id="monitoring-transition:"+hashlib.md5((contract+sep+tenant+sep+transition).encode()).hexdigest(),
        data_classification="confidential_tenant",
        serialization_profile_id="jsonb-text-utf8@1",
        encoded_payload=json.dumps(payload,separators=(",",":")).encode(),
    )
    result=MonitoringAlertingTransport(
        port=Port(),
        execution_authority=Authority(),
        executor_id="worker-container",
    ).consume(envelope)
    if result.get("receipt_state")!="completed":
        raise AssertionError("G6 container smoke did not complete")
    print("g6_worker_container_smoke=PASS current_execution=PASS durable_resync_boundary=PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
