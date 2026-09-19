#!/usr/bin/env python3
from __future__ import annotations
import json,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE_SHA="a701498188867e9b6e5e98a74716f755bf673fc5"
AUTH_ID="g10.itsm-incident@1"
MANIFEST=ROOT/"implementation/g10-itsm-authorization/AUTHORIZATION_MANIFEST.json"
AUTH=ROOT/"implementation/g10-itsm-authorization/AUTHORIZATION.md"
TASK=ROOT/"implementation/g10-itsm-authorization/TASK_PACKET.md"

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
    req(data.get("implementation_authority_after_merge")=="granted_for_exact_g10_itsm_incident_only","post-merge authority drift",errors)
    req(data.get("merge_authorization")=="not_granted","merge authority drift",errors)
    req(data.get("itsm_authority")=="incident_lifecycle_assignment_comments_provider_sync_only","ITSM authority drift",errors)
    model=data.get("incident_v1") or {}
    req(model.get("object_type")=="incident","object type drift",errors)
    req(model.get("lifecycle_states")==["open","in_progress","resolved","closed"],"lifecycle states drift",errors)
    req(set(model.get("allowed_transitions") or [])=={
      "open->in_progress","open->resolved","in_progress->resolved","resolved->closed"
    },"transition graph drift",errors)
    req(model.get("reopen_authorized") is False,"reopen authority widened",errors)
    req(model.get("one_originating_alert") is True,"originating Alert law drift",errors)
    req(model.get("automatic_alert_to_incident") is False,"automatic creation widened",errors)
    req(model.get("one_current_assignee") is True,"assignment cardinality drift",errors)
    req(model.get("comments_immutable") is True,"comment mutability drift",errors)
    req(model.get("external_provider_selected") is False,"named provider was selected",errors)
    req(model.get("provider_adapter_contract")=="itsm_provider_neutral@1","adapter contract drift",errors)
    req(set(model.get("sync_states") or [])=={
      "pending","dispatching","linked","failed","unknown","reconciliation_required"
    },"sync states drift",errors)
    p=data["implementation_path_policy"]
    req(p["implementation_pr_head_prefix"]=="impl/g10-itsm","branch prefix drift",errors)
    req(p["implementation_pr_required_label"]=="jlmirror-slice:g10-itsm","label drift",errors)
    req(p["implementation_claim_authorization_id"]==AUTH_ID,"claim identity drift",errors)
    req(p["exact_sql_path"]=="sql/itsm/001_incident.sql","SQL path drift",errors)
    req(set(p["exact_sql_allowed_relations"])=={
      "itsm.incident","itsm.incident_transition","itsm.incident_assignment",
      "itsm.incident_comment","itsm.incident_provider_link","itsm.incident_sync_outbox"
    },"relation allowlist drift",errors)
    for marker in (
      "ALERT_ID != INCIDENT_ID","ALERT_STATE != INCIDENT_STATE",
      "PROVIDER_TICKET_ID != INCIDENT_ID","PROVIDER_STATUS != INCIDENT_STATUS",
      "INCIDENT_ASSIGNEE != RESPONSIBLE_PERSON","READY_FOR_MERGE != AUTHORIZED_TO_MERGE"
    ):
      req(marker in auth,f"authorization marker missing: {marker}",errors)
    forbidden=set(data.get("explicitly_not_authorized") or [])
    for item in (
      "alert_lifecycle_or_policy_mutation",
      "g8_responsibility_current_action_or_ack_mutation",
      "g9_notification_delivery_mutation",
      "automatic_alert_to_incident_creation",
      "incident_reopen","change_rfc","approval_budget_quote","task_subtask",
      "named_external_itsm_vendor","production_activation"
    ):
      req(item in forbidden,f"missing exclusion: {item}",errors)
    for source in data.get("authority_source_paths") or []:
      req((ROOT/source).is_file(),f"authority source missing: {source}",errors)
    for e in errors: print(f"G10_AUTHORIZATION_ERROR: {e}",file=sys.stderr)
    if errors:return 1
    print("g10_authorization=PASS object=incident provider=neutral exact_scope=itsm-incident")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
