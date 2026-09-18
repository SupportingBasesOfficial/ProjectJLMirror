#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, tempfile
from pathlib import Path

VALIDATOR=Path(__file__).with_name("validate_g6_monitoring_alerting_transport_implementation_scope.py")
REPO="SupportingBasesOfficial/ProjectJLMirror"

POLICY={
 "allowed_prefixes":[
   "apps/g6-monitoring-alerting-transport/",
   "contracts/g6-monitoring-alerting-transport/",
   "implementation/g6-monitoring-alerting-transport/",
   "tests/g6/",
   "tools/g6/"
 ],
 "allowed_exact_paths":[
   "sql/integration/002_monitoring_alerting_consumer.sql",
   ".github/workflows/g6-monitoring-alerting-transport-runtime.yml"
 ],
 "semantic_scan_prefixes":[
   "apps/g6-monitoring-alerting-transport/",
   "contracts/g6-monitoring-alerting-transport/",
   "implementation/g6-monitoring-alerting-transport/",
   "tests/g6/",
   "tools/g6/"
 ],
 "forbidden_path_tokens":[
   "policy","lifecycle","ack","notification","incident","ticket","itsm",
   "automation","aiops","escalation","routing","suppression"
 ],
 "forbidden_code_markers":[
   "alert_creation","create_alert","resolve_alert","reopen_alert",
   "alert_transition_id","lifecycle_state","policy_id","policy_version",
   "alert_policy","policy_evaluation","acknowledge(","jlmirror_ack",
   "suppression","notification_intent","delivery_state","incident_id","ticket_id",
   "provider_write_back","create table alerting.","create schema alerting",
   "insert into alerting.","update alerting.","delete from alerting.",
   "problem.get(","event.get(","trigger.get(",
   "production_deployment","production_c3"
 ],
 "implementation_claim_path":"implementation/g6-monitoring-alerting-transport/IMPLEMENTATION_CLAIM.json",
 "implementation_pr_head_prefix":"impl/g6-monitoring-alerting-transport",
 "implementation_pr_required_label":"jlmirror-slice:g6-monitoring-alerting-transport",
 "exact_sql_path":"sql/integration/002_monitoring_alerting_consumer.sql",
 "runtime_workflow":".github/workflows/g6-monitoring-alerting-transport-runtime.yml",
 "runtime_workflow_name":"JLMIRROR G6 Monitoring Alerting Transport Runtime",
 "runtime_entrypoint":"python tools/g6/run_monitoring_alerting_transport_runtime.py",
 "runtime_allowed_actions":[
  "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
  "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1",
  "actions/setup-node@249970729cb0ef3589644e2896645e5dc5ba9c38"
 ]
}

def init_repo():
    td=tempfile.TemporaryDirectory(); root=Path(td.name)
    subprocess.run(["git","init","-q",str(root)],check=True)
    subprocess.run(["git","-C",str(root),"config","user.email","test@example.invalid"],check=True)
    subprocess.run(["git","-C",str(root),"config","user.name","G6 test"],check=True)
    p=root/"implementation/g6-monitoring-alerting-transport-authorization/AUTHORIZATION_MANIFEST.json"
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps({
      "implementation_authority_after_merge":"granted_for_exact_g6_monitoring_alerting_transport_only",
      "implementation_path_policy":POLICY
    }),encoding="utf-8")
    subprocess.run(["git","-C",str(root),"add","."],check=True)
    subprocess.run(["git","-C",str(root),"commit","-qm","base"],check=True)
    base=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
    return td,root,base

def runtime():
    return json.dumps({
      "name":"JLMIRROR G6 Monitoring Alerting Transport Runtime",
      "on":{"pull_request":{},"workflow_dispatch":{}},
      "permissions":{},
      "jobs":{"g6-runtime":{"runs-on":"ubuntu-24.04","steps":[
        {"uses":"actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"},
        {"uses":"actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"},
        {"uses":"actions/setup-node@249970729cb0ef3589644e2896645e5dc5ba9c38"},
        {"run":"python tools/g6/run_monitoring_alerting_transport_runtime.py"}
      ]}}
    })

def canonical_sql():
    return """
BEGIN;
CREATE ROLE jlmirror_g6_alerting_transport_executor NOLOGIN;
CREATE FUNCTION system.g6_admit_monitoring_alerting_message()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  IF false THEN
    INSERT INTO system.async_consumer_inbox(
      consumer_contract,message_identity_scope,message_id,tenant_id,
      comparison_profile_id,comparison_profile_version,comparison_evidence_form,
      comparison_evidence
    ) VALUES (
      'alerting.monitoring-resync@1','tenant:test','message-test','tenant-test',
      'profile','1','opaque',decode('01','hex')
    );
  END IF;
  PERFORM 'monitoring.problem-state.changed';
  PERFORM 'monitoring.health-projection.changed';
END;
$$;
COMMIT;
"""

def invoke(root,base):
    head=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
    return subprocess.run([
      "python3",str(VALIDATOR),
      "--repo-root",str(root),"--base",base,"--head",head,
      "--head-ref","impl/g6-monitoring-alerting-transport-test",
      "--labels-json",'["jlmirror-slice:g6-monitoring-alerting-transport"]',
      "--head-repo",REPO,"--base-repo",REPO
    ],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)

def run_case(files,expect_ok):
    td,root,base=init_repo()
    try:
      for rel,body in files.items():
        p=root/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(body,encoding="utf-8")
      claim=root/"implementation/g6-monitoring-alerting-transport/IMPLEMENTATION_CLAIM.json"
      claim.parent.mkdir(parents=True,exist_ok=True)
      claim.write_text(json.dumps({
        "schema_version":1,
        "authorization_id":"g6.monitoring-alerting-transport@1",
        "slice_id":"g6.monitoring-alerting-transport@1"
      }),encoding="utf-8")
      sql=root/"sql/integration/002_monitoring_alerting_consumer.sql"
      sql.parent.mkdir(parents=True,exist_ok=True)
      if not sql.exists(): sql.write_text(canonical_sql(),encoding="utf-8")
      wf=root/".github/workflows/g6-monitoring-alerting-transport-runtime.yml"
      wf.parent.mkdir(parents=True,exist_ok=True)
      if not wf.exists(): wf.write_text(runtime(),encoding="utf-8")
      subprocess.run(["git","-C",str(root),"add","."],check=True)
      subprocess.run(["git","-C",str(root),"commit","-qm","candidate"],check=True)
      cp=invoke(root,base)
      if (cp.returncode==0)!=expect_ok:
        raise AssertionError(f"unexpected result\nstdout={cp.stdout}\nstderr={cp.stderr}")
    finally:
      td.cleanup()

def rename_case():
    td,root,base=init_repo()
    try:
      shared=root/"sql/wave2/001_async_correctness.sql"
      shared.parent.mkdir(parents=True,exist_ok=True)
      shared.write_text("CANONICAL=True\n",encoding="utf-8")
      subprocess.run(["git","-C",str(root),"add","."],check=True)
      subprocess.run(["git","-C",str(root),"commit","-qm","shared"],check=True)
      base=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
      dest=root/"apps/g6-monitoring-alerting-transport/stolen_async.py"
      dest.parent.mkdir(parents=True,exist_ok=True)
      subprocess.run(["git","-C",str(root),"mv","sql/wave2/001_async_correctness.sql",str(dest.relative_to(root))],check=True)
      claim=root/"implementation/g6-monitoring-alerting-transport/IMPLEMENTATION_CLAIM.json"
      claim.parent.mkdir(parents=True,exist_ok=True)
      claim.write_text(json.dumps({"schema_version":1,"authorization_id":"g6.monitoring-alerting-transport@1","slice_id":"g6.monitoring-alerting-transport@1"}))
      sql=root/"sql/integration/002_monitoring_alerting_consumer.sql"; sql.parent.mkdir(parents=True,exist_ok=True); sql.write_text(canonical_sql())
      wf=root/".github/workflows/g6-monitoring-alerting-transport-runtime.yml"; wf.parent.mkdir(parents=True,exist_ok=True); wf.write_text(runtime())
      subprocess.run(["git","-C",str(root),"add","."],check=True)
      subprocess.run(["git","-C",str(root),"commit","-qm","candidate"],check=True)
      cp=invoke(root,base)
      if cp.returncode==0 or "sql/wave2/001_async_correctness.sql" not in cp.stderr:
        raise AssertionError(f"rename escape accepted\n{cp.stderr}")
    finally:
      td.cleanup()

def main():
    run_case({"apps/g6-monitoring-alerting-transport/consumer.py":"contract='monitoring.problem-state.changed'\nresync='current-reread'\n"},True)
    run_case({"sql/integration/003_parallel_inbox.sql":"CREATE TABLE system.parallel_inbox(id text);\n"},False)
    run_case({"apps/g6-monitoring-alerting-transport/lifecycle.py":"lifecycle_state='active'\n"},False)
    run_case({"apps/g6-monitoring-alerting-transport/policy.py":"policy_id='p1'\n"},False)
    run_case({"apps/g6-monitoring-alerting-transport/write.py":"db.update('alerting', {'x':1})\n"},False)
    run_case({"apps/g6-monitoring-alerting-transport/provider.py":"client.event.get(request)\n"},False)
    run_case({"sql/integration/002_monitoring_alerting_consumer.sql":canonical_sql()+"\nCREATE TABLE alerting.alert(id text);\n"},False)
    run_case({"sql/integration/002_monitoring_alerting_consumer.sql":canonical_sql()+"\nINSERT INTO alerting.alert VALUES ('x');\n"},False)
    bad=json.loads(runtime()); bad["jobs"]["g6-runtime"]["steps"].append({"run":"python tools/g7/run_alert_lifecycle.py"})
    run_case({".github/workflows/g6-monitoring-alerting-transport-runtime.yml":json.dumps(bad)},False)
    rename_case()
    print("g6_scope_falsification=PASS transport=allowed parallel_inbox=blocked alert_lifecycle=blocked policy=blocked direct_writes=blocked provider_passthrough=blocked sql_business_state=blocked rename_escape=blocked runtime=bounded")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
