#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path

from validate_d4a_evidence_plan import EXPECTED_EVIDENCE, EXPECTED_KINDS, REQUIRED_ASSERTIONS, validate_objects

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


def main() -> int:
    must_fail("collapse inventory", lambda p, e: p.update(required_evidence=[{"evidence_id":"documentation","evidence_kind":"documentation_only","must_prove":[]}]))
    must_fail("auto credit", lambda p, e: p.update(current_run_auto_credit=True))
    must_fail("premature Kafka selection", lambda p, e: p.update(selection_state="selected"))
    must_fail("production numeric escalation", lambda p, e: p.update(production_numeric_authority="granted"))
    must_fail("arbitrary synthetic evidence kind", lambda p, e: item(p, "capacity_envelope_baseline_growth_stress").update(evidence_kind="synthetic_probe"))
    must_fail("weaken ordering evidence kind", lambda p, e: item(p, "ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency").update(evidence_kind="unit_test"))
    must_fail("weaken recovery evidence kind", lambda p, e: item(p, "broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark").update(evidence_kind="documentation_only"))
    must_fail("remove capacity measurement", lambda p, e: item(p, "capacity_envelope_baseline_growth_stress")["must_prove"].remove("throughput_latency_backlog_and_recovery_are_measured"))
    must_fail("remove opaque erasure reference", lambda p, e: item(p, "regulated_payload_erasure_granularity")["must_prove"].remove("opaque_reference_profile_supports_governed_per_record_erasure"))
    must_fail("remove regulated per-tenant exception isolation", lambda p, e: item(p, "regulated_payload_erasure_granularity")["must_prove"].remove("raw_payload_exception_requires_per_tenant_topic_or_partition_assignment"))
    must_fail("remove regulated exception retention ceiling", lambda p, e: item(p, "regulated_payload_erasure_granularity")["must_prove"].remove("raw_payload_exception_requires_maximum_segment_retention_ceiling_meeting_governed_erasure_sla"))
    must_fail("remove regulated exception governance signoff", lambda p, e: item(p, "regulated_payload_erasure_granularity")["must_prove"].remove("raw_payload_exception_requires_signoff_by_erasure_governance_authority"))
    must_fail("remove protected consumer positive control", lambda p, e: item(p, "exactly_once_guardrail_consumer_inbox_enforcement")["must_prove"].remove("valid_consumer_with_real_effect_protection_is_accepted"))
    must_fail("remove trusted ordering identity", lambda p, e: item(p, "ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency")["must_prove"].remove("logical_ordering_scope_maps_from_trusted_identity"))
    must_fail("remove partition fallback", lambda p, e: item(p, "ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency")["must_prove"].remove("tenant_cohort_topic_sharding_fallback_is_exercised"))
    must_fail("remove pre-mapping tenant authorization", lambda p, e: item(p, "physical_naming_routing_and_cell_topology_adapter_mapping")["must_prove"].remove("tenant_authorization_is_enforced_before_transport_mapping"))
    must_fail("remove backlog recovery", lambda p, e: item(p, "broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark")["must_prove"].remove("recovery_drains_backlog_without_starving_current_protected_work"))
    must_fail("remove broker progress non-authority", lambda p, e: item(p, "broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark")["must_prove"].remove("broker_progress_is_not_business_effect_truth"))
    must_fail("precredit entry ledger", lambda p, e: next(t for t in e["tracks"] if t["track_id"] == "D4-A")["evidence_completed"].append("capacity_envelope_baseline_growth_stress"))
    print("d4a_evidence_plan_negative_controls=PASS cases=19")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
