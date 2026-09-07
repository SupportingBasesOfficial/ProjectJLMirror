#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

MANIFEST = Path("implementation/d4-eventing-async/state-manifest.json")
EXPECTED_BASE = "ee8775fc5e7a25b1c4e166a8bb48b53438f6bd42"
EXPECTED_TRACK_SOURCES = {
    "D4-A": ["OPEN-EVT-001", "OPEN-EVT-005", "OPEN-REL-012.A"],
    "D4-B": ["OPEN-EVT-002", "OPEN-EVT-003", "OPEN-EVT-004"],
    "D4-C": ["OPEN-EVT-008", "OPEN-EVT-009", "OPEN-EVT-010", "OPEN-EVT-011", "OPEN-EVT-012", "OPEN-EVT-013", "OPEN-EVT-014", "OPEN-EVT-015", "OPEN-EVT-025"],
    "D4-D": ["OPEN-EVT-016", "OPEN-EVT-017", "OPEN-EVT-018"],
}
EXPECTED_REQUIRED_EVIDENCE = {
    "D4-A": [
        "capacity_envelope_baseline_growth_stress",
        "broker_neutral_anti_corruption_stub_swap",
        "regulated_payload_erasure_granularity",
        "exactly_once_guardrail_consumer_inbox_enforcement",
        "ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency",
        "physical_naming_routing_and_cell_topology_adapter_mapping",
        "broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark",
    ],
    "D4-B": [
        "canonical_bounded_serialization_profile",
        "parser_ambiguity_and_duplicate_field_negative_vectors",
        "schema_catalog_semantic_manifest_compatibility_ci",
        "historical_reader_and_equivalence_profile_continuity",
        "contract_version_representation_and_breaking_change_vectors",
    ],
    "D4-C": [
        "ack_after_durable_responsibility_and_lease_ambiguity",
        "quarantine_redrive_current_authority_and_dedup_preservation",
        "bounded_message_batch_compression_and_parser_limits",
        "scoped_content_equivalence_confidentiality_and_conflict_rejection",
        "outbox_claim_dispatch_ack_ambiguity_and_recovery_continuity",
        "producer_generation_nonresurrection_across_failover_restore",
        "privileged_bounded_replay_with_original_identity_and_effect_safety",
        "historical_reader_upcaster_semantic_and_equivalence_continuity",
        "recovery_generation_rf_inventory_reconciliation_and_activation_gates",
    ],
    "D4-D": [
        "workload_identity_to_broker_credential_adapter_least_privilege",
        "tenant_and_contract_scoped_producer_consumer_authorization",
        "message_protection_key_authority_and_historical_verifier_continuity",
        "secret_credential_payload_exclusion_and_erasure_boundary",
        "trace_context_observability_only_validation_and_redaction",
    ],
}
EXPECTED_COMPLETED = {
    "D4-A": list(EXPECTED_REQUIRED_EVIDENCE["D4-A"]),
    "D4-B": list(EXPECTED_REQUIRED_EVIDENCE["D4-B"]),
    "D4-C": list(EXPECTED_REQUIRED_EVIDENCE["D4-C"]),
    "D4-D": ["workload_identity_to_broker_credential_adapter_least_privilege"],
}
EXPECTED_TOTAL_EVIDENCE = 26
EXPECTED_TOTAL_CREDITED = 22
EXPECTED_D4B_CANDIDATE = {
    "serialization": {
        "surface_policy": "explicit_surface_bound_profiles",
        "internal_broker": "protobuf_profile",
        "outbound_webhook": "bounded_json_plus_json_schema_profile",
    },
    "schema_catalog": "hybrid_reviewed_git_plus_registry_catalog",
    "contract_version": "positive_integer_family_revision",
}
EXPECTED_C3_EXCLUSIONS = {
    "OPEN-EVT-006", "OPEN-EVT-007", "OPEN-EVT-019", "OPEN-EVT-026", "OPEN-EVT-027", "OPEN-EVT-028",
    "OPEN-REL-012.B", "production_partition_counts", "production_retry_backoff_jitter_numerics",
    "production_retention_lag_replay_quarantine_horizons", "production_realtime_buffer_session_numerics",
}
EXPECTED_LATER_EXCLUSIONS = {
    "OPEN-EVT-020", "OPEN-EVT-021", "OPEN-EVT-022", "OPEN-EVT-023", "OPEN-EVT-024",
    "wave4_monitoring_product_implementation", "production_deployment",
}


def load_manifest(root: Path) -> dict:
    return json.loads((root / MANIFEST).read_text(encoding="utf-8"))


def validate_manifest(state: dict) -> list[str]:
    errors: list[str] = []

    def require(ok: bool, message: str) -> None:
        if not ok:
            errors.append(message)

    require(state.get("schema_version") == 1, "schema_version must be 1")
    require(state.get("gate_id") == "D4" and state.get("gate_name") == "eventing_async_transport_c2", "D4 identity drift")
    require(state.get("canonical_base") == EXPECTED_BASE, "D4 canonical_base drift")
    predecessor = state.get("predecessor", {})
    require(predecessor == {"gate_id": "D3", "state": "separately_accepted", "canonical_commit": EXPECTED_BASE}, "D3 predecessor drift")
    require(state.get("gate_state") == "scoped", "D4 must remain scoped until separate full acceptance")
    require(state.get("d4_transport_authority") == "selected_not_granted", "D4 transport must be selected but authority must remain ungranted")
    require(state.get("canonical_product_implementation_authority") == "not_granted", "D4 must not grant canonical Product implementation authority")
    require(state.get("wave4_implementation_authority") == "not_granted", "D4 must not grant Wave 4 implementation authority")
    require(state.get("production_authority") == "none", "D4 must not grant production authority")
    require(state.get("c3_numeric_topology_authority") == "not_selected", "D4 must not select C3 numeric/topology authority")

    tracks = state.get("tracks")
    require(isinstance(tracks, list) and all(isinstance(t, dict) for t in tracks), "tracks must be object list")
    if not isinstance(tracks, list) or not all(isinstance(t, dict) for t in tracks):
        return errors
    ids = [t.get("track_id") for t in tracks]
    require(ids == ["D4-A", "D4-B", "D4-C", "D4-D"], "D4 track identity/order drift")
    require(len(ids) == len(set(ids)), "D4 duplicate track_id is forbidden")
    by_id = {t["track_id"]: t for t in tracks if t.get("track_id") in EXPECTED_TRACK_SOURCES}
    if set(by_id) != set(EXPECTED_TRACK_SOURCES):
        errors.append("D4 track set drift")
        return errors

    for track_id in ("D4-A", "D4-B", "D4-C", "D4-D"):
        track = by_id[track_id]
        required = EXPECTED_REQUIRED_EVIDENCE[track_id]
        completed = EXPECTED_COMPLETED[track_id]
        remaining = [x for x in required if x not in completed]
        require(track.get("source_decisions") == EXPECTED_TRACK_SOURCES[track_id], f"{track_id} source decision drift")
        require(track.get("required_evidence") == required, f"{track_id} required evidence inventory drift")
        require(track.get("evidence_completed") == completed, f"{track_id} completed evidence drift")
        require(track.get("evidence_remaining") == remaining, f"{track_id} remaining evidence drift")
        require(len(track.get("evidence_completed", [])) == len(set(track.get("evidence_completed", []))), f"{track_id} completed evidence multiplicity drift")
        require(set(track.get("evidence_completed", [])).isdisjoint(track.get("evidence_remaining", [])), f"{track_id} completed/remaining overlap")

    d4a, d4b, d4c, d4d = (by_id[x] for x in ("D4-A", "D4-B", "D4-C", "D4-D"))
    require(d4a.get("candidate") == "kafka" and d4a.get("candidate_status") == "selected_c2_candidate" and d4a.get("state") == "selected_candidate", "D4-A selected candidate drift")
    require(d4b.get("candidate") == EXPECTED_D4B_CANDIDATE and d4b.get("candidate_status") == "selected_c2_profile" and d4b.get("state") == "selected_candidate", "D4-B selected profile drift")
    for track_id, track in (("D4-C", d4c), ("D4-D", d4d)):
        require(track.get("candidate") is None, f"{track_id} must not silently select a candidate")
        require(track.get("candidate_status") == "not_selected", f"{track_id} candidate status must remain not_selected")
        require(track.get("state") == "candidate_selection_open", f"{track_id} scoped state drift")

    require(sum(len(t.get("required_evidence", [])) for t in tracks) == EXPECTED_TOTAL_EVIDENCE, "D4 total required evidence inventory drift")
    require(sum(len(t.get("evidence_completed", [])) for t in tracks) == EXPECTED_TOTAL_CREDITED, "D4 total credited evidence drift")
    require(set(state.get("explicit_c3_exclusions", [])) == EXPECTED_C3_EXCLUSIONS, "D4 C3 exclusion set drift")
    require(set(state.get("explicit_product_or_later_gate_exclusions", [])) == EXPECTED_LATER_EXCLUSIONS, "D4 Product/later-gate exclusion set drift")
    require("separate_acceptance" in state.get("acceptance_rule", ""), "D4 acceptance must remain a separate action")
    require("separate_explicit_user_authorization" in state.get("merge_rule", ""), "D4 merge rule must require separate explicit user authorization")
    return errors


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    state = load_manifest(root)
    errors = validate_manifest(state)
    if errors:
        for error in errors:
            print(f"D4_STATE_ERROR: {error}", file=sys.stderr)
        return 1
    print("d4_eventing_async_state=PASS evidence_required=26 evidence_credited=22 d4a=7_of_7 d4b=5_of_5 d4c=9_of_9 d4d=1_of_5 selection_open authorities=unchanged")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
