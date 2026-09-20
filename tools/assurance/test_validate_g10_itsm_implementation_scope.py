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

def init():
 td=tempfile.TemporaryDirectory();root=Path(td.name);subprocess.run(["git","init","-q",str(root)],check=True)
 subprocess.run(["git","-C",str(root),"config","user.email","x@example.invalid"],check=True);subprocess.run(["git","-C",str(root),"config","user.name","G10 test"],check=True)
 p=root/"implementation/g10-itsm-authorization/AUTHORIZATION_MANIFEST.json";p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps({"implementation_authority_after_merge":"granted_for_exact_g10_itsm_incident_only","implementation_path_policy":POLICY}))
 subprocess.run(["git","-C",str(root),"add","."],check=True);subprocess.run(["git","-C",str(root),"commit","-qm","base"],check=True)
 return td,root,subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()

def sql():
 return """BEGIN;
DO $$
DECLARE v_role RECORD;
BEGIN
  FOR v_role IN SELECT * FROM pg_roles LOOP
    IF EXISTS (
      SELECT 1 FROM pg_auth_members
      WHERE roleid=v_role.oid OR member=v_role.oid
    ) THEN
      RAISE EXCEPTION 'g10.role_unsafe_membership';
    END IF;
  END LOOP;
END;
$$;
CREATE SCHEMA IF NOT EXISTS itsm;
CREATE TABLE itsm.incident(tenant_id text,incident_id text,alert_id text);
CREATE TABLE itsm.incident_transition(tenant_id text,incident_transition_id text,incident_id text);
CREATE TABLE itsm.incident_assignment(tenant_id text,incident_assignment_id text,incident_id text);
CREATE TABLE itsm.incident_comment(tenant_id text,incident_comment_id text,incident_id text);
CREATE TABLE itsm.incident_provider_link(tenant_id text,incident_id text,provider_link_id text);
CREATE TABLE itsm.incident_sync_outbox(
  tenant_id text,incident_id text,sync_outbox_id text,sync_identity text,
  sync_state text,claim_expires_at timestamptz,available_at timestamptz
);

CREATE OR REPLACE FUNCTION itsm.g10_create_incident(
  p_tenant_id text,p_alert_id text,p_title text,p_description text,
  p_actor_principal_id text,p_logical_action_id text,p_authority_snapshot jsonb
) RETURNS jsonb LANGUAGE plpgsql AS $$
BEGIN
  PERFORM pg_advisory_xact_lock(
    hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10)
  );
  RETURN '{}'::jsonb;
END;
$$;

CREATE OR REPLACE FUNCTION itsm.g10_transition_incident(
  p_tenant_id text,p_incident_id text,p_target_state text,
  p_actor_principal_id text,p_logical_action_id text,p_authority_snapshot jsonb
) RETURNS jsonb LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'g10.transition_equivalence_conflict';
END;
$$;

CREATE OR REPLACE FUNCTION itsm.g10_next_sync_candidate(p_tenant_id text)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE v_result jsonb;
BEGIN
  SELECT '{}'::jsonb INTO v_result
  FROM itsm.incident_sync_outbox o
  WHERE (o.sync_state='pending' AND o.available_at<=transaction_timestamp())
     OR (o.sync_state='dispatching' AND o.claim_expires_at<=transaction_timestamp());
  RETURN v_result;
END;
$$;

CREATE OR REPLACE FUNCTION itsm.g10_get_incident(p_tenant_id text,p_incident_id text)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE v_alert jsonb;
BEGIN
  SELECT to_jsonb(x) INTO v_alert FROM (
    SELECT alert_id,lifecycle_state,opened_at,resolved_at
    FROM alerting.alert
  ) x;
  RETURN v_alert;
END;
$$;
COMMIT;
"""

def wf():
 return json.dumps({"name":"JLMIRROR G10 ITSM Runtime","on":{"pull_request":{},"workflow_dispatch":{}},"permissions":{},"jobs":{"g10-runtime":{"runs-on":"ubuntu-24.04","steps":[{"uses":"actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"},{"uses":"actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"},{"uses":"actions/setup-node@249970729cb0ef3589644e2896645e5dc5ba9c38"},{"run":"python tools/g10/run_itsm_runtime.py"}]}}})

def case(files,ok):
 td,root,base=init()
 try:
  for rel,body in files.items():
   p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(body)
  claim=root/"implementation/g10-itsm/IMPLEMENTATION_CLAIM.json";claim.parent.mkdir(parents=True,exist_ok=True);claim.write_text(json.dumps({"authorization_id":"g10.itsm-incident@1","slice_id":"g10.itsm-incident@1"}))
  sp=root/"sql/itsm/001_incident.sql";sp.parent.mkdir(parents=True,exist_ok=True)
  if not sp.exists():sp.write_text(sql())
  wp=root/".github/workflows/g10-itsm-runtime.yml";wp.parent.mkdir(parents=True,exist_ok=True)
  if not wp.exists():wp.write_text(wf())
  subprocess.run(["git","-C",str(root),"add","."],check=True);subprocess.run(["git","-C",str(root),"commit","-qm","candidate"],check=True)
  head=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
  cp=subprocess.run(["python3",str(VALIDATOR),"--repo-root",str(root),"--base",base,"--head",head,"--head-ref","impl/g10-itsm-test","--labels-json",'["jlmirror-slice:g10-itsm"]',"--head-repo",REPO,"--base-repo",REPO],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  if (cp.returncode==0)!=ok:raise AssertionError(cp.stdout+"\n"+cp.stderr)
 finally:td.cleanup()

def falsify_incident_alert_timestamp_contract():
 case({"sql/itsm/001_incident.sql":sql().replace("opened_at","created_at",1)},False)

def falsify_expired_sync_discovery_contract():
 case({"sql/itsm/001_incident.sql":sql().replace(
   "OR (o.sync_state='dispatching' AND o.claim_expires_at<=transaction_timestamp())",""
 )},False)

def falsify_privileged_role_membership_guard():
 case({"sql/itsm/001_incident.sql":sql().replace(
   "SELECT 1 FROM pg_auth_members","SELECT 1 FROM pg_roles",1
 )},False)

def falsify_incident_create_serialization():
 case({"sql/itsm/001_incident.sql":sql().replace(
   "  PERFORM pg_advisory_xact_lock(\n    hashtextextended(p_tenant_id||chr(31)||p_logical_action_id,10)\n  );\n",""
 )},False)

def falsify_transition_replay_equivalence():
 case({"sql/itsm/001_incident.sql":sql().replace(
   "g10.transition_equivalence_conflict","g10.transition_duplicate",1
 )},False)

def falsify_sync_retry_idempotency_identity_reuse():
 case({"sql/itsm/001_incident.sql":sql().replace(
   "  sync_state text,claim_expires_at timestamptz,available_at timestamptz\n);",
   "  sync_state text,claim_expires_at timestamptz,available_at timestamptz,\n  UNIQUE (tenant_id,sync_identity)\n);"
 )},False)

def main():
 case({"apps/g10-itsm/model.py":"kind='incident'\nstate='open'\n"},True)
 case({"apps/g10-itsm/change_request.py":"x=1\n"},False)
 case({"apps/g10-itsm/jira_adapter.py":"x=1\n"},False)
 case({"sql/itsm/001_incident.sql":sql()+"\nCREATE TABLE itsm.hidden(id text);\n"},False)
 case({"sql/itsm/001_incident.sql":sql()+"\nUPDATE alerting.alert SET lifecycle_state='resolved';\n"},False)
 falsify_incident_alert_timestamp_contract()
 falsify_expired_sync_discovery_contract()
 falsify_privileged_role_membership_guard()
 falsify_incident_create_serialization()
 falsify_transition_replay_equivalence()
 falsify_sync_retry_idempotency_identity_reuse()
 print("g10_scope_falsification=PASS incident=allowed change_vendor=blocked hidden_relation=blocked cross_domain_mutation=blocked runtime_review_findings=guarded")
 return 0
if __name__=="__main__":raise SystemExit(main())
