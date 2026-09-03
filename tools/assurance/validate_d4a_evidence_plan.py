#!/usr/bin/env python3
from __future__ import annotations

from hashlib import sha256
import json
import sys
from pathlib import Path

PLAN = Path("implementation/d4-eventing-async/d4-a-evidence-plan.json")
ENTRY = Path("implementation/d4-eventing-async/state-manifest.json")
PROMOTION = Path("implementation/d4-eventing-async/ledger-promotions/d4-a-semantic-boundary-promotion-v1.json")
SOURCE_MANIFEST = Path("implementation/d4-eventing-async/source-evidence/semantic-boundary/source-evidence-manifest.json")
EXPECTED_ENTRY_COMMIT = "b385e1b68162b2cf9bf4379011554a9cc4c2d5c4"
EXPECTED_PROMOTION_BASE = "8863f66a0fb6457ad05b72286ef983eb4e8a1c5e"
EXPECTED_SOURCE_HEAD = "d6872579dca7d4f08c9ded82e34b94f8e87ec1e9"
EXPECTED_SOURCE_RUN = 33790608658
EXPECTED_SOURCE_JOB = 100766024114
EXPECTED_ARTIFACT_ID = 9907159265
EXPECTED_ARTIFACT_NAME = "d4-a-semantic-boundary-source-d6872579dca7d4f08c9ded82e34b94f8e87ec1e9-33790608658-1"
EXPECTED_ARTIFACT_DIGEST = "sha256:8b4c4031270479ff3cb0912ae5469df575459f8afaf9e3ff226fb3b73e18ae6a"
EXPECTED_SOURCE_MANIFEST_SHA256 = "690cdc59af819e27a7922cd2eea04d537c20dcd0e005ce4dbd4dac977eb525a1"
EXPECTED_REVIEW_NODE = "PRR_kwDOT7x07M8AAAABMFEmUQ"
EXPECTED_FINAL_GATE_COMMENT = 5530884189
EXPECTED_CREDITED = {
    "broker_neutral_anti_corruption_stub_swap",
    "exactly_once_guardrail_consumer_inbox_enforcement",
}
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


def load(root: Path) -> tuple[dict, dict, dict]:
    plan = json.loads((root / PLAN).read_text(encoding="utf-8"))
    entry = json.loads((root / ENTRY).read_text(encoding="utf-8"))
    promotion = json.loads((root / PROMOTION).read_text(encoding="utf-8"))
    return plan, entry, promotion


def validate_objects(plan: dict, entry: dict, promotion: dict) -> list[str]:
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
    require(plan.get("source_evidence_state") == "reviewed_source_run_available", "reviewed source-run state drift")
    require(plan.get("ledger_credit_state") == "two_of_seven", "ledger must credit exactly two of seven")
    require(set(plan.get("credited_evidence", [])) == EXPECTED_CREDITED, "credited evidence set drift")
    require(len(plan.get("credited_evidence", [])) == len(EXPECTED_CREDITED), "credited evidence multiplicity drift")
    require(plan.get("latest_promotion_record") == PROMOTION.as_posix(), "promotion record path drift")
    require(plan.get("selection_state") == "not_selected", "ledger promotion must not select Kafka")
    require(plan.get("acceptance_state") == "not_eligible", "partial ledger promotion must not claim acceptance eligibility")

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
    require(set(entry_d4a.get("evidence_completed", [])) == EXPECTED_CREDITED, "D4-A completed evidence must equal reviewed promotion")
    require(len(entry_d4a.get("evidence_completed", [])) == len(EXPECTED_CREDITED), "D4-A completed evidence multiplicity drift")
    require(set(entry_d4a.get("evidence_remaining", [])) == EXPECTED_EVIDENCE - EXPECTED_CREDITED, "D4-A remaining evidence drift")
    require(len(entry_d4a.get("evidence_remaining", [])) == len(EXPECTED_EVIDENCE - EXPECTED_CREDITED), "D4-A remaining evidence multiplicity drift")
    require(entry.get("gate_state") == "scoped", "partial promotion must leave D4 scoped")
    require(entry.get("d4_transport_authority") == "not_selected_not_granted", "promotion must leave D4 authority ungranted")
    require(entry.get("canonical_product_implementation_authority") == "not_granted", "promotion must leave Product authority ungranted")
    require(entry.get("wave4_implementation_authority") == "not_granted", "promotion must leave Wave 4 authority ungranted")
    require(entry.get("production_authority") == "none", "promotion must leave production authority none")
    require(entry.get("c3_numeric_topology_authority") == "not_selected", "promotion must leave C3 authority unselected")

    require(promotion.get("schema_version") == 1, "promotion schema drift")
    require(promotion.get("promotion_id") == "d4-a-semantic-boundary-promotion-v1", "promotion identity drift")
    require(promotion.get("track") == "D4-A", "promotion track drift")
    require(promotion.get("promotion_base_main_commit") == EXPECTED_PROMOTION_BASE, "promotion base drift")
    require(promotion.get("source_pr") == 54, "source PR drift")
    require(promotion.get("source_reviewed_head") == EXPECTED_SOURCE_HEAD, "source reviewed HEAD drift")
    require(promotion.get("source_merge_commit") == EXPECTED_PROMOTION_BASE, "source merge commit drift")
    require(promotion.get("source_manifest_path") == SOURCE_MANIFEST.as_posix(), "source manifest path drift")
    require(promotion.get("source_manifest_sha256") == EXPECTED_SOURCE_MANIFEST_SHA256, "source manifest digest drift")
    source_workflow = promotion.get("source_workflow", {})
    require(source_workflow.get("run_id") == EXPECTED_SOURCE_RUN, "source workflow run drift")
    require(source_workflow.get("run_attempt") == 1, "source workflow attempt drift")
    require(source_workflow.get("job_id") == EXPECTED_SOURCE_JOB, "source workflow job drift")
    require(source_workflow.get("job_name") == "D4-A semantic boundary source evidence", "source workflow job name drift")
    require(source_workflow.get("artifact_id") == EXPECTED_ARTIFACT_ID, "source artifact id drift")
    require(source_workflow.get("artifact_name") == EXPECTED_ARTIFACT_NAME, "source artifact name drift")
    require(source_workflow.get("artifact_digest") == EXPECTED_ARTIFACT_DIGEST, "source artifact digest drift")
    review_gate = promotion.get("review_gate", {})
    require(review_gate.get("exact_head_ci_success_count") == 15, "source exact-HEAD CI count drift")
    require(review_gate.get("independent_adversarial_review_node_id") == EXPECTED_REVIEW_NODE, "source adversarial review identity drift")
    require(review_gate.get("final_gate_comment_id") == EXPECTED_FINAL_GATE_COMMENT, "source final gate comment drift")
    require(review_gate.get("fresh_codex_unavailable_due_usage_limit") is True, "source Codex availability record drift")
    require(review_gate.get("older_codex_review_reused_as_clean") is False, "older Codex review must not be reused as clean")
    credited = promotion.get("credited_evidence", [])
    require(isinstance(credited, list), "promotion credited_evidence must be a list")
    credited_by_id = {item.get("evidence_id"): item for item in credited if isinstance(item, dict)}
    require(set(credited_by_id) == EXPECTED_CREDITED, "promotion credited evidence set drift")
    require(len(credited) == len(EXPECTED_CREDITED), "promotion credited evidence multiplicity drift")
    for evidence_id in EXPECTED_CREDITED:
        require(credited_by_id.get(evidence_id, {}).get("evidence_kind") == EXPECTED_KINDS[evidence_id], f"promotion evidence kind drift: {evidence_id}")
    require(promotion.get("source_scope") == "source_evidence_harness_only", "source scope drift")
    for claim in ("live_kafka_broker_claimed", "capacity_benchmark_claimed", "ordering_benchmark_claimed", "recovery_benchmark_claimed"):
        require(promotion.get(claim) is False, f"promotion must not escalate claim: {claim}")
    require(promotion.get("kafka_selection_state") == "not_selected", "promotion must not select Kafka")
    require(promotion.get("d4_transport_authority") == "not_selected_not_granted", "promotion must not grant D4 transport authority")
    require(promotion.get("canonical_product_implementation_authority") == "not_granted", "promotion must not grant Product authority")
    require(promotion.get("wave4_implementation_authority") == "not_granted", "promotion must not grant Wave 4 authority")
    require(promotion.get("production_authority") == "none", "promotion must not grant production authority")
    require(promotion.get("c3_numeric_topology_authority") == "not_selected", "promotion must not grant C3 authority")
    require(promotion.get("promotion_rule") == "reviewed_source_run_to_ledger_credit_only", "promotion rule drift")
    return errors


def validate(root: Path) -> list[str]:
    plan, entry, promotion = load(root)
    errors = validate_objects(plan, entry, promotion)
    source_bytes = (root / SOURCE_MANIFEST).read_bytes()
    actual_source_digest = sha256(source_bytes).hexdigest()
    if actual_source_digest != EXPECTED_SOURCE_MANIFEST_SHA256:
        errors.append("source manifest bytes no longer match promoted digest")
    return errors


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"D4A_PLAN_ERROR: {error}", file=sys.stderr)
        return 1
    print("d4a_evidence_plan=PASS evidence=7 credited=2 remaining=5 kafka=not_selected production_numerics=not_granted provenance=pinned review_gate=pinned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
