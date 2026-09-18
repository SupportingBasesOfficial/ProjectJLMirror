#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, tempfile
from pathlib import Path

VALIDATOR=Path(__file__).with_name("validate_g5_problem_health_implementation_scope.py")
REPO="SupportingBasesOfficial/ProjectJLMirror"

POLICY={
 "allowed_prefixes":["apps/g5-problem-health/","contracts/g5-problem-health/","implementation/g5-problem-health/","tests/g5/","tools/g5/"],
 "allowed_exact_paths":[".github/workflows/g5-problem-health-runtime.yml"],
 "semantic_scan_prefixes":["apps/g5-problem-health/","contracts/g5-problem-health/","implementation/g5-problem-health/","tests/g5/","tools/g5/"],
 "forbidden_path_tokens":["alert","alerting","ack","notification","incident","ticket","itsm","automation","aiops","replacement","cutover"],
 "forbidden_code_markers":["alert_creation","alert_policy","alert_state","monitoring_to_alerting","jlmirror_ack","acknowledge(","notification_intent","delivery_state","incident_id","ticket_id","itsm","provider_write_back","create table monitoring.","create schema monitoring","src/jlmirror_monitoring","sql/wave4","problem.get(","event.get(","trigger.get(","production_deployment","production_c3"],
 "implementation_claim_path":"implementation/g5-problem-health/IMPLEMENTATION_CLAIM.json",
 "implementation_pr_head_prefix":"impl/g5-problem-health",
 "implementation_pr_required_label":"jlmirror-slice:g5-problem-health",
 "runtime_workflow":".github/workflows/g5-problem-health-runtime.yml",
 "runtime_workflow_name":"JLMIRROR G5 Problem Health Runtime",
 "runtime_entrypoint":"python tools/g5/run_problem_health_runtime.py",
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
    subprocess.run(["git","-C",str(root),"config","user.name","G5 test"],check=True)
    p=root/"implementation/g5-problem-health-authorization/AUTHORIZATION_MANIFEST.json"
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps({"implementation_authority_after_merge":"granted_for_exact_g5_problem_health_only","implementation_path_policy":POLICY}),encoding="utf-8")
    subprocess.run(["git","-C",str(root),"add","."],check=True)
    subprocess.run(["git","-C",str(root),"commit","-qm","base"],check=True)
    base=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
    return td,root,base

def runtime():
    return json.dumps({"name":"JLMIRROR G5 Problem Health Runtime","on":{"pull_request":{},"workflow_dispatch":{}},"permissions":{},"jobs":{"g5-runtime":{"runs-on":"ubuntu-24.04","steps":[
      {"uses":"actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"},
      {"uses":"actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"},
      {"uses":"actions/setup-node@249970729cb0ef3589644e2896645e5dc5ba9c38"},
      {"run":"python tools/g5/run_problem_health_runtime.py"}
    ]}}})

def invoke(root,base):
    head=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
    return subprocess.run(["python3",str(VALIDATOR),"--repo-root",str(root),"--base",base,"--head",head,"--head-ref","impl/g5-problem-health-test","--labels-json",'["jlmirror-slice:g5-problem-health"]',"--head-repo",REPO,"--base-repo",REPO],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)

def run_case(files,expect_ok):
    td,root,base=init_repo()
    try:
      for rel,body in files.items():
        p=root/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(body,encoding="utf-8")
      claim=root/"implementation/g5-problem-health/IMPLEMENTATION_CLAIM.json"
      claim.parent.mkdir(parents=True,exist_ok=True)
      claim.write_text(json.dumps({"schema_version":1,"authorization_id":"g5.problem-health@1","slice_id":"g5.problem-health@1"}),encoding="utf-8")
      wf=root/".github/workflows/g5-problem-health-runtime.yml"; wf.parent.mkdir(parents=True,exist_ok=True)
      if not wf.exists(): wf.write_text(runtime(),encoding="utf-8")
      subprocess.run(["git","-C",str(root),"add","."],check=True)
      subprocess.run(["git","-C",str(root),"commit","-qm","candidate"],check=True)
      cp=invoke(root,base)
      if (cp.returncode==0)!=expect_ok:
        raise AssertionError(f"unexpected result\nstdout={cp.stdout}\nstderr={cp.stderr}")
    finally: td.cleanup()

def rename_case():
    td,root,base=init_repo()
    try:
      shared=root/"src/jlmirror_monitoring/problem_state.py"; shared.parent.mkdir(parents=True,exist_ok=True); shared.write_text("CANONICAL=True\n")
      subprocess.run(["git","-C",str(root),"add","."],check=True); subprocess.run(["git","-C",str(root),"commit","-qm","shared"],check=True)
      base=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
      dest=root/"apps/g5-problem-health/stolen_shared.py"; dest.parent.mkdir(parents=True,exist_ok=True)
      subprocess.run(["git","-C",str(root),"mv","src/jlmirror_monitoring/problem_state.py",str(dest.relative_to(root))],check=True)
      claim=root/"implementation/g5-problem-health/IMPLEMENTATION_CLAIM.json"; claim.parent.mkdir(parents=True,exist_ok=True); claim.write_text(json.dumps({"schema_version":1,"authorization_id":"g5.problem-health@1","slice_id":"g5.problem-health@1"}))
      wf=root/".github/workflows/g5-problem-health-runtime.yml"; wf.parent.mkdir(parents=True,exist_ok=True); wf.write_text(runtime())
      subprocess.run(["git","-C",str(root),"add","."],check=True); subprocess.run(["git","-C",str(root),"commit","-qm","candidate"],check=True)
      cp=invoke(root,base)
      if cp.returncode==0 or "src/jlmirror_monitoring/problem_state.py" not in cp.stderr:
        raise AssertionError(f"rename escape accepted\n{cp.stderr}")
    finally: td.cleanup()

def main():
    run_case({"apps/g5-problem-health/read.py":"problem_state='active'\nhealth_class='degraded'\nsql='SELECT problem_id FROM monitoring.monitoring_problem'\n"},True)
    run_case({"sql/g5/parallel.sql":"create table monitoring.problem_shadow(id text);\n"},False)
    run_case({"apps/g5-problem-health/alert.py":"alert_creation=True\n"},False)
    run_case({"apps/g5-problem-health/ack.py":"jlmirror_ack=True\n"},False)
    run_case({"apps/g5-problem-health/itsm.py":"incident_id='x'\n"},False)
    run_case({"apps/g5-problem-health/write.py":"db.update('health_projection', {'x':1})\n"},False)
    run_case({"apps/g5-problem-health/provider.py":"client.problem.get(request)\n"},False)
    bad=json.loads(runtime()); bad["jobs"]["g5-runtime"]["steps"].append({"run":"python tools/g6/run_alerting_transport.py"})
    run_case({".github/workflows/g5-problem-health-runtime.yml":json.dumps(bad)},False)
    rename_case()
    print("g5_scope_falsification=PASS problem_health=allowed alerting=blocked ack=blocked itsm=blocked writes=blocked provider_passthrough=blocked rename_escape=blocked runtime=bounded")
    return 0

if __name__=="__main__": raise SystemExit(main())
