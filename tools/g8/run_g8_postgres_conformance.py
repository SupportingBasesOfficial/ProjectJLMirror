from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import subprocess
import time

ROOT=Path(__file__).resolve().parents[2]
FIXTURES=ROOT/"tests/g8/fixtures"
IMAGE="postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280"
CONTAINER="jlmirror-g8-postgres"
DATABASE="jlmirror"
PASSWORD="g8-human-operations-password"


def run(command:list[str],*,input_text:str|None=None,check:bool=True)->subprocess.CompletedProcess:
    cp=subprocess.run(
        command,cwd=ROOT,input=input_text,text=True,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False,
    )
    if check and cp.returncode!=0:
        raise AssertionError(
            "command failed rc="+str(cp.returncode)
            +"\nstdout="+cp.stdout[-5000:]
            +"\nstderr="+cp.stderr[-5000:]
        )
    return cp


def psql(sql:str,*,check:bool=True)->subprocess.CompletedProcess:
    return run([
        "docker","exec","-i",CONTAINER,
        "psql","-Atq","-v","ON_ERROR_STOP=1",
        "-U","postgres","-d",DATABASE,
    ],input_text=sql,check=check)


def scalar(sql:str)->str:
    return psql(sql).stdout.strip()


def apply(path:Path,*,check:bool=True)->subprocess.CompletedProcess:
    return psql(path.read_text(encoding="utf-8"),check=check)


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


def authority(tenant:str,principal:str,action:str)->str:
    return json.dumps({
        "tenant_id":tenant,
        "principal_id":principal,
        "current":True,
        "action":action,
        "policy_revision":"policy-r1",
    },separators=(",",":"))


def call(statement:str)->dict:
    raw=scalar("SET ROLE jlmirror_g8_human_operations_invoker;\n"+statement+"\nRESET ROLE;")
    return json.loads(raw)


def expect_call_failure(statement:str,marker:str)->None:
    cp=psql("SET ROLE jlmirror_g8_human_operations_invoker;\n"+statement,check=False)
    if cp.returncode==0 or marker not in cp.stdout+cp.stderr:
        raise AssertionError("expected failure marker "+marker+"\n"+cp.stdout+cp.stderr)


def expect_migration_failure(marker:str)->None:
    cp=apply(ROOT/"sql/human_operations/001_human_operations.sql",check=False)
    if cp.returncode==0 or marker not in cp.stdout+cp.stderr:
        raise AssertionError("expected migration failure "+marker+"\n"+cp.stdout+cp.stderr)


def assign_action(logical_action_id:str,owner:str)->dict:
    auth=authority("tenant-a","actor-a","human-operations:write").replace("'","''")
    statement=f"""
SELECT human_operations.g8_assign_alert_action(
 'tenant-a','alert-a','{owner}','investigate_alert','actor-a',
 '{logical_action_id}','{auth}'::jsonb
)::text;
"""
    return call(statement)


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
        apply(ROOT/"sql/alerting/001_alert_policy_lifecycle.sql")

        apply(FIXTURES/"poison_default_execute.sql")
        expect_migration_failure("g8.installed_function_acl_unsafe")
        apply(FIXTURES/"cleanup_default_execute.sql")

        apply(FIXTURES/"poison_executor_owner.sql")
        expect_migration_failure("g8.executor_unexpected_owned_object")
        apply(FIXTURES/"cleanup_executor_owner.sql")

        apply(FIXTURES/"poison_existing_function_acl.sql")
        expect_migration_failure("g8.existing_function_acl_unsafe")
        apply(FIXTURES/"cleanup_existing_function_acl.sql")

        apply(ROOT/"sql/human_operations/001_human_operations.sql")
        apply(FIXTURES/"postgres_seed.sql")

        roles=scalar("""
SELECT string_agg(
 rolname||':'||rolcanlogin::int||':'||rolsuper::int||':'||rolinherit::int||':'||rolbypassrls::int,
 ',' ORDER BY rolname
)
FROM pg_roles
WHERE rolname IN ('jlmirror_g8_human_operations_executor','jlmirror_g8_human_operations_invoker');
""")
        if roles!=(
            "jlmirror_g8_human_operations_executor:0:0:0:0,"
            "jlmirror_g8_human_operations_invoker:0:0:0:0"
        ):
            raise AssertionError("G8 role hardening drift: "+roles)

        relations=(
            "human_operations.resource_responsibility_assignment",
            "human_operations.alert_action_assignment",
            "human_operations.alert_acknowledgement",
            "human_operations.visibility_requirement",
            "human_operations.visibility_receipt",
            "human_operations.current_action_projection",
        )
        for relation in relations:
            acl=scalar(
                "SELECT "
                f"has_table_privilege('jlmirror_g8_human_operations_invoker','{relation}','SELECT')::int||':'||"
                f"has_table_privilege('jlmirror_g8_human_operations_invoker','{relation}','INSERT')::int||':'||"
                f"has_table_privilege('jlmirror_g8_human_operations_invoker','{relation}','UPDATE')::int||':'||"
                f"has_table_privilege('jlmirror_g8_human_operations_invoker','{relation}','DELETE')::int;"
            )
            if acl!="0:0:0:0":
                raise AssertionError("invoker direct table authority drift on "+relation+": "+acl)

        rls=scalar("""
SELECT count(*)::text||':'||
       count(*) FILTER (WHERE c.relrowsecurity AND c.relforcerowsecurity)::text
FROM pg_class c
JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='human_operations'
  AND c.relname IN (
    'resource_responsibility_assignment','alert_action_assignment',
    'alert_acknowledgement','visibility_requirement',
    'visibility_receipt','current_action_projection'
  );
""")
        if rls!="6:6":
            raise AssertionError("G8 FORCE RLS drift: "+rls)

        auth_write=authority("tenant-a","actor-a","human-operations:write").replace("'","''")
        first_resp=call(f"""
SELECT human_operations.g8_assign_resource_responsibility(
 'tenant-a','resource-a','principal-r1','technical_responsible','manual',
 'actor-a','resp-op-1','{auth_write}'::jsonb
)::text;
""")
        second_resp=call(f"""
SELECT human_operations.g8_assign_resource_responsibility(
 'tenant-a','resource-a','principal-r2','service_owner','configured',
 'actor-a','resp-op-2','{auth_write}'::jsonb
)::text;
""")
        if first_resp["duplicate"] or second_resp["duplicate"]:
            raise AssertionError("initial responsibility assignment unexpectedly duplicate")

        replay_resp=call(f"""
SELECT human_operations.g8_assign_resource_responsibility(
 'tenant-a','resource-a','principal-r1','technical_responsible','manual',
 'actor-a','resp-op-1','{auth_write}'::jsonb
)::text;
""")
        if not replay_resp["duplicate"]:
            raise AssertionError("responsibility replay lost idempotency")

        expect_call_failure(f"""
SELECT human_operations.g8_assign_resource_responsibility(
 'tenant-a','resource-a','principal-other','technical_responsible','manual',
 'actor-a','resp-op-1','{auth_write}'::jsonb
);
""","g8.responsibility_equivalence_conflict")

        current_responsibles=scalar("""
SET ROLE jlmirror_g8_human_operations_executor;
SELECT set_config('jlmirror.tenant_id','tenant-a',true);
SELECT count(*) FROM human_operations.resource_responsibility_assignment
WHERE tenant_id='tenant-a' AND monitoring_resource_id='resource-a' AND effective_until IS NULL;
RESET ROLE;
""")
        if current_responsibles!="2":
            raise AssertionError("multiple responsible principals not preserved")

        initial_action=assign_action("action-op-1","owner-1")
        if initial_action["duplicate"]:
            raise AssertionError("initial action assignment unexpectedly duplicate")

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[
                pool.submit(assign_action,"action-op-2","owner-2"),
                pool.submit(assign_action,"action-op-3","owner-3"),
            ]
            concurrent=[f.result() for f in futures]
        if any(row["duplicate"] for row in concurrent):
            raise AssertionError("concurrent distinct action assignment unexpectedly duplicate")

        action_state=scalar("""
SET ROLE jlmirror_g8_human_operations_executor;
SELECT set_config('jlmirror.tenant_id','tenant-a',true);
SELECT
 count(*) FILTER (WHERE effective_until IS NULL)::text||':'||
 count(*)::text
FROM human_operations.alert_action_assignment
WHERE tenant_id='tenant-a' AND alert_id='alert-a';
RESET ROLE;
""")
        if action_state!="1:3":
            raise AssertionError("action concurrency did not preserve one current owner/history: "+action_state)

        lifecycle_before=scalar("SELECT lifecycle_state FROM alerting.alert WHERE tenant_id='tenant-a' AND alert_id='alert-a';")
        auth_ack=authority("tenant-a","ack-principal","human-operations:ack").replace("'","''")
        ack=call(f"""
SELECT human_operations.g8_acknowledge_alert(
 'tenant-a','alert-a','ack-principal','ack-op-1','triaged','{auth_ack}'::jsonb
)::text;
""")
        if ack["duplicate"]:
            raise AssertionError("initial ACK unexpectedly duplicate")
        ack_replay=call(f"""
SELECT human_operations.g8_acknowledge_alert(
 'tenant-a','alert-a','ack-principal','ack-op-1','triaged','{auth_ack}'::jsonb
)::text;
""")
        if not ack_replay["duplicate"]:
            raise AssertionError("ACK replay lost idempotency")
        lifecycle_after=scalar("SELECT lifecycle_state FROM alerting.alert WHERE tenant_id='tenant-a' AND alert_id='alert-a';")
        if lifecycle_before!="active" or lifecycle_after!="active":
            raise AssertionError("G8 ACK mutated G7 Alert lifecycle")

        auth_req=authority("tenant-a","actor-a","human-operations:write").replace("'","''")
        view_req=call(f"""
SELECT human_operations.g8_create_visibility_requirement(
 'tenant-a','alert-a','viewer-customer','customer',
 'platform_native_authenticated_view@1','alert-a','actor-a',
 'view-op-1','{auth_req}'::jsonb
)::text;
""")
        requirement=view_req["visibility_requirement_id"]

        before_view=call("""
SELECT human_operations.g8_alert_human_operations('tenant-a','alert-a')::text;
""")
        states=[row["visibility_state"] for row in before_view["visibility"]]
        if states!=["not_viewed_yet"]:
            raise AssertionError("native visibility did not begin unobserved")

        apply(FIXTURES/"resolve_alert_a.sql")

        expect_call_failure(f"""
SELECT human_operations.g8_acknowledge_alert(
 'tenant-a','alert-a','ack-principal','ack-op-after','late','{auth_ack}'::jsonb
);
""","g8.active_alert_required")
        expect_call_failure(f"""
SELECT human_operations.g8_assign_alert_action(
 'tenant-a','alert-a','owner-late','review_alert','actor-a',
 'action-after','{auth_write}'::jsonb
);
""","g8.active_alert_required")
        expect_call_failure(f"""
SELECT human_operations.g8_create_visibility_requirement(
 'tenant-a','alert-a','viewer-customer','customer',
 'platform_native_authenticated_view@1','alert-a-late','actor-a',
 'view-op-after','{auth_req}'::jsonb
);
""","g8.active_alert_required")

        auth_view=authority("tenant-a","viewer-customer","human-operations:view").replace("'","''")
        receipt=call(f"""
SELECT human_operations.g8_record_visibility_receipt(
 'tenant-a','{requirement}','viewer-customer','view-receipt-op-1',
 '{auth_view}'::jsonb,'{{"session_generation":"s1","admission_revision":"a1"}}'::jsonb
)::text;
""")
        if receipt["duplicate"]:
            raise AssertionError("initial native view receipt unexpectedly duplicate")

        receipt_replay=call(f"""
SELECT human_operations.g8_record_visibility_receipt(
 'tenant-a','{requirement}','viewer-customer','view-receipt-op-1',
 '{auth_view}'::jsonb,'{{"session_generation":"s1","admission_revision":"a1"}}'::jsonb
)::text;
""")
        if not receipt_replay["duplicate"]:
            raise AssertionError("native view receipt replay lost idempotency")

        after_view=call("""
SELECT human_operations.g8_alert_human_operations('tenant-a','alert-a')::text;
""")
        if after_view["visibility"][0]["visibility_state"]!="viewed":
            raise AssertionError("authoritative native view receipt was not reflected")
        if after_view["current_action"]["action_kind"]!="no_human_action_required":
            raise AssertionError("resolved Alert still exposed a current human action")
        if after_view["alert_lifecycle_state"]!="resolved":
            raise AssertionError("late view evidence mutated Alert lifecycle")

        wrong_viewer=authority("tenant-a","viewer-wrong","human-operations:view").replace("'","''")
        expect_call_failure(f"""
SELECT human_operations.g8_record_visibility_receipt(
 'tenant-a','{requirement}','viewer-wrong','view-receipt-op-wrong',
 '{wrong_viewer}'::jsonb,'{{"session_generation":"s2"}}'::jsonb
);
""","g8.visibility_viewer_mismatch")

        stale_auth=json.dumps({
            "tenant_id":"tenant-a","principal_id":"actor-a","current":False,
            "action":"human-operations:write","policy_revision":"policy-r1",
        },separators=(",",":")).replace("'","''")
        expect_call_failure(f"""
SELECT human_operations.g8_assign_resource_responsibility(
 'tenant-a','resource-a','principal-x','operator','manual',
 'actor-a','resp-stale','{stale_auth}'::jsonb
);
""","g8.current_authority_required")

        cross_auth=authority("tenant-b","actor-b","human-operations:write").replace("'","''")
        expect_call_failure(f"""
SELECT human_operations.g8_assign_alert_action(
 'tenant-b','alert-a','owner-x','review_alert','actor-b',
 'cross-action','{cross_auth}'::jsonb
);
""","g8.active_alert_required")

        direct=apply(FIXTURES/"forbidden_direct_write.sql",check=False)
        if direct.returncode==0:
            raise AssertionError("invoker direct table write unexpectedly succeeded")

        print(
            "g8_postgres_conformance=PASS default_acl_poison=BLOCKED "
            "executor_owner_poison=BLOCKED existing_function_acl_poison=BLOCKED "
            "roles=PASS rls=PASS direct_acl=PASS multiple_responsibles=PASS "
            "action_concurrency=PASS ack_idempotency=PASS lifecycle_separation=PASS "
            "resolved_effects_blocked=PASS late_native_view=PASS tenant_isolation=PASS"
        )
        return 0
    finally:
        subprocess.run(["docker","rm","-f",CONTAINER],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


if __name__=="__main__":
    raise SystemExit(main())
