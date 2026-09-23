#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MANIFEST=ROOT/"implementation/g8-human-operations-authorization/AUTHORIZATION_MANIFEST.json"


def require(ok:bool,msg:str)->None:
    if not ok:
        raise AssertionError(msg)


def main()->int:
    data=json.loads(MANIFEST.read_text(encoding="utf-8"))
    policy=data["implementation_path_policy"]

    require(data["authorization_id"]=="g8.human-operations@1","authorization id drift")
    require("apps/g8-human-operations/" in policy["allowed_prefixes"],"app prefix missing")
    require("sql/human_operations/001_human_operations.sql" in policy["allowed_exact_paths"],"exact SQL missing")
    require(data["human_operations_authority"]=="responsibility_ack_current_action_and_native_visibility_only","G8 authority widened")

    relations=set(policy["exact_sql_allowed_relations"])
    require(len(relations)==6,"G8 relation surface widened")
    require("human_operations.alert_acknowledgement" in relations,"ACK relation missing")
    require("human_operations.visibility_receipt" in relations,"visibility receipt missing")

    forbidden=set(data["explicitly_not_authorized"])
    for item in (
        "notification_intent",
        "dispatch_provider_acceptance_or_delivery_state",
        "external_channel_read_receipts",
        "budget_quote_or_approval_workflow",
        "itsm_incident_ticket_task_behavior",
        "provider_write_back",
    ):
        require(item in forbidden,f"missing exclusion: {item}")

    print("g8_authorization_falsification=PASS human_operations=allowed g9_plus=blocked production=blocked")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
