#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from validate_d4a_evidence_plan import validate_objects

ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = ROOT / "implementation/d4-eventing-async/d4-a-evidence-plan.json"
ENTRY_PATH = ROOT / "implementation/d4-eventing-async/state-manifest.json"


def must_fail(name: str, mutate) -> None:
    plan = json.loads(PLAN_PATH.read_text())
    entry = json.loads(ENTRY_PATH.read_text())
    mutate(plan, entry)
    assert validate_objects(plan, entry), f"negative control unexpectedly passed: {name}"


def item(plan: dict, evidence_id: str) -> dict:
    return next(i for i in plan["required_evidence"] if i["evidence_id"] == evidence_id)


def remove_assertion(evidence_id: str, assertion: str):
    def mutate(plan: dict, entry: dict) -> None:
        item(plan, evidence_id)["must_prove"].remove(assertion)
    return mutate


def main() -> int:
    must_fail("collapse inventory", lambda p, e: p.update(required_evidence=[{"evidence_id":"documentation","evidence_kind":"documentation_only","must_prove":[]}]))
    must_fail("auto credit", lambda p, e: p.update(current_run_auto_credit=True))
    must_fail("premature Kafka selection", lambda p, e: p.update(selection_state="selected"))
    must_fail("production numeric escalation", lambda p, e: p.update(production_numeric_authority="granted"))
    must_fail("arbitrary synthetic evidence kind", lambda p, e: item(p, "capacity_envelope_baseline_growth_stress").update(evidence_kind="synthetic_probe"))
    must_fail("weaken ordering evidence kind", lambda p, e: item(p, "ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency").update(evidence_kind="unit_test"))
    must_fail("weaken recovery evidence kind", lambda p, e: item(p, "broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark").update(evidence_kind="documentation_only"))

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
    must_fail("remove backlog recovery", remove_assertion("broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark", "recovery_drains_backlog_without_starving_current_protected_work"))
    must_fail("remove broker progress non-authority", remove_assertion("broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark", "broker_progress_is_not_business_effect_truth"))
    must_fail("precredit entry ledger", lambda p, e: next(t for t in e["tracks"] if t["track_id"] == "D4-A")["evidence_completed"].append("capacity_envelope_baseline_growth_stress"))
    print("d4a_evidence_plan_negative_controls=PASS cases=24")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
