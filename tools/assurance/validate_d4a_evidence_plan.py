#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

PLAN = Path("implementation/d4-eventing-async/d4-a-evidence-plan.json")
ENTRY = Path("implementation/d4-eventing-async/state-manifest.json")
EXPECTED_ENTRY_COMMIT = "b385e1b68162b2cf9bf4379011554a9cc4c2d5c4"
EXPECTED_EVIDENCE = {
    "capacity_envelope_baseline_growth_stress",
    "broker_neutral_anti_corruption_stub_swap",
    "regulated_payload_erasure_granularity",
    "exactly_once_guardrail_consumer_inbox_enforcement",
    "ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency",
    "physical_naming_routing_and_cell_topology_adapter_mapping",
    "broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark",
}
EXPECTED_KINDS = {
    "capacity_envelope_baseline_growth_stress": "real_candidate_benchmark",
    "broker_neutral_anti_corruption_stub_swap": "candidate_plus_alternate_transport_conformance",
    "regulated_payload_erasure_granularity": "contract_policy_and_negative_runtime_probe",
    "exactly_once_guardrail_consumer_inbox_enforcement": "contract_registration_negative_control",
    "ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency": "real_candidate_benchmark_and_concurrency_probe",
    "physical_naming_routing_and_cell_topology_adapter_mapping": "topology_adapter_conformance",
    "broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark": "real_candidate_failure_recovery_benchmark",
}
REQUIRED_ASSERTIONS = {
    "capacity_envelope_baseline_growth_stress": {
        "baseline_growth_stress_tiers_are_explicit",
        "tenant_and_event_rate_skew_is_exercised",
        "throughput_latency_backlog_and_recovery_are_measured",
        "failure_or_degradation_boundary_is_observed",
        "bounded_test_values_do_not_become_production_numerics",
    },
    "broker_neutral_anti_corruption_stub_swap": {
        "every_actual_broker_facing_outbox_inbox_dispatch_and_consumer_path_uses_shared_logical_port_or_is_statically_proven_unable_to_bypass_it",
        "same_shared_logical_ports_are_exercised_by_kafka_and_alternate_stub",
        "canonical_message_identity_has_no_topic_partition_offset_or_group_dependency",
        "kafka_transactions_are_not_business_effect_authority",
    },
    "regulated_payload_erasure_granularity": {
        "sensitive_or_regulated_raw_value_bytes_are_rejected_by_default",
        "opaque_reference_profile_supports_governed_per_record_erasure",
        "negative_control_detects_raw_regulated_payload_leak",
        "raw_payload_exception_requires_per_tenant_topic_or_partition_assignment",
        "raw_payload_exception_requires_maximum_segment_retention_ceiling_meeting_governed_erasure_sla",
        "raw_payload_exception_requires_signoff_by_erasure_governance_authority",
    },
    "exactly_once_guardrail_consumer_inbox_enforcement": {
        "actual_consumer_registration_ci_gate_rejects_consumer_without_inbox_dedup_effect_protection_before_kafka_topic_registration",
        "actual_consumer_registration_ci_gate_accepts_valid_consumer_with_real_effect_protection",
        "kafka_idempotence_or_transactions_do_not_bypass_actual_registration_gate_rejection",
    },
    "ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency": {
        "every_declared_ordering_scope_class_has_documented_mapping_from_trusted_logical_identity_to_partition_key_strategy",
        "named_and_cited_consumer_side_key_level_concurrency_component_is_exercised",
        "key_level_serialization_does_not_require_global_or_tenant_wide_serialization",
        "practical_partition_ceiling_is_benchmarked_per_test_tier",
        "tenant_cohort_topic_sharding_fallback_is_exercised",
        "bounded_test_partition_counts_do_not_grant_c3_authority",
    },
    "physical_naming_routing_and_cell_topology_adapter_mapping": {
        "physical_topic_group_and_cell_names_do_not_become_contract_identity",
        "tenant_authorization_is_enforced_before_transport_mapping",
        "replacement_mapping_does_not_require_consumer_semantic_rewrite",
    },
    "broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark": {
        "committed_outbox_backlog_survives_broker_outage",
        "recovery_drains_backlog_without_starving_current_protected_work",
        "broker_ack_ambiguity_reuses_same_logical_message_identity",
        "broker_progress_is_not_business_effect_truth",
        "bounded_test_lag_and_drain_values_do_not_grant_c3_authority",
    },
}


def load(root: Path) -> tuple[dict, dict]:
    plan = json.loads((root / PLAN).read_text(encoding="utf-8"))
    entry = json.loads((root / ENTRY).read_text(encoding="utf-8"))
    return plan, entry


def validate_objects(plan: dict, entry: dict) -> list[str]:
    errors: list[str] = []

    def require(ok: bool, message: str) -> None:
        if not ok:
            errors.append(message)

    require(plan.get("schema_version") == 1, "plan schema_version drift")
    require(plan.get("gate_id") == "D4" and plan.get("track_id") == "D4-A", "plan identity drift")
    require(plan.get("canonical_entry_commit") == EXPECTED_ENTRY_COMMIT, "canonical entry commit drift")
    require(plan.get("candidate") == "kafka", "D4-A candidate must be Kafka")
    require(plan.get("candidate_status") == "leading_candidate_closure_pending", "Kafka must remain closure-pending")
    require(plan.get("evidence_credit_policy") == "source_runs_first_ledger_promotion_separate", "source/ledger separation drift")
    require(plan.get("current_run_auto_credit") is False, "current run must never auto-credit evidence")
    require(plan.get("production_numeric_authority") == "not_granted", "evidence plan must not grant production numerics")
    require(plan.get("source_evidence_state") == "not_run", "planning PR must not claim source evidence")
    require(plan.get("ledger_credit_state") == "zero_of_seven", "planning PR must keep ledger at zero")
    require(plan.get("selection_state") == "not_selected", "planning PR must not select Kafka")
    require(plan.get("acceptance_state") == "not_eligible", "planning PR must not claim acceptance eligibility")

    items = plan.get("required_evidence", [])
    require(isinstance(items, list), "required_evidence must be a list")
    by_id = {item.get("evidence_id"): item for item in items if isinstance(item, dict)}
    require(set(by_id) == EXPECTED_EVIDENCE, "D4-A evidence plan inventory drift")
    require(len(items) == len(EXPECTED_EVIDENCE), "D4-A evidence plan multiplicity drift")
    for evidence_id in EXPECTED_EVIDENCE:
        item = by_id.get(evidence_id, {})
        assertions = item.get("must_prove", [])
        require(isinstance(assertions, list), f"{evidence_id} must_prove must be a list")
        require(set(assertions) == REQUIRED_ASSERTIONS[evidence_id], f"{evidence_id} proof assertion set drift")
        require(len(assertions) == len(REQUIRED_ASSERTIONS[evidence_id]), f"{evidence_id} proof assertion multiplicity drift")
        require(item.get("evidence_kind") == EXPECTED_KINDS[evidence_id], f"{evidence_id} evidence kind drift")

    entry_d4a = next((t for t in entry.get("tracks", []) if t.get("track_id") == "D4-A"), {})
    require(set(entry_d4a.get("required_evidence", [])) == EXPECTED_EVIDENCE, "plan no longer matches machine-owned D4-A inventory")
    require(entry_d4a.get("evidence_completed") == [], "planning PR must not mutate D4-A evidence credit")
    require(entry.get("gate_state") == "scoped", "planning PR must leave D4 scoped")
    require(entry.get("d4_transport_authority") == "not_selected_not_granted", "planning PR must leave D4 authority ungranted")
    require(entry.get("canonical_product_implementation_authority") == "not_granted", "planning PR must leave Product authority ungranted")
    require(entry.get("wave4_implementation_authority") == "not_granted", "planning PR must leave Wave 4 authority ungranted")
    require(entry.get("production_authority") == "none", "planning PR must leave production authority none")
    require(entry.get("c3_numeric_topology_authority") == "not_selected", "planning PR must leave C3 authority unselected")
    return errors


def validate(root: Path) -> list[str]:
    return validate_objects(*load(root))


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"D4A_PLAN_ERROR: {error}", file=sys.stderr)
        return 1
    print("d4a_evidence_plan=PASS evidence=7 credited=0 kafka=not_selected production_numerics=not_granted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
