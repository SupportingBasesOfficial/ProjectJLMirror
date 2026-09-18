#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE_SHA="96de4f58831e9c773d9bc00595e771fce9094f1e"
AUTH_ID="g5.problem-health@1"
MANIFEST=ROOT/"implementation/g5-problem-health-authorization/AUTHORIZATION_MANIFEST.json"
AUTH=ROOT/"implementation/g5-problem-health-authorization/AUTHORIZATION.md"
TASK=ROOT/"implementation/g5-problem-health-authorization/TASK_PACKET.md"
def req(ok,msg,errors):
    if not ok: errors.append(msg)
def main()->int:
    errors=[]
    data=json.loads(MANIFEST.read_text(encoding="utf-8"))
    auth=AUTH.read_text(encoding="utf-8")
    task=TASK.read_text(encoding="utf-8")
    req(data.get("authorization_id")==AUTH_ID,"authorization id drift",errors)
    req(data.get("canonical_base")==f"main@{BASE_SHA}","canonical base drift",errors)
    req(data.get("implementation_authority_before_merge")=="blocked","pre-merge authority drift",errors)
    req(data.get("implementation_authority_after_merge")=="granted_for_exact_g5_problem_health_only","post-merge authority drift",errors)
    req(data.get("merge_authorization")=="not_granted","self-merge authority forbidden",errors)
    policy=data["implementation_path_policy"]
    req(policy["implementation_pr_head_prefix"]=="impl/g5-problem-health","branch prefix drift",errors)
    req(policy["implementation_pr_required_label"]=="jlmirror-slice:g5-problem-health","label drift",errors)
    req(policy["implementation_claim_authorization_id"]==AUTH_ID,"claim identity drift",errors)
    req(policy["runtime_workflow"]==".github/workflows/g5-problem-health-runtime.yml","runtime path drift",errors)
    req(policy["runtime_workflow_name"]=="JLMIRROR G5 Problem Health Runtime","runtime name drift",errors)
    req(policy["runtime_entrypoint"]=="python tools/g5/run_problem_health_runtime.py","runtime entrypoint drift",errors)
    for marker in (
        "PROVIDER_EVENT_ID != PROBLEM_ID",
        "PROBLEM_ABSENCE_WITHOUT_AUTHORITATIVE_COMPLETENESS != HEALTHY",
        "PROVIDER_ACKNOWLEDGED != JLMIRROR_ACK",
        "G5_AUTHORIZED != G6_AUTHORIZED",
        "READY_FOR_MERGE != AUTHORIZED_TO_MERGE",
    ):
        req(marker in auth,f"authorization missing marker: {marker}",errors)
    for marker in (
        "provider acknowledged != JLMirror ACK",
        "incomplete omission != resolved",
        "problem absence without completeness != healthy",
        "G5 != G6",
    ):
        req(marker in task,f"task packet missing marker: {marker}",errors)
    forbidden=set(data.get("explicitly_not_authorized") or [])
    for item in (
        "monitoring_to_alerting_transport_changes",
        "alert_creation_resolution_policy_or_evaluation",
        "jlmirror_ack_or_responsibility",
        "itsm_incident_ticket_task_behavior",
        "provider_write_back",
    ):
        req(item in forbidden,f"critical non-authority missing: {item}",errors)
    for p in data.get("authority_source_paths") or []:
        req((ROOT/p).is_file(),f"authority source missing: {p}",errors)
    for e in errors: print(f"G5_AUTHORIZATION_ERROR: {e}",file=sys.stderr)
    if errors: return 1
    print("g5_authorization=PASS exact_scope=problem-health merge_authorization=not-granted")
    return 0
if __name__=="__main__": raise SystemExit(main())
