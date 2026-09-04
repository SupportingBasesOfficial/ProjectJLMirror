#!/usr/bin/env python3
from __future__ import annotations

from hashlib import sha256
import json
import sys
from pathlib import Path

PLAN = Path("implementation/d4-eventing-async/d4-a-evidence-plan.json")
ENTRY = Path("implementation/d4-eventing-async/state-manifest.json")
PROMOTION = Path("implementation/d4-eventing-async/ledger-promotions/d4-a-recovery-promotion-v1.json")
PREVIOUS_PROMOTION = Path("implementation/d4-eventing-async/ledger-promotions/d4-a-capacity-ordering-promotion-v1.json")
SOURCE_MANIFEST = Path("implementation/d4-eventing-async/source-evidence/recovery/source-evidence-manifest.json")

EXPECTED_ENTRY_COMMIT = "b385e1b68162b2cf9bf4379011554a9cc4c2d5c4"
EXPECTED_PROMOTION_BASE = "9fdf02dd7841ac9f4f28610759af751096057264"
EXPECTED_SOURCE_HEAD = "40820f543c064c976b0e1443a227120a5577d36b"
EXPECTED_SOURCE_RUN = 33824087573
EXPECTED_SOURCE_JOB = 100872898415
EXPECTED_ARTIFACT_ID = 9919338891
EXPECTED_ARTIFACT_NAME = "d4-a-recovery-source-40820f543c064c976b0e1443a227120a5577d36b-33824087573-1"
EXPECTED_ARTIFACT_DIGEST = "sha256:e0d5c4990627533408201ca6b50895c9272c4a0298acd0458b4813295c1731de"
EXPECTED_SOURCE_MANIFEST_SHA256 = "eec7d7a2d01a29b3194ac9185af741f7fdf89132dc9547689b1ab47fbfef958c"
EXPECTED_PREVIOUS_PROMOTION_SHA256 = "8c6ee60b43033a54780585cf244f74367f97953c76619ad1b3dd52f89482d04f"
EXPECTED_INDEPENDENT_REVIEW = "PRR_kwDOT7x07M8AAAABMHlhng"
EXPECTED_FRESH_CODEX_REVIEW = "PRR_kwDOT7x07M8AAAABMHl-Kw"
EXPECTED_FINAL_GATE_COMMENT = 5534198183
EXPECTED_FINDINGS = {"align_declared_drain_control_with_executed_bound"}

EXPECTED_EVIDENCE = {
    "capacity_envelope_baseline_growth_stress",
    "broker_neutral_anti_corruption_stub_swap",
    "regulated_payload_erasure_granularity",
    "exactly_once_guardrail_consumer_inbox_enforcement",
    "ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency",
    "physical_naming_routing_and_cell_topology_adapter_mapping",
    "broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark",
}
EXPECTED_PRIOR_CREDIT = EXPECTED_EVIDENCE - {"broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark"}
EXPECTED_NEW_CREDIT = {"broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark"}
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
    return (
        json.loads((root / PLAN).read_text(encoding="utf-8")),
        json.loads((root / ENTRY).read_text(encoding="utf-8")),
        json.loads((root / PROMOTION).read_text(encoding="utf-8")),
    )


def validate_objects(plan: dict, entry: dict, promotion: dict) -> list[str]:
    errors: list[str] = []

    def require(ok: bool, message: str) -> None:
        if not ok:
            errors.append(message)

    require(plan.get("schema_version") == 1, "plan schema_version drift")
    require(plan.get("gate_id") == "D4" and plan.get("track_id") == "D4-A", "plan identity drift")
    require(plan.get("canonical_entry_commit") == EXPECTED_ENTRY_COMMIT, "canonical entry commit drift")
    require(plan.get("candidate") == "kafka", "D4-A leading candidate must remain Kafka")
    require(plan.get("candidate_status") == "leading_candidate_evidence_complete_selection_pending", "Kafka evidence-complete selection-pending state drift")
    require(plan.get("evidence_credit_policy") == "source_runs_first_ledger_promotion_separate", "source/ledger separation drift")
    require(plan.get("current_run_auto_credit") is False, "current run must never auto-credit evidence")
    require(plan.get("production_numeric_authority") == "not_granted", "production numeric authority escalation")
    require(plan.get("source_evidence_state") == "reviewed_source_runs_available", "reviewed source state drift")
    require(plan.get("ledger_credit_state") == "seven_of_seven", "ledger must credit exactly seven of seven")
    require(set(plan.get("credited_evidence", [])) == EXPECTED_EVIDENCE, "credited evidence set drift")
    require(len(plan.get("credited_evidence", [])) == 7, "credited evidence multiplicity drift")
    require(plan.get("latest_promotion_record") == PROMOTION.as_posix(), "promotion record path drift")
    require(plan.get("selection_state") == "not_selected", "evidence completion must not select Kafka")
    require(plan.get("acceptance_state") == "evidence_complete_separate_acceptance_required", "evidence completion must require separate acceptance")

    items = plan.get("required_evidence", [])
    require(isinstance(items, list), "required_evidence must be a list")
    by_id = {i.get("evidence_id"): i for i in items if isinstance(i, dict)}
    require(set(by_id) == EXPECTED_EVIDENCE, "D4-A evidence inventory drift")
    require(len(items) == len(EXPECTED_EVIDENCE), "D4-A evidence multiplicity drift")
    for evidence_id in EXPECTED_EVIDENCE:
        item = by_id.get(evidence_id, {})
        assertions = item.get("must_prove", [])
        require(item.get("evidence_kind") == EXPECTED_KINDS[evidence_id], f"evidence kind drift: {evidence_id}")
        require(isinstance(assertions, list), f"{evidence_id} must_prove must be a list")
        require(set(assertions) == REQUIRED_ASSERTIONS[evidence_id], f"{evidence_id} proof assertion set drift")
        require(len(assertions) == len(REQUIRED_ASSERTIONS[evidence_id]), f"{evidence_id} proof assertion multiplicity drift")

    d4a = next((t for t in entry.get("tracks", []) if t.get("track_id") == "D4-A"), {})
    require(set(d4a.get("required_evidence", [])) == EXPECTED_EVIDENCE, "state D4-A inventory drift")
    require(set(d4a.get("evidence_completed", [])) == EXPECTED_EVIDENCE, "state completed seven-of-seven evidence drift")
    require(d4a.get("evidence_remaining") == [], "state D4-A evidence_remaining must be empty")
    require(d4a.get("state") == "evidence_complete_selection_pending", "state D4-A evidence-complete selection-pending drift")
    require(d4a.get("candidate") == "kafka", "state D4-A leading candidate drift")
    require(d4a.get("candidate_status") == "leading_candidate_evidence_complete_selection_pending", "state D4-A candidate status drift")
    require(entry.get("gate_state") == "scoped", "D4 must remain scoped")
    require(entry.get("d4_transport_authority") == "not_selected_not_granted", "D4 transport authority escalation")
    require(entry.get("canonical_product_implementation_authority") == "not_granted", "Product authority escalation")
    require(entry.get("wave4_implementation_authority") == "not_granted", "Wave4 authority escalation")
    require(entry.get("production_authority") == "none", "production authority escalation")
    require(entry.get("c3_numeric_topology_authority") == "not_selected", "C3 authority escalation")

    require(promotion.get("schema_version") == 1, "promotion schema drift")
    require(promotion.get("promotion_id") == "d4-a-recovery-promotion-v1", "promotion identity drift")
    require(promotion.get("track") == "D4-A", "promotion track drift")
    require(promotion.get("promotion_base_main_commit") == EXPECTED_PROMOTION_BASE, "promotion base drift")
    previous = promotion.get("previous_promotion", {})
    require(previous.get("path") == PREVIOUS_PROMOTION.as_posix(), "previous promotion path drift")
    require(previous.get("promotion_id") == "d4-a-capacity-ordering-promotion-v1", "previous promotion identity drift")
    require(previous.get("sha256") == EXPECTED_PREVIOUS_PROMOTION_SHA256, "previous promotion digest drift")
    require(promotion.get("source_pr") == 61, "source PR drift")
    require(promotion.get("source_reviewed_head") == EXPECTED_SOURCE_HEAD, "source reviewed HEAD drift")
    require(promotion.get("source_merge_commit") == EXPECTED_PROMOTION_BASE, "source merge commit drift")
    require(promotion.get("source_manifest_path") == SOURCE_MANIFEST.as_posix(), "source manifest path drift")
    require(promotion.get("source_manifest_sha256") == EXPECTED_SOURCE_MANIFEST_SHA256, "source manifest digest drift")
    w = promotion.get("source_workflow", {})
    require(w.get("run_id") == EXPECTED_SOURCE_RUN, "source run drift")
    require(w.get("run_attempt") == 1, "source run attempt drift")
    require(w.get("job_id") == EXPECTED_SOURCE_JOB, "source job drift")
    require(w.get("job_name") == "D4-A recovery source evidence", "source job name drift")
    require(w.get("artifact_id") == EXPECTED_ARTIFACT_ID, "artifact id drift")
    require(w.get("artifact_name") == EXPECTED_ARTIFACT_NAME, "artifact name drift")
    require(w.get("artifact_digest") == EXPECTED_ARTIFACT_DIGEST, "artifact digest drift")
    g = promotion.get("review_gate", {})
    require(g.get("exact_head_ci_success_count") == 18, "source exact-HEAD CI count drift")
    require(g.get("independent_adversarial_review_node_id") == EXPECTED_INDEPENDENT_REVIEW, "independent review identity drift")
    require(g.get("fresh_codex_exact_head_review_node_id") == EXPECTED_FRESH_CODEX_REVIEW, "fresh Codex review identity drift")
    require(g.get("fresh_codex_reviewed_head") == EXPECTED_SOURCE_HEAD, "fresh Codex reviewed HEAD drift")
    require(set(g.get("prior_material_findings_resolved", [])) == EXPECTED_FINDINGS, "resolved material finding set drift")
    require(len(g.get("prior_material_findings_resolved", [])) == len(EXPECTED_FINDINGS), "resolved finding multiplicity drift")
    require(g.get("unresolved_material_review_threads") == 0, "unresolved material review threads drift")
    require(g.get("final_gate_comment_id") == EXPECTED_FINAL_GATE_COMMENT, "final gate comment drift")
    require(g.get("older_review_reused_as_clean") is False, "older review reused as clean")
    require(set(promotion.get("prior_credited_evidence", [])) == EXPECTED_PRIOR_CREDIT, "prior credited evidence drift")
    require(len(promotion.get("prior_credited_evidence", [])) == len(EXPECTED_PRIOR_CREDIT), "prior credited evidence multiplicity drift")
    credited = promotion.get("credited_evidence", [])
    require(isinstance(credited, list), "promotion credited_evidence must be a list")
    credited_by_id = {i.get("evidence_id"): i for i in credited if isinstance(i, dict)}
    require(set(credited_by_id) == EXPECTED_NEW_CREDIT, "newly credited recovery evidence drift")
    require(len(credited) == 1, "newly credited recovery evidence multiplicity drift")
    recovery = "broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark"
    require(credited_by_id.get(recovery, {}).get("evidence_kind") == EXPECTED_KINDS[recovery], "promotion recovery evidence kind drift")
    require(promotion.get("resulting_credited_evidence_count") == 7, "resulting credit count drift")
    require(promotion.get("source_scope") == "source_evidence_harness_only", "source scope drift")
    require(promotion.get("live_kafka_broker_claimed") is True, "historical live Kafka source claim missing")
    require(promotion.get("recovery_benchmark_claimed") is True, "historical recovery source claim missing")
    require(promotion.get("kafka_selection_state") == "not_selected", "promotion selects Kafka")
    require(promotion.get("d4a_evidence_state") == "complete_selection_pending", "promotion evidence-complete state drift")
    require(promotion.get("d4_transport_authority") == "not_selected_not_granted", "promotion grants D4 transport authority")
    require(promotion.get("canonical_product_implementation_authority") == "not_granted", "promotion grants Product authority")
    require(promotion.get("wave4_implementation_authority") == "not_granted", "promotion grants Wave4 authority")
    require(promotion.get("production_authority") == "none", "promotion grants production authority")
    require(promotion.get("c3_numeric_topology_authority") == "not_selected", "promotion grants C3 authority")
    require(promotion.get("promotion_rule") == "reviewed_source_run_to_ledger_credit_only", "promotion rule drift")
    return errors


def _safe_repo_path(value: object) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    return candidate


def validate_promotion_chain(root: Path, latest: dict) -> list[str]:
    errors: list[str] = []
    current = latest
    seen_paths: set[str] = set()

    while True:
        promotion_id = current.get("promotion_id") or "<unknown-promotion>"
        manifest_path = _safe_repo_path(current.get("source_manifest_path"))
        expected_manifest_digest = current.get("source_manifest_sha256")
        if manifest_path is None:
            errors.append(f"{promotion_id} source manifest path invalid")
        elif not isinstance(expected_manifest_digest, str) or len(expected_manifest_digest) != 64:
            errors.append(f"{promotion_id} source manifest digest invalid")
        else:
            full_manifest = root / manifest_path
            if not full_manifest.is_file():
                errors.append(f"{promotion_id} source manifest missing: {manifest_path}")
            elif sha256(full_manifest.read_bytes()).hexdigest() != expected_manifest_digest:
                errors.append(f"{promotion_id} source manifest bytes no longer match promoted digest")

        previous = current.get("previous_promotion")
        if previous is None:
            break
        if not isinstance(previous, dict):
            errors.append(f"{promotion_id} previous promotion link invalid")
            break
        previous_path = _safe_repo_path(previous.get("path"))
        expected_previous_id = previous.get("promotion_id")
        expected_previous_digest = previous.get("sha256")
        if previous_path is None:
            errors.append(f"{promotion_id} previous promotion path invalid")
            break
        path_key = previous_path.as_posix()
        if path_key in seen_paths:
            errors.append(f"promotion chain cycle detected at {path_key}")
            break
        seen_paths.add(path_key)
        full_previous = root / previous_path
        if not full_previous.is_file():
            errors.append(f"{promotion_id} previous promotion missing: {previous_path}")
            break
        previous_bytes = full_previous.read_bytes()
        if not isinstance(expected_previous_digest, str) or sha256(previous_bytes).hexdigest() != expected_previous_digest:
            errors.append(f"{promotion_id} previous promotion bytes no longer match chained digest")
            break
        try:
            previous_object = json.loads(previous_bytes)
        except json.JSONDecodeError:
            errors.append(f"{promotion_id} previous promotion is not valid JSON")
            break
        if previous_object.get("promotion_id") != expected_previous_id:
            errors.append(f"{promotion_id} previous promotion identity mismatch")
            break
        if previous_object.get("track") != "D4-A":
            errors.append(f"{promotion_id} previous promotion track drift")
            break
        current = previous_object
    return errors


def validate(root: Path) -> list[str]:
    plan, entry, promotion = load(root)
    errors = validate_objects(plan, entry, promotion)
    errors.extend(validate_promotion_chain(root, promotion))
    return errors


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"D4A_PLAN_ERROR: {error}", file=sys.stderr)
        return 1
    print("d4a_evidence_plan=PASS evidence=7 credited=7 remaining=0 exact_assertions=preserved kafka=not_selected acceptance=separate_required production_numerics=not_granted provenance=full_chain review_gate=pinned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
