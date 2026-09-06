from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "implementation/d4-eventing-async/source-evidence/schema-contract/source-evidence-manifest.json"
STATE = ROOT / "implementation/d4-eventing-async/state-manifest.json"
D4C_CREDITS = [
    "ack_after_durable_responsibility_and_lease_ambiguity",
    "quarantine_redrive_current_authority_and_dedup_preservation",
    "bounded_message_batch_compression_and_parser_limits",
    "scoped_content_equivalence_confidentiality_and_conflict_rejection",
]
EXPECTED_IDS = {
    "canonical_bounded_serialization_profile",
    "parser_ambiguity_and_duplicate_field_negative_vectors",
    "schema_catalog_semantic_manifest_compatibility_ci",
    "historical_reader_and_equivalence_profile_continuity",
    "contract_version_representation_and_breaking_change_vectors",
}
EXPECTED_D4A_IDS = {
    "capacity_envelope_baseline_growth_stress",
    "broker_neutral_anti_corruption_stub_swap",
    "regulated_payload_erasure_granularity",
    "exactly_once_guardrail_consumer_inbox_enforcement",
    "ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency",
    "physical_naming_routing_and_cell_topology_adapter_mapping",
    "broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark",
}
EXPECTED_SELECTED = {
    "serialization": {
        "surface_policy": "explicit_surface_bound_profiles",
        "internal_broker": "protobuf_profile",
        "outbound_webhook": "bounded_json_plus_json_schema_profile",
    },
    "schema_catalog": "hybrid_reviewed_git_plus_registry_catalog",
    "contract_version": "positive_integer_family_revision",
}
EXPECTED_TRACK_IDS = {"D4-A", "D4-B", "D4-C", "D4-D"}
EXPECTED_KINDS = {
    "canonical_bounded_serialization_profile": "deterministic_reference_profile_and_negative_vectors",
    "parser_ambiguity_and_duplicate_field_negative_vectors": "parser_falsification_vectors",
    "schema_catalog_semantic_manifest_compatibility_ci": "machine_readable_catalog_compatibility_gate",
    "historical_reader_and_equivalence_profile_continuity": "historical_reader_equivalence_continuity_probe",
    "contract_version_representation_and_breaking_change_vectors": "version_representation_breaking_change_vectors",
}
EXPECTED_REFERENCE_PROPERTIES = {
    "single_structured_interpretation",
    "duplicate_member_rejection",
    "explicit_required_optional_null_enum_semantics",
    "bounded_depth_members_strings_arrays_and_bytes",
    "deterministic_semantic_manifest",
    "historical_reader_and_equivalence_profile_preservation",
}


def main() -> int:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    state = json.loads(STATE.read_text(encoding="utf-8"))

    assert source["schema_version"] == 1
    assert source["package_id"] == "d4-b-schema-contract-source-v1"
    assert source["canonical_base_commit"] == "790f967446bf039ba4d5f618c9f30494c720ee7c"
    assert source["gate_id"] == "D4" and source["track"] == "D4-B"
    assert source["scope"] == "source_evidence_harness_only"
    assert set(source["source_decisions"]) == {"OPEN-EVT-002", "OPEN-EVT-003", "OPEN-EVT-004"}
    assert len(source["source_decisions"]) == 3
    assert set(source["evidence_ids"]) == EXPECTED_IDS and len(source["evidence_ids"]) == 5
    assert source["evidence_kinds"] == EXPECTED_KINDS
    assert source["candidate"] is None and source["candidate_status"] == "not_selected"
    assert source["current_run_auto_credit"] is False and source["ledger_credit"] == []
    assert source["serialization_selection_state"] == "not_selected"
    assert source["schema_catalog_selection_state"] == "not_selected"
    assert source["contract_version_syntax_selection_state"] == "not_selected"
    profile = source["reference_profile"]
    assert profile["name"] == "bounded_logical_structured_message_v1"
    assert profile["authority"] == "test_reference_only_not_wire_selection"
    assert set(profile["properties"]) == EXPECTED_REFERENCE_PROPERTIES and len(profile["properties"]) == 6
    assert source["promotion_rule"] == "source_run_review_then_separate_ledger_promotion"
    assert source["selection_rule"] == "source_evidence_does_not_select_serialization_registry_or_version_syntax"
    assert source["d4_transport_authority"] == "selected_not_granted"
    assert source["canonical_product_implementation_authority"] == "not_granted"
    assert source["wave4_implementation_authority"] == "not_granted"
    assert source["production_authority"] == "none"
    assert source["c3_numeric_topology_authority"] == "not_selected"

    state_tracks = state.get("tracks")
    assert isinstance(state_tracks, list) and len(state_tracks) == 4
    assert all(isinstance(track, dict) for track in state_tracks)
    track_ids = [track.get("track_id") for track in state_tracks]
    assert len(track_ids) == len(set(track_ids)) and set(track_ids) == EXPECTED_TRACK_IDS
    tracks = {track["track_id"]: track for track in state_tracks}
    d4a, d4b, d4c, d4d = tracks["D4-A"], tracks["D4-B"], tracks["D4-C"], tracks["D4-D"]
    assert d4a["candidate"] == "kafka" and d4a["candidate_status"] == "selected_c2_candidate"
    assert d4a["state"] == "selected_candidate"
    assert set(d4a["evidence_completed"]) == EXPECTED_D4A_IDS and len(d4a["evidence_completed"]) == 7
    assert d4a["evidence_remaining"] == []
    assert d4b["candidate"] == EXPECTED_SELECTED and d4b["candidate_status"] == "selected_c2_profile"
    assert d4b["state"] == "selected_candidate"
    assert set(d4b["required_evidence"]) == EXPECTED_IDS and len(d4b["required_evidence"]) == 5
    assert set(d4b["evidence_completed"]) == EXPECTED_IDS and len(d4b["evidence_completed"]) == 5
    assert d4b["evidence_remaining"] == []

    assert d4c["candidate"] is None and d4c["candidate_status"] == "not_selected"
    assert d4c["state"] == "candidate_selection_open"
    assert d4c["evidence_completed"] == D4C_CREDITS
    expected_remaining = [x for x in d4c["required_evidence"] if x not in D4C_CREDITS]
    assert d4c["evidence_remaining"] == expected_remaining and len(expected_remaining) == 5
    assert d4d["candidate"] is None and d4d["candidate_status"] == "not_selected"
    assert d4d["evidence_completed"] == []
    assert sum(len(track["evidence_completed"]) for track in state_tracks) == 16
    assert state["gate_state"] == "scoped"
    assert state["d4_transport_authority"] == "selected_not_granted"
    assert state["canonical_product_implementation_authority"] == "not_granted"
    assert state["wave4_implementation_authority"] == "not_granted"
    assert state["production_authority"] == "none"
    assert state["c3_numeric_topology_authority"] == "not_selected"

    print(
        "d4b_schema_contract_source_manifest=PASS evidence_ids=5 evidence_kinds=exact reference_properties=exact "
        "source_credit=0 source_history=not_selected current_selection=selected_c2_profile unique_tracks=true "
        "d4a=exact_7_of_7_kafka_selected d4c=4_of_9 d4wide=16/26 d4d=open authorities=not_granted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
