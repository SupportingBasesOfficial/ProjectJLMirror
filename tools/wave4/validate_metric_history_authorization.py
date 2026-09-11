#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTH = ROOT / "implementation/wave-4-metric-history-authorization/AUTHORIZATION.md"
MANIFEST = ROOT / "implementation/wave-4-metric-history-authorization/AUTHORIZATION_MANIFEST.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"WAVE4_METRIC_HISTORY_AUTHORIZATION_ERROR: {message}")


def main() -> None:
    require(AUTH.is_file(), "missing authorization document")
    require(MANIFEST.is_file(), "missing authorization manifest")

    auth = AUTH.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    require(manifest["authorization_id"] == "wave4.monitoring-metric-history@1", "wrong authorization id")
    require(manifest["base_commit"] == "033222f023e09f0ab0339f8e0237bb2b8345ce08", "wrong canonical base")
    require(manifest["authorized_slice"] == "history_get_and_pending_acceptance_to_metric_observation", "wrong bounded slice")
    require(manifest["implementation_authority_before_merge"] == "blocked", "implementation must remain blocked before merge")
    require(manifest["production_authority"] == "none", "production authority must remain absent")
    require(manifest["frontend_authority"] == "not_granted", "frontend authority must remain absent")
    require(manifest["merge_authorization"] == "not_granted", "authorization package cannot self-authorize merge")

    required = set(manifest["required_invariants"])
    for invariant in {
        "history_separate_from_current_state",
        "canonical_observation_identity_scoped_by_tenant_source_generation",
        "provider_event_time_not_append_position",
        "fast_high_water_mark_not_completeness",
        "clock_second_not_safe_cursor_by_itself",
        "late_arrival_not_duplicate",
        "pending_history_obligation_not_projected_history",
        "historical_generation_not_current_authority",
        "history_checkpoint_authority_independent_from_current_poll_authority",
        "history_checkpoint_authority_independent_from_item_definition_poll_authority",
        "history_checkpoint_authority_independent_from_host_inventory_poll_authority",
        "uncertainty_not_complete",
        "retention_loss_not_successful_backfill",
        "history_api_cursor_not_hidden_authority_snapshot",
        "cursor_possession_not_read_authority",
    }:
        require(invariant in required, f"missing invariant: {invariant}")

    authorized = set(manifest["authorized_behavior"])
    for behavior in {
        "bounded_read_only_zabbix_history_get",
        "history_get_as_metric_observation_stream",
        "canonical_owner_bound_metric_observation_projection",
        "idempotent_projection_from_pending_accepted_observation",
        "direct_history_acceptance_converges_with_current_acceptance_identity",
        "immutable_metric_observation_after_acceptance",
        "per_item_value_type_logical_history_checkpoint",
        "endpoint_specific_history_recovery_safe_authority",
        "inclusive_boundary_overlap",
        "same_second_ns_aware_completeness",
        "truncation_blocks_unsafe_checkpoint_advance",
        "provisional_high_water_mark_as_optimization_only",
        "bounded_background_late_arrival_reconciliation",
        "explicit_history_gap_when_retention_prevents_recovery",
        "crash_safe_observation_projection_and_checkpoint_advance",
        "idempotent_window_replay",
        "bounded_time_range_history_reads",
        "observation_id_anchor_cursor_with_metric_window_generation_revalidation",
        "history_response_no_store",
        "historical_generation_backfill_without_current_authority",
        "telemetry_port_storage_abstraction_preserved",
    }:
        require(behavior in authorized, f"missing authorized behavior: {behavior}")

    blocked = set(manifest["explicitly_not_authorized"])
    for item in {
        "history_mutates_metric_current_state",
        "item_get_latest_as_history_completeness",
        "strict_clock_plus_one_only_cursor",
        "single_forward_pass_as_complete_history",
        "checkpoint_advance_after_truncated_or_uncertain_page",
        "global_checkpoint_shared_across_item_streams",
        "final_completeness_without_lateness_retention_evidence",
        "fabricated_history_observations",
        "hidden_provider_retention_gap",
        "rewrite_immutable_historical_observation",
        "unbounded_history_api_scan",
        "hidden_protected_history_cursor_state",
        "shared_public_history_cache",
        "irreversible_production_telemetry_store_selection",
        "health_projection",
        "frontend_route_or_navigation_creation",
        "production_deployment",
    }:
        require(item in blocked, f"missing explicit exclusion: {item}")

    for marker in (
        "HISTORY != CURRENT STATE",
        "PROVIDER EVENT TIME != APPEND POSITION",
        "FAST HIGH-WATER MARK != COMPLETENESS",
        "ONE FORWARD PASS != FINALIZATION",
        "CLOCK SECOND != SAFE CURSOR BY ITSELF",
        "CURRENT PENDING HISTORY OBLIGATION != PROJECTED HISTORY",
        "HISTORY CHECKPOINT AUTHORITY != CURRENT POLL AUTHORITY",
        "HISTORY API CURSOR != HIDDEN AUTHORITY SNAPSHOT",
        "CURSOR POSSESSION != READ AUTHORITY",
        "Historical generation is valid history",
        "Single durable acceptance boundary",
        "Current-created obligations are first-class",
        "Inclusive overlap is required",
        "Same-second completeness is explicit",
        "Late-arrival reconciliation is mandatory",
        "Finalization is evidence-bound",
        "Retention loss becomes a visible gap",
        "Checkpoint advancement is crash-safe",
        "History cursor follows the accepted anchor profile",
        "History responses are `no_store`",
        "Physical storage remains behind the telemetry port",
    ):
        require(marker in auth, f"authorization marker missing: {marker}")

    for forbidden in (
        "history may mutate metric_current_state",
        "clock + 1 is the authoritative cursor",
        "one forward pass proves completeness",
        "history storage vendor is permanently selected",
    ):
        require(forbidden not in auth.lower(), f"forbidden authority leaked: {forbidden}")

    surfaces = set(manifest["contract_surfaces"])
    for surface in {
        "docs/03-domains/monitoring-domain-contract.md",
        "docs/08-data/telemetry-plane.md",
        "docs/09-api-contracts/monitoring-domain-api-contract.md",
        "docs/09-api-contracts/zabbix-monitoring-source-provider-contract.md",
        "docs/16-implementation-readiness/16-wave-4-monitoring-entry-gate.md",
    }:
        require(surface in surfaces, f"missing contract surface: {surface}")

    print(
        "wave4_metric_history_authorization=PASS "
        "id=wave4.monitoring-metric-history@1 "
        "history_get=authorized observation=owner-bound replay=idempotent "
        "checkpoint=per-stream late_arrival=reconciled completeness=evidence-bound "
        "api_cursor=observation-anchor cache=no-store current_mutation=blocked "
        "frontend=blocked production=blocked"
    )


if __name__ == "__main__":
    main()
