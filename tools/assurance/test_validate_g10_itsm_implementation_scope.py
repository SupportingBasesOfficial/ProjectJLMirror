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
  SELECT * INTO v_role FROM pg_roles LIMIT 1;
  PERFORM 1 FROM pg_auth_members WHERE roleid=v_role.oid OR member=v_role.oid;
END;
$$;

CREATE OR REPLACE FUNCTION itsm.g10_create_incident(
 p_tenant_id text,p_alert_id text,p_title text,p_description text,
 p_actor_principal_id text,p_logical_action_id text,p_authority_snapshot jsonb
) RETURNS jsonb LANGUAGE plpgsql AS $$
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||p_logical_action_id,10));
  RETURN '{}'::jsonb;
END;
$$;

CREATE OR REPLACE FUNCTION itsm.g10_transition_incident(
 p_tenant_id text,p_incident_id text,p_target_state text,p_actor_principal_id text,
 p_logical_action_id text,p_authority_snapshot jsonb
) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE v_existing_transition record;
BEGIN
  IF v_existing_transition.to_state IS DISTINCT FROM p_target_state THEN
    RAISE EXCEPTION 'g10.transition_equivalence_conflict';
  END IF;
  RETURN '{}'::jsonb;
END;
$$;

CREATE OR REPLACE FUNCTION itsm.g10_next_sync_candidate(p_tenant_id text)
RETURNS jsonb LANGUAGE plpgsql AS $$
BEGIN
  PERFORM 1 FROM itsm.incident_sync_outbox
   WHERE sync_state='dispatching' AND claim_expires_at<=transaction_timestamp();
  RETURN '{}'::jsonb;
END;
$$;

CREATE OR REPLACE FUNCTION itsm.g10_get_incident(p_tenant_id text,p_incident_id text)
RETURNS jsonb LANGUAGE plpgsql AS $$
BEGIN
  PERFORM opened_at FROM alerting.alert;
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
    require_rejected(GOOD_SQL.replace("PERFORM opened_at FROM alerting.alert;","PERFORM created_at FROM alerting.alert;"))

def falsify_g10_expired_sync_discovery():
    require_rejected(GOOD_SQL.replace("sync_state='dispatching' AND claim_expires_at<=transaction_timestamp()","sync_state='pending'"))

def falsify_g10_privileged_role_membership_fence():
    require_rejected(GOOD_SQL.replace("PERFORM 1 FROM pg_auth_members WHERE roleid=v_role.oid OR member=v_role.oid;","PERFORM 1;"))

def falsify_g10_concurrent_incident_create_serialization():
    require_rejected(GOOD_SQL.replace("PERFORM pg_advisory_xact_lock(hashtextextended(p_tenant_id||p_logical_action_id,10));","PERFORM 1;"))

def falsify_g10_transition_replay_equivalence():
    require_rejected(GOOD_SQL.replace("RAISE EXCEPTION 'g10.transition_equivalence_conflict';","RETURN '{}'::jsonb;"))

def falsify_g10_hidden_relation():
    require_rejected(GOOD_SQL+"\nCREATE TABLE itsm.hidden(id text);\n")

def falsify_g10_cross_domain_mutation():
    require_rejected(GOOD_SQL+"\nUPDATE alerting.alert SET lifecycle_state='resolved';\n")

def falsify_g10_forbidden_vendor_path():
    case({"apps/g10-itsm/jira_adapter.py":"x=1\n"},False)

def main():
 case({"apps/g10-itsm/model.py":"kind='incident'\nstate='open'\n"},True)
 falsify_g10_alert_opened_at_projection()
 falsify_g10_expired_sync_discovery()
 falsify_g10_privileged_role_membership_fence()
 falsify_g10_concurrent_incident_create_serialization()
 falsify_g10_transition_replay_equivalence()
 falsify_g10_hidden_relation()
 falsify_g10_cross_domain_mutation()
 falsify_g10_forbidden_vendor_path()
 print("g10_scope_falsification=PASS review_findings=locked vendor=blocked hidden_relation=blocked cross_domain_mutation=blocked")
 return 0

if __name__=="__main__":main()
