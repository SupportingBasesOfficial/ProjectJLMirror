#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTH = ROOT / "implementation/wave-4-metric-current-state-authorization/AUTHORIZATION.md"
MANIFEST = ROOT / "implementation/wave-4-metric-current-state-authorization/AUTHORIZATION_MANIFEST.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"WAVE4_METRIC_CURRENT_STATE_AUTHORIZATION_ERROR: {message}")


def main() -> None:
    require(AUTH.is_file(), "missing authorization document")
    require(MANIFEST.is_file(), "missing authorization manifest")

    auth = AUTH.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    require(manifest["authorization_id"] == "wave4.monitoring-metric-current-state@1", "wrong authorization id")
    require(manifest["base_commit"] == "84e9111dadaaca5823b8e696efc1c0764596e269", "wrong canonical base")
    require(manifest["authorized_slice"] == "item_get_current_evidence_to_metric_current_state", "wrong bounded slice")
    require(manifest["implementation_authority_before_merge"] == "blocked", "implementation must remain blocked before merge")
    require(manifest["production_authority"] == "none", "production authority must remain absent")
    require(manifest["frontend_authority"] == "not_granted", "frontend authority must remain absent")
    require(manifest["merge_authorization"] == "not_granted", "authorization package cannot self-authorize merge")

    required_invariants = set(manifest["required_invariants"])
    for invariant in {
        "metric_current_state_separate_from_history",
        "provider_event_time_not_current_state_ordering_authority",
        "later_poll_generation_not_semantic_value_change",
        "last_known_value_not_current_evidence",
        "current_state_poll_authority_independent_from_item_definition_poll_authority",
        "current_state_poll_authority_independent_from_host_inventory_poll_authority",
        "active_generation_required_for_current_authority",
        "current_scope_required_for_current_authority",
    }:
        require(invariant in required_invariants, f"missing invariant: {invariant}")

    authorized = set(manifest["authorized_behavior"])
    for behavior in {
        "canonical_metric_current_state_projection",
        "endpoint_specific_current_state_poll_epoch_generation_and_admission",
        "poll_generation_as_precedence_and_fence_authority",
        "same_value_semantic_noop_without_last_changed_transition",
        "last_known_value_retained_with_noncurrent_evidence",
        "bounded_current_state_transition_outbox_on_genuine_change_only",
        "recovery_safe_fail_closed_current_authority",
    }:
        require(behavior in authorized, f"missing authorized behavior: {behavior}")

    blocked = set(manifest["explicitly_not_authorized"])
    for item in {
        "history_get",
        "metric_observation_storage",
        "metric_history_checkpoint_backfill",
        "health_projection",
        "reuse_item_definition_poll_epoch_generation_or_admission_for_current",
        "reuse_host_inventory_poll_epoch_generation_or_admission_for_current",
        "provider_timestamp_as_sole_ordering_authority",
        "duplicate_transition_for_same_value_refresh",
        "frontend_route_or_navigation_creation",
        "production_deployment",
    }:
        require(item in blocked, f"missing explicit exclusion: {item}")

    for marker in (
        "CURRENT STATE != HISTORY",
        "PROVIDER EVENT TIME != CURRENT-STATE ORDERING AUTHORITY",
        "LATER POLL GENERATION != SEMANTIC VALUE CHANGE",
        "CURRENT-STATE POLL AUTHORITY != ITEM-DEFINITION POLL AUTHORITY",
        "CURRENT-STATE POLL AUTHORITY != HOST-INVENTORY POLL AUTHORITY",
        "Poll generation is precedence/fence authority",
        "Last-known survives uncertainty without masquerading as current",
        "No history obligation from this slice",
        "Recovery fails closed",
    ):
        require(marker in auth, f"authorization marker missing: {marker}")

    forbidden_authority = (
        "history.get is authorized",
        "metric_observation persistence is authorized",
        "reuse Item Definition poll authority",
        "reuse Host Inventory poll authority",
    )
    for text in forbidden_authority:
        require(text not in auth, f"forbidden authority leaked into authorization: {text}")

    print("wave4_metric_current_state_authorization=PASS id=wave4.monitoring-metric-current-state@1 scope=current-only history=blocked poll_stream=independent frontend=blocked production=blocked")


if __name__ == "__main__":
    main()
