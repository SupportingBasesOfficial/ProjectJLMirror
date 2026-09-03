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
ORDERED_SCOPES = {"per_subject_ordered", "per_process_ordered", "per_source_ordered", "custom_bounded_order"}
EXPECTED_PRIOR_CREDIT = {
    "broker_neutral_anti_corruption_stub_swap",
    "regulated_payload_erasure_granularity",
    "exactly_once_guardrail_consumer_inbox_enforcement",
    "physical_naming_routing_and_cell_topology_adapter_mapping",
}
EXPECTED_IMAGE_INDEX = "sha256:77e3df9054047a88b520d0cc46e16696d3b22022e1d580aeccd2632df6532837"
EXPECTED_AMD64_MANIFEST = "sha256:ccd1314e47ec76909e01f86308b4dcf2064f19f7c89759234322314b0e319e26"
EXPECTED_IMAGE = f"apache/kafka:4.3.1@{EXPECTED_IMAGE_INDEX}"
FORBIDDEN_PHYSICAL_KEY_TOKENS = ("topic", "partition", "offset", "consumer_group", "group_id", "cell")


def load_objects() -> tuple[dict, dict, dict, dict]:
    return (
        json.loads(MANIFEST.read_text()),
        json.loads(PROFILE.read_text()),
        json.loads(PLAN.read_text()),
        json.loads(STATE.read_text()),
    )


def validate_objects(source: dict, profile: dict, plan: dict, state: dict) -> list[str]:
    errors: list[str] = []
    d4a = next((t for t in state.get("tracks", []) if t.get("track_id") == "D4-A"), {})

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    require(source.get("canonical_base_commit") == "32a35e9d9d695e9a37ed4ea3499b5598b0005a1e", "canonical base drift")
    require(source.get("candidate") == "kafka" and source.get("candidate_status") == "leading_candidate_closure_pending", "candidate state drift")
    require(source.get("candidate_version") == "4.3.1", "candidate version drift")
    require(source.get("candidate_image") == EXPECTED_IMAGE, "Kafka image pin drift")
    require(source.get("candidate_image_index_digest") == EXPECTED_IMAGE_INDEX, "Kafka index digest drift")
    require(source.get("candidate_linux_amd64_manifest_digest") == EXPECTED_AMD64_MANIFEST, "Kafka amd64 digest drift")
    require(source.get("candidate_pin_authority") == "bounded_c2_test_candidate_only", "candidate pin authority drift")
    require(set(source.get("evidence_ids", [])) == EXPECTED_IDS, "source evidence inventory drift")
    require(source.get("evidence_kinds") == EXPECTED_KINDS, "source evidence kind drift")
    require(set(source.get("prior_promoted_ledger_credit", [])) == EXPECTED_PRIOR_CREDIT, "prior promoted credit drift")
    require(source.get("scope") == "source_evidence_harness_only", "source scope drift")
    require(source.get("live_kafka_broker_claimed") is True, "live Kafka claim missing")
    require(source.get("capacity_benchmark_claimed") is True, "capacity benchmark claim missing")
    require(source.get("ordering_benchmark_claimed") is True, "ordering benchmark claim missing")
    require(source.get("outage_recovery_benchmark_claimed") is False, "D4-A7 outage recovery overclaim")
    require(source.get("current_run_auto_credit") is False and source.get("ledger_credit") == [], "source package self-promotion")
    require(source.get("kafka_selection_state") == "not_selected", "premature Kafka selection")
    require(source.get("d4_transport_authority") == "not_selected_not_granted", "transport authority escalation")
    require(source.get("canonical_product_implementation_authority") == "not_granted", "product authority escalation")
    require(source.get("wave4_implementation_authority") == "not_granted", "Wave4 authority escalation")
    require(source.get("production_authority") == "none", "production authority escalation")
    require(source.get("c3_numeric_topology_authority") == "not_selected", "C3 authority escalation")
    provenance = source.get("source_run_provenance", {})
    require(provenance.get("mode") == "runtime_resolved_artifact_required" and provenance.get("benchmark_result_required") is True, "provenance requirement drift")
    require(source.get("promotion_rule") == "source_run_review_then_separate_ledger_promotion", "promotion rule drift")

    component = source.get("ordering_component", {})
    require(component.get("name") == "JLMIRROR KeySerialExecutor", "named ordering component drift")
    require(component.get("implementation_path") == "tools/assurance/d4a_capacity_ordering/key_serial_executor.py", "ordering component path drift")
    require(component.get("pattern") == "consumer_side_key_level_virtual_sequencing_bounded_per_key_concurrency", "ordering pattern drift")
    require(component.get("global_or_tenant_wide_serialization") is False, "global/tenant-wide serialization prohibited")
    require("OPEN-EVT-001-kafka-decision-record.md" in str(component.get("pattern_citation", "")), "ordering component citation drift")

    require(profile.get("numeric_authority") == "test_values_only_not_production", "numeric authority drift")
    require(profile.get("environment_scope") == "ephemeral_single_node_kraft_github_runner", "benchmark environment drift")
    tiers = profile.get("tiers", [])
    require([tier.get("name") for tier in tiers] == ["Baseline", "Growth", "Stress"], "tier inventory/order drift")
    previous_messages = previous_rate = 0
    for tier in tiers:
        name = str(tier.get("name", "?"))
        message_count = tier.get("message_count")
        target_rate = tier.get("target_messages_per_second")
        require(type(message_count) is int and message_count > previous_messages, f"{name} message pressure not increasing")
        require(type(target_rate) is int and target_rate > previous_rate, f"{name} rate pressure not increasing")
        previous_messages = message_count if type(message_count) is int else previous_messages
        previous_rate = target_rate if type(target_rate) is int else previous_rate
        require(type(tier.get("record_size_bytes")) is int and tier.get("record_size_bytes", 0) > 0, f"{name} record size invalid")
        weights = tier.get("tenant_weights", {})
        require(isinstance(weights, dict) and len(weights) >= 2 and sum(weights.values()) == 100, f"{name} tenant weights invalid")
        if isinstance(weights, dict) and weights:
            require(max(weights.values()) > 100 / len(weights), f"{name} tenant skew missing")
        probes = tier.get("partition_probe_counts", [])
        require(isinstance(probes, list) and len(probes) >= 3 and probes == sorted(set(probes)) and all(type(v) is int and v > 0 for v in probes), f"{name} partition probes invalid")
        require(tier.get("backlog_pause_seconds", 0) > 0, f"{name} backlog pause invalid")
        admission = tier.get("admission", {})
        require(admission.get("minimum_records_per_second", 0) > 0, f"{name} minimum throughput admission invalid")
        require(admission.get("maximum_avg_latency_ms", 0) > 0, f"{name} max latency admission invalid")

    degradation = profile.get("degradation_probe", {})
    require(degradation.get("mechanism") == "real_kafka_client_producer_byte_rate_quota", "degradation mechanism must use real Kafka quota")
    require(degradation.get("client_id") == "jlmirror-d4a-quota-probe", "degradation client id drift")
    require(type(degradation.get("producer_byte_rate")) is int and degradation.get("producer_byte_rate", 0) > 0, "degradation byte-rate invalid")
    drop = degradation.get("minimum_throughput_drop_fraction")
    require(type(drop) in (int, float) and 0 < drop < 1, "degradation drop threshold invalid")
    require(profile.get("partition_ceiling_policy", {}).get("definition") == "highest_tested_partition_count_meeting_bounded_tier_admission", "partition ceiling policy drift")

    mappings = profile.get("ordering_scope_mappings", {})
    require(set(mappings) == EXPECTED_SCOPES, "ordering scope coverage drift")
    for scope, mapping in mappings.items():
        key = str(mapping.get("partition_key", "")).lower()
        require(not any(token in key for token in FORBIDDEN_PHYSICAL_KEY_TOKENS), f"{scope} partition key leaks physical transport identity")
        if scope in ORDERED_SCOPES:
            require(mapping.get("serialization") == "key_serial", f"{scope} must use key_serial")
        else:
            require(mapping.get("serialization") == "none", f"{scope} must not claim ordering serialization")

    fallback = profile.get("tenant_cohort_fallback", {})
    require(fallback.get("cohort_count") == 2, "bounded fallback must exercise exactly two cohorts")
    require("trusted_tenant_identity" in str(fallback.get("mapping", "")), "fallback mapping must derive from trusted tenant identity")
    require(fallback.get("exercise") == "real_kafka_cohort_topics_with_each_topic_at_or_below_bounded_test_ceiling", "fallback must exercise real cohort topics")
    require(fallback.get("logical_contract_identity_changes") is False, "fallback must not change logical contract identity")

    require(set(plan.get("credited_evidence", [])) == EXPECTED_PRIOR_CREDIT, "existing four-of-seven credit drift")
    require(EXPECTED_IDS.isdisjoint(set(plan.get("credited_evidence", []))), "source evidence already credited")
    require(EXPECTED_IDS.issubset(set(d4a.get("evidence_remaining", []))), "source evidence missing from remaining ledger")
    require(set(d4a.get("evidence_completed", [])) == EXPECTED_PRIOR_CREDIT, "D4-A completed evidence drift")
    require(plan.get("ledger_credit_state") == "four_of_seven" and plan.get("selection_state") == "not_selected", "plan authority state drift")
    require(state.get("gate_state") == "scoped", "D4 gate must remain scoped")
    require(state.get("d4_transport_authority") == "not_selected_not_granted", "state transport authority escalation")
    require(state.get("canonical_product_implementation_authority") == "not_granted", "state product authority escalation")
    require(state.get("wave4_implementation_authority") == "not_granted", "state Wave4 authority escalation")
    require(state.get("production_authority") == "none", "state production authority escalation")
    require(state.get("c3_numeric_topology_authority") == "not_selected", "state C3 authority escalation")
    return errors


def main() -> None:
    errors = validate_objects(*load_objects())
    if errors:
        raise AssertionError("; ".join(errors))
    print("d4a_capacity_ordering_source_manifest=PASS evidence=2 ledger_credit=0 live_kafka=required immutable_pin=PASS tiers=3 ordering_scopes=6 quota=required kafka=not_selected authorities=not_granted")


if __name__ == "__main__":
    main()
