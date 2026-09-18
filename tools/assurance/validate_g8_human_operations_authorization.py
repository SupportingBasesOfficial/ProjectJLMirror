#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE_SHA="be9d2a2fe49c308d4d8c9ca06e9ebafbb4ae69f8"
AUTH_ID="g8.human-operations@1"
MANIFEST=ROOT/"implementation/g8-human-operations-authorization/AUTHORIZATION_MANIFEST.json"
AUTH=ROOT/"implementation/g8-human-operations-authorization/AUTHORIZATION.md"
TASK=ROOT/"implementation/g8-human-operations-authorization/TASK_PACKET.md"


def req(ok:bool,msg:str,errors:list[str])->None:
    if not ok:
        errors.append(msg)


def main()->int:
    errors:list[str]=[]
    data=json.loads(MANIFEST.read_text(encoding="utf-8"))
    auth=AUTH.read_text(encoding="utf-8")
    task=TASK.read_text(encoding="utf-8")

    req(data.get("authorization_id")==AUTH_ID,"authorization id drift",errors)
    req(data.get("canonical_base")==f"main@{BASE_SHA}","canonical base drift",errors)
    req(data.get("implementation_authority_before_merge")=="blocked","pre-merge authority drift",errors)
    req(data.get("implementation_authority_after_merge")=="granted_for_exact_g8_human_operations_only","post-merge authority drift",errors)
    req(data.get("merge_authorization")=="not_granted","self-merge authority forbidden",errors)
    req(data.get("human_operations_authority")=="responsibility_ack_current_action_and_native_visibility_only","human-operations authority drift",errors)

    policy=data["implementation_path_policy"]
    req(policy["implementation_pr_head_prefix"]=="impl/g8-human-operations","branch prefix drift",errors)
    req(policy["implementation_pr_required_label"]=="jlmirror-slice:g8-human-operations","label drift",errors)
    req(policy["implementation_claim_authorization_id"]==AUTH_ID,"claim identity drift",errors)
    req(policy["exact_sql_path"]=="sql/human_operations/001_human_operations.sql","exact SQL path drift",errors)
    req(set(policy.get("exact_sql_allowed_relations") or [])=={
        "human_operations.resource_responsibility_assignment",
        "human_operations.alert_action_assignment",
        "human_operations.alert_acknowledgement",
        "human_operations.visibility_requirement",
        "human_operations.visibility_receipt",
        "human_operations.current_action_projection",
    },"exact SQL relation allowlist drift",errors)
    req(policy["runtime_workflow"]==".github/workflows/g8-human-operations-runtime.yml","runtime path drift",errors)
    req(policy["runtime_workflow_name"]=="JLMIRROR G8 Human Operations Runtime","runtime name drift",errors)
    req(policy["runtime_entrypoint"]=="python tools/g8/run_human_operations_runtime.py","runtime entrypoint drift",errors)

    for marker in (
        "ALERT_LIFECYCLE != RESPONSIBILITY",
        "RESPONSIBILITY != CURRENT_ACTION_OWNER",
        "VIEWER != ACKNOWLEDGER",
        "ACKNOWLEDGEMENT != ALERT_RESOLUTION",
        "NATIVE_VISIBILITY != EXTERNAL_DELIVERY",
        "G8_AUTHORIZED != G9_AUTHORIZED",
        "READY_FOR_MERGE != AUTHORIZED_TO_MERGE",
    ):
        req(marker in auth,f"authorization missing marker: {marker}",errors)

    for marker in (
        "Alert lifecycle != responsibility",
        "Responsibility != current action owner",
        "Viewer != acknowledger",
        "ACK != Alert lifecycle",
        "Native visibility != external delivery",
        "G8 != G9",
    ):
        req(marker in task,f"task packet missing marker: {marker}",errors)

    forbidden=set(data.get("explicitly_not_authorized") or [])
    for item in (
        "alert_lifecycle_or_policy_mutation",
        "unacknowledge",
        "notification_intent",
        "dispatch_provider_acceptance_or_delivery_state",
        "external_channel_read_receipts",
        "budget_quote_or_approval_workflow",
        "itsm_incident_ticket_task_behavior",
        "provider_write_back",
    ):
        req(item in forbidden,f"critical non-authority missing: {item}",errors)

    laws=set(data.get("identity_laws") or [])
    for law in (
        "RESPONSIBILITY != CURRENT_ACTION_OWNER",
        "VIEWER != ACKNOWLEDGER",
        "ACKNOWLEDGEMENT != ALERT_RESOLUTION",
        "VISIBILITY != DELIVERY",
        "TIMELINE != MUTABLE_BUSINESS_TRUTH",
    ):
        req(law in laws,f"identity law missing: {law}",errors)

    for p in data.get("authority_source_paths") or []:
        req((ROOT/p).is_file(),f"authority source missing: {p}",errors)

    for error in errors:
        print(f"G8_AUTHORIZATION_ERROR: {error}",file=sys.stderr)
    if errors:
        return 1
    print("g8_authorization=PASS exact_scope=human-operations merge_authorization=not-granted")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
