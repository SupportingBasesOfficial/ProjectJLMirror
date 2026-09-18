#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MANIFEST=ROOT/"implementation/g5-problem-health-authorization/AUTHORIZATION_MANIFEST.json"

def require(ok: bool, msg: str) -> None:
    if not ok:
        raise AssertionError(msg)

def main() -> int:
    data=json.loads(MANIFEST.read_text(encoding="utf-8"))
    policy=data["implementation_path_policy"]
    require(data["authorization_id"]=="g5.problem-health@1","authorization id drift")
    require("apps/g5-problem-health/" in policy["allowed_prefixes"],"canonical app prefix missing")
    require("sql/g5/" not in policy["allowed_prefixes"],"parallel SQL authority forbidden")
    require("src/jlmirror_g5/" not in policy["allowed_prefixes"],"parallel domain authority forbidden")
    forbidden=set(data["explicitly_not_authorized"])
    for item in (
        "monitoring_to_alerting_transport_changes",
        "alert_creation_resolution_policy_or_evaluation",
        "jlmirror_ack_or_responsibility",
        "itsm_incident_ticket_task_behavior",
        "provider_write_back",
    ):
        require(item in forbidden,f"missing exclusion: {item}")
    print("g5_authorization_falsification=PASS parallel_truth=blocked alerting=blocked ack=blocked itsm=blocked provider_writeback=blocked")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
