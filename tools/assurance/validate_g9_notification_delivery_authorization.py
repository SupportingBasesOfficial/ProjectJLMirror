#!/usr/bin/env python3
from __future__ import annotations
import json,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE_SHA="a264e17852bfd114546438ee9094c7655c920839"
AUTH_ID="g9.notification-delivery@1"
MANIFEST=ROOT/"implementation/g9-notification-delivery-authorization/AUTHORIZATION_MANIFEST.json"
AUTH=ROOT/"implementation/g9-notification-delivery-authorization/AUTHORIZATION.md"
TASK=ROOT/"implementation/g9-notification-delivery-authorization/TASK_PACKET.md"

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
    req(data.get("implementation_authority_after_merge")=="granted_for_exact_g9_notification_delivery_only","post-merge authority drift",errors)
    req(data.get("merge_authorization")=="not_granted","merge authority drift",errors)
    req(data.get("notification_authority")=="whatsapp_intent_dispatch_delivery_evidence_only","notification authority drift",errors)
    model=data.get("notification_v1") or {}
    req(model.get("channels")==["whatsapp_business@1"],"channel set drift",errors)
    req(set(model.get("intent_reasons") or [])=={"alert_requires_attention","alert_action_requested","customer_awareness_required"},"intent reasons drift",errors)
    req(set(model.get("attempt_states") or [])=={"dispatching","sent","provider_accepted","delivered","failed","unknown"},"attempt states drift",errors)
    req(set(model.get("provider_evidence_kinds") or [])=={"provider_accepted","delivered","external_read_observed","failed","unknown"},"evidence kinds drift",errors)
    req(model.get("retry_same_channel_only") is True,"retry scope drift",errors)
    req(model.get("second_transport_channel_authorized") is False,"second channel widened",errors)
    req(model.get("external_read_is_authoritative_native_view") is False,"external read authority widened",errors)
    req(model.get("authoritative_awareness_requires_g8_native_visibility_when_required") is True,"G8 visibility composition drift",errors)
    p=data["implementation_path_policy"]
    req(p["implementation_pr_head_prefix"]=="impl/g9-notification-delivery","branch prefix drift",errors)
    req(p["implementation_pr_required_label"]=="jlmirror-slice:g9-notification-delivery","label drift",errors)
    req(p["implementation_claim_authorization_id"]==AUTH_ID,"claim identity drift",errors)
    req(p["exact_sql_path"]=="sql/notification/001_notification_delivery.sql","SQL path drift",errors)
    req(set(p["exact_sql_allowed_relations"])=={
      "notification.notification_intent","notification.notification_attempt",
      "notification.notification_provider_evidence","notification.notification_projection",
      "notification.notification_dispatch_outbox","notification.notification_callback_inbox"
    },"relation allowlist drift",errors)
    for marker in (
      "SENT != DELIVERED","DELIVERED != VIEWED","EXTERNAL_READ != AUTHORITATIVE_NATIVE_VIEW",
      "NOTIFICATION_RECIPIENT != RESPONSIBLE_PERSON","PROVIDER_ID != PLATFORM_ID",
      "READY_FOR_MERGE != AUTHORIZED_TO_MERGE"
    ):
      req(marker in auth,f"authorization marker missing: {marker}",errors)
    forbidden=set(data.get("explicitly_not_authorized") or [])
    for item in (
      "alert_lifecycle_or_policy_mutation","responsibility_current_action_or_ack_mutation",
      "g8_visibility_receipt_fabrication","budget_quote_or_approval_workflow",
      "itsm_incident_ticket_task_behavior","additional_transport_channels","production_activation"
    ):
      req(item in forbidden,f"missing exclusion: {item}",errors)
    for source in data.get("authority_source_paths") or []:
      req((ROOT/source).is_file(),f"authority source missing: {source}",errors)
    for e in errors: print(f"G9_AUTHORIZATION_ERROR: {e}",file=sys.stderr)
    if errors: return 1
    print("g9_authorization=PASS channel=whatsapp_business@1 exact_scope=notification-delivery")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
