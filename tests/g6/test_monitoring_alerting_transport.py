from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"apps/g6-monitoring-alerting-transport"))

from consumer import (  # noqa: E402
    HEALTH_CONTRACT,
    PROBLEM_CONTRACT,
    ClaimEvidence,
    MonitoringAlertingTransport,
    MonitoringEnvelope,
    ReceiptIdentity,
)
from pg_transport import PgMonitoringAlertingTransportPort  # noqa: E402
from jlmirror_async import AsyncExecutionAdmission, AsyncExecutionRequest  # noqa: E402
from jlmirror_authority import EnvironmentClass, PrincipalKind, TenantContext  # noqa: E402


NOW=datetime(2026,9,18,12,0,tzinfo=timezone.utc)


def context(tenant_id="tenant-a"):
    return TenantContext(
        tenant_id=tenant_id,
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
        fence_scope_id=f"{tenant_id}-worker",
        fence_epoch=7,
        constructed_at=NOW,
    )


class CurrentAuthority:
    def __init__(self, *, current=True, tenant_id="tenant-a") -> None:
        self.current=current
        self.tenant_id=tenant_id
        self.requests=[]

    def finalize_current_execution(self, *, request: AsyncExecutionRequest):
        self.requests.append(request)
        return AsyncExecutionAdmission(
            request=request,
            principal_id="service-alerting-worker",
            principal_credential_generation="cred-1",
            authorization_revision="authz-1",
            admission_revision="admission-1",
            runtime_generation="runtime-1",
            environment_class=EnvironmentClass.PRODUCTION,
            observed_at=NOW,
            current=self.current,
            tenant_context=context(self.tenant_id),
        )


def envelope(contract=PROBLEM_CONTRACT, *, tenant_id="tenant-a"):
    if contract==PROBLEM_CONTRACT:
        subject_type="monitoring_problem"
        subject_id="problem-1"
        transition="problem-transition-1"
        payload={
            "monitoring_resource_id":"resource-1",
            "monitoring_source_id":"source-1",
            "problem_id":"problem-1",
            "problem_transition_id":transition,
            "projection_revision":7,
            "source_instance_generation":"generation-1",
        }
    else:
        subject_type="monitoring_resource"
        subject_id="resource-1"
        transition="health-transition-1"
        payload={
            "health_transition_id":transition,
            "monitoring_resource_id":"resource-1",
            "monitoring_source_id":"source-1",
            "projection_revision":11,
            "source_instance_generation":"generation-1",
        }
    import hashlib
    sep=chr(31)
    scope="monitoring:tenant:"+hashlib.md5(tenant_id.encode()).hexdigest()
    message_id=contract+"@1:"+hashlib.md5((tenant_id+sep+transition).encode()).hexdigest()
    correlation="monitoring-correlation:"+hashlib.md5((tenant_id+sep+transition).encode()).hexdigest()
    causation="monitoring-transition:"+hashlib.md5((contract+sep+tenant_id+sep+transition).encode()).hexdigest()
    return MonitoringEnvelope(
        producer_message_scope=scope,
        message_id=message_id,
        message_class="integration_event",
        contract_name=contract,
        contract_version="1",
        producer="Monitoring",
        producer_generation=None,
        scope_class="tenant",
        tenant_id=tenant_id,
        subject_type=subject_type,
        subject_id=subject_id,
        occurred_at=NOW,
        created_at=None,
        operation_id=None,
        not_before=None,
        deadline=None,
        correlation_id=correlation,
        causation_id=causation,
        data_classification="confidential_tenant",
        serialization_profile_id="jsonb-text-utf8@1",
        encoded_payload=json.dumps(payload,separators=(",",":")).encode(),
    )


class FakePort:
    def __init__(self):
        self.state="admitted"
        self.calls=[]
        self.complete_result={
            "receipt_state":"completed",
            "effect_result_id":"g6-resync-result",
            "effect_result_kind":"monitoring_problem_owner_reread_current",
        }

    def admit(self,e):
        self.calls.append(("admit",e.contract_name))
        return ReceiptIdentity(e.producer_message_scope,e.message_id,e.tenant_id),self.state

    def claim(self,identity,*,executor_id,claim_seconds,admission):
        self.calls.append(("claim",identity.message_id,admission.request))
        return "processing",ClaimEvidence(executor_id,1)

    def complete(self,identity,claim):
        self.calls.append(("complete",identity.message_id,claim.execution_generation))
        return self.complete_result


class WorkerTests(unittest.TestCase):
    def test_problem_event_requires_current_execution_before_claim(self):
        port=FakePort()
        authority=CurrentAuthority()
        result=MonitoringAlertingTransport(
            port=port,execution_authority=authority,executor_id="worker-a"
        ).consume(envelope())
        self.assertEqual(result["receipt_state"],"completed")
        self.assertEqual(len(authority.requests),1)
        req=authority.requests[0]
        self.assertEqual(req.authority_contract,"alerting.monitoring-resync@1")
        self.assertEqual(req.runtime_profile_id,"runtime.worker@1")
        self.assertEqual(req.tenant_id,"tenant-a")
        self.assertEqual([c[0] for c in port.calls],["admit","claim","complete"])

    def test_health_contract_is_admitted_without_semantic_state_in_payload(self):
        e=envelope(HEALTH_CONTRACT)
        e.validate()
        payload=json.loads(e.encoded_payload)
        self.assertNotIn("health_class",payload)
        self.assertNotIn("evidence_state",payload)

    def test_noncurrent_execution_fails_before_claim(self):
        port=FakePort()
        with self.assertRaises(ValueError):
            MonitoringAlertingTransport(
                port=port,execution_authority=CurrentAuthority(current=False),executor_id="worker-a"
            ).consume(envelope())
        self.assertEqual([c[0] for c in port.calls],["admit"])

    def test_completed_duplicate_never_reexecutes(self):
        port=FakePort(); port.state="completed"
        authority=CurrentAuthority()
        result=MonitoringAlertingTransport(
            port=port,execution_authority=authority,executor_id="worker-a"
        ).consume(envelope())
        self.assertEqual(result,{"receipt_state":"completed","duplicate":True})
        self.assertEqual(authority.requests,[])
        self.assertEqual([c[0] for c in port.calls],["admit"])

    def test_reconciliation_blocked_receipt_never_reexecutes(self):
        port=FakePort(); port.state="reconciliation_required"
        result=MonitoringAlertingTransport(
            port=port,execution_authority=CurrentAuthority(),executor_id="worker-a"
        ).consume(envelope())
        self.assertEqual(result["receipt_state"],"reconciliation_required")
        self.assertEqual([c[0] for c in port.calls],["admit"])

    def test_wrong_contract_fails_before_durable_admission(self):
        port=FakePort()
        bad=envelope()
        bad=MonitoringEnvelope(**{**bad.__dict__,"contract_name":"alerting.rule.changed"})
        with self.assertRaises(ValueError):
            MonitoringAlertingTransport(
                port=port,execution_authority=CurrentAuthority(),executor_id="worker-a"
            ).consume(bad)
        self.assertEqual(port.calls,[])


class FakePg:
    def __init__(self,responses):
        self.responses=list(responses)
        self.calls=[]
    def query(self,sql,**variables):
        self.calls.append((sql,variables))
        return self.responses.pop(0)


class PgAdapterTests(unittest.TestCase):
    def test_adapter_uses_only_g6_capabilities(self):
        e=envelope()
        pg=FakePg([
            json.dumps({
                "consumer_contract":"alerting.monitoring-resync@1",
                "message_identity_scope":e.producer_message_scope,
                "message_id":e.message_id,
                "tenant_id":"tenant-a",
                "receipt_state":"admitted",
                "duplicate":False,
            }),
            json.dumps({"receipt_state":"processing","execution_generation":1,"claim_expires_at":"2026-09-18T12:00:30Z"}),
            json.dumps({"receipt_state":"completed","effect_result_id":"r","effect_result_kind":"monitoring_problem_owner_reread_current"}),
        ])
        port=PgMonitoringAlertingTransportPort(pg)
        identity,state=port.admit(e)
        admission=CurrentAuthority().finalize_current_execution(request=AsyncExecutionRequest(
            authority_contract="alerting.monitoring-resync@1",
            runtime_profile_id="runtime.worker@1",
            tenant_id="tenant-a",
            message_identity=identity.scoped(),
        ))
        claim_state,claim=port.claim(identity,executor_id="worker-a",claim_seconds=30,admission=admission)
        result=port.complete(identity,claim)
        self.assertEqual(state,"admitted")
        self.assertEqual(claim_state,"processing")
        self.assertEqual(result["receipt_state"],"completed")
        sql="\n".join(call[0] for call in pg.calls)
        self.assertIn("g6_admit_monitoring_alerting_message",sql)
        self.assertIn("g6_claim_monitoring_alerting_receipt",sql)
        self.assertIn("g6_complete_monitoring_alerting_resync",sql)
        self.assertNotIn("INSERT INTO",sql.upper())
        self.assertNotIn("UPDATE ",sql.upper())


if __name__=="__main__":
    unittest.main()
