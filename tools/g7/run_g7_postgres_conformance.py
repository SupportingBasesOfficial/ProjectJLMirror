from __future__ import annotations

from pathlib import Path
import json
import subprocess
import time

ROOT=Path(__file__).resolve().parents[2]
IMAGE="postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280"
CONTAINER="jlmirror-g7-postgres"
DATABASE="jlmirror"
PASSWORD="g7-alerting-password"
FIXTURES=ROOT/"tests/g7/fixtures"


def run(command:list[str],*,input_text:str|None=None,check:bool=True)->subprocess.CompletedProcess:
    cp=subprocess.run(
        command,cwd=ROOT,input=input_text,text=True,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False,
    )
    if check and cp.returncode!=0:
        raise AssertionError(
            "command failed rc="+str(cp.returncode)
            +"\nstdout="+cp.stdout[-4000:]
            +"\nstderr="+cp.stderr[-4000:]
        )
    return cp


def psql(sql:str)->str:
    return run([
        "docker","exec","-i",CONTAINER,
        "psql","-Atq","-v","ON_ERROR_STOP=1",
        "-U","postgres","-d",DATABASE,
    ],input_text=sql).stdout.strip()


def apply(path:Path,*,check:bool=True)->subprocess.CompletedProcess:
    return run([
        "docker","exec","-i",CONTAINER,
        "psql","-Atq","-v","ON_ERROR_STOP=1",
        "-U","postgres","-d",DATABASE,
    ],input_text=path.read_text(encoding="utf-8"),check=check)


def expect_migration_failure(marker:str)->None:
    cp=apply(ROOT/"sql/alerting/001_alert_policy_lifecycle.sql",check=False)
    if cp.returncode==0 or marker not in cp.stdout+cp.stderr:
        raise AssertionError(
            "expected G7 migration failure marker "+marker
            +"\nstdout="+cp.stdout[-2500:]
            +"\nstderr="+cp.stderr[-2500:]
        )


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


def call(statement:str)->dict:
    raw=psql("SET ROLE jlmirror_g7_alerting_invoker;\n"+statement+"\nRESET ROLE;")
    return json.loads(raw)


def expect_call_failure(statement:str,marker:str)->None:
    cp=run([
        "docker","exec","-i",CONTAINER,
        "psql","-Atq","-v","ON_ERROR_STOP=1",
        "-U","postgres","-d",DATABASE,
    ],input_text="SET ROLE jlmirror_g7_alerting_invoker;\n"+statement,check=False)
    if cp.returncode==0 or marker not in cp.stdout+cp.stderr:
        raise AssertionError("expected failure marker "+marker+"\n"+cp.stdout+cp.stderr)


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

        apply(FIXTURES/"poison_default_execute.sql")
        expect_migration_failure("g7.installed_function_acl_unsafe")
        apply(FIXTURES/"cleanup_default_execute.sql")

        apply(FIXTURES/"poison_executor_owner.sql")
        expect_migration_failure("g7.executor_unexpected_owned_object")
        apply(FIXTURES/"cleanup_executor_owner.sql")

        apply(FIXTURES/"poison_existing_function_acl.sql")
        expect_migration_failure("g7.existing_function_acl_unsafe")
        apply(FIXTURES/"cleanup_existing_function_acl.sql")

        apply(ROOT/"sql/alerting/001_alert_policy_lifecycle.sql")
        apply(FIXTURES/"postgres_seed.sql")

        roles=psql("""
SELECT string_agg(
 rolname||':'||rolcanlogin::int||':'||rolsuper::int||':'||rolinherit::int||':'||rolbypassrls::int,
 ',' ORDER BY rolname
)
FROM pg_roles
WHERE rolname IN ('jlmirror_g7_alerting_executor','jlmirror_g7_alerting_invoker');
""")
        if roles!=(
            "jlmirror_g7_alerting_executor:0:0:0:0,"
            "jlmirror_g7_alerting_invoker:0:0:0:0"
        ):
            raise AssertionError("G7 role hardening drift: "+roles)

        relations=(
            "alerting.alert_policy",
            "alerting.alert_policy_version",
            "alerting.alert_policy_effective_version",
            "alerting.alert",
            "alerting.alert_transition",
            "alerting.alert_decision",
        )
        for relation in relations:
            acl=psql(
                "SELECT "
                f"has_table_privilege('jlmirror_g7_alerting_invoker','{relation}','SELECT')::int||':'||"
                f"has_table_privilege('jlmirror_g7_alerting_invoker','{relation}','INSERT')::int||':'||"
                f"has_table_privilege('jlmirror_g7_alerting_invoker','{relation}','UPDATE')::int||':'||"
                f"has_table_privilege('jlmirror_g7_alerting_invoker','{relation}','DELETE')::int;"
            )
            if acl!="0:0:0:0":
                raise AssertionError("invoker direct table authority drift on "+relation+": "+acl)

        rls=psql("""
SELECT count(*)::text||':'||
       count(*) FILTER (WHERE c.relrowsecurity AND c.relforcerowsecurity)::text
FROM pg_class c
JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='alerting'
  AND c.relname IN (
    'alert_policy','alert_policy_version','alert_policy_effective_version',
    'alert','alert_transition','alert_decision'
  );
""")
        if rls!="6:6":
            raise AssertionError("G7 FORCE RLS drift: "+rls)

        first=call("""
SELECT alerting.g7_create_policy_version(
 'tenant-a','policy-problem',1,'monitoring_problem','warning',
 ARRAY[]::TEXT[],NULL,NULL
)::text;
""")
        if first["policy_version"]!=1 or first["duplicate"]:
            raise AssertionError("problem policy creation drift")

        duplicate=call("""
SELECT alerting.g7_create_policy_version(
 'tenant-a','policy-problem',1,'monitoring_problem','warning',
 ARRAY[]::TEXT[],NULL,NULL
)::text;
""")
        if not duplicate["duplicate"]:
            raise AssertionError("equivalent policy replay was not idempotent")

        expect_call_failure("""
SELECT alerting.g7_create_policy_version(
 'tenant-a','policy-problem',1,'monitoring_problem','critical',
 ARRAY[]::TEXT[],NULL,NULL
);
""","g7.policy_version_equivalence_conflict")

        call("""
SELECT alerting.g7_set_effective_policy_version(
 'tenant-a','policy-problem',1,true
)::text;
""")
        created=call("""
SELECT alerting.g7_apply_current_evaluation(
 'tenant-a','policy-problem',1,'problem-a'
)::text;
""")
        if created["effect"]!="create" or created["duplicate"]:
            raise AssertionError("current Problem did not create Alert")
        problem_alert=created["alert_id"]

        replay=call("""
SELECT alerting.g7_apply_current_evaluation(
 'tenant-a','policy-problem',1,'problem-a'
)::text;
""")
        if replay["effect"]!="create" or not replay["duplicate"] or replay["alert_id"]!=problem_alert:
            raise AssertionError("Problem create replay lost durable effect identity")

        call("""
SELECT alerting.g7_create_policy_version(
 'tenant-a','policy-problem',2,'monitoring_problem','critical',
 ARRAY[]::TEXT[],NULL,NULL
)::text;
""")
        call("""
SELECT alerting.g7_set_effective_policy_version(
 'tenant-a','policy-problem',2,true
)::text;
""")
        cross_version=call("""
SELECT alerting.g7_apply_current_evaluation(
 'tenant-a','policy-problem',2,'problem-a'
)::text;
""")
        if cross_version.get("reason")!="active_occurrence_owned_by_other_policy_version":
            raise AssertionError("new policy version duplicated active lineage occurrence")

        apply(FIXTURES/"problem_resolve.sql")
        resolved=call("""
SELECT alerting.g7_apply_current_evaluation(
 'tenant-a','policy-problem',1,'problem-a'
)::text;
""")
        if resolved["effect"]!="resolve" or resolved["alert_id"]!=problem_alert:
            raise AssertionError("superseded pinned version failed to resolve its Alert")

        resolve_replay=call("""
SELECT alerting.g7_apply_current_evaluation(
 'tenant-a','policy-problem',1,'problem-a'
)::text;
""")
        if resolve_replay["effect"]!="resolve" or not resolve_replay["duplicate"] or resolve_replay["alert_id"]!=problem_alert:
            raise AssertionError("Problem resolve replay lost durable effect identity")

        expect_call_failure("""
SELECT alerting.g7_set_effective_policy_version(
 'tenant-a','policy-problem',1,true
);
""","g7.policy_version_missing_or_superseded")

        apply(FIXTURES/"source_stale.sql")
        stale=call("""
SELECT alerting.g7_apply_current_evaluation(
 'tenant-a','policy-problem',2,'problem-a'
)::text;
""")
        if stale.get("reason")!="currentness_unproven":
            raise AssertionError("stale Monitoring owner evidence did not fail closed")
        apply(FIXTURES/"source_current.sql")

        health=call("""
SELECT alerting.g7_create_policy_version(
 'tenant-b','policy-health',1,'monitoring_health_projection',NULL,
 ARRAY['degraded','unhealthy']::TEXT[],NULL,NULL
)::text;
""")
        if health["policy_version"]!=1:
            raise AssertionError("health policy creation drift")
        call("""
SELECT alerting.g7_set_effective_policy_version(
 'tenant-b','policy-health',1,true
)::text;
""")
        health_create=call("""
SELECT alerting.g7_apply_current_evaluation(
 'tenant-b','policy-health',1,'resource-b'
)::text;
""")
        if health_create["effect"]!="create":
            raise AssertionError("current Health did not create Alert")
        first_health_alert=health_create["alert_id"]

        apply(FIXTURES/"health_healthy.sql")
        health_resolve=call("""
SELECT alerting.g7_apply_current_evaluation(
 'tenant-b','policy-health',1,'resource-b'
)::text;
""")
        if health_resolve["effect"]!="resolve" or health_resolve["alert_id"]!=first_health_alert:
            raise AssertionError("Health recovery did not resolve Alert")
        health_resolve_replay=call("""
SELECT alerting.g7_apply_current_evaluation(
 'tenant-b','policy-health',1,'resource-b'
)::text;
""")
        if health_resolve_replay["effect"]!="resolve" or not health_resolve_replay["duplicate"]:
            raise AssertionError("Health resolve replay was not idempotent")

        apply(FIXTURES/"health_unhealthy.sql")
        health_recur=call("""
SELECT alerting.g7_apply_current_evaluation(
 'tenant-b','policy-health',1,'resource-b'
)::text;
""")
        if health_recur["effect"]!="create" or health_recur["alert_id"]==first_health_alert:
            raise AssertionError("later Health occurrence did not receive a new Alert identity")

        tenant_a=json.loads(psql("""
SET ROLE jlmirror_g7_alerting_invoker;
SELECT alerting.g7_list_alerts('tenant-a',100)::text;
RESET ROLE;
"""))
        tenant_b=json.loads(psql("""
SET ROLE jlmirror_g7_alerting_invoker;
SELECT alerting.g7_list_alerts('tenant-b',100)::text;
RESET ROLE;
"""))
        if any(row["source_subject_id"]=="resource-b" for row in tenant_a):
            raise AssertionError("tenant A read crossed into tenant B")
        if any(row["source_subject_id"]=="problem-a" for row in tenant_b):
            raise AssertionError("tenant B read crossed into tenant A")

        counts=psql("""
SELECT
 count(*) FILTER (WHERE lifecycle_state='active')::text||':'||
 count(*) FILTER (WHERE lifecycle_state='resolved')::text||':'||
 (SELECT count(*) FROM alerting.alert_transition)::text||':'||
 (SELECT count(*) FROM alerting.alert_decision)::text
FROM alerting.alert;
""")
        if counts!="1:2:5:5":
            raise AssertionError("unexpected G7 durable state: "+counts)

        direct=apply(FIXTURES/"forbidden_direct_mutation.sql",check=False)
        if direct.returncode==0:
            raise AssertionError("invoker direct table mutation unexpectedly succeeded")

        print(
            "g7_postgres_conformance=PASS default_acl_poison=BLOCKED "
            "executor_owner_poison=BLOCKED existing_function_acl_poison=BLOCKED "
            "roles=PASS rls=PASS acl=PASS "
            "problem_create=PASS create_replay=PASS policy_supersession=PASS "
            "cross_version_uniqueness=PASS pinned_resolve=PASS resolve_replay=PASS "
            "stale_fail_closed=PASS health_create=PASS health_resolve=PASS "
            "health_recurrence=PASS tenant_reads=PASS direct_write_blocked=PASS"
        )
        return 0
    finally:
        subprocess.run(["docker","rm","-f",CONTAINER],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


if __name__=="__main__":
    raise SystemExit(main())
