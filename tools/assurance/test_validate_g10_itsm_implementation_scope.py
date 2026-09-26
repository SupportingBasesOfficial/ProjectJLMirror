#!/usr/bin/env python3
from __future__ import annotations
import json,subprocess,tempfile
from pathlib import Path

VALIDATOR=Path(__file__).with_name("validate_g10_itsm_implementation_scope.py")
REPO="SupportingBasesOfficial/ProjectJLMirror"
POLICY={
"allowed_prefixes":["apps/g10-itsm/","contracts/g10-itsm/","implementation/g10-itsm/","tests/g10/","tools/g10/"],
"allowed_exact_paths":["sql/itsm/001_incident.sql",".github/workflows/g10-itsm-runtime.yml"],
"semantic_scan_prefixes":["apps/g10-itsm/","contracts/g10-itsm/","implementation/g10-itsm/","tests/g10/","tools/g10/"],
"forbidden_path_tokens":["change","rfc","approval","budget","quote","knowledge","maintenance","automation","aiops","servicenow","jira","zendesk"],
"forbidden_code_markers":["alert_reopen","alert_resolve","notification_delivery_mutation","approval_state","awaiting_budget_approval","change_request","knowledge_article","maintenance_window","automation_execute","aiops_mutation"],
"implementation_claim_path":"implementation/g10-itsm/IMPLEMENTATION_CLAIM.json",
"implementation_pr_head_prefix":"impl/g10-itsm",
"implementation_pr_required_label":"jlmirror-slice:g10-itsm",
"exact_sql_path":"sql/itsm/001_incident.sql",
"exact_sql_allowed_relations":["itsm.incident","itsm.incident_transition","itsm.incident_assignment","itsm.incident_comment","itsm.incident_provider_link","itsm.incident_sync_outbox"],
"runtime_workflow":".github/workflows/g10-itsm-runtime.yml",
"runtime_workflow_name":"JLMIRROR G10 ITSM Runtime",
"runtime_entrypoint":"python tools/g10/run_itsm_runtime.py",
"runtime_allowed_actions":["actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1","actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1","actions/setup-node@249970729cb0ef3589644e2896645e5dc5ba9c38"]}

GOOD_SQL="""BEGIN;
CREATE SCHEMA IF NOT EXISTS itsm;
CREATE TABLE itsm.incident(tenant_id text,incident_id text,alert_id text);
CREATE TABLE itsm.incident_transition(tenant_id text,incident_transition_id text,incident_id text);
CREATE TABLE itsm.incident_assignment(tenant_id text,incident_assignment_id text,incident_id text);
CREATE TABLE itsm.incident_comment(tenant_id text,incident_comment_id text,incident_id text);
CREATE TABLE itsm.incident_provider_link(tenant_id text,incident_id text,provider_link_id text);
CREATE TABLE itsm.incident_sync_outbox(tenant_id text,incident_id text,sync_outbox_id text);

DO $$
DECLARE v_role record;
BEGIN
  FOR v_role IN SELECT * FROM pg_catalog.pg_roles
    WHERE rolname IN ('jlmirror_g10_itsm_executor','jlmirror_g10_itsm_app_invoker','jlmirror_g10_itsm_worker_invoker')
  LOOP
    IF v_role.rolcanlogin OR v_role.rolsuper OR v_role.rolcreatedb OR v_role.rolcreaterole
       OR v_role.rolinherit OR v_role.rolreplication OR v_role.rolbypassrls THEN
      RAISE EXCEPTION 'g10.role_unsafe:%',v_role.rolname;
    END IF;
    IF EXISTS (
      SELECT 1 FROM pg_catalog.pg_auth_members
      WHERE roleid=v_role.oid OR member=v_role.oid
    ) THEN
      RAISE EXCEPTION 'g10.role_unsafe_membership:%',v_role.rolname;
    END IF;
  END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION itsm.g10_create_incident(
 p_tenant_id text,p_alert_id text,p_title text,p_description text,
 p_actor_principal_id text,p_logical_action_id text,p_authority_snapshot jsonb
) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE v_existing record;
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10));
  SELECT * INTO v_existing FROM itsm.incident
   WHERE tenant_id=p_tenant_id AND logical_action_id=p_logical_action_id;
  IF FOUND THEN
    IF v_existing.content_hash<>v_hash THEN RAISE EXCEPTION 'g10.incident_equivalence_conflict'; END IF;
    RETURN jsonb_build_object('incident_id',v_existing.incident_id,'duplicate',TRUE);
  END IF;
  INSERT INTO itsm.incident(tenant_id,incident_id,alert_id)
  VALUES (p_tenant_id,'fixture-incident',p_alert_id);
  RETURN jsonb_build_object('incident_id','fixture-incident','duplicate',FALSE);
END;
$;

CREATE OR REPLACE FUNCTION itsm.g10_transition_incident(
 p_tenant_id text,p_incident_id text,p_target_state text,p_actor_principal_id text,
 p_logical_action_id text,p_authority_snapshot jsonb
) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE v_existing_transition record;
BEGIN
  SELECT * INTO v_existing_transition
  FROM itsm.incident_transition
  WHERE tenant_id=p_tenant_id AND incident_id=p_incident_id
    AND logical_action_id=p_logical_action_id;
  IF FOUND THEN
    IF v_existing_transition.to_state IS DISTINCT FROM p_target_state THEN
      RAISE EXCEPTION 'g10.transition_equivalence_conflict';
    END IF;
    RETURN jsonb_build_object('incident_id',p_incident_id,'duplicate',TRUE);
  END IF;
  RETURN '{}'::jsonb;
END;
$$;

CREATE OR REPLACE FUNCTION itsm.g10_next_sync_candidate(p_tenant_id text)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE v_result jsonb;
BEGIN
  SELECT to_jsonb(x) INTO v_result FROM (
    SELECT o.sync_outbox_id,o.incident_id
    FROM itsm.incident_sync_outbox o
    WHERE o.tenant_id=p_tenant_id
      AND (
        (o.sync_state='pending' AND o.available_at<=transaction_timestamp())
        OR
        (o.sync_state='dispatching' AND o.claim_expires_at<=transaction_timestamp())
      )
    LIMIT 1
  ) x;
  RETURN v_result;
END;
$$;

CREATE OR REPLACE FUNCTION itsm.g10_get_incident(p_tenant_id text,p_incident_id text)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE v_alert jsonb;
BEGIN
  SELECT to_jsonb(x) INTO v_alert FROM (
    SELECT alert_id,lifecycle_state,opened_at,resolved_at
    FROM alerting.alert WHERE tenant_id=p_tenant_id AND alert_id=v_incident->>'alert_id'
  ) x;
  RETURN '{}'::jsonb;
END;
$$;
COMMIT;
"""

def init():
 td=tempfile.TemporaryDirectory();root=Path(td.name);subprocess.run(["git","init","-q",str(root)],check=True)
 subprocess.run(["git","-C",str(root),"config","user.email","x@example.invalid"],check=True)
 subprocess.run(["git","-C",str(root),"config","user.name","G10 test"],check=True)
 p=root/"implementation/g10-itsm-authorization/AUTHORIZATION_MANIFEST.json";p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps({"implementation_authority_after_merge":"granted_for_exact_g10_itsm_incident_only","implementation_path_policy":POLICY}))
 subprocess.run(["git","-C",str(root),"add","."],check=True);subprocess.run(["git","-C",str(root),"commit","-qm","base"],check=True)
 return td,root,subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()

def wf():
 return json.dumps({"name":"JLMIRROR G10 ITSM Runtime","on":{"pull_request":{},"workflow_dispatch":{}},"permissions":{},"jobs":{"g10-runtime":{"runs-on":"ubuntu-24.04","steps":[{"uses":"actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"},{"uses":"actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"},{"uses":"actions/setup-node@249970729cb0ef3589644e2896645e5dc5ba9c38"},{"run":"python tools/g10/run_itsm_runtime.py"}]}}})

def case(files,ok):
 td,root,base=init()
 try:
  for rel,body in files.items():
   p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(body)
  claim=root/"implementation/g10-itsm/IMPLEMENTATION_CLAIM.json";claim.parent.mkdir(parents=True,exist_ok=True)
  claim.write_text(json.dumps({"authorization_id":"g10.itsm-incident@1","slice_id":"g10.itsm-incident@1"}))
  sp=root/"sql/itsm/001_incident.sql";sp.parent.mkdir(parents=True,exist_ok=True)
  if not sp.exists():sp.write_text(GOOD_SQL)
  wp=root/".github/workflows/g10-itsm-runtime.yml";wp.parent.mkdir(parents=True,exist_ok=True)
  if not wp.exists():wp.write_text(wf())
  subprocess.run(["git","-C",str(root),"add","."],check=True);subprocess.run(["git","-C",str(root),"commit","-qm","candidate"],check=True)
  head=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
  cp=subprocess.run(["python3",str(VALIDATOR),"--repo-root",str(root),"--base",base,"--head",head,
      "--head-ref","impl/g10-itsm-test","--labels-json",'["jlmirror-slice:g10-itsm"]',
      "--head-repo",REPO,"--base-repo",REPO],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  if (cp.returncode==0)!=ok:raise AssertionError(cp.stdout+"\n"+cp.stderr)
 finally:td.cleanup()

def require_rejected(sql_text):
    case({"sql/itsm/001_incident.sql":sql_text},False)

def falsify_g10_alert_opened_at_projection():
    require_rejected(GOOD_SQL.replace(
      "SELECT alert_id,lifecycle_state,opened_at,resolved_at",
      "SELECT alert_id,lifecycle_state,a.created_at AS opened_at,resolved_at"
    ))
    require_rejected(GOOD_SQL.replace(
      "SELECT alert_id,lifecycle_state,opened_at,resolved_at",
      "SELECT alert_id,lifecycle_state,resolved_at AS opened_at,resolved_at"
    ))
    require_rejected(GOOD_SQL.replace(
      "SELECT alert_id,lifecycle_state,opened_at,resolved_at",
      "SELECT alert_id,lifecycle_state,resolved_at opened_at,resolved_at"
    ))
    require_rejected(GOOD_SQL.replace(
      "SELECT alert_id,lifecycle_state,opened_at,resolved_at\n    FROM alerting.alert",
      "SELECT alert_id,lifecycle_state,opened_at,resolved_at FROM (SELECT alert_id,lifecycle_state,resolved_at AS opened_at,resolved_at FROM alerting.alert) nested"
    ))
    require_rejected(GOOD_SQL.replace(
      "SELECT alert_id,lifecycle_state,opened_at,resolved_at\n    FROM alerting.alert",
      "SELECT alert_id,lifecycle_state,opened_at,resolved_at FROM (SELECT alert_id,lifecycle_state,COALESCE(resolved_at,resolved_at) AS opened_at,resolved_at FROM alerting.alert) nested"
    ))
    require_rejected(GOOD_SQL.replace(
      """  SELECT to_jsonb(x) INTO v_alert FROM (
    SELECT alert_id,lifecycle_state,opened_at,resolved_at
    FROM alerting.alert WHERE tenant_id=p_tenant_id AND alert_id=v_incident->>'alert_id'
  ) x;""",
      """  PERFORM $q$SELECT to_jsonb(x) INTO v_alert FROM (
    SELECT alert_id,lifecycle_state,opened_at,resolved_at
    FROM alerting.alert WHERE tenant_id=p_tenant_id AND alert_id=v_incident->>'alert_id'
  ) x;$q$;"""
    ))

def falsify_g10_expired_sync_discovery():
    require_rejected(GOOD_SQL.replace(
      "BEGIN\n  SELECT to_jsonb(x) INTO v_result FROM (",
      "BEGIN\n  CASE WHEN FALSE THEN\n  SELECT to_jsonb(x) INTO v_result FROM ("
    ).replace(
      "  ) x;\n  RETURN v_result;\nEND;",
      "  ) x;\n  RETURN v_result;\n  ELSE NULL;\n  END CASE;\n  RETURN '{}'::jsonb;\nEND;"
    ))
    canonical_worker_body="""BEGIN
  SELECT to_jsonb(x) INTO v_result FROM (
    SELECT o.sync_outbox_id,o.incident_id
    FROM itsm.incident_sync_outbox o
    WHERE o.tenant_id=p_tenant_id
      AND (
        (o.sync_state='pending' AND o.available_at<=transaction_timestamp())
        OR
        (o.sync_state='dispatching' AND o.claim_expires_at<=transaction_timestamp())
      )
    LIMIT 1
  ) x;
  RETURN v_result;
END;"""
    require_rejected(GOOD_SQL.replace(
      canonical_worker_body,
      """BEGIN
  PERFORM $q$SELECT to_jsonb(x) INTO v_result FROM (
    SELECT o.sync_outbox_id,o.incident_id
    FROM itsm.incident_sync_outbox o
    WHERE o.tenant_id=p_tenant_id
      AND (
        (o.sync_state='pending' AND o.available_at<=transaction_timestamp())
        OR
        (o.sync_state='dispatching' AND o.claim_expires_at<=transaction_timestamp())
      )
    LIMIT 1
  ) x;
  RETURN v_result;$q$;
  RETURN '{}'::jsonb;
END;"""
    ))
    require_rejected(GOOD_SQL.replace(
      "    FROM itsm.incident_sync_outbox o",
      "    FROM (SELECT 'fake'::text AS sync_outbox_id,'fake-inc'::text AS incident_id,'pending'::text AS sync_state,transaction_timestamp() AS available_at,transaction_timestamp() AS claim_expires_at) o"
    ))
    require_rejected(GOOD_SQL.replace(
      "    FROM itsm.incident_sync_outbox o",
      "    FROM itsm.incident_sync_outbox o JOIN (SELECT 1) dead ON FALSE"
    ))
    require_rejected(GOOD_SQL.replace(
      "    WHERE o.tenant_id=p_tenant_id\n      AND (\n        (o.sync_state='pending'",
      "    WHERE o.tenant_id=p_tenant_id\n      AND FALSE AND (\n        (o.sync_state='pending'"
    ))
    require_rejected(GOOD_SQL.replace(
      ")\n        OR\n        (o.sync_state='dispatching'",
      ")\n        AND\n        (o.sync_state='dispatching'"
    ))
    require_rejected(GOOD_SQL.replace(
      "      )\n    LIMIT 1",
      "      ) AND FALSE\n    LIMIT 1"
    ))
    require_rejected(GOOD_SQL.replace(
      "SELECT to_jsonb(x) INTO v_result FROM (",
      "PERFORM 1 FROM ("
    ).replace(
      "  ) x;\n  RETURN v_result;",
      "  ) x;\n  RETURN '{}'::jsonb;"
    ))
    require_rejected(GOOD_SQL.replace(
      "BEGIN\n  SELECT to_jsonb(x) INTO v_result FROM (",
      "BEGIN\n  RETURN '{}'::jsonb;\n  SELECT to_jsonb(x) INTO v_result FROM ("
    ))
    require_rejected(GOOD_SQL.replace(
      "BEGIN\n  SELECT to_jsonb(x) INTO v_result FROM (",
      "BEGIN\n  RAISE EXCEPTION 'stop';\n  SELECT to_jsonb(x) INTO v_result FROM ("
    ))
    require_rejected(GOOD_SQL.replace(
      "BEGIN\n  SELECT to_jsonb(x) INTO v_result FROM (",
      "BEGIN\n  RAISE SQLSTATE 'P0001';\n  SELECT to_jsonb(x) INTO v_result FROM ("
    ))
    require_rejected(GOOD_SQL.replace(
      "BEGIN\n  SELECT to_jsonb(x) INTO v_result FROM (",
      "BEGIN\n  IF FALSE THEN\n  SELECT to_jsonb(x) INTO v_result FROM ("
    ).replace(
      "  ) x;\n  RETURN v_result;",
      "  ) x;\n  END IF;\n  RETURN v_result;"
    ))
    require_rejected(GOOD_SQL.replace(
      "BEGIN\n  SELECT to_jsonb(x) INTO v_result FROM (",
      "BEGIN\n  IF FALSE THEN\n  PERFORM 'END IF;';\n  SELECT to_jsonb(x) INTO v_result FROM ("
    ).replace(
      "  ) x;\n  RETURN v_result;",
      "  ) x;\n  RETURN v_result;\n  END IF;\n  RETURN '{}'::jsonb;"
    ))
    require_rejected(GOOD_SQL.replace(
      "BEGIN\n  SELECT to_jsonb(x) INTO v_result FROM (",
      "BEGIN\n  WHILE FALSE LOOP\n  SELECT to_jsonb(x) INTO v_result FROM ("
    ).replace(
      "  ) x;\n  RETURN v_result;",
      "  ) x;\n  RETURN v_result;\n  END LOOP;\n  RETURN '{}'::jsonb;"
    ))
    require_rejected(GOOD_SQL.replace(
      "BEGIN\n  SELECT to_jsonb(x) INTO v_result FROM (",
      "BEGIN\n  IF p_tenant_id IS NULL THEN\n  SELECT to_jsonb(x) INTO v_result FROM ("
    ).replace(
      "  ) x;\n  RETURN v_result;",
      "  ) x;\n  RETURN v_result;\n  END IF;\n  RETURN '{}'::jsonb;"
    ))
    case({"sql/itsm/001_incident.sql":GOOD_SQL.replace(
      "BEGIN\n  SELECT to_jsonb(x) INTO v_result FROM (",
      "BEGIN\n  IF p_tenant_id IS NULL THEN\n    RAISE EXCEPTION 'tenant required';\n  END IF;\n  SELECT to_jsonb(x) INTO v_result FROM ("
    )},True)

def falsify_g10_privileged_role_membership_fence():
    loop_block="""  FOR v_role IN SELECT * FROM pg_catalog.pg_roles
    WHERE rolname IN ('jlmirror_g10_itsm_executor','jlmirror_g10_itsm_app_invoker','jlmirror_g10_itsm_worker_invoker')
  LOOP
    IF v_role.rolcanlogin OR v_role.rolsuper OR v_role.rolcreatedb OR v_role.rolcreaterole
       OR v_role.rolinherit OR v_role.rolreplication OR v_role.rolbypassrls THEN
      RAISE EXCEPTION 'g10.role_unsafe:%',v_role.rolname;
    END IF;
    IF EXISTS (
      SELECT 1 FROM pg_catalog.pg_auth_members
      WHERE roleid=v_role.oid OR member=v_role.oid
    ) THEN
      RAISE EXCEPTION 'g10.role_unsafe_membership:%',v_role.rolname;
    END IF;
  END LOOP;"""
    require_rejected(GOOD_SQL.replace(
      loop_block,
      "  NULL;"
    ).replace(
      "CREATE OR REPLACE FUNCTION itsm.g10_create_incident(",
      "CREATE OR REPLACE FUNCTION itsm.never_called_membership_check() RETURNS void LANGUAGE plpgsql AS $\nDECLARE v_role record;\nBEGIN\n"+loop_block+"\nEND;\n$;\n\nCREATE OR REPLACE FUNCTION itsm.g10_create_incident("
    ))
    guard="""    IF EXISTS (
      SELECT 1 FROM pg_catalog.pg_auth_members
      WHERE roleid=v_role.oid OR member=v_role.oid
    ) THEN
      RAISE EXCEPTION 'g10.role_unsafe_membership:%',v_role.rolname;
    END IF;"""
    require_rejected(GOOD_SQL.replace(
      guard,
      "    PERFORM 1 FROM pg_catalog.pg_auth_members WHERE roleid=v_role.oid OR member=v_role.oid;"
    ))
    require_rejected(
      "CREATE TEMP VIEW pg_auth_members AS SELECT * FROM pg_catalog.pg_auth_members WHERE FALSE;\n"+
      GOOD_SQL.replace("FROM pg_catalog.pg_auth_members","FROM pg_auth_members")
    )
    require_rejected(
      "CREATE TEMP VIEW pg_roles AS SELECT * FROM pg_catalog.pg_roles WHERE FALSE;\n"+
      GOOD_SQL.replace("FROM pg_catalog.pg_roles","FROM pg_roles")
    )
    require_rejected(GOOD_SQL.replace(
      "FOR v_role IN SELECT * FROM pg_catalog.pg_roles\n    WHERE rolname IN ('jlmirror_g10_itsm_executor','jlmirror_g10_itsm_app_invoker','jlmirror_g10_itsm_worker_invoker')",
      "FOR v_role IN SELECT * FROM pg_catalog.pg_roles WHERE rolname='jlmirror_g10_itsm_executor'"
    ))
    require_rejected(GOOD_SQL.replace(
      "WHERE rolname IN ('jlmirror_g10_itsm_executor','jlmirror_g10_itsm_app_invoker','jlmirror_g10_itsm_worker_invoker')",
      "WHERE rolname IN ('jlmirror_g10_itsm_executor'||$q$_x$q$,'jlmirror_g10_itsm_app_invoker'||$q$_x$q$,'jlmirror_g10_itsm_worker_invoker'||$q$_x$q$)"
    ))
    require_rejected(GOOD_SQL.replace(
      """    IF v_role.rolcanlogin OR v_role.rolsuper OR v_role.rolcreatedb OR v_role.rolcreaterole
       OR v_role.rolinherit OR v_role.rolreplication OR v_role.rolbypassrls THEN
      RAISE EXCEPTION 'g10.role_unsafe:%',v_role.rolname;
    END IF;
""",
      ""
    ))
    require_rejected(GOOD_SQL.replace(
      guard+"\n  END LOOP;",
      "    NULL;\n  END LOOP;\n"+guard
    ))
    require_rejected(GOOD_SQL.replace(
      guard,
      "    IF FALSE THEN\n"+guard+"\n    END IF;"
    ))
    require_rejected(GOOD_SQL.replace(
      guard,
      "    IF v_role.rolname = 'never-a-g10-role' THEN\n"+guard+"\n    END IF;"
    ))
    require_rejected(GOOD_SQL.replace(
      guard,
      "    BEGIN\n      NULL;\n    EXCEPTION WHEN OTHERS THEN\n"+guard+"\n    END;"
    ))
    require_rejected(GOOD_SQL.replace(
      guard,
      "    PERFORM $q$"+guard+"$q$;"
    ))
    require_rejected(GOOD_SQL.replace(
      "  LOOP\n    IF v_role.rolcanlogin OR v_role.rolsuper OR v_role.rolcreatedb OR v_role.rolcreaterole\n       OR v_role.rolinherit OR v_role.rolreplication OR v_role.rolbypassrls THEN\n      RAISE EXCEPTION 'g10.role_unsafe:%',v_role.rolname;\n    END IF;\n    IF EXISTS (",
      "  LOOP\n    CONTINUE;\n    IF EXISTS ("
    ))
    require_rejected(GOOD_SQL.replace(
      "  LOOP\n    IF v_role.rolcanlogin OR v_role.rolsuper OR v_role.rolcreatedb OR v_role.rolcreaterole\n       OR v_role.rolinherit OR v_role.rolreplication OR v_role.rolbypassrls THEN\n      RAISE EXCEPTION 'g10.role_unsafe:%',v_role.rolname;\n    END IF;\n    IF EXISTS (",
      "  LOOP\n    EXIT WHEN TRUE;\n    IF EXISTS ("
    ))
    require_rejected(GOOD_SQL.replace(
      "  LOOP\n    IF v_role.rolcanlogin OR v_role.rolsuper OR v_role.rolcreatedb OR v_role.rolcreaterole\n       OR v_role.rolinherit OR v_role.rolreplication OR v_role.rolbypassrls THEN\n      RAISE EXCEPTION 'g10.role_unsafe:%',v_role.rolname;\n    END IF;\n    IF EXISTS (",
      "  LOOP\n    CONTINUE WHEN TRUE;\n    IF EXISTS ("
    ))

    require_rejected(GOOD_SQL.replace(
      loop_block,
      "  IF FALSE THEN\n"+loop_block+"\n  END IF;"
    ))
    require_rejected(GOOD_SQL.replace(
      loop_block,
      "  CASE WHEN FALSE THEN\n"+loop_block+"\n  ELSE NULL;\n  END CASE;"
    ))
    require_rejected(GOOD_SQL+"\nGRANT jlmirror_g10_itsm_executor TO jlmirror_g10_itsm_app_invoker;\n")
    require_rejected(GOOD_SQL+"\nGRANT unrelated_role TO GROUP jlmirror_g10_itsm_executor;\n")
    require_rejected(GOOD_SQL+"\nGRANT unrelated_role TO \"jlmirror_g10_itsm_executor\";\n")
    require_rejected(GOOD_SQL+"\nGRANT \"unrelated_role\" TO jlmirror_g10_itsm_executor;\n")
    require_rejected(GOOD_SQL+"\nREVOKE \"unrelated_role\" FROM jlmirror_g10_itsm_executor;\n")
    require_rejected(GOOD_SQL+"\nGRANT pg_read_all_data, jlmirror_g10_itsm_executor TO attacker;\n")
    require_rejected(GOOD_SQL+"\nGRANT unrelated_role TO attacker, jlmirror_g10_itsm_executor;\n")
    require_rejected(GOOD_SQL+"\nREVOKE pg_read_all_data, jlmirror_g10_itsm_executor FROM attacker;\n")
    require_rejected(GOOD_SQL+"\nREVOKE unrelated_role FROM attacker, jlmirror_g10_itsm_executor;\n")
    require_rejected(GOOD_SQL+"\nCREATE ROLE \"ON\"; CREATE ROLE attacker; GRANT \"ON\", jlmirror_g10_itsm_executor TO attacker;\n")
    require_rejected(GOOD_SQL+"\nCREATE ROLE \"ON\"; CREATE ROLE attacker; REVOKE \"ON\", jlmirror_g10_itsm_executor FROM attacker;\n")
    require_rejected(GOOD_SQL+"\nGRANT unrelated_role TO jlmirror_g10_itsm_executor WITH ADMIN OPTION;\n")
    require_rejected(GOOD_SQL+"\nCREATE ROLE attacker IN ROLE jlmirror_g10_itsm_executor;\n")
    require_rejected(GOOD_SQL+"\nCREATE ROLE attacker ROLE jlmirror_g10_itsm_executor;\n")
    require_rejected(GOOD_SQL+"\nCREATE ROLE attacker ADMIN jlmirror_g10_itsm_executor;\n")
    require_rejected(GOOD_SQL+"\nALTER GROUP jlmirror_g10_itsm_executor ADD USER attacker;\n")
    require_rejected(GOOD_SQL+"\nALTER ROLE jlmirror_g10_itsm_app_invoker SUPERUSER;\n")
    require_rejected(GOOD_SQL+"\nALTER USER \"jlmirror_g10_itsm_worker_invoker\" CREATEDB;\n")
    require_rejected(GOOD_SQL+"\nCREATE ROLE jlmirror_g10_itsm_app_invoker SUPERUSER;\n")
    require_rejected(GOOD_SQL+"\nCREATE USER \"jlmirror_g10_itsm_worker_invoker\" CREATEDB;\n")
    require_rejected(GOOD_SQL+"\nCREATE GROUP jlmirror_g10_itsm_app_invoker WITH SUPERUSER;\n")
    require_rejected(GOOD_SQL.replace(
      "  END LOOP;\nEND;\n$$;",
      "  END LOOP;\n  GRANT jlmirror_g10_itsm_executor TO jlmirror_g10_itsm_app_invoker;\nEND;\n$$;"
    ))
    require_rejected(GOOD_SQL.replace(
      "  LOOP\n    IF v_role.rolcanlogin OR v_role.rolsuper OR v_role.rolcreatedb OR v_role.rolcreaterole\n       OR v_role.rolinherit OR v_role.rolreplication OR v_role.rolbypassrls THEN\n      RAISE EXCEPTION 'g10.role_unsafe:%',v_role.rolname;\n    END IF;\n    IF EXISTS (",
      "  LOOP\n    IF v_role.rolcanlogin THEN\n      RAISE EXCEPTION 'g10.role_unsafe:%',v_role.rolname;\n    END IF;\n    IF EXISTS ("
    ))
def falsify_g10_incident_create_replay_equivalence():
    weakened=GOOD_SQL.replace(
      "    IF v_existing.content_hash<>v_hash THEN RAISE EXCEPTION 'g10.incident_equivalence_conflict'; END IF;\n",
      ""
    )
    assert weakened != GOOD_SQL, "incident replay equivalence mutation was a no-op"
    require_rejected(weakened)

def falsify_g10_concurrent_incident_create_serialization():
    require_rejected(GOOD_SQL.replace(
      "WHERE tenant_id=p_tenant_id AND logical_action_id=p_logical_action_id;",
      "WHERE FALSE AND logical_action_id=p_logical_action_id;",
      1
    ))
    require_rejected(GOOD_SQL.replace(
      """  SELECT * INTO v_existing FROM itsm.incident
   WHERE tenant_id=p_tenant_id AND logical_action_id=p_logical_action_id;""",
      """  IF FALSE THEN
    SELECT * INTO v_existing FROM itsm.incident
     WHERE tenant_id=p_tenant_id AND logical_action_id=p_logical_action_id;
  END IF;"""
    ))
    require_rejected(GOOD_SQL.replace(
      "BEGIN\n  PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10));",
      "BEGIN\n  RAISE EXCEPTION 'stop-before-lock';\n  PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10));"
    ))
    require_rejected(GOOD_SQL.replace(
      "  PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10));",
      "  /* outer /* inner */ PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10)); */"
    ))
    require_rejected(GOOD_SQL.replace(
      "  PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10));",
      "  PERFORM 'pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10))';"
    ))
    require_rejected(GOOD_SQL.replace(
      "  PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10));",
      "  -- PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10));"
    ))
    require_rejected(GOOD_SQL.replace(
      "  PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10));",
      "  PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_logical_action_id||random()::text,10));"
    ))
    require_rejected(GOOD_SQL.replace(
      """  PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10));
  SELECT * INTO v_existing FROM itsm.incident
   WHERE tenant_id=p_tenant_id AND logical_action_id=p_logical_action_id;""",
      """  SELECT * INTO v_existing FROM itsm.incident
   WHERE tenant_id=p_tenant_id AND logical_action_id=p_logical_action_id;
  PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10));"""
    ))
    require_rejected(GOOD_SQL.replace(
      """  SELECT * INTO v_existing FROM itsm.incident
   WHERE tenant_id=p_tenant_id AND logical_action_id=p_logical_action_id;""",
      """  PERFORM $q$SELECT * INTO v_existing FROM itsm.incident
   WHERE tenant_id=p_tenant_id AND logical_action_id=p_logical_action_id$q$;"""
    ))
    require_rejected(GOOD_SQL.replace(
      "  PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10));",
      "  IF FALSE THEN\n    PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10));\n  END IF;"
    ))
    require_rejected(GOOD_SQL.replace(
      "  PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10));",
      "  IF p_logical_action_id IS NULL THEN\n    PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10));\n  END IF;"
    ))
    require_rejected(GOOD_SQL.replace(
      "  PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10));",
      "  WHILE FALSE LOOP\n    PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10));\n  END LOOP;"
    ))
    require_rejected(GOOD_SQL.replace(
      "  PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10));",
      "  CASE WHEN FALSE THEN\n    PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10));\n  ELSE NULL;\n  END CASE;"
    ))
    require_rejected(GOOD_SQL.replace(
      "BEGIN\n  PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10));",
      "BEGIN\n  BEGIN\n    NULL;\n  EXCEPTION WHEN OTHERS THEN\n    PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10));\n  END;"
    ))
    require_rejected(GOOD_SQL.replace(
      "BEGIN\n  PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10));",
      "BEGIN\n  BEGIN\n    NULL;\n  EXCEPTION WHEN OTHERS THEN\n    BEGIN\n      PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10));\n    END;\n  END;"
    ))

def falsify_g10_transition_replay_equivalence():
    require_rejected(GOOD_SQL.replace(
      "BEGIN\n  SELECT * INTO v_existing_transition",
      "BEGIN\n  RAISE EXCEPTION 'stop-before-replay';\n  SELECT * INTO v_existing_transition"
    ))
    require_rejected(GOOD_SQL.replace(
      """  SELECT * INTO v_existing_transition
  FROM itsm.incident_transition
  WHERE tenant_id=p_tenant_id AND incident_id=p_incident_id
    AND logical_action_id=p_logical_action_id;
  IF FOUND THEN
    IF v_existing_transition.to_state IS DISTINCT FROM p_target_state THEN
      RAISE EXCEPTION 'g10.transition_equivalence_conflict';
    END IF;
    RETURN jsonb_build_object('incident_id',p_incident_id,'duplicate',TRUE);
  END IF;""",
      """  PERFORM $q$  SELECT * INTO v_existing_transition
  FROM itsm.incident_transition
  WHERE tenant_id=p_tenant_id AND incident_id=p_incident_id
    AND logical_action_id=p_logical_action_id;
  IF FOUND THEN
    IF v_existing_transition.to_state IS DISTINCT FROM p_target_state THEN
      RAISE EXCEPTION 'g10.transition_equivalence_conflict';
    END IF;
    RETURN jsonb_build_object('incident_id',p_incident_id,'duplicate',TRUE);
  END IF;$q$;
  RETURN '{}'::jsonb;"""
    ))
    require_rejected(GOOD_SQL.replace(
      """  SELECT * INTO v_existing_transition
  FROM itsm.incident_transition
  WHERE tenant_id=p_tenant_id AND incident_id=p_incident_id
    AND logical_action_id=p_logical_action_id;
  IF FOUND THEN
    IF v_existing_transition.to_state IS DISTINCT FROM p_target_state THEN
      RAISE EXCEPTION 'g10.transition_equivalence_conflict';
    END IF;
    RETURN jsonb_build_object('incident_id',p_incident_id,'duplicate',TRUE);
  END IF;""",
      """  IF FALSE THEN
    SELECT * INTO v_existing_transition
    FROM itsm.incident_transition
    WHERE tenant_id=p_tenant_id AND incident_id=p_incident_id
      AND logical_action_id=p_logical_action_id;
    IF FOUND THEN
      IF v_existing_transition.to_state IS DISTINCT FROM p_target_state THEN
        RAISE EXCEPTION 'g10.transition_equivalence_conflict';
      END IF;
      RETURN jsonb_build_object('incident_id',p_incident_id,'duplicate',TRUE);
    END IF;
  END IF;"""
    ))
    require_rejected(GOOD_SQL.replace(
      """  SELECT * INTO v_existing_transition
  FROM itsm.incident_transition
  WHERE tenant_id=p_tenant_id AND incident_id=p_incident_id
    AND logical_action_id=p_logical_action_id;
""",
      ""
    ))
    require_rejected(GOOD_SQL.replace(
      """  IF FOUND THEN
    IF v_existing_transition.to_state IS DISTINCT FROM p_target_state THEN
      RAISE EXCEPTION 'g10.transition_equivalence_conflict';
    END IF;
    RETURN jsonb_build_object('incident_id',p_incident_id,'duplicate',TRUE);
  END IF;""",
      """  IF FOUND THEN
    RETURN jsonb_build_object('incident_id',p_incident_id,'duplicate',TRUE);
    IF v_existing_transition.to_state IS DISTINCT FROM p_target_state THEN
      RAISE EXCEPTION 'g10.transition_equivalence_conflict';
    END IF;
  END IF;"""
    ))
    require_rejected(GOOD_SQL.replace(
      """  IF FOUND THEN
    IF v_existing_transition.to_state IS DISTINCT FROM p_target_state THEN
      RAISE EXCEPTION 'g10.transition_equivalence_conflict';
    END IF;
    RETURN jsonb_build_object('incident_id',p_incident_id,'duplicate',TRUE);
  END IF;""",
      """  IF FALSE THEN
    IF FOUND THEN
      IF v_existing_transition.to_state IS DISTINCT FROM p_target_state THEN
        RAISE EXCEPTION 'g10.transition_equivalence_conflict';
      END IF;
      RETURN jsonb_build_object('incident_id',p_incident_id,'duplicate',TRUE);
    END IF;
  END IF;"""
    ))

    require_rejected(GOOD_SQL.replace(
      """  SELECT * INTO v_existing_transition
  FROM itsm.incident_transition
  WHERE tenant_id=p_tenant_id AND incident_id=p_incident_id
    AND logical_action_id=p_logical_action_id;
  IF FOUND THEN
    IF v_existing_transition.to_state IS DISTINCT FROM p_target_state THEN
      RAISE EXCEPTION 'g10.transition_equivalence_conflict';
    END IF;
    RETURN jsonb_build_object('incident_id',p_incident_id,'duplicate',TRUE);
  END IF;""",
      """  WHILE FALSE LOOP
    SELECT * INTO v_existing_transition
    FROM itsm.incident_transition
    WHERE tenant_id=p_tenant_id AND incident_id=p_incident_id
      AND logical_action_id=p_logical_action_id;
    IF FOUND THEN
      IF v_existing_transition.to_state IS DISTINCT FROM p_target_state THEN
        RAISE EXCEPTION 'g10.transition_equivalence_conflict';
      END IF;
      RETURN jsonb_build_object('incident_id',p_incident_id,'duplicate',TRUE);
    END IF;
  END LOOP;"""
    ))

    require_rejected(GOOD_SQL.replace(
      """  SELECT * INTO v_existing_transition
  FROM itsm.incident_transition
  WHERE tenant_id=p_tenant_id AND incident_id=p_incident_id
    AND logical_action_id=p_logical_action_id;
  IF FOUND THEN
    IF v_existing_transition.to_state IS DISTINCT FROM p_target_state THEN
      RAISE EXCEPTION 'g10.transition_equivalence_conflict';
    END IF;
    RETURN jsonb_build_object('incident_id',p_incident_id,'duplicate',TRUE);
  END IF;""",
      """  CASE WHEN FALSE THEN
    SELECT * INTO v_existing_transition
    FROM itsm.incident_transition
    WHERE tenant_id=p_tenant_id AND incident_id=p_incident_id
      AND logical_action_id=p_logical_action_id;
    IF FOUND THEN
      IF v_existing_transition.to_state IS DISTINCT FROM p_target_state THEN
        RAISE EXCEPTION 'g10.transition_equivalence_conflict';
      END IF;
      RETURN jsonb_build_object('incident_id',p_incident_id,'duplicate',TRUE);
    END IF;
  ELSE NULL;
  END CASE;"""
    ))

    transition_block="""CREATE OR REPLACE FUNCTION itsm.g10_transition_incident(
 p_tenant_id text,p_incident_id text,p_target_state text,p_actor_principal_id text,
 p_logical_action_id text,p_authority_snapshot jsonb
) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE v_existing_transition record;
BEGIN
  SELECT * INTO v_existing_transition
  FROM itsm.incident_transition
  WHERE tenant_id=p_tenant_id AND incident_id=p_incident_id
    AND logical_action_id=p_logical_action_id;
  IF FOUND THEN
    IF v_existing_transition.to_state IS DISTINCT FROM p_target_state THEN
      RAISE EXCEPTION 'g10.transition_equivalence_conflict';
    END IF;
    RETURN jsonb_build_object('incident_id',p_incident_id,'duplicate',TRUE);
  END IF;
  RETURN '{}'::jsonb;
END;
$$;"""
    require_rejected(GOOD_SQL.replace(
      transition_block,
      transition_block.replace("AS $$","AS $fn$").replace("$$;","$fn$;").replace(
        """  SELECT * INTO v_existing_transition
  FROM itsm.incident_transition
  WHERE tenant_id=p_tenant_id AND incident_id=p_incident_id
    AND logical_action_id=p_logical_action_id;
  IF FOUND THEN
    IF v_existing_transition.to_state IS DISTINCT FROM p_target_state THEN
      RAISE EXCEPTION 'g10.transition_equivalence_conflict';
    END IF;
    RETURN jsonb_build_object('incident_id',p_incident_id,'duplicate',TRUE);
  END IF;""",
        """  /* SELECT * INTO v_existing_transition
  FROM itsm.incident_transition
  WHERE tenant_id=p_tenant_id AND incident_id=p_incident_id
    AND logical_action_id=p_logical_action_id;
  IF FOUND THEN
    IF v_existing_transition.to_state IS DISTINCT FROM p_target_state THEN
      RAISE EXCEPTION 'g10.transition_equivalence_conflict';
    END IF;
    RETURN jsonb_build_object('incident_id',p_incident_id,'duplicate',TRUE);
  END IF; */"""
      )
    ))

def falsify_g10_duplicate_validated_function_definition():
    canonical_worker="""CREATE OR REPLACE FUNCTION itsm.g10_next_sync_candidate(p_tenant_id text)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE v_result jsonb;
BEGIN
  SELECT to_jsonb(x) INTO v_result FROM (
    SELECT o.sync_outbox_id,o.incident_id
    FROM itsm.incident_sync_outbox o
    WHERE o.tenant_id=p_tenant_id
      AND (
        (o.sync_state='pending' AND o.available_at<=transaction_timestamp())
        OR
        (o.sync_state='dispatching' AND o.claim_expires_at<=transaction_timestamp())
      )
    LIMIT 1
  ) x;
  RETURN v_result;
END;
$$;"""

    require_rejected(GOOD_SQL+"\nCREATE OR REPLACE FUNCTION \"itsm\".\"g10_next_sync_candidate\"(p_tenant_id text) RETURNS jsonb LANGUAGE plpgsql AS $ BEGIN RETURN '{}'::jsonb; END; $;\n")
    require_rejected(GOOD_SQL.replace(
      "CREATE OR REPLACE FUNCTION itsm.g10_get_incident(",
      "CREATE OR REPLACE FUNCTION \"ITSM\".g10_get_incident("
    ).replace(
      "CREATE OR REPLACE FUNCTION itsm.g10_next_sync_candidate(",
      "CREATE OR REPLACE FUNCTION \"ITSM\".g10_next_sync_candidate("
    ).replace(
      "CREATE OR REPLACE FUNCTION itsm.g10_create_incident(",
      "CREATE OR REPLACE FUNCTION \"ITSM\".g10_create_incident("
    ).replace(
      "CREATE OR REPLACE FUNCTION itsm.g10_transition_incident(",
      "CREATE OR REPLACE FUNCTION \"ITSM\".g10_transition_incident("
    ))
    require_rejected(GOOD_SQL.replace(
      "CREATE OR REPLACE FUNCTION itsm.g10_get_incident(",
      "CREATE OR REPLACE FUNCTION \"ITSM\".\"g10_get_incident\"("
    ).replace(
      "CREATE OR REPLACE FUNCTION itsm.g10_next_sync_candidate(",
      "CREATE OR REPLACE FUNCTION \"ITSM\".\"g10_next_sync_candidate\"("
    ).replace(
      "CREATE OR REPLACE FUNCTION itsm.g10_create_incident(",
      "CREATE OR REPLACE FUNCTION \"ITSM\".\"g10_create_incident\"("
    ).replace(
      "CREATE OR REPLACE FUNCTION itsm.g10_transition_incident(",
      "CREATE OR REPLACE FUNCTION \"ITSM\".\"g10_transition_incident\"("
    ))

    require_rejected(GOOD_SQL+"""\nDO $$
BEGIN
  EXECUTE 'DROP FUN' || 'CTION itsm.g10_next_sync_candidate(text)';
  EXECUTE 'CREATE FUN' || 'CTION itsm.g10_next_sync_candidate(p_tenant_id text) RETURNS jsonb LANGUAGE plpgsql AS $q$ BEGIN RETURN ''{}''::jsonb; END; $q$';
END;
$$;
""")

    require_rejected(GOOD_SQL.replace(
      canonical_worker,
      """CREATE OR REPLACE FUNCTION itsm.g10_next_sync_candidate(p_tenant_id text)
RETURNS jsonb LANGUAGE plpgsql AS $$
BEGIN
  RETURN '{}'::jsonb;
END;
$$;
SET search_path=itsm;
CREATE FUNCTION decoy_worker(p_tenant_id text)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE v_result jsonb;
BEGIN
  SELECT to_jsonb(x) INTO v_result FROM (
    SELECT o.sync_outbox_id,o.incident_id
    FROM itsm.incident_sync_outbox o
    WHERE o.tenant_id=p_tenant_id
      AND (
        (o.sync_state='pending' AND o.available_at<=transaction_timestamp())
        OR
        (o.sync_state='dispatching' AND o.claim_expires_at<=transaction_timestamp())
      )
    LIMIT 1
  ) x;
  RETURN v_result;
END;
$$;"""
    ))

    require_rejected(GOOD_SQL.replace(
      canonical_worker,
      """CREATE OR REPLACE FUNCTION itsm.g10_next_sync_candidate(p_tenant_id text)
RETURNS jsonb LANGUAGE plpgsql AS $$
BEGIN
  RETURN '{}'::jsonb;
END;
$$;

create or replace function itsm.decoy_worker(p_tenant_id text)
returns jsonb language plpgsql as $$
DECLARE v_result jsonb;
BEGIN
  SELECT to_jsonb(x) INTO v_result FROM (
    SELECT o.sync_outbox_id,o.incident_id
    FROM itsm.incident_sync_outbox o
    WHERE o.tenant_id=p_tenant_id
      AND (
        (o.sync_state='pending' AND o.available_at<=transaction_timestamp())
        OR
        (o.sync_state='dispatching' AND o.claim_expires_at<=transaction_timestamp())
      )
    LIMIT 1
  ) x;
  RETURN v_result;
END;
$$;"""
    ))

    require_rejected(GOOD_SQL.replace(
      "COMMIT;\n",
      """DROP FUNCTION itsm.g10_next_sync_candidate(text);
CREATE FUNCTION itsm.g10_next_sync_candidate(p_tenant_id text)
RETURNS jsonb LANGUAGE plpgsql AS $$
BEGIN
  RETURN '{}'::jsonb;
END;
$$;
COMMIT;
"""
    ))

    require_rejected(GOOD_SQL.replace(
      "COMMIT;\n",
      """CREATE FUNCTION itsm.decoy_worker(p_tenant_id text)
RETURNS jsonb LANGUAGE plpgsql AS $$
BEGIN
  RETURN '{}'::jsonb;
END;
$$;
ALTER FUNCTION itsm.g10_next_sync_candidate(text) RENAME TO old_g10_next_sync_candidate;
ALTER FUNCTION itsm.decoy_worker(text) RENAME TO g10_next_sync_candidate;
COMMIT;
"""
    ))

    require_rejected(GOOD_SQL.replace(
      "COMMIT;\n",
      """CREATE FUNCTION itsm.decoy_worker(p_tenant_id text)
RETURNS jsonb LANGUAGE plpgsql AS $$
BEGIN
  RETURN '{}'::jsonb;
END;
$$;
ALTER ROUTINE itsm.g10_next_sync_candidate(text) RENAME TO old_g10_next_sync_candidate;
ALTER ROUTINE itsm.decoy_worker(text) RENAME TO g10_next_sync_candidate;
COMMIT;
"""
    ))

    require_rejected(GOOD_SQL.replace(
      "COMMIT;\n",
      """CREATE OR REPLACE FUNCTION itsm.g10_next_sync_candidate(p_tenant_id text)
RETURNS jsonb LANGUAGE plpgsql AS $$
BEGIN
  RETURN '{}'::jsonb;
END;
$$;
COMMIT;
"""
    ))

    require_rejected(GOOD_SQL+"\nSET search_path=itsm;\nDROP FUNCTION g10_next_sync_candidate(text);\nCREATE FUNCTION g10_next_sync_candidate(p_tenant_id text) RETURNS jsonb LANGUAGE plpgsql AS $$ BEGIN RETURN '{}'::jsonb; END; $$;\n")
    require_rejected(GOOD_SQL+"\nCREATE SCHEMA decoy;\nALTER FUNCTION itsm.g10_next_sync_candidate(text) SET SCHEMA decoy;\n")
    require_rejected(GOOD_SQL+"\nCREATE SCHEMA decoy;\nALTER ROUTINE itsm.g10_next_sync_candidate(text) SET SCHEMA decoy;\n")

def falsify_g10_hidden_relation():
    require_rejected(GOOD_SQL+"\nCREATE TABLE itsm.hidden(id text);\n")

def falsify_g10_cross_domain_mutation():
    require_rejected(GOOD_SQL+"\nSET standard_conforming_strings = off;\nSELECT 'abc\\'--xyz'; INSERT INTO alerting.alert(tenant_id) VALUES ('t');\n")
    require_rejected(GOOD_SQL+"\nSET standard_conforming_strings = 0;\nSELECT 'abc\\'--xyz'; INSERT INTO alerting.alert(tenant_id) VALUES ('t');\n")
    require_rejected(GOOD_SQL+"\nSET standard_conforming_strings = NO;\nSELECT 'abc\\'--xyz'; INSERT INTO alerting.alert(tenant_id) VALUES ('t');\n")
    require_rejected(GOOD_SQL+"\nSELECT set_config('standard_conforming_strings','off',false);\nSELECT 'abc\\'--xyz'; INSERT INTO alerting.alert(tenant_id) VALUES ('t');\n")
    require_rejected(GOOD_SQL+"\nSELECT pg_catalog.set_config('standard_conforming_strings','false',false);\nSELECT 'abc\\'--xyz'; INSERT INTO alerting.alert(tenant_id) VALUES ('t');\n")
    require_rejected(GOOD_SQL+"\nSELECT set_config($x$standard_conforming_strings$x$,$x$off$x$,false);\nSELECT 'abc\\'--xyz'; INSERT INTO alerting.alert(tenant_id) VALUES ('t');\n")
    require_rejected(GOOD_SQL+"\nSELECT set_config('standard_' || 'conforming_strings','off',false);\nSELECT 'abc\\'--xyz'; INSERT INTO alerting.alert(tenant_id) VALUES ('t');\n")
    require_rejected(GOOD_SQL+"\nSELECT set_config('application_name','g10',false);\n")
    require_rejected(GOOD_SQL+"\nSELECT pg_catalog.\"set_config\"('search_path','alerting',false);\nDELETE FROM alert;\n")
    require_rejected(GOOD_SQL+"\nSET search_path TO alerting, public;\nINSERT INTO alert(tenant_id) VALUES ('t');\n")
    require_rejected(GOOD_SQL+"\nSET SCHEMA 'alerting';\nDELETE FROM alert;\n")
    require_rejected(GOOD_SQL+"\nSELECT $$--$$; INSERT INTO alerting.alert(tenant_id) VALUES ('t');\n")
    require_rejected(GOOD_SQL+"\nUPDATE alerting.alert SET lifecycle_state='resolved';\n")
    require_rejected(GOOD_SQL+"\nDELETE FROM human_operations.some_table;\n")
    require_rejected(GOOD_SQL+"\nMERGE INTO notification.delivery d USING notification.delivery s ON FALSE WHEN NOT MATCHED THEN INSERT DEFAULT VALUES;\n")
    require_rejected(GOOD_SQL+"\nUPDATE ONLY alerting.alert SET lifecycle_state='resolved';\n")
    require_rejected(GOOD_SQL+"\nDELETE FROM ONLY alerting.alert;\n")
    require_rejected(GOOD_SQL+"\nMERGE INTO ONLY alerting.alert a USING alerting.alert b ON FALSE WHEN NOT MATCHED THEN INSERT DEFAULT VALUES;\n")
    require_rejected(GOOD_SQL+"\nCOPY alerting.alert(tenant_id) FROM STDIN;\n")
    require_rejected(GOOD_SQL+"\nCOPY \"notification\".\"delivery\" FROM STDIN;\n")
    require_rejected(GOOD_SQL+"\nTRUNCATE alerting.alert;\n")
    require_rejected(GOOD_SQL+"\nTRUNCATE TABLE itsm.incident_comment, alerting.alert CASCADE;\n")
    require_rejected(GOOD_SQL+"\nTRUNCATE TABLE itsm.incident_comment, ONLY \"notification\".\"delivery\" RESTART IDENTITY;\n")
    require_rejected(GOOD_SQL+"\nDROP TABLE alerting.alert;\n")
    require_rejected(GOOD_SQL+"\nALTER TABLE alerting.alert ADD COLUMN attacker text;\n")
    require_rejected(GOOD_SQL+"\nALTER TABLE ONLY alerting.alert DISABLE TRIGGER ALL;\n")
    require_rejected(GOOD_SQL+"\nALTER TABLE IF EXISTS ONLY alerting.alert DISABLE TRIGGER ALL;\n")
    require_rejected(GOOD_SQL+"\nALTER TABLE IF EXISTS ONLY \"notification\".\"delivery\" ENABLE TRIGGER ALL;\n")
    require_rejected(GOOD_SQL+"\nALTER TABLE ONLY \"notification\".\"delivery\" ENABLE TRIGGER ALL;\n")
    require_rejected(GOOD_SQL+"\nINSERT INTO \"alerting\".\"alert\"(tenant_id) VALUES ('t');\n")
    require_rejected(GOOD_SQL+"\nTRUNCATE TABLE \"notification\".\"delivery\";\n")
    require_rejected(GOOD_SQL+"\nDROP SCHEMA monitoring;\n")
    require_rejected(GOOD_SQL+"\nCREATE INDEX evil ON alerting.alert(tenant_id);\n")
    require_rejected(GOOD_SQL+"\nCREATE UNIQUE INDEX evil_unique ON ONLY \"notification\".\"delivery\"(tenant_id);\n")
    require_rejected(GOOD_SQL+"\nCREATE TRIGGER g10_block_alert BEFORE UPDATE OR DELETE ON alerting.alert FOR EACH ROW EXECUTE FUNCTION itsm.g10_reject_immutable_mutation();\n")
    require_rejected(GOOD_SQL+"\nCREATE CONSTRAINT TRIGGER g10_block_notify AFTER INSERT ON \"notification\".\"delivery\" DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION itsm.g10_reject_immutable_mutation();\n")
    require_rejected(GOOD_SQL+"\nDROP TRIGGER g10_existing ON human_operations.some_table;\n")
    require_rejected(GOOD_SQL+"\nCREATE RULE g10_rule AS ON UPDATE TO monitoring.resource DO INSTEAD NOTHING;\n")
    require_rejected(GOOD_SQL+"\nCREATE OR REPLACE RULE evil AS ON UPDATE TO alerting.alert DO INSTEAD NOTHING;\n")
    require_rejected(GOOD_SQL+"\nDROP RULE g10_rule ON monitoring.resource;\n")
    require_rejected(GOOD_SQL+"\nCREATE POLICY g10_policy ON alerting.alert USING (TRUE);\n")
    require_rejected(GOOD_SQL+"\nALTER POLICY g10_policy ON alerting.alert USING (FALSE);\n")
    require_rejected(GOOD_SQL+"\nDROP POLICY g10_policy ON alerting.alert;\n")
    require_rejected(GOOD_SQL+"\nGRANT INSERT, UPDATE, DELETE ON alerting.alert TO jlmirror_g10_itsm_app_invoker;\n")
    require_rejected(GOOD_SQL+"\nGRANT SELECT, UPDATE(lifecycle_state) ON TABLE \"alerting\".\"alert\" TO jlmirror_g10_itsm_worker_invoker;\n")
    require_rejected(GOOD_SQL+"\nGRANT ALL PRIVILEGES ON notification.delivery TO jlmirror_g10_itsm_app_invoker;\n")
    require_rejected(GOOD_SQL+"\nGRANT DELETE ON ALL TABLES IN SCHEMA human_operations TO jlmirror_g10_itsm_worker_invoker;\n")
    require_rejected(GOOD_SQL+"\nGRANT CREATE ON SCHEMA alerting TO jlmirror_g10_itsm_app_invoker;\n")
    require_rejected(GOOD_SQL+"\nGRANT ALL PRIVILEGES ON SCHEMA notification TO jlmirror_g10_itsm_worker_invoker;\n")
    require_rejected(GOOD_SQL+"\nDO $ BEGIN PERFORM '--'; INSERT INTO alerting.alert(tenant_id,alert_id,lifecycle_state) VALUES ('t','a','active'); END; $;\n")
    require_rejected(GOOD_SQL+"\nDO $ BEGIN PERFORM $q$--$q$; INSERT INTO alerting.alert(tenant_id,alert_id,lifecycle_state) VALUES ('t','a','active'); END; $;\n")
    require_rejected(GOOD_SQL+"\nDO LANGUAGE plpgsql $ BEGIN DELETE FROM alerting.alert; END $;\n")
    require_rejected(GOOD_SQL+"\nDO LANGUAGE plpgsql $x$ BEGIN EXECUTE 'DELETE FROM alerting.alert'; END $x$;\n")
    require_rejected(GOOD_SQL+"\nSELECT E'abc\\'--xyz'; INSERT INTO alerting.alert(tenant_id) VALUES ('t');\n")

def falsify_g10_forbidden_vendor_path():
    case({"apps/g10-itsm/jira_adapter.py":"x=1\n"},False)

def main():
 case({"apps/g10-itsm/model.py":"kind='incident'\nstate='open'\n"},True)
 canonical_sql=(Path(__file__).resolve().parents[2]/"sql/itsm/001_incident.sql").read_text(encoding="utf-8")
 case({"sql/itsm/001_incident.sql":canonical_sql},True)
 falsify_g10_alert_opened_at_projection()
 falsify_g10_expired_sync_discovery()
 falsify_g10_privileged_role_membership_fence()
 falsify_g10_incident_create_replay_equivalence()
 falsify_g10_concurrent_incident_create_serialization()
 falsify_g10_transition_replay_equivalence()
 falsify_g10_duplicate_validated_function_definition()
 falsify_g10_hidden_relation()
 falsify_g10_cross_domain_mutation()
 falsify_g10_forbidden_vendor_path()
 print("g10_scope_falsification=PASS review_findings=locked vendor=blocked hidden_relation=blocked cross_domain_mutation=blocked")
 return 0

if __name__=="__main__":main()
