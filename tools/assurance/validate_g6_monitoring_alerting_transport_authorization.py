#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE_SHA="edaa73b4b1752ab7bd9d4e8b73fd6e60976364c4"
AUTH_ID="g6.monitoring-alerting-transport@1"
MANIFEST=ROOT/"implementation/g6-monitoring-alerting-transport-authorization/AUTHORIZATION_MANIFEST.json"
AUTH=ROOT/"implementation/g6-monitoring-alerting-transport-authorization/AUTHORIZATION.md"
TASK=ROOT/"implementation/g6-monitoring-alerting-transport-authorization/TASK_PACKET.md"

def req(ok,msg,errors):
    if not ok:
        errors.append(msg)

def main()->int:
    errors=[]
    data=json.loads(MANIFEST.read_text(encoding="utf-8"))
    auth=AUTH.read_text(encoding="utf-8")
    task=TASK.read_text(encoding="utf-8")
    req(data.get("authorization_id")==AUTH_ID,"authorization id drift",errors)
    req(data.get("canonical_base")==f"main@{BASE_SHA}","canonical base drift",errors)
    req(data.get("implementation_authority_before_merge")=="blocked","pre-merge authority drift",errors)
    req(data.get("implementation_authority_after_merge")=="granted_for_exact_g6_monitoring_alerting_transport_only","post-merge authority drift",errors)
    req(data.get("merge_authorization")=="not_granted","self-merge authority forbidden",errors)
    req(data.get("alert_business_authority")=="none","G6 must not gain Alert business authority",errors)

    policy=data["implementation_path_policy"]
    req(policy["implementation_pr_head_prefix"]=="impl/g6-monitoring-alerting-transport","branch prefix drift",errors)
    req(policy["implementation_pr_required_label"]=="jlmirror-slice:g6-monitoring-alerting-transport","label drift",errors)
    req(policy["implementation_claim_authorization_id"]==AUTH_ID,"claim identity drift",errors)
    req(policy["exact_sql_path"]=="sql/integration/002_monitoring_alerting_consumer.sql","exact SQL path drift",errors)
    req(policy["runtime_workflow"]==".github/workflows/g6-monitoring-alerting-transport-runtime.yml","runtime path drift",errors)
    req(policy["runtime_workflow_name"]=="JLMIRROR G6 Monitoring Alerting Transport Runtime","runtime name drift",errors)
    req(policy["runtime_entrypoint"]=="python tools/g6/run_monitoring_alerting_transport_runtime.py","runtime entrypoint drift",errors)

    for marker in (
        "MONITORING_EVENT != ALERT",
        "INBOX_RECEIPT != ALERT",
        "INBOX_COMPLETED != ALERT_CREATED",
        "CURRENT_REREAD_REQUIRED_BEFORE_RESYNC_COMPLETION",
        "G6_AUTHORIZED != G7_AUTHORIZED",
        "READY_FOR_MERGE != AUTHORIZED_TO_MERGE",
    ):
        req(marker in auth,f"authorization missing marker: {marker}",errors)

    for marker in (
        "Monitoring event != Alert",
        "event payload != current Monitoring state",
        "inbox completed != Alert created",
        "current Monitoring reread required before completion",
        "G6 != G7",
    ):
        req(marker in task,f"task packet missing marker: {marker}",errors)

    forbidden=set(data.get("explicitly_not_authorized") or [])
    for item in (
        "alert_projection_persistence",
        "alert_transition_persistence",
        "alert_creation_resolution_reopen",
        "alert_policy_identity_or_evaluation",
        "alert_acknowledgement_or_suppression",
        "new_broker_outbox_or_inbox_substrate",
        "monitoring_business_truth_mutation",
    ):
        req(item in forbidden,f"critical non-authority missing: {item}",errors)

    for p in data.get("authority_source_paths") or []:
        req((ROOT/p).is_file(),f"authority source missing: {p}",errors)

    for e in errors:
        print(f"G6_AUTHORIZATION_ERROR: {e}",file=sys.stderr)
    if errors:
        return 1
    print("g6_authorization=PASS exact_scope=monitoring-alerting-transport merge_authorization=not-granted")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
