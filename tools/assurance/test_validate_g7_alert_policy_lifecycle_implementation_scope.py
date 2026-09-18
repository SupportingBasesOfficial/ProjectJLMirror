#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, tempfile
from pathlib import Path
VALIDATOR=Path(__file__).with_name("validate_g7_alert_policy_lifecycle_implementation_scope.py")
REPO="SupportingBasesOfficial/ProjectJLMirror"

POLICY={
 "allowed_prefixes":["apps/g7-alert-policy-lifecycle/","contracts/g7-alert-policy-lifecycle/","implementation/g7-alert-policy-lifecycle/","tests/g7/","tools/g7/"],
 "allowed_exact_paths":["sql/alerting/001_alert_policy_lifecycle.sql",".github/workflows/g7-alert-policy-lifecycle-runtime.yml"],
 "semantic_scan_prefixes":["apps/g7-alert-policy-lifecycle/","contracts/g7-alert-policy-lifecycle/","implementation/g7-alert-policy-lifecycle/","tests/g7/","tools/g7/"],
 "forbidden_path_tokens":["ack","responsib","assignment","notification","delivery","receipt","response","approval","budget","incident","ticket","itsm","automation","aiops","escalation","routing","suppression"],
 "forbidden_code_markers":["acknowledge(","jlmirror_ack","responsible_person","notification_intent","delivery_state","view_receipt","incident_id","ticket_id","provider_write_back","problem.get(","event.get(","trigger.get(","production_deployment","production_c3"],
 "implementation_claim_path":"implementation/g7-alert-policy-lifecycle/IMPLEMENTATION_CLAIM.json",
 "implementation_pr_head_prefix":"impl/g7-alert-policy-lifecycle",
 "implementation_pr_required_label":"jlmirror-slice:g7-alert-policy-lifecycle",
 "exact_sql_path":"sql/alerting/001_alert_policy_lifecycle.sql",
 "exact_sql_allowed_relations":["alerting.alert_policy","alerting.alert_policy_version","alerting.alert_policy_effective_version","alerting.alert","alerting.alert_transition","alerting.alert_decision"],
 "runtime_workflow":".github/workflows/g7-alert-policy-lifecycle-runtime.yml",
 "runtime_workflow_name":"JLMIRROR G7 Alert Policy Lifecycle Runtime",
 "runtime_entrypoint":"python tools/g7/run_alert_policy_lifecycle_runtime.py",
 "runtime_allowed_actions":["actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1","actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1","actions/setup-node@249970729cb0ef3589644e2896645e5dc5ba9c38"]
}

def init_repo():
    td=tempfile.TemporaryDirectory(); root=Path(td.name)
    subprocess.run(["git","init","-q",str(root)],check=True)
    subprocess.run(["git","-C",str(root),"config","user.email","test@example.invalid"],check=True)
    subprocess.run(["git","-C",str(root),"config","user.name","G7 test"],check=True)
    p=root/"implementation/g7-alert-policy-lifecycle-authorization/AUTHORIZATION_MANIFEST.json"; p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps({"implementation_authority_after_merge":"granted_for_exact_g7_alert_policy_lifecycle_only","implementation_path_policy":POLICY}))
    subprocess.run(["git","-C",str(root),"add","."],check=True); subprocess.run(["git","-C",str(root),"commit","-qm","base"],check=True)
    base=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
    return td,root,base

def runtime():
    return json.dumps({"name":"JLMIRROR G7 Alert Policy Lifecycle Runtime","on":{"pull_request":{},"workflow_dispatch":{}},"permissions":{},"jobs":{"g7-runtime":{"runs-on":"ubuntu-24.04","steps":[{"uses":"actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"},{"uses":"actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"},{"uses":"actions/setup-node@249970729cb0ef3589644e2896645e5dc5ba9c38"},{"run":"python tools/g7/run_alert_policy_lifecycle_runtime.py"}]}}})

def canonical_sql():
    return """BEGIN;
CREATE SCHEMA IF NOT EXISTS alerting;
CREATE TABLE alerting.alert_policy(policy_id uuid);
CREATE TABLE alerting.alert_policy_version(policy_id uuid, policy_version bigint, source_kind text);
CREATE TABLE alerting.alert_policy_effective_version(policy_id uuid, policy_version bigint);
CREATE TABLE alerting.alert(alert_id uuid, lifecycle_state text, policy_id uuid, policy_version bigint);
CREATE TABLE alerting.alert_transition(alert_transition_id uuid, alert_id uuid, lifecycle_state text, policy_id uuid, policy_version bigint);
CREATE TABLE alerting.alert_decision(alert_id uuid, policy_id uuid, policy_version bigint);
COMMENT ON TABLE alerting.alert IS 'active resolved';
COMMIT;
"""

def invoke(root,base):
    head=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
    return subprocess.run(["python3",str(VALIDATOR),"--repo-root",str(root),"--base",base,"--head",head,"--head-ref","impl/g7-alert-policy-lifecycle-test","--labels-json",'["jlmirror-slice:g7-alert-policy-lifecycle"]',"--head-repo",REPO,"--base-repo",REPO],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)

def run_case(files,expect_ok):
    td,root,base=init_repo()
    try:
        for rel,body in files.items():
            p=root/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(body)
        claim=root/"implementation/g7-alert-policy-lifecycle/IMPLEMENTATION_CLAIM.json"; claim.parent.mkdir(parents=True,exist_ok=True)
        claim.write_text(json.dumps({"schema_version":1,"authorization_id":"g7.alert-policy-lifecycle@1","slice_id":"g7.alert-policy-lifecycle@1"}))
        sql=root/"sql/alerting/001_alert_policy_lifecycle.sql"; sql.parent.mkdir(parents=True,exist_ok=True)
        if not sql.exists(): sql.write_text(canonical_sql())
        wf=root/".github/workflows/g7-alert-policy-lifecycle-runtime.yml"; wf.parent.mkdir(parents=True,exist_ok=True)
        if not wf.exists(): wf.write_text(runtime())
        subprocess.run(["git","-C",str(root),"add","."],check=True); subprocess.run(["git","-C",str(root),"commit","-qm","candidate"],check=True)
        cp=invoke(root,base)
        if (cp.returncode==0)!=expect_ok: raise AssertionError(f"unexpected result\nstdout={cp.stdout}\nstderr={cp.stderr}")
    finally: td.cleanup()

def main():
    run_case({"apps/g7-alert-policy-lifecycle/evaluator.py":"source_kind='monitoring_problem'\npolicy_version=1\nlifecycle='active'\n"},True)
    run_case({"apps/g7-alert-policy-lifecycle/ack.py":"acknowledge(alert_id)\n"},False)
    run_case({"apps/g7-alert-policy-lifecycle/notification.py":"notification_intent='x'\n"},False)
    run_case({"apps/g7-alert-policy-lifecycle/write.py":"db.update('alerting', {'x':1})\n"},False)
    run_case({"apps/g7-alert-policy-lifecycle/provider.py":"client.problem.get(request)\n"},False)
    run_case({"sql/alerting/001_alert_policy_lifecycle.sql":canonical_sql()+"\nCREATE TABLE alerting.notification_intent(id uuid);\n"},False)
    run_case({"sql/alerting/001_alert_policy_lifecycle.sql":canonical_sql()+"\nCREATE TABLE alerting.hidden_business_state(id uuid);\n"},False)
    run_case({"sql/alerting/001_alert_policy_lifecycle.sql":canonical_sql()+'\nCREATE TABLE "alerting"."hidden_quoted_state"(id uuid);\n'},False)
    run_case({"sql/alerting/001_alert_policy_lifecycle.sql":canonical_sql()+"\nUPDATE monitoring.monitoring_problem SET severity='x';\n"},False)
    print("g7_scope_falsification=PASS policy_lifecycle=allowed ack=blocked notification=blocked hidden_relation=blocked direct_writes=blocked provider_passthrough=blocked monitoring_mutation=blocked")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
