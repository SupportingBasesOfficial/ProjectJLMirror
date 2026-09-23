#!/usr/bin/env python3
from __future__ import annotations
import json,subprocess,tempfile
from pathlib import Path
VALIDATOR=Path(__file__).with_name("validate_g9_notification_delivery_implementation_scope.py")
REPO="SupportingBasesOfficial/ProjectJLMirror"
POLICY={
"allowed_prefixes":["apps/g9-notification-delivery/","contracts/g9-notification-delivery/","implementation/g9-notification-delivery/","tests/g9/","tools/g9/"],
"allowed_exact_paths":["sql/notification/001_notification_delivery.sql",".github/workflows/g9-notification-delivery-runtime.yml"],
"semantic_scan_prefixes":["apps/g9-notification-delivery/","contracts/g9-notification-delivery/","implementation/g9-notification-delivery/","tests/g9/","tools/g9/"],
"forbidden_path_tokens":["email","sms","push","teams","slack","approval","budget","quote","itsm","incident","ticket","automation","aiops","provider-write"],
"forbidden_code_markers":["alert_reopen","unacknowledge","approval_state","awaiting_budget_approval","incident_id","ticket_id","provider_write_back","send_email","send_sms","teams_webhook","slack_webhook"],
"implementation_claim_path":"implementation/g9-notification-delivery/IMPLEMENTATION_CLAIM.json",
"implementation_pr_head_prefix":"impl/g9-notification-delivery",
"implementation_pr_required_label":"jlmirror-slice:g9-notification-delivery",
"exact_sql_path":"sql/notification/001_notification_delivery.sql",
"exact_sql_allowed_relations":["notification.notification_intent","notification.notification_attempt","notification.notification_provider_evidence","notification.notification_projection","notification.notification_dispatch_outbox","notification.notification_callback_inbox"],
"runtime_workflow":".github/workflows/g9-notification-delivery-runtime.yml",
"runtime_workflow_name":"JLMIRROR G9 Notification Delivery Runtime",
"runtime_entrypoint":"python tools/g9/run_notification_delivery_runtime.py",
"runtime_allowed_actions":["actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1","actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1","actions/setup-node@249970729cb0ef3589644e2896645e5dc5ba9c38"]}

def init():
 td=tempfile.TemporaryDirectory();root=Path(td.name);subprocess.run(["git","init","-q",str(root)],check=True)
 subprocess.run(["git","-C",str(root),"config","user.email","x@example.invalid"],check=True);subprocess.run(["git","-C",str(root),"config","user.name","G9 test"],check=True)
 p=root/"implementation/g9-notification-delivery-authorization/AUTHORIZATION_MANIFEST.json";p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps({"implementation_authority_after_merge":"granted_for_exact_g9_notification_delivery_only","implementation_path_policy":POLICY}))
 subprocess.run(["git","-C",str(root),"add","."],check=True);subprocess.run(["git","-C",str(root),"commit","-qm","base"],check=True)
 return td,root,subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()

def sql():
 return """BEGIN;
CREATE SCHEMA IF NOT EXISTS notification;
CREATE TABLE notification.notification_intent(tenant_id text,notification_intent_id text);
CREATE TABLE notification.notification_attempt(tenant_id text,notification_attempt_id text);
CREATE TABLE notification.notification_provider_evidence(tenant_id text,provider_evidence_id text);
CREATE TABLE notification.notification_projection(tenant_id text,notification_intent_id text);
CREATE TABLE notification.notification_dispatch_outbox(tenant_id text,dispatch_outbox_id text);
CREATE TABLE notification.notification_callback_inbox(tenant_id text,callback_inbox_id text);
COMMIT;
"""

def wf():
 return json.dumps({"name":"JLMIRROR G9 Notification Delivery Runtime","on":{"pull_request":{},"workflow_dispatch":{}},"permissions":{},"jobs":{"g9-runtime":{"runs-on":"ubuntu-24.04","steps":[{"uses":"actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"},{"uses":"actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"},{"uses":"actions/setup-node@249970729cb0ef3589644e2896645e5dc5ba9c38"},{"run":"python tools/g9/run_notification_delivery_runtime.py"}]}}})

def case(files,ok):
 td,root,base=init()
 try:
  for rel,body in files.items():
   p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(body)
  claim=root/"implementation/g9-notification-delivery/IMPLEMENTATION_CLAIM.json";claim.parent.mkdir(parents=True,exist_ok=True);claim.write_text(json.dumps({"authorization_id":"g9.notification-delivery@1","slice_id":"g9.notification-delivery@1"}))
  sp=root/"sql/notification/001_notification_delivery.sql";sp.parent.mkdir(parents=True,exist_ok=True)
  if not sp.exists():sp.write_text(sql())
  wp=root/".github/workflows/g9-notification-delivery-runtime.yml";wp.parent.mkdir(parents=True,exist_ok=True)
  if not wp.exists():wp.write_text(wf())
  subprocess.run(["git","-C",str(root),"add","."],check=True);subprocess.run(["git","-C",str(root),"commit","-qm","candidate"],check=True)
  head=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
  cp=subprocess.run(["python3",str(VALIDATOR),"--repo-root",str(root),"--base",base,"--head",head,"--head-ref","impl/g9-notification-delivery-test","--labels-json",'["jlmirror-slice:g9-notification-delivery"]',"--head-repo",REPO,"--base-repo",REPO],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  if (cp.returncode==0)!=ok:raise AssertionError(cp.stdout+"\n"+cp.stderr)
 finally:td.cleanup()

def main():
 case({"apps/g9-notification-delivery/model.py":"channel='whatsapp_business@1'\nstate='delivered'\n"},True)
 case({"apps/g9-notification-delivery/email_adapter.py":"x=1\n"},False)
 case({"apps/g9-notification-delivery/approval.py":"approval_state='pending'\n"},False)
 case({"sql/notification/001_notification_delivery.sql":sql()+"\nCREATE TABLE notification.hidden(id text);\n"},False)
 case({"sql/notification/001_notification_delivery.sql":sql()+"\nUPDATE alerting.alert SET lifecycle_state='resolved';\n"},False)
 print("g9_scope_falsification=PASS whatsapp=allowed extra_channels=blocked hidden_relation=blocked cross_domain_mutation=blocked")
 return 0
if __name__=="__main__":raise SystemExit(main())
