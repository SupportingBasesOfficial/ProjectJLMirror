from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"apps/g6-monitoring-alerting-transport"))

from consumer import ClaimEvidence, MonitoringEnvelope, ReceiptIdentity  # noqa: E402
from pg_port import PgTransportPort  # noqa: E402
from jlmirror_async import AsyncExecutionAdmission, AsyncExecutionRequest, ScopedMessageIdentity  # noqa: E402
from jlmirror_authority import EnvironmentClass, PrincipalKind, TenantContext  # noqa: E402

NOW=datetime(2026,9,18,12,0,tzinfo=timezone.utc)


class FakePg:
    def __init__(self,responses):
        self.responses=list(responses)
        self.calls=[]
    def query(self,sql,**variables):
        self.calls.append((sql,variables))
        return self.responses.pop(0)


def envelope():
    return MonitoringEnvelope(
        producer_message_scope="monitoring:tenant:scope",
        message_id="message-1",
        message_class="integration_event",
        contract_name="monitoring.problem-state.changed",
        contract_version="1",
        producer="Monitoring",
        producer_generation=None,
        scope_class="tenant",
        tenant_id="tenant-a",
        subject_type="monitoring_problem",
        subject_id="problem-1",
        occurred_at=NOW,
        created_at=None,
        operation_id=None,
        not_before=None,
        deadline=None,
        correlation_id="corr-1",
        causation_id="cause-1",
        data_classification="confidential_tenant",
        serialization_profile_id="jsonb-text-utf8@1",
        encoded_payload=b"{}",
    )


def admission():
    identity=ScopedMessageIdentity(
        consumer_contract="alerting.monitoring-resync",
        message_identity_scope="monitoring:tenant:scope",
        message_id="message-1",
        tenant_id="tenant-a",
    )
    request=AsyncExecutionRequest(
        authority_contract="alerting.monitoring-resync",
        runtime_profile_id="runtime.worker@1",
        tenant_id="tenant-a",
        message_identity=identity,
    )
    context=TenantContext(
        tenant_id="tenant-a",
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
        fence_scope_id="tenant-a-worker",
        fence_epoch=9,
        constructed_at=NOW,
    )
    return AsyncExecutionAdmission(
        request=request,
        principal_id="service-worker-a",
        principal_credential_generation="cred-7",
        authorization_revision="authz-19",
        admission_revision="admission-1",
        runtime_generation="runtime-4",
        environment_class=EnvironmentClass.PRODUCTION,
        observed_at=NOW,
        current=True,
        tenant_context=context,
    )


class PgPortTests(unittest.TestCase):
    def test_admit_calls_only_guarded_capability(self):
        pg=FakePg(['{"consumer_contract":"alerting.monitoring-resync","message_identity_scope":"monitoring:tenant:scope","message_id":"message-1","tenant_id":"tenant-a","receipt_state":"admitted","duplicate":false}'])
        identity,state=PgTransportPort(pg).admit(envelope())
        self.assertEqual(state,"admitted")
        self.assertEqual(identity.tenant_id,"tenant-a")
        sql,variables=pg.calls[0]
        self.assertIn("SELECT system.g6_admit_monitoring_alerting_message(",sql)
        self.assertNotIn("INSERT INTO system.async_consumer_inbox",sql)
        self.assertEqual(variables["payload_hex"],b"{}".hex())

    def test_claim_passes_revision_bound_current_execution_evidence(self):
        pg=FakePg(['{"receipt_state":"processing","execution_generation":4,"claim_expires_at":"2026-09-18T12:00:30Z"}'])
        state,claim=PgTransportPort(pg).claim(
            ReceiptIdentity("monitoring:tenant:scope","message-1","tenant-a"),
            executor_id="worker-1",
            claim_seconds=30,
            admission=admission(),
        )
        self.assertEqual(state,"processing")
        self.assertEqual(claim.execution_generation,4)
        sql,variables=pg.calls[0]
        self.assertIn("SELECT system.g6_claim_monitoring_alerting_receipt(",sql)
        self.assertEqual(variables["admission_revision"],"admission-1")
        self.assertEqual(variables["authorization_revision"],"authz-19")
        self.assertEqual(variables["placement_version"],"placement-11")
        self.assertEqual(variables["fence_epoch"],"9")

    def test_complete_calls_only_guarded_reread_capability(self):
        pg=FakePg(['{"receipt_state":"completed","effect_result_id":"g6-resync:abc","effect_result_kind":"monitoring_problem_owner_reread_current"}'])
        value=PgTransportPort(pg).complete(
            ReceiptIdentity("monitoring:tenant:scope","message-1","tenant-a"),
            ClaimEvidence("worker-1",4),
        )
        self.assertEqual(value["receipt_state"],"completed")
        sql,_=pg.calls[0]
        self.assertIn("SELECT system.g6_complete_monitoring_alerting_resync(",sql)
        self.assertNotIn("UPDATE system.async_consumer_inbox",sql)


if __name__=="__main__":
    unittest.main()
