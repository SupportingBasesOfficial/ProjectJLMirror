from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"apps/g6-monitoring-alerting-transport"))

from consumer import (  # noqa: E402
    ClaimEvidence,
    MonitoringAlertingTransport,
    MonitoringEnvelope,
    ReceiptIdentity,
)
from jlmirror_async import AsyncExecutionAdmission  # noqa: E402
from jlmirror_authority import EnvironmentClass, PrincipalKind, TenantContext  # noqa: E402

NOW=datetime(2026,9,18,12,0,tzinfo=timezone.utc)


def context(tenant_id: str="tenant-a")->TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        principal_id="service-worker-a",
        principal_kind=PrincipalKind.INTERNAL_SERVICE_PRINCIPAL,
        principal_credential_generation="cred-7",
        cell_id="cell-a",
        placement_version="placement-11",
        runtime_generation="runtime-4",
        runtime_profile_id="runtime.worker@1",
        runtime_isolation_class="isolation.application-serving@1",
        configuration_generation="config-3",
        workload_credential_generation="workload-5",
        network_policy_generation="network-2",
        environment_class=EnvironmentClass.PRODUCTION,
        isolation_class="pooled",
        fence_scope_id=f"{tenant_id}-worker",
        fence_epoch=9,
        constructed_at=NOW,
    )


class CurrentAuthority:
    def __init__(self, *, current: bool=True, fail: bool=False) -> None:
        self.current=current
        self.fail=fail
        self.requests=[]

    def finalize_current_execution(self, *, request):
        self.requests.append(request)
        if self.fail:
            raise RuntimeError("authority unavailable")
        return AsyncExecutionAdmission(
            request=request,
            principal_id="service-worker-a",
            principal_credential_generation="cred-7",
            authorization_revision="authz-19",
            admission_revision=f"admission-{len(self.requests)}",
            runtime_generation="runtime-4",
            environment_class=EnvironmentClass.PRODUCTION,
            observed_at=NOW,
            current=self.current,
            tenant_context=context(request.tenant_id) if request.tenant_id else None,
        )


class Port:
    def __init__(self) -> None:
        self.state="admitted"
        self.identity=ReceiptIdentity("monitoring:tenant:scope","message-1","tenant-a")
        self.claimed=[]
        self.completed=[]

    def admit(self,envelope):
        self.identity=ReceiptIdentity(
            envelope.producer_message_scope,
            envelope.message_id,
            envelope.tenant_id,
        )
        return self.identity,self.state

    def claim(self,identity,*,executor_id,claim_seconds,admission):
        self.claimed.append((identity,executor_id,claim_seconds,admission))
        return "processing",ClaimEvidence(executor_id=executor_id,execution_generation=1)

    def complete(self,identity,claim):
        self.completed.append((identity,claim))
        return {
            "receipt_state":"completed",
            "effect_result_id":"g6-resync:abc",
            "effect_result_kind":"monitoring_problem_owner_reread_current",
        }


def envelope(*,contract="monitoring.problem-state.changed")->MonitoringEnvelope:
    payload=(
        {
            "problem_id":"problem-1",
            "monitoring_source_id":"source-a",
            "source_instance_generation":"generation-a",
            "monitoring_resource_id":"resource-1",
            "projection_revision":7,
            "problem_transition_id":"transition-1",
        }
        if contract=="monitoring.problem-state.changed"
        else {
            "monitoring_source_id":"source-a",
            "source_instance_generation":"generation-a",
            "monitoring_resource_id":"resource-1",
            "projection_revision":11,
            "health_transition_id":"health-transition-1",
        }
    )
    return MonitoringEnvelope(
        producer_message_scope="monitoring:tenant:scope",
        message_id="message-1",
        message_class="integration_event",
        contract_name=contract,
        contract_version="1",
        producer="Monitoring",
        producer_generation=None,
        scope_class="tenant",
        tenant_id="tenant-a",
        subject_type="monitoring_problem" if contract.endswith("problem-state.changed") else "monitoring_resource",
        subject_id="problem-1" if contract.endswith("problem-state.changed") else "resource-1",
        occurred_at=NOW,
        created_at=None,
        operation_id=None,
        not_before=None,
        deadline=None,
        correlation_id="correlation-1",
        causation_id="causation-1",
        data_classification="confidential_tenant",
        serialization_profile_id="jsonb-text-utf8@1",
        encoded_payload=json.dumps(payload,separators=(",",":")).encode(),
    )


class ConsumerTests(unittest.TestCase):
    def test_worker_reauthorizes_exact_scoped_message_before_claim(self):
        port=Port()
        authority=CurrentAuthority()
        result=MonitoringAlertingTransport(
            port=port,
            execution_authority=authority,
            executor_id="worker-1",
        ).consume(envelope())
        self.assertEqual(result["receipt_state"],"completed")
        self.assertEqual(len(authority.requests),1)
        request=authority.requests[0]
        self.assertEqual(request.authority_contract,"alerting.monitoring-resync")
        self.assertEqual(request.runtime_profile_id,"runtime.worker@1")
        self.assertEqual(request.tenant_id,"tenant-a")
        self.assertEqual(request.message_identity.message_id,"message-1")
        self.assertEqual(len(port.claimed),1)
        self.assertEqual(len(port.completed),1)

    def test_stale_current_execution_authority_fails_before_claim(self):
        port=Port()
        authority=CurrentAuthority(current=False)
        with self.assertRaises(ValueError):
            MonitoringAlertingTransport(
                port=port,
                execution_authority=authority,
                executor_id="worker-1",
            ).consume(envelope())
        self.assertEqual(port.claimed,[])
        self.assertEqual(port.completed,[])

    def test_completed_duplicate_does_not_reexecute(self):
        port=Port()
        port.state="completed"
        authority=CurrentAuthority()
        result=MonitoringAlertingTransport(
            port=port,
            execution_authority=authority,
            executor_id="worker-1",
        ).consume(envelope())
        self.assertEqual(result,{"receipt_state":"completed","duplicate":True})
        self.assertEqual(authority.requests,[])
        self.assertEqual(port.claimed,[])

    def test_reconciliation_blocked_duplicate_does_not_reexecute(self):
        port=Port()
        port.state="reconciliation_required"
        authority=CurrentAuthority()
        result=MonitoringAlertingTransport(
            port=port,
            execution_authority=authority,
            executor_id="worker-1",
        ).consume(envelope())
        self.assertEqual(result["receipt_state"],"reconciliation_required")
        self.assertEqual(port.claimed,[])

    def test_only_two_monitoring_contracts_are_accepted(self):
        bad=envelope()
        bad=MonitoringEnvelope(**{**bad.__dict__,"contract_name":"monitoring.metric.changed"})
        with self.assertRaises(ValueError):
            bad.validate()

    def test_envelope_cannot_smuggle_command_fields(self):
        bad=MonitoringEnvelope(**{**envelope().__dict__,"created_at":NOW})
        with self.assertRaises(ValueError):
            bad.validate()

    def test_health_contract_subject_is_bound(self):
        value=envelope(contract="monitoring.health-projection.changed")
        value.validate()
        self.assertEqual(value.subject_type,"monitoring_resource")


if __name__=="__main__":
    unittest.main()
