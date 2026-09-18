from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"apps/g6-monitoring-alerting-transport"))

from consumer import MonitoringAlertingTransport, MonitoringEnvelope  # noqa: E402
from pg_port import Pg, PgTransportPort  # noqa: E402
from jlmirror_async import (  # noqa: E402
    AsyncExecutionAdmission,
    AsyncExecutionRequest,
    ScopedMessageIdentity,
    require_current_execution,
)
from jlmirror_authority import EnvironmentClass, PrincipalKind, TenantContext  # noqa: E402

IMAGE="postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280"
CONTAINER="jlmirror-g6-postgres"
DATABASE="jlmirror"
PASSWORD="g6-transport-password"


def run(command:list[str],*,input_text:str|None=None,check:bool=True)->subprocess.CompletedProcess:
    completed=subprocess.run(
        command,cwd=ROOT,input=input_text,text=True,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False,
    )
    if check and completed.returncode!=0:
        raise AssertionError(
            "command failed rc="+str(completed.returncode)
            +"\nstdout="+completed.stdout[-3000:]
            +"\nstderr="+completed.stderr[-3000:]
        )
    return completed


def psql(sql:str)->str:
    return run([
        "docker","exec","-i",CONTAINER,
        "psql","-Atq","-v","ON_ERROR_STOP=1",
        "-U","postgres","-d",DATABASE,
    ],input_text=sql).stdout.strip()


def apply(path:Path)->None:
    psql(path.read_text(encoding="utf-8"))


def wait_ready()->None:
    stable=0
    for _ in range(90):
        cp=run([
            "docker","exec",CONTAINER,
            "psql","-Atq","-U","postgres","-d",DATABASE,"-c","SELECT 1",
        ],check=False)
        if cp.returncode==0 and cp.stdout.strip()=="1":
            stable+=1
            if stable>=3:
                return
        else:
            stable=0
        time.sleep(1)
    raise AssertionError("PostgreSQL did not become ready")


def context(tenant_id:str)->TenantContext:
    now=datetime.now(timezone.utc)
    return TenantContext(
        tenant_id=tenant_id,
        principal_id="service-worker-a",
        principal_kind=PrincipalKind.SERVICE_WORKLOAD,
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
        fence_scope_id=tenant_id+"-worker",
        fence_epoch=9,
        constructed_at=now,
    )


class CurrentAuthority:
    def __init__(self)->None:
        self.requests=[]

    def finalize_current_execution(self,*,request):
        self.requests.append(request)
        return AsyncExecutionAdmission(
            request=request,
            principal_id="service-worker-a",
            principal_credential_generation="cred-7",
            authorization_revision="authz-g6-1",
            admission_revision="admission-g6-"+str(len(self.requests)),
            runtime_generation="runtime-4",
            environment_class=EnvironmentClass.PRODUCTION,
            observed_at=datetime.now(timezone.utc),
            current=True,
            tenant_context=context(request.tenant_id),
        )


def load_envelopes()->dict[str,MonitoringEnvelope]:
    raw=psql("""
SELECT COALESCE(json_agg(json_build_object(
  'producer_message_scope',producer_message_scope,
  'message_id',message_id,
  'message_class',message_class,
  'contract_name',contract_name,
  'contract_version',contract_version,
  'producer',producer,
  'producer_generation',producer_generation,
  'scope_class',scope_class,
  'tenant_id',tenant_id,
  'subject_type',subject_type,
  'subject_id',subject_id,
  'occurred_at',occurred_at,
  'created_at',created_at,
  'operation_id',operation_id,
  'not_before',not_before,
  'deadline',deadline,
  'correlation_id',correlation_id,
  'causation_id',causation_id,
  'data_classification',data_classification,
  'serialization_profile_id',serialization_profile_id,
  'payload_hex',encode(encoded_payload,'hex'),
  'transition_id',COALESCE(
      convert_from(encoded_payload,'UTF8')::jsonb->>'problem_transition_id',
      convert_from(encoded_payload,'UTF8')::jsonb->>'health_transition_id'
  )
) ORDER BY outbox_record_id),'[]'::json)::text
FROM system.async_outbox_message
WHERE contract_name IN ('monitoring.problem-state.changed','monitoring.health-projection.changed');
""")
    rows=json.loads(raw or "[]")
    result={}
    for row in rows:
        result[row["transition_id"]]=MonitoringEnvelope(
            producer_message_scope=row["producer_message_scope"],
            message_id=row["message_id"],
            message_class=row["message_class"],
            contract_name=row["contract_name"],
            contract_version=row["contract_version"],
            producer=row["producer"],
            producer_generation=row["producer_generation"],
            scope_class=row["scope_class"],
            tenant_id=row["tenant_id"],
            subject_type=row["subject_type"],
            subject_id=row["subject_id"],
            occurred_at=datetime.fromisoformat(row["occurred_at"]),
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            operation_id=row["operation_id"],
            not_before=datetime.fromisoformat(row["not_before"]) if row["not_before"] else None,
            deadline=datetime.fromisoformat(row["deadline"]) if row["deadline"] else None,
            correlation_id=row["correlation_id"],
            causation_id=row["causation_id"],
            data_classification=row["data_classification"],
            serialization_profile_id=row["serialization_profile_id"],
            encoded_payload=bytes.fromhex(row["payload_hex"]),
        )
    return result


def main()->int:
    subprocess.run(["docker","rm","-f",CONTAINER],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        run(["docker","pull",IMAGE])
        run([
            "docker","run","-d","--rm","--name",CONTAINER,
            "-e","POSTGRES_PASSWORD="+PASSWORD,
            "-e","POSTGRES_DB="+DATABASE,
            IMAGE,
        ])
        wait_ready()

        for path in sorted((ROOT/"sql/wave2").glob("*.sql")):
            apply(path)
        for path in sorted((ROOT/"sql/wave4").glob("*.sql")):
            apply(path)
        apply(ROOT/"sql/integration/001_monitoring_alerting_publication.sql")
        apply(ROOT/"sql/integration/002_monitoring_alerting_consumer.sql")

        role_state=psql("""
SELECT string_agg(
  rolname||':'||rolcanlogin::int||':'||rolsuper::int||':'||rolinherit::int||':'||rolbypassrls::int,
  ',' ORDER BY rolname
)
FROM pg_roles
WHERE rolname IN ('jlmirror_g6_alerting_transport_executor','jlmirror_g6_alerting_transport_invoker');
""")
        if role_state!="jlmirror_g6_alerting_transport_executor:0:0:0:0,jlmirror_g6_alerting_transport_invoker:0:0:0:0":
            raise AssertionError("G6 role hardening drift: "+role_state)

        acl=psql("""
SELECT
 has_table_privilege('jlmirror_g6_alerting_transport_executor','system.async_consumer_inbox','SELECT')::int||':'||
 has_table_privilege('jlmirror_g6_alerting_transport_executor','system.async_consumer_inbox','INSERT')::int||':'||
 has_table_privilege('jlmirror_g6_alerting_transport_executor','system.async_consumer_inbox','UPDATE')::int||':'||
 has_table_privilege('jlmirror_g6_alerting_transport_invoker','system.async_consumer_inbox','SELECT')::int||':'||
 has_table_privilege('jlmirror_g6_alerting_transport_invoker','system.async_consumer_inbox','INSERT')::int||':'||
 has_table_privilege('jlmirror_g6_alerting_transport_invoker','system.async_consumer_inbox','UPDATE')::int;
""")
        if acl!="1:1:1:0:0:0":
            raise AssertionError("G6 inbox ACL drift: "+acl)

        psql("""
SET session_replication_role=replica;
INSERT INTO monitoring.monitoring_source(
 tenant_id,monitoring_source_id,provider_scope_tenant_binding_id,provider_profile,
 active_source_instance_generation,configuration_revision,scope_revision,display_name,
 credential_binding_ref,configured_provider_scope,operational_evidence_state,
 replacement_candidate_ref,last_successful_sync_at,last_attempt_at,last_sync_operation_id
) VALUES (
 'tenant-a','source-a','binding-a','zabbix','generation-a',1,1,'Source A',
 'credential-a','{"host_group_refs":["10"]}'::jsonb,'current',
 NULL,transaction_timestamp(),transaction_timestamp(),'sync-fixture'
);

INSERT INTO monitoring.monitoring_source_generation(
 tenant_id,monitoring_source_id,source_instance_generation,provider_profile,
 provider_instance_ref,provider_base_url
) VALUES
 ('tenant-a','source-a','generation-a','zabbix','provider-a','https://zabbix.example.test'),
 ('tenant-a','source-a','generation-old','zabbix','provider-a-old','https://zabbix-old.example.test');

INSERT INTO monitoring.monitoring_resource(
 tenant_id,monitoring_resource_id,monitoring_source_id,source_instance_generation,
 resource_kind,provider_object_kind,provider_external_ref,display_name,
 scope_state,scope_projection_revision,scope_evidence_state,presence_state,
 presence_evidence_state,last_observed_at,last_confirmed_present_at,removed_at,
 latest_provider_evidence_id
) VALUES (
 'tenant-a','resource-1','source-a','generation-a','host','zabbix_host','101','Host 101',
 'in_scope',1,'current','present','current',
 transaction_timestamp(),transaction_timestamp(),NULL,NULL
);

INSERT INTO monitoring.monitoring_problem_provider_binding(
 tenant_id,problem_id,monitoring_source_id,source_instance_generation,
 monitoring_resource_id,provider_profile,provider_external_ref,provider_trigger_ref
) VALUES (
 'tenant-a','problem-1','source-a','generation-a','resource-1',
 'zabbix','9001','trigger-1'
);

INSERT INTO monitoring.monitoring_problem(
 tenant_id,problem_id,monitoring_source_id,source_instance_generation,
 monitoring_resource_id,problem_state,severity_class,summary,opened_at,resolved_at,
 last_confirmed_at,evidence_state,projection_revision,problem_poll_epoch,
 problem_poll_generation,provider_acknowledged,provider_metadata
) VALUES (
 'tenant-a','problem-1','source-a','generation-a','resource-1',
 'active','warning','CPU threshold exceeded',
 transaction_timestamp()-interval '10 minutes',NULL,transaction_timestamp(),
 'current',7,1,1,false,'{}'::jsonb
);

INSERT INTO monitoring.health_projection(
 tenant_id,monitoring_resource_id,monitoring_source_id,source_instance_generation,
 health_class,evidence_state,projection_revision,last_changed_at,last_evidence_at,
 problem_snapshot_evidence_id,reason_refs
) VALUES (
 'tenant-a','resource-1','source-a','generation-a','degraded','current',11,
 transaction_timestamp()-interval '5 minutes',transaction_timestamp(),
 NULL,'["problem-1"]'::jsonb
);
SET session_replication_role=origin;
""")

        psql("""
CREATE TEMP TABLE problem_transition_fixture(
  tenant_id text NOT NULL,
  problem_transition_id text NOT NULL,
  problem_id text NOT NULL,
  monitoring_source_id text NOT NULL,
  source_instance_generation text NOT NULL,
  monitoring_resource_id text NOT NULL,
  projection_revision bigint NOT NULL,
  occurred_at timestamptz NOT NULL
);
CREATE TRIGGER problem_fixture_outbox
AFTER INSERT ON problem_transition_fixture
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_publish_problem_transition();

CREATE TEMP TABLE health_transition_fixture(
  tenant_id text NOT NULL,
  health_transition_id text NOT NULL,
  monitoring_resource_id text NOT NULL,
  monitoring_source_id text NOT NULL,
  source_instance_generation text NOT NULL,
  projection_revision bigint NOT NULL,
  occurred_at timestamptz NOT NULL
);
CREATE TRIGGER health_fixture_outbox
AFTER INSERT ON health_transition_fixture
FOR EACH ROW EXECUTE FUNCTION monitoring.wave4_publish_health_transition();

INSERT INTO problem_transition_fixture VALUES
 ('tenant-a','problem-transition-7','problem-1','source-a','generation-a','resource-1',7,'2026-09-18 12:00:00+00'),
 ('tenant-a','problem-transition-6','problem-1','source-a','generation-a','resource-1',6,'2026-09-18 11:59:00+00'),
 ('tenant-a','problem-transition-old','problem-1','source-a','generation-old','resource-1',1,'2026-09-18 11:00:00+00'),
 ('tenant-a','problem-transition-conflict','problem-1','source-a','generation-a','resource-1',7,'2026-09-18 12:01:00+00');

INSERT INTO health_transition_fixture VALUES
 ('tenant-a','health-transition-11','resource-1','source-a','generation-a',11,'2026-09-18 12:02:00+00'),
 ('tenant-a','health-transition-lease','resource-1','source-a','generation-a',11,'2026-09-18 12:03:00+00');
""")

        envelopes=load_envelopes()
        required={
            "problem-transition-7","problem-transition-6","problem-transition-old",
            "problem-transition-conflict","health-transition-11","health-transition-lease",
        }
        if set(envelopes)!=required:
            raise AssertionError("published G6 fixture envelope set drift")

        pg=Pg(container=CONTAINER,database=DATABASE)
        port=PgTransportPort(pg)
        authority=CurrentAuthority()
        worker=MonitoringAlertingTransport(
            port=port,
            execution_authority=authority,
            executor_id="g6-worker-a",
            claim_seconds=30,
        )

        problem_result=worker.consume(envelopes["problem-transition-7"])
        if problem_result.get("effect_result_kind")!="monitoring_problem_owner_reread_current":
            raise AssertionError("Problem current reread did not complete")

        duplicate=worker.consume(envelopes["problem-transition-7"])
        if duplicate!={"receipt_state":"completed","duplicate":True}:
            raise AssertionError("equivalent duplicate was not observed idempotently")

        health_result=worker.consume(envelopes["health-transition-11"])
        if health_result.get("effect_result_kind")!="monitoring_health_owner_reread_current":
            raise AssertionError("Health current reread did not complete")

        historical=worker.consume(envelopes["problem-transition-old"])
        if historical.get("effect_result_kind")!="monitoring_owner_reread_noncurrent_generation":
            raise AssertionError("historical generation gained current input authority")

        reordered=worker.consume(envelopes["problem-transition-6"])
        if reordered.get("effect_result_kind")!="monitoring_problem_owner_reread_current":
            raise AssertionError("reordered older event failed current owner reread")
        if reordered.get("effect_result_id")!=problem_result.get("effect_result_id"):
            raise AssertionError("reordered event regressed current owner disposition")

        bad_producer=replace(envelopes["problem-transition-6"],producer="NotMonitoring")
        try:
            port.admit(bad_producer)
        except RuntimeError:
            pass
        else:
            raise AssertionError("wrong producer was admitted")

        conflict=envelopes["problem-transition-conflict"]
        psql(f"""
INSERT INTO system.async_consumer_inbox(
 consumer_contract,message_identity_scope,message_id,tenant_id,
 comparison_profile_id,comparison_profile_version,comparison_evidence_form,
 comparison_verifier_generation,comparison_evidence
) VALUES (
 'alerting.monitoring-resync@1',
 {json.dumps(conflict.producer_message_scope)}::text,
 {json.dumps(conflict.message_id)}::text,
 'tenant-a','monitoring-invalidation-equivalence','1',
 'canonical-jsonb-envelope-payload',NULL,decode('00','hex')
);
""")
        try:
            port.admit(conflict)
        except RuntimeError:
            pass
        else:
            raise AssertionError("conflicting equivalence was accepted")

        lease=envelopes["health-transition-lease"]
        identity,state=port.admit(lease)
        if state!="admitted":
            raise AssertionError("lease fixture was not admitted")
        request=AsyncExecutionRequest(
            authority_contract="alerting.monitoring-resync@1",
            runtime_profile_id="runtime.worker@1",
            tenant_id=identity.tenant_id,
            message_identity=ScopedMessageIdentity(
                consumer_contract="alerting.monitoring-resync@1",
                message_identity_scope=identity.message_identity_scope,
                message_id=identity.message_id,
                tenant_id=identity.tenant_id,
            ),
        )
        admission=require_current_execution(authority,request)
        claim_state,claim=port.claim(
            identity,
            executor_id="g6-worker-lease",
            claim_seconds=1,
            admission=admission,
        )
        if claim_state!="processing" or claim is None:
            raise AssertionError("lease fixture was not claimed")
        time.sleep(1.2)
        state_after,_=port.claim(
            identity,
            executor_id="g6-worker-lease-2",
            claim_seconds=30,
            admission=require_current_execution(authority,request),
        )
        if state_after!="reconciliation_required":
            raise AssertionError("expired claim did not block blind retry")

        states=psql("""
SELECT
 count(*) FILTER (WHERE state='completed')::text||':'||
 count(*) FILTER (WHERE state='reconciliation_required')::text||':'||
 count(*) FILTER (WHERE state='quarantined')::text
FROM system.async_consumer_inbox
WHERE consumer_contract='alerting.monitoring-resync@1';
""")
        if states!="4:1:0":
            raise AssertionError("unexpected G6 durable receipt states: "+states)

        print(
            "g6_postgres_conformance=PASS publication=PASS admission=PASS "
            "duplicate=PASS conflict=PASS problem_reread=PASS health_reread=PASS "
            "historical=PASS reorder=PASS lease_reconciliation=PASS"
        )
        return 0
    finally:
        subprocess.run(["docker","rm","-f",CONTAINER],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


if __name__=="__main__":
    raise SystemExit(main())
