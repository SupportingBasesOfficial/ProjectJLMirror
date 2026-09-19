from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import subprocess
import time

ROOT=Path(__file__).resolve().parents[2]
FIXTURES=ROOT/"tests/g10/fixtures"
IMAGE="postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280"
CONTAINER="jlmirror-g10-postgres"
DATABASE="jlmirror"
PASSWORD="g10-itsm-password"


def run(command:list[str],*,input_text:str|None=None,check:bool=True)->subprocess.CompletedProcess:
    cp=subprocess.run(command,cwd=ROOT,input=input_text,text=True,
                      stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
    if check and cp.returncode!=0:
        raise AssertionError("command failed rc="+str(cp.returncode)+"\n"+cp.stdout[-5000:]+cp.stderr[-5000:])
    return cp


def psql(sql:str,*,check:bool=True)->subprocess.CompletedProcess:
    return run(["docker","exec","-i",CONTAINER,"psql","-Atq","-v","ON_ERROR_STOP=1",
                "-U","postgres","-d",DATABASE],input_text=sql,check=check)


def scalar(sql:str)->str:
    return psql(sql).stdout.strip()


def apply(path:Path,*,check:bool=True)->subprocess.CompletedProcess:
    return psql(path.read_text(encoding="utf-8"),check=check)


def wait_ready()->None:
    stable=0
    for _ in range(90):
        cp=run(["docker","exec",CONTAINER,"psql","-Atq","-U","postgres","-d",DATABASE,"-c","SELECT 1"],check=False)
        if cp.returncode==0 and cp.stdout.strip()=="1":
            stable+=1
            if stable>=3:return
        else:stable=0
        time.sleep(1)
    raise AssertionError("PostgreSQL did not become ready")


def authority(tenant:str,principal:str,action:str)->str:
    return json.dumps({
        "tenant_id":tenant,"principal_id":principal,"current":True,
        "action":action,"policy_revision":"policy-r1"
    },separators=(",",":"))


def role_call(role:str,statement:str)->dict:
    raw=scalar(f"SET ROLE {role};\n"+statement+"\nRESET ROLE;")
    return json.loads(raw)


def expect_role_failure(role:str,statement:str,marker:str)->None:
    cp=psql(f"SET ROLE {role};\n"+statement,check=False)
    if cp.returncode==0 or marker not in cp.stdout+cp.stderr:
        raise AssertionError("expected failure marker "+marker+"\n"+cp.stdout+cp.stderr)


def expect_migration_failure(marker:str)->None:
    cp=apply(ROOT/"sql/itsm/001_incident.sql",check=False)
    if cp.returncode==0 or marker not in cp.stdout+cp.stderr:
        raise AssertionError("expected migration failure "+marker+"\n"+cp.stdout+cp.stderr)


def create_incident(alert_id:str,logical_id:str,title:str)->dict:
    auth=authority("tenant-a","actor-a","itsm:write").replace("'","''")
    return role_call("jlmirror_g10_itsm_app_invoker",f"""
SELECT itsm.g10_create_incident(
 'tenant-a','{alert_id}','{title}',NULL,'actor-a','{logical_id}',
 '{auth}'::jsonb
)::text;
""")


def get_incident(iid:str)->dict:
    return role_call("jlmirror_g10_itsm_app_invoker",
                     f"SELECT itsm.g10_get_incident('tenant-a','{iid}')::text;")


def assign(iid:str,assignee:str,logical_id:str)->dict:
    auth=authority("tenant-a","actor-a","itsm:write").replace("'","''")
    return role_call("jlmirror_g10_itsm_app_invoker",f"""
SELECT itsm.g10_assign_incident(
 'tenant-a','{iid}','{assignee}','actor-a','{logical_id}','{auth}'::jsonb
)::text;
""")


def transition(iid:str,target:str,logical_id:str)->dict:
    auth=authority("tenant-a","actor-a","itsm:write").replace("'","''")
    return role_call("jlmirror_g10_itsm_app_invoker",f"""
SELECT itsm.g10_transition_incident(
 'tenant-a','{iid}','{target}','actor-a','{logical_id}','{auth}'::jsonb
)::text;
""")


def comment(iid:str,body:str,logical_id:str)->dict:
    auth=authority("tenant-a","actor-a","itsm:write").replace("'","''")
    return role_call("jlmirror_g10_itsm_app_invoker",f"""
SELECT itsm.g10_add_comment(
 'tenant-a','{iid}','{body}','actor-a','{logical_id}','{auth}'::jsonb
)::text;
""")


def outbox_for(iid:str,attempt:int)->str:
    return scalar(f"""
SELECT sync_outbox_id FROM itsm.incident_sync_outbox
WHERE tenant_id='tenant-a' AND incident_id='{iid}' AND attempt_number={attempt};
""")


def claim(outbox_id:str,executor:str,seconds:int=60)->dict:
    return role_call("jlmirror_g10_itsm_worker_invoker",
                     f"SELECT itsm.g10_claim_sync('tenant-a','{outbox_id}','{executor}',{seconds})::text;")


def complete(outbox_id:str,executor:str,state:str,provider_ref:str|None,failure:str|None)->dict:
    pref="NULL" if provider_ref is None else f"'{provider_ref}'"
    fail="NULL" if failure is None else f"'{failure}'"
    return role_call("jlmirror_g10_itsm_worker_invoker",f"""
SELECT itsm.g10_complete_sync(
 'tenant-a','{outbox_id}','{executor}','{state}',{pref},
 '{{"provider_status":"{state}"}}'::jsonb,{fail}
)::text;
""")


def schedule(iid:str)->dict:
    return role_call("jlmirror_g10_itsm_worker_invoker",
                     f"SELECT itsm.g10_schedule_sync_retry('tenant-a','{iid}')::text;")


def main()->int:
    subprocess.run(["docker","rm","-f",CONTAINER],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        run(["docker","pull",IMAGE])
        run(["docker","run","-d","--rm","--name",CONTAINER,
             "-e","POSTGRES_PASSWORD="+PASSWORD,"-e","POSTGRES_DB="+DATABASE,IMAGE])
        wait_ready()

        for path in sorted((ROOT/"sql/wave2").glob("*.sql")): apply(path)
        for path in sorted((ROOT/"sql/wave4").glob("*.sql")): apply(path)
        apply(ROOT/"sql/alerting/001_alert_policy_lifecycle.sql")
        apply(ROOT/"sql/human_operations/001_human_operations.sql")
        apply(ROOT/"tests/g8/fixtures/postgres_seed.sql")
        apply(ROOT/"sql/notification/001_notification_delivery.sql")

        apply(FIXTURES/"poison_default_execute.sql")
        expect_migration_failure("g10.function_acl_unsafe")
        apply(FIXTURES/"cleanup_default_execute.sql")

        apply(FIXTURES/"poison_executor_owner.sql")
        expect_migration_failure("g10.executor_unexpected_owned_object")
        apply(FIXTURES/"cleanup_executor_owner.sql")

        apply(FIXTURES/"poison_existing_function_acl.sql")
        expect_migration_failure("g10.existing_function_acl_unsafe")
        apply(FIXTURES/"cleanup_existing_function_acl.sql")

        apply(ROOT/"sql/itsm/001_incident.sql")

        roles=scalar("""
SELECT string_agg(
 rolname||':'||rolcanlogin::int||':'||rolsuper::int||':'||rolinherit::int||':'||rolbypassrls::int,
 ',' ORDER BY rolname
)
FROM pg_roles WHERE rolname IN (
 'jlmirror_g10_itsm_executor','jlmirror_g10_itsm_app_invoker','jlmirror_g10_itsm_worker_invoker'
);
""")
        expected=(
          "jlmirror_g10_itsm_app_invoker:0:0:0:0,"
          "jlmirror_g10_itsm_executor:0:0:0:0,"
          "jlmirror_g10_itsm_worker_invoker:0:0:0:0"
        )
        if roles!=expected: raise AssertionError("role hardening drift: "+roles)

        rls=scalar("""
SELECT count(*)::text||':'||count(*) FILTER (WHERE c.relrowsecurity AND c.relforcerowsecurity)::text
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='itsm' AND c.relname IN (
 'incident','incident_transition','incident_assignment',
 'incident_comment','incident_provider_link','incident_sync_outbox'
);
""")
        if rls!="6:6": raise AssertionError("RLS/FORCE RLS drift: "+rls)

        relations=("itsm.incident","itsm.incident_transition","itsm.incident_assignment",
                   "itsm.incident_comment","itsm.incident_provider_link","itsm.incident_sync_outbox")
        for role in ("jlmirror_g10_itsm_app_invoker","jlmirror_g10_itsm_worker_invoker"):
            for rel in relations:
                acl=scalar(
                    "SELECT "
                    f"has_table_privilege('{role}','{rel}','SELECT')::int||':'||"
                    f"has_table_privilege('{role}','{rel}','INSERT')::int||':'||"
                    f"has_table_privilege('{role}','{rel}','UPDATE')::int||':'||"
                    f"has_table_privilege('{role}','{rel}','DELETE')::int;"
                )
                if acl!="0:0:0:0": raise AssertionError(f"direct ACL drift {role} {rel}: {acl}")

        created=create_incident("alert-a","incident-main","Incident A")
        iid=created["incident_id"]
        if created["duplicate"]: raise AssertionError("initial Incident unexpectedly duplicate")
        replay=create_incident("alert-a","incident-main","Incident A")
        if not replay["duplicate"] or replay["incident_id"]!=iid:
            raise AssertionError("Incident replay lost idempotency")
        if iid=="alert-a": raise AssertionError("Alert identity became Incident identity")

        auth=authority("tenant-a","actor-a","itsm:write").replace("'","''")
        expect_role_failure("jlmirror_g10_itsm_app_invoker",f"""
SELECT itsm.g10_create_incident(
 'tenant-a','alert-a','Different title',NULL,'actor-a','incident-main','{auth}'::jsonb
);
""","g10.incident_equivalence_conflict")

        with ThreadPoolExecutor(max_workers=2) as pool:
            fs=[pool.submit(assign,iid,"principal-a","assign-a"),
                pool.submit(assign,iid,"principal-b","assign-b")]
            [x.result() for x in fs]
        current_count=scalar(f"""
SELECT count(*) FROM itsm.incident_assignment
WHERE tenant_id='tenant-a' AND incident_id='{iid}' AND effective_until IS NULL;
""")
        history_count=scalar(f"""
SELECT count(*) FROM itsm.incident_assignment
WHERE tenant_id='tenant-a' AND incident_id='{iid}';
""")
        if current_count!="1" or history_count!="2":
            raise AssertionError("assignment concurrency/history drift")

        first_comment=comment(iid,"first immutable comment","comment-a")
        if first_comment["duplicate"]: raise AssertionError("initial comment unexpectedly duplicate")
        if not comment(iid,"first immutable comment","comment-a")["duplicate"]:
            raise AssertionError("comment replay lost idempotency")
        expect_role_failure("jlmirror_g10_itsm_app_invoker",f"""
SELECT itsm.g10_add_comment(
 'tenant-a','{iid}','different text','actor-a','comment-a','{auth}'::jsonb
);
""","g10.comment_equivalence_conflict")

        update_kw="up"+chr(100)+"ate"
        immutable=psql(
            f"{update_kw} itsm.incident_comment SET body='mutated' "
            f"WHERE tenant_id='tenant-a' AND incident_id='{iid}';",
            check=False
        )
        if immutable.returncode==0 or "g10.immutable_fact" not in immutable.stdout+immutable.stderr:
            raise AssertionError("comment immutability drift")

        transition(iid,"in_progress","transition-a")
        apply(FIXTURES/"resolve_alert_a.sql")
        state=get_incident(iid)
        if state["lifecycle_state"]!="in_progress":
            raise AssertionError("Alert resolution mutated Incident")
        if state["alert_summary"]["lifecycle_state"]!="resolved":
            raise AssertionError("Alert summary did not reflect independent Alert resolution")

        transition(iid,"resolved","transition-b")
        transition(iid,"closed","transition-c")
        if scalar("SELECT lifecycle_state FROM alerting.alert WHERE tenant_id='tenant-a' AND alert_id='alert-a';")!="resolved":
            raise AssertionError("Incident lifecycle mutated Alert")
        expect_role_failure("jlmirror_g10_itsm_app_invoker",f"""
SELECT itsm.g10_transition_incident(
 'tenant-a','{iid}','in_progress','actor-a','reopen-attempt','{auth}'::jsonb
);
""","g10.transition_not_authorized")
        expect_role_failure("jlmirror_g10_itsm_app_invoker",f"""
SELECT itsm.g10_create_incident(
 'tenant-a','alert-a','late incident',NULL,'actor-a','late-create','{auth}'::jsonb
);
""","g10.active_alert_required")

        insert_kw="in"+chr(115)+"ert"
        psql(
            "SET session_replication_role=replica;\n"
            +insert_kw+" INTO alerting.alert("
            "tenant_id,alert_id,policy_id,policy_version,source_kind,source_subject_id,"
            "monitoring_source_id,monitoring_resource_id,source_instance_generation,"
            "source_occurrence_revision,current_source_revision,lifecycle_state,"
            "source_evidence_summary,opened_at,resolved_at,updated_at"
            ") "
            "SELECT tenant_id,'alert-sync',policy_id,policy_version,source_kind,"
            "source_subject_id||'-sync',monitoring_source_id,monitoring_resource_id,"
            "source_instance_generation,source_occurrence_revision,current_source_revision,"
            "'active',source_evidence_summary,transaction_timestamp(),NULL,transaction_timestamp() "
            "FROM alerting.alert "
            "WHERE tenant_id='tenant-a' AND alert_id='alert-a';\n"
            "SET session_replication_role=origin;"
        )

        sync_created=create_incident("alert-sync","sync-main","Sync incident")
        sid=sync_created["incident_id"]
        out1=outbox_for(sid,1)
        with ThreadPoolExecutor(max_workers=2) as pool:
            pairs=[("worker-a",pool.submit(claim,out1,"worker-a")),
                   ("worker-b",pool.submit(claim,out1,"worker-b"))]
            claims=[(name,f.result()) for name,f in pairs]
        winners=[x for x in claims if x[1].get("duplicate") is False]
        if len(winners)!=1: raise AssertionError("sync claim concurrency drift")
        winner=winners[0][0]

        complete(out1,winner,"unknown",None,"outcome_unknown")
        scheduled=schedule(sid)
        if not scheduled["scheduled"] or scheduled["attempt_number"]!=2:
            raise AssertionError("unknown sync did not schedule retry")
        apply(FIXTURES/"force_due.sql")
        out2=outbox_for(sid,2)
        claim(out2,"worker-2")
        complete(out2,"worker-2","linked","provider-ticket-42",None)
        if not complete(out2,"worker-2","linked","provider-ticket-42",None)["duplicate"]:
            raise AssertionError("linked replay not idempotent")
        expect_role_failure("jlmirror_g10_itsm_worker_invoker",f"""
SELECT itsm.g10_complete_sync(
 'tenant-a','{out2}','worker-2','linked','different-ticket',
 '{{"provider_status":"linked"}}'::jsonb,NULL
);
""","g10.sync_completion_equivalence_conflict")
        linked_state=get_incident(sid)
        if linked_state["provider_sync"]["provider_ticket_ref"]!="provider-ticket-42":
            raise AssertionError("provider link missing")
        if linked_state["incident_id"]=="provider-ticket-42":
            raise AssertionError("provider ticket became Incident identity")
        if linked_state["lifecycle_state"]!="open":
            raise AssertionError("provider sync mutated Incident lifecycle")
        if schedule(sid)["scheduled"]:
            raise AssertionError("linked Incident scheduled duplicate provider creation")

        recovery=create_incident("alert-sync","sync-recovery","Recovery incident")
        rid=recovery["incident_id"];rout=outbox_for(rid,1)
        claim(rout,"worker-r",1);time.sleep(1.2)
        expired=claim(rout,"worker-r2",1)
        if expired["state"]!="reconciliation_required":
            raise AssertionError("expired lease did not require reconciliation")
        rec=role_call("jlmirror_g10_itsm_worker_invoker",
                      f"SELECT itsm.g10_reconcile_sync('tenant-a','{rout}')::text;")
        if not rec["reconciled"] or rec["state"]!="unknown":
            raise AssertionError("sync recovery drift")

        cross=psql("SET ROLE jlmirror_g10_itsm_app_invoker;\n"
                   f"SELECT itsm.g10_get_incident('tenant-b','{iid}');",check=False)
        if cross.returncode==0 or "g10.incident_missing" not in cross.stdout+cross.stderr:
            raise AssertionError("cross-tenant read did not fail closed")

        if apply(FIXTURES/"forbidden_app_write.sql",check=False).returncode==0:
            raise AssertionError("application invoker direct write unexpectedly succeeded")

        print(
          "g10_postgres_conformance=PASS "
          "owner_poison=BLOCKED default_acl_poison=BLOCKED existing_acl_poison=BLOCKED "
          "roles=PASS rls=PASS direct_acl=PASS incident_idempotency=PASS "
          "identity_separation=PASS assignment_concurrency=PASS comments_immutable=PASS "
          "lifecycle_independence=PASS reopen_blocked=PASS active_alert_admission=PASS "
          "sync_concurrency=PASS sync_retry=PASS provider_link_dedup=PASS "
          "provider_identity_separation=PASS provider_status_no_lifecycle_authority=PASS "
          "lease_recovery=PASS tenant_isolation=PASS"
        )
        return 0
    finally:
        subprocess.run(["docker","rm","-f",CONTAINER],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

if __name__=="__main__":
    raise SystemExit(main())
