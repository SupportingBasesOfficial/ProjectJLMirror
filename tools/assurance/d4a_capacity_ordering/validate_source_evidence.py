from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "implementation/d4-eventing-async/source-evidence/capacity-ordering/source-evidence-manifest.json"
PROFILE = ROOT / "implementation/d4-eventing-async/source-evidence/capacity-ordering/benchmark-profile.json"
PLAN = ROOT / "implementation/d4-eventing-async/d4-a-evidence-plan.json"
STATE = ROOT / "implementation/d4-eventing-async/state-manifest.json"

EXPECTED_IDS = {
    "capacity_envelope_baseline_growth_stress",
    "ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency",
}
EXPECTED_KINDS = {
    "capacity_envelope_baseline_growth_stress": "real_candidate_benchmark",
    "ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency": "real_candidate_benchmark_and_concurrency_probe",
}
EXPECTED_SCOPES = {
    "unordered", "causal_only", "per_subject_ordered", "per_process_ordered", "per_source_ordered", "custom_bounded_order"
}
EXPECTED_PRIOR_CREDIT = {
    "broker_neutral_anti_corruption_stub_swap",
    "regulated_payload_erasure_granularity",
    "exactly_once_guardrail_consumer_inbox_enforcement",
    "physical_naming_routing_and_cell_topology_adapter_mapping",
}
EXPECTED_IMAGE_INDEX = "sha256:77e3df9054047a88b520d0cc46e16696d3b22022e1d580aeccd2632df6532837"
EXPECTED_AMD64_MANIFEST = "sha256:ccd1314e47ec76909e01f86308b4dcf2064f19f7c89759234322314b0e319e26"
EXPECTED_IMAGE = f"apache/kafka:4.3.1@{EXPECTED_IMAGE_INDEX}"


def main() -> None:
    source = json.loads(MANIFEST.read_text())
    profile = json.loads(PROFILE.read_text())
    plan = json.loads(PLAN.read_text())
    state = json.loads(STATE.read_text())
    d4a = next(t for t in state["tracks"] if t["track_id"] == "D4-A")

    assert source["canonical_base_commit"] == "32a35e9d9d695e9a37ed4ea3499b5598b0005a1e"
    assert source["candidate"] == "kafka"
    assert source["candidate_status"] == "leading_candidate_closure_pending"
    assert source["candidate_version"] == "4.3.1"
    assert source["candidate_image"] == EXPECTED_IMAGE
    assert source["candidate_image_index_digest"] == EXPECTED_IMAGE_INDEX
    assert source["candidate_linux_amd64_manifest_digest"] == EXPECTED_AMD64_MANIFEST
    assert source["candidate_pin_authority"] == "bounded_c2_test_candidate_only"
    assert set(source["evidence_ids"]) == EXPECTED_IDS
    assert source["evidence_kinds"] == EXPECTED_KINDS
    assert set(source["prior_promoted_ledger_credit"]) == EXPECTED_PRIOR_CREDIT
    assert source["scope"] == "source_evidence_harness_only"
    assert source["live_kafka_broker_claimed"] is True
    assert source["capacity_benchmark_claimed"] is True
    assert source["ordering_benchmark_claimed"] is True
    assert source["outage_recovery_benchmark_claimed"] is False
    assert source["current_run_auto_credit"] is False
    assert source["ledger_credit"] == []
    assert source["kafka_selection_state"] == "not_selected"
    assert source["source_run_provenance"]["mode"] == "runtime_resolved_artifact_required"
    assert source["source_run_provenance"]["benchmark_result_required"] is True
    assert source["promotion_rule"] == "source_run_review_then_separate_ledger_promotion"

    assert profile["numeric_authority"] == "test_values_only_not_production"
    assert [tier["name"] for tier in profile["tiers"]] == ["Baseline", "Growth", "Stress"]
    for tier in profile["tiers"]:
        assert tier["message_count"] > 0
        assert tier["record_size_bytes"] > 0
        assert tier["target_messages_per_second"] > 0
        assert len(tier["tenant_weights"]) >= 2
        assert sum(tier["tenant_weights"].values()) == 100
        assert tier["partition_probe_counts"] == sorted(set(tier["partition_probe_counts"]))
        assert len(tier["partition_probe_counts"]) >= 3
        assert tier["backlog_pause_seconds"] > 0

    assert set(profile["ordering_scope_mappings"]) == EXPECTED_SCOPES
    for scope in EXPECTED_SCOPES:
        assert "partition_key" in profile["ordering_scope_mappings"][scope]
        assert "serialization" in profile["ordering_scope_mappings"][scope]
    component = source["ordering_component"]
    assert component["name"] == "JLMIRROR KeySerialExecutor"
    assert component["implementation_path"] == "tools/assurance/d4a_capacity_ordering/key_serial_executor.py"
    assert component["pattern"] == "consumer_side_key_level_virtual_sequencing_bounded_per_key_concurrency"
    assert component["global_or_tenant_wide_serialization"] is False
    assert "OPEN-EVT-001-kafka-decision-record.md" in component["pattern_citation"]
    fallback = profile["tenant_cohort_fallback"]
    assert fallback["cohort_count"] >= 2
    assert fallback["logical_contract_identity_changes"] is False

    assert EXPECTED_PRIOR_CREDIT == set(plan["credited_evidence"])
    assert EXPECTED_IDS.isdisjoint(set(plan["credited_evidence"]))
    assert EXPECTED_IDS.issubset(set(d4a["evidence_remaining"]))
    assert set(d4a["evidence_completed"]) == set(plan["credited_evidence"])
    assert plan["ledger_credit_state"] == "four_of_seven"

    assert state["gate_state"] == "scoped"
    assert state["d4_transport_authority"] == "not_selected_not_granted"
    assert state["canonical_product_implementation_authority"] == "not_granted"
    assert state["wave4_implementation_authority"] == "not_granted"
    assert state["production_authority"] == "none"
    assert state["c3_numeric_topology_authority"] == "not_selected"

    print("d4a_capacity_ordering_source_manifest=PASS evidence=2 ledger_credit=0 live_kafka=required immutable_pin=PASS tiers=3 ordering_scopes=6 kafka=not_selected authorities=not_granted")


if __name__ == "__main__":
    main()
