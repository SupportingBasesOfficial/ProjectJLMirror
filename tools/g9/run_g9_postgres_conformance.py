from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import subprocess
import time

ROOT=Path(__file__).resolve().parents[2]
FIXTURES=ROOT/"tests/g9/fixtures"
IMAGE="postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280"
CONTAINER="jlmirror-g9-postgres"
DATABASE="jlmirror"
PASSWORD="g9-notification-password"


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


def role_call(role:str,statement:str)->dict:
    raw=scalar(f"SET ROLE {role};\n"+statement+"\nRESET ROLE;")
    return json.loads(raw)


def expect_role_failure(role:str,statement:str,marker:str)->None:
    cp=psql(f"SET ROLE {role};\n"+statement,check=False)
    if cp.returncode==0 or marker not in cp.stdout+cp.stderr:
        raise AssertionError("expected failure marker "+marker+"\n"+cp.stdout+cp.stderr)


def expect_migration_failure(marker:str)->None:
    cp=apply(ROOT/"sql/notification/001_notification_delivery.sql",check=False)
    if cp.returncode==0 or marker not in cp.stdout+cp.stderr:
        raise AssertionError("expected migration failure "+marker+"\n"+cp.stdout+cp.stderr)


def create_intent(logical_id:str,destination:str,visibility_id:str|None)->dict:
    auth=authority("tenant-a","actor-a","notification:write").replace("'","''")
    vis="NULL" if visibility_id is None else "'"+visibility_id.replace("'","''")+"'"
    return role_call(
        "jlmirror_g9_notification_app_invoker",
        f"""
SELECT notification.g9_create_intent(
 'tenant-a','alert-a','customer-a','{destination}',
 'whatsapp_business@1','alert_requires_attention',
 'template-a','payload-hash-a',{vis},'actor-a','{logical_id}',
 '{auth}'::jsonb
)::text;
""",
    )


def outbox_for(intent_id:str,attempt:int)->str:
    return scalar(f"""
SELECT dispatch_outbox_id
FROM notification.notification_dispatch_outbox
WHERE tenant_id='tenant-a'
  AND notification_intent_id='{intent_id}'
  AND attempt_number={attempt};
""")


def claim(outbox_id:str,executor:str,claim_seconds:int=60)->dict:
    return role_call(
        "jlmirror_g9_notification_worker_invoker",
        f"""
SELECT notification.g9_claim_dispatch(
 'tenant-a','{outbox_id}','{executor}',{claim_seconds},
 'fixture-whatsapp@1',
 '{{"channel":"whatsapp_business@1","payload_hash":"payload-hash-a"}}'::jsonb
)::text;
""",
    )


def complete(outbox_id:str,executor:str,state:str,provider_ref:str|None,failure:str|None)->dict:
    provider="NULL" if provider_ref is None else "'"+provider_ref+"'"
    failure_sql="NULL" if failure is None else "'"+failure+"'"
    return role_call(
        "jlmirror_g9_notification_worker_invoker",
        f"""
SELECT notification.g9_complete_dispatch(
 'tenant-a','{outbox_id}','{executor}','{state}',{provider},{failure_sql}
)::text;
""",
    )


def schedule(intent_id:str)->dict:
    return role_call(
        "jlmirror_g9_notification_worker_invoker",
        f"SELECT notification.g9_schedule_retry('tenant-a','{intent_id}')::text;",
    )


def callback(
    callback_ref:str,provider_ref:str,kind:str,payload_hash:str|None=None
)->dict:
    digest=payload_hash or ("hash-"+callback_ref)
    return role_call(
        "jlmirror_g9_notification_callback_invoker",
        f"""
SELECT notification.g9_record_provider_callback(
 'tenant-a','{callback_ref}','{provider_ref}','{digest}','{kind}',
 '{{"verified":true,"trusted_route_ref":"account-a","timestamp_epoch":1,"signature_profile":"hmac-sha256@1"}}'::jsonb,
 '{{"status":"{kind}"}}'::jsonb,
 transaction_timestamp()
)::text;
""",
    )


def get_intent(intent_id:str)->dict:
    return role_call(
        "jlmirror_g9_notification_app_invoker",
        f"SELECT notification.g9_get_intent('tenant-a','{intent_id}')::text;",
    )


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
        apply(ROOT/"sql/human_operations/001_human_operations.sql")
        apply(ROOT/"tests/g8/fixtures/postgres_seed.sql")

        apply(FIXTURES/"poison_default_execute.sql")
        expect_migration_failure("g9.function_acl_unsafe")
        apply(FIXTURES/"cleanup_default_execute.sql")

        apply(FIXTURES/"poison_executor_owner.sql")
        expect_migration_failure("g9.executor_unexpected_owned_object")
        apply(FIXTURES/"cleanup_executor_owner.sql")

        apply(FIXTURES/"poison_existing_function_acl.sql")
        expect_migration_failure("g9.existing_function_acl_unsafe")
        apply(FIXTURES/"cleanup_existing_function_acl.sql")

        apply(ROOT/"sql/notification/001_notification_delivery.sql")

        roles=scalar("""
SELECT string_agg(
 rolname||':'||rolcanlogin::int||':'||rolsuper::int||':'||rolinherit::int||':'||rolbypassrls::int,
 ',' ORDER BY rolname
)
FROM pg_roles
WHERE rolname IN (
 'jlmirror_g9_notification_executor',
 'jlmirror_g9_notification_app_invoker',
 'jlmirror_g9_notification_worker_invoker',
 'jlmirror_g9_notification_callback_invoker'
);
""")
        expected_roles=(
          "jlmirror_g9_notification_app_invoker:0:0:0:0,"
          "jlmirror_g9_notification_callback_invoker:0:0:0:0,"
          "jlmirror_g9_notification_executor:0:0:0:0,"
          "jlmirror_g9_notification_worker_invoker:0:0:0:0"
        )
        if roles!=expected_roles:
            raise AssertionError("G9 role hardening drift: "+roles)

        rls=scalar("""
SELECT count(*)::text||':'||
       count(*) FILTER (WHERE c.relrowsecurity AND c.relforcerowsecurity)::text
FROM pg_class c
JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='notification'
  AND c.relname IN (
    'notification_intent','notification_attempt','notification_provider_evidence',
    'notification_projection','notification_dispatch_outbox','notification_callback_inbox'
  );
""")
        if rls!="6:6":
            raise AssertionError("G9 FORCE RLS drift: "+rls)

        relations=(
          "notification.notification_intent",
          "notification.notification_attempt",
          "notification.notification_provider_evidence",
          "notification.notification_projection",
          "notification.notification_dispatch_outbox",
          "notification.notification_callback_inbox",
        )
        invokers=(
          "jlmirror_g9_notification_app_invoker",
          "jlmirror_g9_notification_worker_invoker",
          "jlmirror_g9_notification_callback_invoker",
        )
        for role in invokers:
            for relation in relations:
                acl=scalar(
                    "SELECT "
                    f"has_table_privilege('{role}','{relation}','SELECT')::int||':'||"
                    f"has_table_privilege('{role}','{relation}','INSERT')::int||':'||"
                    f"has_table_privilege('{role}','{relation}','UPDATE')::int||':'||"
                    f"has_table_privilege('{role}','{relation}','DELETE')::int;"
                )
                if acl!="0:0:0:0":
                    raise AssertionError(f"direct table authority drift {role} {relation}: {acl}")

        vis_auth=authority("tenant-a","actor-a","human-operations:write").replace("'","''")
        visibility=json.loads(scalar(f"""
SELECT human_operations.g8_create_visibility_requirement(
 'tenant-a','alert-a','customer-a','customer',
 'platform_native_authenticated_view@1','alert-a','actor-a',
 'g9-native-view-required','{vis_auth}'::jsonb
)::text;
"""))
        visibility_id=visibility["visibility_requirement_id"]

        main_intent=create_intent("notify-main","destination-ref-a",visibility_id)
        main_id=main_intent["notification_intent_id"]
        if main_intent["duplicate"]:
            raise AssertionError("initial intent unexpectedly duplicate")

        replay=create_intent("notify-main","destination-ref-a",visibility_id)
        if not replay["duplicate"] or replay["notification_intent_id"]!=main_id:
            raise AssertionError("intent replay lost idempotency")

        auth=authority("tenant-a","actor-a","notification:write").replace("'","''")
        expect_role_failure(
            "jlmirror_g9_notification_app_invoker",
            f"""
SELECT notification.g9_create_intent(
 'tenant-a','alert-a','customer-a','different-destination',
 'whatsapp_business@1','alert_requires_attention',
 'template-a','payload-hash-a','{visibility_id}','actor-a','notify-main',
 '{auth}'::jsonb
);
""",
            "g9.intent_equivalence_conflict",
        )

        retry_intent=create_intent("notify-retry","destination-ref-b",None)
        retry_id=retry_intent["notification_intent_id"]
        recovery_intent=create_intent("notify-recovery","destination-ref-c",None)
        recovery_id=recovery_intent["notification_intent_id"]

        main_outbox=outbox_for(main_id,1)
        with ThreadPoolExecutor(max_workers=2) as pool:
            pairs=[
                ("worker-a",pool.submit(claim,main_outbox,"worker-a")),
                ("worker-b",pool.submit(claim,main_outbox,"worker-b")),
            ]
            claimed=[(executor,f.result()) for executor,f in pairs]
        winners=[x for x in claimed if x[1].get("duplicate") is False]
        duplicates=[x for x in claimed if x[1].get("duplicate") is True]
        if len(winners)!=1 or len(duplicates)!=1:
            raise AssertionError("dispatch concurrency did not converge to one claim")
        winner=winners[0][0]

        sent=complete(main_outbox,winner,"sent","provider-msg-main",None)
        if sent["state"]!="sent":
            raise AssertionError("sent completion drift")
        sent_replay=complete(main_outbox,winner,"sent","provider-msg-main",None)
        if not sent_replay["duplicate"]:
            raise AssertionError("dispatch completion replay lost idempotency")
        expect_role_failure(
            "jlmirror_g9_notification_worker_invoker",
            f"""
SELECT notification.g9_complete_dispatch(
 'tenant-a','{main_outbox}','{winner}','delivered','provider-msg-main',NULL
);
""",
            "g9.dispatch_completion_equivalence_conflict",
        )

        state=get_intent(main_id)
        if state["projection"]["delivery_state"]!="sent":
            raise AssertionError("sent was incorrectly promoted before provider evidence")
        if state["projection"]["native_visibility_state"]!="not_viewed_yet":
            raise AssertionError("native visibility requirement linkage drift")

        apply(FIXTURES/"resolve_alert_a.sql")

        read_evidence=callback("cb-read","provider-msg-main","external_read_observed")
        if read_evidence["state"]!="processed":
            raise AssertionError("external read callback not processed")
        state=get_intent(main_id)
        if state["projection"]["delivery_state"]!="sent":
            raise AssertionError("external read incorrectly promoted delivery")
        if state["projection"]["external_read_observed"] is not True:
            raise AssertionError("external read evidence missing")
        if state["projection"]["native_visibility_state"]!="not_viewed_yet":
            raise AssertionError("external read fabricated native view")

        callback("cb-accepted","provider-msg-main","provider_accepted")
        state=get_intent(main_id)
        if state["projection"]["delivery_state"]!="provider_accepted":
            raise AssertionError("provider acceptance projection drift")

        callback("cb-delivered","provider-msg-main","delivered")
        state=get_intent(main_id)
        if state["projection"]["delivery_state"]!="delivered":
            raise AssertionError("delivery evidence projection drift")
        if state["projection"]["fallback_action_required"] is not True:
            raise AssertionError("missing native awareness did not require fallback")
        if state["projection"]["fallback_reason"]!="authoritative_awareness_missing":
            raise AssertionError("awareness fallback reason drift")

        callback("cb-accepted-late","provider-msg-main","provider_accepted")
        state=get_intent(main_id)
        if state["projection"]["delivery_state"]!="delivered":
            raise AssertionError("out-of-order evidence downgraded delivered state")

        duplicate=callback("cb-delivered","provider-msg-main","delivered")
        if not duplicate["duplicate"]:
            raise AssertionError("callback duplicate not deduped")
        expect_role_failure(
            "jlmirror_g9_notification_callback_invoker",
            """
SELECT notification.g9_record_provider_callback(
 'tenant-a','cb-delivered','provider-msg-main','different-hash','delivered',
 '{"verified":true,"trusted_route_ref":"account-a"}'::jsonb,
 '{"status":"delivered"}'::jsonb,transaction_timestamp()
);
""",
            "g9.callback_equivalence_conflict",
        )

        view_auth=authority("tenant-a","customer-a","human-operations:view").replace("'","''")
        json.loads(scalar(f"""
SELECT human_operations.g8_record_visibility_receipt(
 'tenant-a','{visibility_id}','customer-a','g9-native-view-receipt',
 '{view_auth}'::jsonb,
 '{{"session_generation":"s1","admission_revision":"a1"}}'::jsonb
)::text;
"""))
        state=get_intent(main_id)
        if state["projection"]["native_visibility_state"]!="viewed":
            raise AssertionError("G8 native visibility was not composed")
        if state["projection"]["external_read_observed"] is not True:
            raise AssertionError("native view erased external read evidence")
        if state["projection"]["fallback_action_required"] is not False:
            raise AssertionError("native view did not clear awareness-only fallback in read projection")

        retry_outbox=outbox_for(retry_id,1)
        retry_claim=claim(retry_outbox,"worker-retry-1")
        if retry_claim["state"]!="processing":
            raise AssertionError("retry intent initial claim drift")
        complete(retry_outbox,"worker-retry-1","unknown",None,"outcome_unknown")
        retry_state=get_intent(retry_id)
        if retry_state["projection"]["delivery_state"]!="unknown":
            raise AssertionError("unknown outcome was not preserved")
        if retry_state["projection"]["retry_required"] is not True:
            raise AssertionError("unknown outcome did not require retry")
        scheduled=schedule(retry_id)
        if not scheduled["scheduled"] or scheduled["attempt_number"]!=2:
            raise AssertionError("second attempt was not scheduled")

        apply(FIXTURES/"force_due.sql")
        outbox2=outbox_for(retry_id,2)
        claim(outbox2,"worker-retry-2")
        complete(outbox2,"worker-retry-2","failed",None,"transport_failed")
        scheduled=schedule(retry_id)
        if not scheduled["scheduled"] or scheduled["attempt_number"]!=3:
            raise AssertionError("third attempt was not scheduled")

        apply(FIXTURES/"force_due.sql")
        outbox3=outbox_for(retry_id,3)
        claim(outbox3,"worker-retry-3")
        complete(outbox3,"worker-retry-3","failed",None,"transport_failed")
        retry_state=get_intent(retry_id)
        if retry_state["projection"]["retry_required"] is not False:
            raise AssertionError("retry remained enabled beyond budget")
        if retry_state["projection"]["fallback_action_required"] is not True:
            raise AssertionError("retry exhaustion did not surface fallback")
        if retry_state["projection"]["fallback_reason"]!="retry_budget_exhausted":
            raise AssertionError("retry exhaustion reason drift")

        recovery_outbox=outbox_for(recovery_id,1)
        claim(recovery_outbox,"worker-recovery",1)
        time.sleep(1.2)
        expired=claim(recovery_outbox,"worker-recovery-2",1)
        if expired["state"]!="reconciliation_required":
            raise AssertionError("expired claim did not enter reconciliation")
        reconciled=role_call(
            "jlmirror_g9_notification_worker_invoker",
            f"SELECT notification.g9_reconcile_dispatch_claim('tenant-a','{recovery_outbox}')::text;",
        )
        if not reconciled["reconciled"] or reconciled["state"]!="unknown":
            raise AssertionError("expired claim reconciliation drift")
        recovery_state=get_intent(recovery_id)
        if recovery_state["projection"]["delivery_state"]!="unknown":
            raise AssertionError("recovery did not preserve unknown outcome")

        quarantined=role_call(
            "jlmirror_g9_notification_callback_invoker",
            """
SELECT notification.g9_record_provider_callback(
 'tenant-a','cb-unbound','provider-msg-missing','hash-unbound','unknown',
 '{"verified":true,"trusted_route_ref":"account-a"}'::jsonb,
 '{"status":"unknown"}'::jsonb,transaction_timestamp()
)::text;
""",
        )
        if quarantined["state"]!="quarantined":
            raise AssertionError("unbindable callback was not quarantined")

        cross=psql(
            "SET ROLE jlmirror_g9_notification_app_invoker;\n"
            f"SELECT notification.g9_get_intent('tenant-b','{main_id}');",
            check=False,
        )
        if cross.returncode==0 or "g9.intent_missing" not in cross.stdout+cross.stderr:
            raise AssertionError("cross-tenant read did not fail closed")

        direct=apply(FIXTURES/"forbidden_app_write.sql",check=False)
        if direct.returncode==0:
            raise AssertionError("application invoker direct write unexpectedly succeeded")

        if main_id=="provider-msg-main":
            raise AssertionError("provider message reference became platform identity")

        print(
          "g9_postgres_conformance=PASS "
          "owner_poison=BLOCKED default_acl_poison=BLOCKED existing_acl_poison=BLOCKED "
          "roles=PASS rls=PASS direct_acl=PASS intent_idempotency=PASS "
          "dispatch_concurrency=PASS dispatch_equivalence=PASS sent_not_delivered=PASS "
          "callback_dedup=PASS out_of_order=PASS external_read_separation=PASS "
          "native_visibility_composition=PASS retry_budget=PASS lease_recovery=PASS "
          "tenant_isolation=PASS quarantine=PASS"
        )
        return 0
    finally:
        subprocess.run(["docker","rm","-f",CONTAINER],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


if __name__=="__main__":
    raise SystemExit(main())
