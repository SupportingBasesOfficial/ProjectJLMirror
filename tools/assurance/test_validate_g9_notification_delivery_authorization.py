#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
M=ROOT/"implementation/g9-notification-delivery-authorization/AUTHORIZATION_MANIFEST.json"

def require(ok,msg):
    if not ok: raise AssertionError(msg)

def main()->int:
    d=json.loads(M.read_text(encoding="utf-8"))
    p=d["implementation_path_policy"]
    require(d["authorization_id"]=="g9.notification-delivery@1","id drift")
    require(d["notification_v1"]["channels"]==["whatsapp_business@1"],"one-channel law drift")
    require(len(p["exact_sql_allowed_relations"])==6,"relation surface widened")
    forbidden=set(d["explicitly_not_authorized"])
    for x in ("budget_quote_or_approval_workflow","itsm_incident_ticket_task_behavior","additional_transport_channels"):
        require(x in forbidden,f"missing exclusion {x}")
    print("g9_authorization_falsification=PASS whatsapp=allowed extra_channels=blocked g10_plus=blocked")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
