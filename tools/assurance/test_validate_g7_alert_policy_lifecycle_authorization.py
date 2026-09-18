#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
MANIFEST=ROOT/"implementation/g7-alert-policy-lifecycle-authorization/AUTHORIZATION_MANIFEST.json"

def require(ok,msg):
    if not ok: raise AssertionError(msg)

def main()->int:
    data=json.loads(MANIFEST.read_text(encoding="utf-8")); p=data["implementation_path_policy"]
    require(data["authorization_id"]=="g7.alert-policy-lifecycle@1","authorization id drift")
    require("apps/g7-alert-policy-lifecycle/" in p["allowed_prefixes"],"app prefix missing")
    require("sql/alerting/001_alert_policy_lifecycle.sql" in p["allowed_exact_paths"],"exact SQL missing")
    require(data["alert_business_authority"]=="policy_evaluation_and_active_resolved_lifecycle_only","Alert authority widened")
    forbidden=set(data["explicitly_not_authorized"])
    for item in ("acknowledgement_or_unacknowledgement","responsibility_or_assignment","notification_intent","delivery_attempt_or_state","itsm_incident_ticket_task_behavior","arbitrary_or_unbounded_policy_dsl"):
        require(item in forbidden,f"missing exclusion: {item}")
    print("g7_authorization_falsification=PASS policy_lifecycle=allowed g8_plus=blocked production=blocked")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
