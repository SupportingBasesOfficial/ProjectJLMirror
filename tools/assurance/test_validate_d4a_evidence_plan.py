#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from validate_d4a_evidence_plan import validate_objects

ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = ROOT / "implementation/d4-eventing-async/d4-a-evidence-plan.json"
ENTRY_PATH = ROOT / "implementation/d4-eventing-async/state-manifest.json"
PROMOTION_PATH = ROOT / "implementation/d4-eventing-async/ledger-promotions/d4-a-data-topology-promotion-v1.json"


def must_fail(name: str, mutate) -> None:
    plan = json.loads(PLAN_PATH.read_text())
    entry = json.loads(ENTRY_PATH.read_text())
    promotion = json.loads(PROMOTION_PATH.read_text())
    mutate(plan, entry, promotion)
    assert validate_objects(plan, entry, promotion), f"negative control unexpectedly passed: {name}"


def item(plan: dict, evidence_id: str) -> dict:
    return next(i for i in plan["required_evidence"] if i["evidence_id"] == evidence_id)


def remove_assertion(evidence_id: str, assertion: str):
    def mutate(plan: dict, entry: dict, promotion: dict) -> None:
        item(plan, evidence_id)["must_prove"].remove(assertion)
    return mutate


def d4a(entry: dict) -> dict:
    return next(t for t in entry["tracks"] if t["track_id"] == "D4-A")


def main() -> int:
    must_fail("collapse inventory", lambda p, e, r: p.update(required_evidence=[{"evidence_id":"documentation","evidence_kind":"documentation_only","must_prove":[]}]))
    must_fail("auto credit", lambda p, e, r: p.update(current_run_auto_credit=True))
    must_fail("premature Kafka selection", lambda p, e, r: p.update(selection_state="selected"))
    must_fail("production numeric escalation", lambda p, e, r: p.update(production_numeric_authority="granted"))
    must_fail("arbitrary synthetic evidence kind", lambda p, e, r: item(p, "capacity_envelope_baseline_growth_stress").update(evidence_kind="synthetic_probe"))
    must_fail("weaken ordering evidence kind", lambda p, e, r: item(p, "ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency").update(evidence_kind="unit_test"))
    must_fail("weaken recovery evidence kind", lambda p, e, r: item(p, "broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark").update(evidence_kind="documentation_only"))

    must_fail("remove capacity measurement", remove_assertion("capacity_envelope_baseline_growth_stress", "throughput_latency_backlog_and_recovery_are_measured"))
    must_fail("remove complete broker path boundary", remove_assertion("broker_neutral_anti_corruption_stub_swap", "every_actual_broker_facing_outbox_inbox_dispatch_and_consumer_path_uses_shared_logical_port_or_is_statically_proven_unable_to_bypass_it"))
    must_fail("remove shared-port swap", remove_assertion("broker_neutral_anti_corruption_stub_swap", "same_shared_logical_ports_are_exercised_by_kafka_and_alternate_stub"))
    must_fail("remove opaque erasure reference", remove_assertion("regulated_payload_erasure_granularity", "opaque_reference_profile_supports_governed_per_record_erasure"))
    must_fail("remove regulated per-tenant exception isolation", remove_assertion("regulated_payload_erasure_granularity", "raw_payload_exception_requires_per_tenant_topic_or_partition_assignment"))
    must_fail("remove regulated exception retention ceiling", remove_assertion("regulated_payload_erasure_granularity", "raw_payload_exception_requires_maximum_segment_retention_ceiling_meeting_governed_erasure_sla"))
    must_fail("remove regulated exception governance signoff", remove_assertion("regulated_payload_erasure_granularity", "raw_payload_exception_requires_signoff_by_erasure_governance_authority"))
    must_fail("replace actual consumer registration reject gate", remove_assertion("exactly_once_guardrail_consumer_inbox_enforcement", "actual_consumer_registration_ci_gate_rejects_consumer_without_inbox_dedup_effect_protection_before_kafka_topic_registration"))
    must_fail("remove actual consumer registration positive gate", remove_assertion("exactly_once_guardrail_consumer_inbox_enforcement", "actual_consumer_registration_ci_gate_accepts_valid_consumer_with_real_effect_protection"))
    must_fail("remove transaction bypass protection on actual gate", remove_assertion("exactly_once_guardrail_consumer_inbox_enforcement", "kafka_idempotence_or_transactions_do_not_bypass_actual_registration_gate_rejection"))
    must_fail("remove every ordering scope mapping", remove_assertion("ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency", "every_declared_ordering_scope_class_has_documented_mapping_from_trusted_logical_identity_to_partition_key_strategy"))
    must_fail("remove named cited concurrency component", remove_assertion("ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency", "named_and_cited_consumer_side_key_level_concurrency_component_is_exercised"))
    must_fail("remove partition fallback", remove_assertion("ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency", "tenant_cohort_topic_sharding_fallback_is_exercised"))
    must_fail("remove pre-mapping tenant authorization", remove_assertion("physical_naming_routing_and_cell_topology_adapter_mapping", "tenant_authorization_is_enforced_before_transport_mapping"))
    must_fail("remove consumer semantic replacement proof", remove_assertion("physical_naming_routing_and_cell_topology_adapter_mapping", "replacement_mapping_does_not_require_consumer_semantic_rewrite"))
    must_fail("remove backlog recovery", remove_assertion("broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark", "recovery_drains_backlog_without_starving_current_protected_work"))
    must_fail("remove broker progress non-authority", remove_assertion("broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark", "broker_progress_is_not_business_effect_truth"))

    must_fail("drop credited source evidence", lambda p, e, r: p["credited_evidence"].pop())
    must_fail("credit fifth evidence in plan", lambda p, e, r: p["credited_evidence"].append("capacity_envelope_baseline_growth_stress"))
    must_fail("credit fifth evidence in state", lambda p, e, r: d4a(e)["evidence_completed"].append("capacity_envelope_baseline_growth_stress"))
    must_fail("remove promoted state credit", lambda p, e, r: d4a(e)["evidence_completed"].pop())
    must_fail("wrong source head", lambda p, e, r: r.update(source_reviewed_head="0" * 40))
    must_fail("wrong source run", lambda p, e, r: r["source_workflow"].update(run_id=1))
    must_fail("wrong source attempt", lambda p, e, r: r["source_workflow"].update(run_attempt=2))
    must_fail("wrong source job", lambda p, e, r: r["source_workflow"].update(job_id=1))
    must_fail("wrong artifact name", lambda p, e, r: r["source_workflow"].update(artifact_name="wrong-artifact"))
    must_fail("wrong artifact digest", lambda p, e, r: r["source_workflow"].update(artifact_digest="sha256:" + "0" * 64))
    must_fail("wrong source CI count", lambda p, e, r: r["review_gate"].update(exact_head_ci_success_count=15))
    must_fail("wrong initial Codex review", lambda p, e, r: r["review_gate"].update(initial_codex_review_node_id="PRR_wrong"))
    must_fail("wrong independent review", lambda p, e, r: r["review_gate"].update(independent_adversarial_review_node_id="PRR_wrong"))
    must_fail("wrong fresh Codex review", lambda p, e, r: r["review_gate"].update(fresh_codex_exact_head_review_node_id="PRR_wrong"))
    must_fail("wrong fresh Codex reviewed head", lambda p, e, r: r["review_gate"].update(fresh_codex_reviewed_head="0" * 40))
    must_fail("drop resolved P1", lambda p, e, r: r["review_gate"]["prior_material_findings_resolved"].pop())
    must_fail("unresolved material thread", lambda p, e, r: r["review_gate"].update(unresolved_material_review_threads=1))
    must_fail("wrong final gate comment", lambda p, e, r: r["review_gate"].update(final_gate_comment_id=1))
    must_fail("reuse older review clean", lambda p, e, r: r["review_gate"].update(older_review_reused_as_clean=True))
    must_fail("wrong previous promotion path", lambda p, e, r: r["previous_promotion"].update(path="wrong.json"))
    must_fail("wrong previous promotion digest", lambda p, e, r: r["previous_promotion"].update(sha256="0" * 64))
    must_fail("wrong prior credit chain", lambda p, e, r: r["prior_credited_evidence"].pop())
    must_fail("wrong new evidence kind in promotion", lambda p, e, r: r["credited_evidence"][0].update(evidence_kind="documentation_only"))
    must_fail("promotion adds third new credit", lambda p, e, r: r["credited_evidence"].append({"evidence_id":"capacity_envelope_baseline_growth_stress","evidence_kind":"real_candidate_benchmark"}))
    must_fail("wrong resulting count", lambda p, e, r: r.update(resulting_credited_evidence_count=5))
    must_fail("promotion selects Kafka", lambda p, e, r: r.update(kafka_selection_state="selected"))
    must_fail("promotion grants transport authority", lambda p, e, r: r.update(d4_transport_authority="granted"))
    must_fail("promotion claims live Kafka", lambda p, e, r: r.update(live_kafka_broker_claimed=True))

    print("d4a_evidence_plan_negative_controls=PASS ledger_credit=4 provenance_chain_tamper=blocked review_tamper=blocked fifth_credit=blocked authority_escalation=blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
