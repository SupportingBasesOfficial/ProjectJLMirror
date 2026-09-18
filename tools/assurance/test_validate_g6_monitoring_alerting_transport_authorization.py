#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MANIFEST=ROOT/"implementation/g6-monitoring-alerting-transport-authorization/AUTHORIZATION_MANIFEST.json"

def require(ok:bool,msg:str)->None:
    if not ok:
        raise AssertionError(msg)

def main()->int:
    data=json.loads(MANIFEST.read_text(encoding="utf-8"))
    policy=data["implementation_path_policy"]
    require(data["authorization_id"]=="g6.monitoring-alerting-transport@1","authorization id drift")
    require("apps/g6-monitoring-alerting-transport/" in policy["allowed_prefixes"],"canonical app prefix missing")
    require("sql/integration/002_monitoring_alerting_consumer.sql" in policy["allowed_exact_paths"],"exact integration SQL missing")
    require("sql/g6/" not in policy["allowed_prefixes"],"parallel SQL authority forbidden")
    require(data["alert_business_authority"]=="none","Alert business authority widened")
    forbidden=set(data["explicitly_not_authorized"])
    for item in (
        "alert_projection_persistence",
        "alert_transition_persistence",
        "alert_creation_resolution_reopen",
        "alert_policy_identity_or_evaluation",
        "new_broker_outbox_or_inbox_substrate",
        "monitoring_business_truth_mutation",
    ):
        require(item in forbidden,f"missing exclusion: {item}")
    print("g6_authorization_falsification=PASS transport=allowed alert_business=blocked parallel_async=blocked production=blocked")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
