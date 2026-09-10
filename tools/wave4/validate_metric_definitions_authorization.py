#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTH = ROOT / "implementation/wave-4-metric-definitions-authorization/AUTHORIZATION.md"
MANIFEST = ROOT / "implementation/wave-4-metric-definitions-authorization/AUTHORIZATION_MANIFEST.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"WAVE4_METRIC_DEFINITIONS_AUTHORIZATION_ERROR: {message}")


def main() -> None:
    require(AUTH.is_file(), "missing AUTHORIZATION.md")
    require(MANIFEST.is_file(), "missing AUTHORIZATION_MANIFEST.json")

    auth = AUTH.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    require(manifest["authorization_id"] == "wave4.monitoring-metric-definitions@1", "wrong authorization id")
    require(manifest["authorization_state"] == "proposed", "authorization must remain proposed before merge")
    require(manifest["implementation_authority_before_merge"] == "blocked", "implementation must remain blocked before merge")
    require(manifest["merge_authorization"] == "not_granted", "merge cannot be pre-authorized")

    required_auth_markers = (
        "METRIC DEFINITION IDENTITY != PROVIDER ITEM ID",
        "METRIC DEFINITION != PROVIDER BINDING",
        "ITEM.GET LASTVALUE != AUTHORIZED CURRENT-STATE INGESTION IN THIS SLICE",
        "ITEM.GET METADATA != METRIC HISTORY",
        "SCOPE EXCLUSION != METRIC RETIREMENT",
        "GENERATION RETIREMENT != METRIC RETIREMENT",
        "UNCERTAINTY != NEGATIVE EVIDENCE",
        "provider_object_kind = zabbix_item",
        "Boolean is not inferred from integer `0/1`",
        "metric_current_state",
        "history.get",
        "frontend route or navigation creation",
    )
    for marker in required_auth_markers:
        require(marker in auth, f"missing authorization invariant: {marker}")

    forbidden_authorized = {
        "metric_current_state_persistence",
        "item_get_lastvalue_as_current_state",
        "metric_history_ingestion",
        "history_get",
        "metric_observation_storage",
        "trigger_problem_event_ingestion",
        "health_projection",
        "provider_write_back",
        "frontend_route_or_navigation_creation",
        "production_deployment",
    }
    not_authorized = set(manifest["explicitly_not_authorized"])
    require(forbidden_authorized <= not_authorized, "explicit exclusion set is incomplete")

    authorized = set(manifest["authorized_behavior"])
    require("separate_zabbix_item_binding_and_provenance" in authorized, "binding separation missing")
    require("canonical_resource_ownership_required" in authorized, "resource ownership requirement missing")
    require("retirement_only_from_complete_authoritative_negative_item_snapshot" in authorized, "negative evidence rule missing")

    print("wave4_metric_definitions_authorization=PASS state=proposed slice=item_get_to_metric_definitions_and_bindings implementation=blocked")


if __name__ == "__main__":
    main()
