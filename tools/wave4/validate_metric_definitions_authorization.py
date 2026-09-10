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

    for marker in (
        "METRIC DEFINITION IDENTITY != PROVIDER ITEM ID",
        "METRIC DEFINITION != PROVIDER BINDING",
        "ITEM.GET LASTVALUE != AUTHORIZED CURRENT-STATE INGESTION IN THIS SLICE",
        "ITEM.GET METADATA != METRIC HISTORY",
        "SCOPE EXCLUSION != METRIC RETIREMENT",
        "GENERATION RETIREMENT != METRIC RETIREMENT",
        "PROVIDER DISABLED/UNSUPPORTED != METRIC RETIREMENT",
        "VALUE-KIND DRIFT != SILENT IN-PLACE COMPATIBILITY",
        "UNCERTAINTY != NEGATIVE EVIDENCE",
        "ITEM-DEFINITION POLL AUTHORITY != HOST-INVENTORY POLL AUTHORITY",
        "SHARED RECOVERY LAWS != SHARED STREAM STATE",
        "provider_object_kind = zabbix_item",
        "Boolean is not inferred from integer `0/1`",
    ):
        require(marker in auth, f"missing authorization invariant: {marker}")

    forbidden = {
        "metric_current_state_persistence",
        "item_get_lastvalue_as_current_state",
        "metric_history_ingestion",
        "history_get",
        "metric_observation_storage",
        "trigger_problem_event_ingestion",
        "health_projection",
        "provider_write_back",
        "reuse_host_inventory_poll_epoch_generation_or_runtime_admission_for_item_definitions",
        "provider_disabled_or_unsupported_as_metric_retirement",
        "silent_in_place_value_kind_mutation",
        "automatic_metric_successor_identity_for_value_kind_drift",
        "frontend_route_or_navigation_creation",
        "production_deployment",
    }
    require(forbidden <= set(manifest["explicitly_not_authorized"]), "explicit exclusion set is incomplete")

    authorized = set(manifest["authorized_behavior"])
    invariants = set(manifest["required_invariants"])
    for capability in (
        "separate_zabbix_item_binding_and_provenance",
        "canonical_resource_ownership_required",
        "retirement_only_from_complete_authoritative_negative_item_snapshot",
        "provider_disabled_or_unsupported_retained_as_binding_evidence",
        "value_kind_drift_enters_reconciliation_required",
        "reuse_accepted_recovery_laws_and_trusted_authority_pattern",
        "independent_item_definition_poll_epoch_generation_and_admission_state",
    ):
        require(capability in authorized, f"missing authorized capability: {capability}")

    for invariant in (
        "provider_disabled_or_unsupported_not_metric_retirement",
        "value_kind_drift_not_silent_in_place_compatibility",
        "item_definition_poll_authority_independent_from_host_inventory_poll_authority",
        "shared_recovery_laws_do_not_mean_shared_stream_state",
    ):
        require(invariant in invariants, f"missing invariant: {invariant}")

    print("wave4_metric_definitions_authorization=PASS state=proposed slice=item_get_to_metric_definitions_and_bindings lifecycle=fail-closed poll_authority=item-definition-independent implementation=blocked")


if __name__ == "__main__":
    main()
