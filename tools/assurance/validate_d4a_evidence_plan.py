#!/usr/bin/env python3
from __future__ import annotations

from hashlib import sha256
import json
import sys
from pathlib import Path

PLAN = Path("implementation/d4-eventing-async/d4-a-evidence-plan.json")
ENTRY = Path("implementation/d4-eventing-async/state-manifest.json")
PROMOTION = Path("implementation/d4-eventing-async/ledger-promotions/d4-a-capacity-ordering-promotion-v1.json")
PREVIOUS_PROMOTION = Path("implementation/d4-eventing-async/ledger-promotions/d4-a-data-topology-promotion-v1.json")
SOURCE_MANIFEST = Path("implementation/d4-eventing-async/source-evidence/capacity-ordering/source-evidence-manifest.json")

EXPECTED_ENTRY_COMMIT = "b385e1b68162b2cf9bf4379011554a9cc4c2d5c4"
EXPECTED_PROMOTION_BASE = "80ee52a0057cd30dbfd84a4176a0bbb0144e45bb"
EXPECTED_SOURCE_HEAD = "da86d9442b9091f3255f2bf643d6ab1dc87baa7f"
EXPECTED_SOURCE_RUN = 33818533105
EXPECTED_SOURCE_JOB = 100855875375
EXPECTED_ARTIFACT_ID = 9917494653
EXPECTED_ARTIFACT_NAME = "d4-a-capacity-ordering-source-da86d9442b9091f3255f2bf643d6ab1dc87baa7f-33818533105-1"
EXPECTED_ARTIFACT_DIGEST = "sha256:b961f2febbeae8c42f2d821f8ac1ab14887b44a041418c975d6e2b500d0c40c7"
EXPECTED_SOURCE_MANIFEST_SHA256 = "b7bbf9c66845c9a7e1b04f29745917697c210a85dc70a6abbe881ce00e2b6675"
EXPECTED_PREVIOUS_PROMOTION_SHA256 = "cc4138c6161bed942fa68469f393e9fe0993b764113ce532dda53d22bd5cf813"
EXPECTED_INDEPENDENT_REVIEW = "PRR_kwDOT7x07M8AAAABMHNIGQ"
EXPECTED_FRESH_CODEX_REVIEW = "PRR_kwDOT7x07M8AAAABMHOEcg"
EXPECTED_FINAL_GATE_COMMENT = 5533586795
EXPECTED_FINDINGS = {
    "validate_immutable_kafka_candidate_pin",
    "measure_real_kafka_degradation_boundary",
    "benchmark_load_before_partition_ceiling",
    "exercise_canonical_key_serial_executor",
    "tie_partition_admission_to_tier_load_target",
    "exercise_actual_over_ceiling_fallback_workload",
    "exercise_device_cardinality_in_capacity_tiers",
}
EXPECTED_PRIOR_CREDIT = {
    "broker_neutral_anti_corruption_stub_swap",
    "regulated_payload_erasure_granularity",
    "exactly_once_guardrail_consumer_inbox_enforcement",
    "physical_naming_routing_and_cell_topology_adapter_mapping",
}
EXPECTED_NEW_CREDIT = {
    "capacity_envelope_baseline_growth_stress",
    "ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency",
}
EXPECTED_CREDITED = EXPECTED_PRIOR_CREDIT | EXPECTED_NEW_CREDIT
EXPECTED_RECOVERY = {"broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark"}
EXPECTED_EVIDENCE = EXPECTED_CREDITED | EXPECTED_RECOVERY
EXPECTED_KINDS = {
    "capacity_envelope_baseline_growth_stress": "real_candidate_benchmark",
    "broker_neutral_anti_corruption_stub_swap": "candidate_plus_alternate_transport_conformance",
    "regulated_payload_erasure_granularity": "contract_policy_and_negative_runtime_probe",
    "exactly_once_guardrail_consumer_inbox_enforcement": "contract_registration_negative_control",
    "ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency": "real_candidate_benchmark_and_concurrency_probe",
    "physical_naming_routing_and_cell_topology_adapter_mapping": "topology_adapter_conformance",
    "broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark": "real_candidate_failure_recovery_benchmark",
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
    require(plan.get("candidate") == "kafka", "D4-A candidate must remain Kafka")
    require(plan.get("candidate_status") == "leading_candidate_closure_pending", "Kafka must remain closure-pending")
    require(plan.get("evidence_credit_policy") == "source_runs_first_ledger_promotion_separate", "source/ledger separation drift")
    require(plan.get("current_run_auto_credit") is False, "current run must never auto-credit evidence")
    require(plan.get("production_numeric_authority") == "not_granted", "production numeric authority escalation")
    require(plan.get("source_evidence_state") == "reviewed_source_runs_available", "reviewed source state drift")
    require(plan.get("ledger_credit_state") == "six_of_seven", "ledger must credit exactly six of seven")
    require(set(plan.get("credited_evidence", [])) == EXPECTED_CREDITED, "credited evidence set drift")
    require(len(plan.get("credited_evidence", [])) == 6, "credited evidence multiplicity drift")
    require(plan.get("latest_promotion_record") == PROMOTION.as_posix(), "promotion record path drift")
    require(plan.get("selection_state") == "not_selected", "promotion must not select Kafka")
    require(plan.get("acceptance_state") == "not_eligible", "six-of-seven is not final D4-A acceptance")
    items = plan.get("required_evidence", [])
    by_id = {i.get("evidence_id"): i for i in items if isinstance(i, dict)}
    require(set(by_id) == EXPECTED_EVIDENCE and len(items) == 7, "D4-A evidence inventory drift")
    for evidence_id, kind in EXPECTED_KINDS.items():
        require(by_id.get(evidence_id, {}).get("evidence_kind") == kind, f"evidence kind drift: {evidence_id}")
        require(bool(by_id.get(evidence_id, {}).get("must_prove")), f"missing proof assertions: {evidence_id}")

    d4a = next((t for t in entry.get("tracks", []) if t.get("track_id") == "D4-A"), {})
    require(set(d4a.get("required_evidence", [])) == EXPECTED_EVIDENCE, "state D4-A inventory drift")
    require(set(d4a.get("evidence_completed", [])) == EXPECTED_CREDITED, "state completed evidence drift")
    require(set(d4a.get("evidence_remaining", [])) == EXPECTED_RECOVERY, "state remaining recovery evidence drift")
    require(entry.get("gate_state") == "scoped", "D4 must remain scoped")
    require(entry.get("d4_transport_authority") == "not_selected_not_granted", "D4 transport authority escalation")
    require(entry.get("canonical_product_implementation_authority") == "not_granted", "Product authority escalation")
    require(entry.get("wave4_implementation_authority") == "not_granted", "Wave4 authority escalation")
    require(entry.get("production_authority") == "none", "production authority escalation")
    require(entry.get("c3_numeric_topology_authority") == "not_selected", "C3 authority escalation")

    require(promotion.get("schema_version") == 1, "promotion schema drift")
    require(promotion.get("promotion_id") == "d4-a-capacity-ordering-promotion-v1", "promotion identity drift")
    require(promotion.get("track") == "D4-A", "promotion track drift")
    require(promotion.get("promotion_base_main_commit") == EXPECTED_PROMOTION_BASE, "promotion base drift")
    previous = promotion.get("previous_promotion", {})
    require(previous.get("path") == PREVIOUS_PROMOTION.as_posix(), "previous promotion path drift")
    require(previous.get("promotion_id") == "d4-a-data-topology-promotion-v1", "previous promotion identity drift")
    require(previous.get("sha256") == EXPECTED_PREVIOUS_PROMOTION_SHA256, "previous promotion digest drift")
    require(promotion.get("source_pr") == 59, "source PR drift")
    require(promotion.get("source_reviewed_head") == EXPECTED_SOURCE_HEAD, "source reviewed HEAD drift")
    require(promotion.get("source_merge_commit") == EXPECTED_PROMOTION_BASE, "source merge commit drift")
    require(promotion.get("source_manifest_path") == SOURCE_MANIFEST.as_posix(), "source manifest path drift")
    require(promotion.get("source_manifest_sha256") == EXPECTED_SOURCE_MANIFEST_SHA256, "source manifest digest drift")
    w = promotion.get("source_workflow", {})
    require(w.get("run_id") == EXPECTED_SOURCE_RUN, "source run drift")
    require(w.get("run_attempt") == 1, "source run attempt drift")
    require(w.get("job_id") == EXPECTED_SOURCE_JOB, "source job drift")
    require(w.get("job_name") == "D4-A capacity ordering source evidence", "source job name drift")
    require(w.get("artifact_id") == EXPECTED_ARTIFACT_ID, "artifact id drift")
    require(w.get("artifact_name") == EXPECTED_ARTIFACT_NAME, "artifact name drift")
    require(w.get("artifact_digest") == EXPECTED_ARTIFACT_DIGEST, "artifact digest drift")
    g = promotion.get("review_gate", {})
    require(g.get("exact_head_ci_success_count") == 17, "source exact-HEAD CI count drift")
    require(g.get("independent_adversarial_review_node_id") == EXPECTED_INDEPENDENT_REVIEW, "independent review identity drift")
    require(g.get("fresh_codex_exact_head_review_node_id") == EXPECTED_FRESH_CODEX_REVIEW, "fresh Codex review identity drift")
    require(g.get("fresh_codex_reviewed_head") == EXPECTED_SOURCE_HEAD, "fresh Codex reviewed HEAD drift")
    require(set(g.get("prior_material_findings_resolved", [])) == EXPECTED_FINDINGS, "resolved material finding set drift")
    require(len(g.get("prior_material_findings_resolved", [])) == 7, "resolved finding multiplicity drift")
    require(g.get("unresolved_material_review_threads") == 0, "unresolved material review threads drift")
    require(g.get("final_gate_comment_id") == EXPECTED_FINAL_GATE_COMMENT, "final gate comment drift")
    require(g.get("older_review_reused_as_clean") is False, "older review reused as clean")
    require(set(promotion.get("prior_credited_evidence", [])) == EXPECTED_PRIOR_CREDIT, "prior credited evidence drift")
    credited = promotion.get("credited_evidence", [])
    credited_by_id = {i.get("evidence_id"): i for i in credited if isinstance(i, dict)}
    require(set(credited_by_id) == EXPECTED_NEW_CREDIT and len(credited) == 2, "newly credited evidence drift")
    for evidence_id in EXPECTED_NEW_CREDIT:
        require(credited_by_id.get(evidence_id, {}).get("evidence_kind") == EXPECTED_KINDS[evidence_id], f"promotion evidence kind drift: {evidence_id}")
    require(promotion.get("resulting_credited_evidence_count") == 6, "resulting credit count drift")
    require(promotion.get("source_scope") == "source_evidence_harness_only", "source scope drift")
    require(promotion.get("live_kafka_broker_claimed") is True, "historical live Kafka source claim missing")
    require(promotion.get("capacity_benchmark_claimed") is True, "historical capacity source claim missing")
    require(promotion.get("ordering_benchmark_claimed") is True, "historical ordering source claim missing")
    require(promotion.get("recovery_benchmark_claimed") is False, "recovery overclaim")
    require(promotion.get("kafka_selection_state") == "not_selected", "promotion selects Kafka")
    require(promotion.get("d4_transport_authority") == "not_selected_not_granted", "promotion grants D4 transport authority")
    require(promotion.get("canonical_product_implementation_authority") == "not_granted", "promotion grants Product authority")
    require(promotion.get("wave4_implementation_authority") == "not_granted", "promotion grants Wave4 authority")
    require(promotion.get("production_authority") == "none", "promotion grants production authority")
    require(promotion.get("c3_numeric_topology_authority") == "not_selected", "promotion grants C3 authority")
    require(promotion.get("promotion_rule") == "reviewed_source_run_to_ledger_credit_only", "promotion rule drift")
    return errors


def validate(root: Path) -> list[str]:
    plan, entry, promotion = load(root)
    errors = validate_objects(plan, entry, promotion)
    if sha256((root / SOURCE_MANIFEST).read_bytes()).hexdigest() != EXPECTED_SOURCE_MANIFEST_SHA256:
        errors.append("source manifest bytes no longer match promoted digest")
    if sha256((root / PREVIOUS_PROMOTION).read_bytes()).hexdigest() != EXPECTED_PREVIOUS_PROMOTION_SHA256:
        errors.append("previous promotion bytes no longer match chained digest")
    return errors


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"D4A_PLAN_ERROR: {error}", file=sys.stderr)
        return 1
    print("d4a_evidence_plan=PASS evidence=7 credited=6 remaining=1 kafka=not_selected production_numerics=not_granted provenance=chained review_gate=pinned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
