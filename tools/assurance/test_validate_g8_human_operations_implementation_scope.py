#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

VALIDATOR=Path(__file__).with_name("validate_g8_human_operations_implementation_scope.py")
REPO="SupportingBasesOfficial/ProjectJLMirror"

POLICY={
 "allowed_prefixes":["apps/g8-human-operations/","contracts/g8-human-operations/","implementation/g8-human-operations/","tests/g8/","tools/g8/"],
 "allowed_exact_paths":["sql/human_operations/001_human_operations.sql",".github/workflows/g8-human-operations-runtime.yml"],
 "semantic_scan_prefixes":["apps/g8-human-operations/","contracts/g8-human-operations/","implementation/g8-human-operations/","tests/g8/","tools/g8/"],
 "forbidden_path_tokens":["notification","delivery","whatsapp","email","sms","teams","slack","approval","budget","itsm","incident","ticket","automation","aiops","provider-write"],
 "forbidden_code_markers":["notification_intent","delivery_attempt","delivery_state","provider_accepted","whatsapp","send_email","send_sms","teams_webhook","slack_webhook","awaiting_budget_approval","approval_state","incident_id","ticket_id","provider_write_back","alert_reopen","unacknowledge"],
 "implementation_claim_path":"implementation/g8-human-operations/IMPLEMENTATION_CLAIM.json",
 "implementation_pr_head_prefix":"impl/g8-human-operations",
 "implementation_pr_required_label":"jlmirror-slice:g8-human-operations",
 "exact_sql_path":"sql/human_operations/001_human_operations.sql",
 "exact_sql_allowed_relations":[
  "human_operations.resource_responsibility_assignment",
  "human_operations.alert_action_assignment",
  "human_operations.alert_acknowledgement",
  "human_operations.visibility_requirement",
  "human_operations.visibility_receipt",
  "human_operations.current_action_projection"
 ],
 "runtime_workflow":".github/workflows/g8-human-operations-runtime.yml",
 "runtime_workflow_name":"JLMIRROR G8 Human Operations Runtime",
 "runtime_entrypoint":"python tools/g8/run_human_operations_runtime.py",
 "runtime_allowed_actions":["actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1","actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1","actions/setup-node@249970729cb0ef3589644e2896645e5dc5ba9c38"]
}


def init_repo():
    td=tempfile.TemporaryDirectory()
    root=Path(td.name)
    subprocess.run(["git","init","-q",str(root)],check=True)
    subprocess.run(["git","-C",str(root),"config","user.email","test@example.invalid"],check=True)
    subprocess.run(["git","-C",str(root),"config","user.name","G8 test"],check=True)
    p=root/"implementation/g8-human-operations-authorization/AUTHORIZATION_MANIFEST.json"
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps({
        "implementation_authority_after_merge":"granted_for_exact_g8_human_operations_only",
        "implementation_path_policy":POLICY,
    }))
    subprocess.run(["git","-C",str(root),"add","."],check=True)
    subprocess.run(["git","-C",str(root),"commit","-qm","base"],check=True)
    base=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
    return td,root,base


def runtime():
    return json.dumps({
        "name":"JLMIRROR G8 Human Operations Runtime",
        "on":{"pull_request":{},"workflow_dispatch":{}},
        "permissions":{},
        "jobs":{"g8-runtime":{"runs-on":"ubuntu-24.04","steps":[
            {"uses":"actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"},
            {"uses":"actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"},
            {"uses":"actions/setup-node@249970729cb0ef3589644e2896645e5dc5ba9c38"},
            {"run":"python tools/g8/run_human_operations_runtime.py"},
        ]}},
    })


def canonical_sql():
    return """BEGIN;
CREATE SCHEMA IF NOT EXISTS human_operations;
CREATE TABLE human_operations.resource_responsibility_assignment(responsibility_assignment_id uuid, tenant_id text);
CREATE TABLE human_operations.alert_action_assignment(action_assignment_id uuid, tenant_id text, current_action text);
CREATE TABLE human_operations.alert_acknowledgement(acknowledgement_id uuid, tenant_id text);
CREATE TABLE human_operations.visibility_requirement(visibility_requirement_id uuid, tenant_id text);
CREATE TABLE human_operations.visibility_receipt(visibility_receipt_id uuid, visibility_requirement_id uuid, tenant_id text);
CREATE TABLE human_operations.current_action_projection(tenant_id text, current_action text);
COMMIT;
"""


def invoke(root,base):
    head=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
    return subprocess.run([
        "python3",str(VALIDATOR),
        "--repo-root",str(root),
        "--base",base,
        "--head",head,
        "--head-ref","impl/g8-human-operations-test",
        "--labels-json",'["jlmirror-slice:g8-human-operations"]',
        "--head-repo",REPO,
        "--base-repo",REPO,
    ],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)


def run_case(files,expect_ok):
    td,root,base=init_repo()
    try:
        for rel,body in files.items():
            p=root/rel
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text(body)

        claim=root/"implementation/g8-human-operations/IMPLEMENTATION_CLAIM.json"
        claim.parent.mkdir(parents=True,exist_ok=True)
        claim.write_text(json.dumps({
            "schema_version":1,
            "authorization_id":"g8.human-operations@1",
            "slice_id":"g8.human-operations@1",
        }))

        sql=root/"sql/human_operations/001_human_operations.sql"
        sql.parent.mkdir(parents=True,exist_ok=True)
        if not sql.exists():
            sql.write_text(canonical_sql())

        wf=root/".github/workflows/g8-human-operations-runtime.yml"
        wf.parent.mkdir(parents=True,exist_ok=True)
        if not wf.exists():
            wf.write_text(runtime())

        subprocess.run(["git","-C",str(root),"add","."],check=True)
        subprocess.run(["git","-C",str(root),"commit","-qm","candidate"],check=True)
        cp=invoke(root,base)
        if (cp.returncode==0)!=expect_ok:
            raise AssertionError(f"unexpected result\nstdout={cp.stdout}\nstderr={cp.stderr}")
    finally:
        td.cleanup()


def main()->int:
    run_case({"apps/g8-human-operations/model.py":"acknowledgement_id='a'\nresponsibility_assignment_id='r'\nvisibility_receipt_id='v'\n"},True)
    run_case({"apps/g8-human-operations/notification.py":"notification_intent='x'\n"},False)
    run_case({"apps/g8-human-operations/approval.py":"approval_state='pending'\n"},False)
    run_case({"apps/g8-human-operations/write.py":"db.update('human_operations', {'x':1})\n"},False)
    run_case({"apps/g8-human-operations/reopen.py":"alert_reopen=True\n"},False)
    run_case({"sql/human_operations/001_human_operations.sql":canonical_sql()+"\nCREATE TABLE human_operations.hidden_state(id uuid);\n"},False)
    run_case({"sql/human_operations/001_human_operations.sql":canonical_sql()+'\nCREATE TABLE "human_operations"."hidden_quoted_state"(id uuid);\n'},False)
    run_case({"sql/human_operations/001_human_operations.sql":canonical_sql()+"\nUPDATE alerting.alert SET lifecycle_state='resolved';\n"},False)
    print("g8_scope_falsification=PASS responsibility_ack_visibility=allowed g9_plus=blocked hidden_relation=blocked direct_writes=blocked alert_mutation=blocked")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
