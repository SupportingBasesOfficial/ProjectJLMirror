from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "implementation/d4-eventing-async/source-evidence/recovery/source-evidence-manifest.json"
PROFILE = ROOT / "implementation/d4-eventing-async/source-evidence/recovery/recovery-profile.json"
PLAN = ROOT / "implementation/d4-eventing-async/d4-a-evidence-plan.json"
STATE = ROOT / "implementation/d4-eventing-async/state-manifest.json"

EVIDENCE_ID = "broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark"
EVIDENCE_KIND = "real_candidate_failure_recovery_benchmark"
PRIOR_CREDIT = {
    "capacity_envelope_baseline_growth_stress",
    "broker_neutral_anti_corruption_stub_swap",
    "regulated_payload_erasure_granularity",
    "exactly_once_guardrail_consumer_inbox_enforcement",
    "ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency",
    "physical_naming_routing_and_cell_topology_adapter_mapping",
}
EXPECTED_IMAGE_INDEX = "sha256:77e3df9054047a88b520d0cc46e16696d3b22022e1d580aeccd2632df6532837"
EXPECTED_AMD64 = "sha256:ccd1314e47ec76909e01f86308b4dcf2064f19f7c89759234322314b0e319e26"
EXPECTED_IMAGE = f"apache/kafka:4.3.1@{EXPECTED_IMAGE_INDEX}"
EXPECTED_MEASUREMENTS = {
    "outbox_rows_committed_while_broker_unavailable",
    "outbox_rows_remaining_after_broker_restart",
    "backlog_drain_seconds",
    "protected_delivery_positions",
    "max_backlog_before_each_protected_delivery",
    "ambiguous_publish_attempts",
    "ambiguous_distinct_logical_message_ids",
    "broker_end_offset_before_business_effects",
    "business_effect_count_before_consumer_admission",
    "business_effect_count_after_consumer_admission",
    "duplicate_business_effects_suppressed",
}


def load_objects() -> tuple[dict, dict, dict, dict]:
    return tuple(json.loads(path.read_text()) for path in (MANIFEST, PROFILE, PLAN, STATE))  # type: ignore[return-value]


def validate_objects(source: dict, profile: dict, plan: dict, state: dict) -> list[str]:
    errors: list[str] = []

    def require(ok: bool, message: str) -> None:
        if not ok:
            errors.append(message)

    require(source.get("schema_version") == 1, "source schema drift")
    require(source.get("package_id") == "d4-a-recovery-source-v1", "source package identity drift")
    require(source.get("canonical_base_commit") == "3f517258cdade3adc55765435cc087f9a8e90c3a", "source canonical base drift")
    require(source.get("track") == "D4-A", "source track drift")
    require(source.get("candidate") == "kafka" and source.get("candidate_status") == "leading_candidate_closure_pending", "candidate state drift")
    require(source.get("candidate_version") == "4.3.1", "candidate version drift")
    require(source.get("candidate_image") == EXPECTED_IMAGE, "Kafka image pin drift")
    require(source.get("candidate_image_index_digest") == EXPECTED_IMAGE_INDEX, "Kafka index digest drift")
    require(source.get("candidate_linux_amd64_manifest_digest") == EXPECTED_AMD64, "Kafka amd64 digest drift")
    require(source.get("candidate_pin_authority") == "bounded_c2_test_candidate_only", "candidate pin authority drift")
    require(source.get("evidence_ids") == [EVIDENCE_ID], "source evidence inventory drift")
    require(source.get("evidence_kinds") == {EVIDENCE_ID: EVIDENCE_KIND}, "source evidence kind drift")
    require(set(source.get("prior_promoted_ledger_credit", [])) == PRIOR_CREDIT, "source historical prior credit drift")
    require(len(source.get("prior_promoted_ledger_credit", [])) == 6, "source historical prior credit multiplicity drift")
    require(source.get("scope") == "source_evidence_harness_only", "source scope drift")
    require(source.get("live_kafka_broker_claimed") is True, "live Kafka recovery claim missing")
    require(source.get("outage_recovery_benchmark_claimed") is True, "outage recovery benchmark claim missing")
    require(source.get("current_run_auto_credit") is False and source.get("ledger_credit") == [], "source package self-promotion")
    require(source.get("kafka_selection_state") == "not_selected", "source package selects Kafka")
    require(source.get("d4_transport_authority") == "not_selected_not_granted", "source grants D4 transport authority")
    require(source.get("canonical_product_implementation_authority") == "not_granted", "source grants Product authority")
    require(source.get("wave4_implementation_authority") == "not_granted", "source grants Wave4 authority")
    require(source.get("production_authority") == "none", "source grants production authority")
    require(source.get("c3_numeric_topology_authority") == "not_selected", "source grants C3 authority")
    require(source.get("benchmark_profile") == "implementation/d4-eventing-async/source-evidence/recovery/recovery-profile.json", "profile path drift")
    require(source.get("promotion_rule") == "source_run_review_then_separate_ledger_promotion", "promotion rule drift")

    require(profile.get("schema_version") == 1 and profile.get("profile_id") == "d4-a-recovery-bounded-v1", "recovery profile identity drift")
    require(profile.get("environment_scope") == "ci_single_node_real_kafka_candidate", "recovery environment scope drift")
    require(profile.get("numeric_authority") == "test_values_only_not_production", "bounded recovery numerics escalated")
    require(type(profile.get("partitions")) is int and profile.get("partitions", 0) > 0, "test partition count invalid")
    require(type(profile.get("committed_backlog_messages")) is int and profile.get("committed_backlog_messages", 0) >= 12, "outage backlog too weak")
    require(type(profile.get("protected_current_messages")) is int and profile.get("protected_current_messages", 0) >= 3, "protected current workload too weak")
    require(type(profile.get("normal_priority")) is int and type(profile.get("protected_priority")) is int and profile.get("protected_priority", 0) > profile.get("normal_priority", 0), "protected priority must exceed backlog priority")
    require(type(profile.get("max_backlog_dispatches_before_protected")) is int and 0 < profile.get("max_backlog_dispatches_before_protected", 0) <= 5, "anti-starvation bound invalid")
    require(type(profile.get("dispatcher_batch_limit")) is int and profile.get("dispatcher_batch_limit", 0) > 0, "dispatcher batch bound invalid")
    ambiguity = profile.get("ack_ambiguity", {})
    require(ambiguity.get("enabled") is True, "ack ambiguity probe disabled")
    require(isinstance(ambiguity.get("logical_message_id"), str) and ambiguity.get("logical_message_id"), "ack ambiguity logical identity missing")
    require(ambiguity.get("retry_same_logical_identity") is True, "ack ambiguity must reuse same logical identity")
    require(set(profile.get("required_measurements", [])) == EXPECTED_MEASUREMENTS, "recovery measurement inventory drift")
    require(len(profile.get("required_measurements", [])) == len(EXPECTED_MEASUREMENTS), "recovery measurement multiplicity drift")
    invariants = profile.get("fixed_invariants", {})
    require(invariants.get("committed_outbox_is_business_truth") is True, "outbox business truth invariant drift")
    require(invariants.get("broker_progress_is_business_effect_truth") is False, "broker progress promoted to business truth")
    require(invariants.get("same_fact_retry_reuses_message_id") is True, "stable retry identity invariant drift")
    require(invariants.get("protected_current_work_must_not_starve") is True, "protected anti-starvation invariant drift")
    require(invariants.get("backlog_must_eventually_drain") is True, "backlog drain invariant drift")

    require(plan.get("ledger_credit_state") == "six_of_seven", "global ledger must remain six_of_seven in source PR")
    require(set(plan.get("credited_evidence", [])) == PRIOR_CREDIT, "global promoted six-of-seven credit drift")
    require(EVIDENCE_ID not in set(plan.get("credited_evidence", [])), "recovery source auto-credited in plan")
    require(plan.get("selection_state") == "not_selected" and plan.get("acceptance_state") == "not_eligible", "plan authority escalation")
    d4a = next((track for track in state.get("tracks", []) if track.get("track_id") == "D4-A"), {})
    require(set(d4a.get("evidence_completed", [])) == PRIOR_CREDIT, "state completed six-of-seven evidence drift")
    require(set(d4a.get("evidence_remaining", [])) == {EVIDENCE_ID}, "state must leave recovery evidence pending")
    require(state.get("gate_state") == "scoped", "D4 must remain scoped")
    require(state.get("d4_transport_authority") == "not_selected_not_granted", "D4 transport authority escalation")
    require(state.get("canonical_product_implementation_authority") == "not_granted", "Product authority escalation")
    require(state.get("wave4_implementation_authority") == "not_granted", "Wave4 authority escalation")
    require(state.get("production_authority") == "none", "production authority escalation")
    require(state.get("c3_numeric_topology_authority") == "not_selected", "C3 authority escalation")
    return errors


def main() -> None:
    errors = validate_objects(*load_objects())
    if errors:
        raise AssertionError("; ".join(errors))
    print("d4a_recovery_source_manifest=PASS source_credit=0 global_credit=6 recovery_pending=1 live_kafka_outage=required ack_ambiguity=same_identity priority_drain=bounded broker_progress_business_truth=false numerics=test_only authorities=not_granted")


if __name__ == "__main__":
    main()
