from __future__ import annotations

import copy

from validate_source_evidence import load_objects, validate_objects, FINAL_RECOVERY_ID


def must_fail(name: str, mutate, expected: str) -> None:
    source, profile, plan, state = (copy.deepcopy(item) for item in load_objects())
    mutate(source, profile, plan, state)
    errors = validate_objects(source, profile, plan, state)
    if not any(expected in error for error in errors):
        raise AssertionError(f"negative control {name!r} unexpectedly passed: {errors!r}")


def main() -> int:
    d4a = lambda st: next(t for t in st["tracks"] if t["track_id"] == "D4-A")
    must_fail("mutable Kafka tag", lambda s,p,l,st: s.__setitem__("candidate_image", "apache/kafka:4.3.1"), "Kafka image pin drift")
    must_fail("physical partition key", lambda s,p,l,st: p["ordering_scope_mappings"]["per_subject_ordered"].__setitem__("partition_key", "topic+partition"), "physical transport identity")
    must_fail("missing ordering profile", lambda s,p,l,st: p["ordering_scope_mappings"].pop("per_source_ordered"), "ordering scope coverage drift")
    must_fail("global serialization", lambda s,p,l,st: s["ordering_component"].__setitem__("global_or_tenant_wide_serialization", True), "global/tenant-wide serialization prohibited")
    must_fail("synthetic degradation substitute", lambda s,p,l,st: p["degradation_probe"].__setitem__("mechanism", "synthetic_sleep"), "real Kafka quota")
    must_fail("remove partition admission", lambda s,p,l,st: p["tiers"][0].__setitem__("admission", {}), "target-relative throughput admission drift")
    must_fail("weaken partition admission", lambda s,p,l,st: p["tiers"][2]["admission"].__setitem__("minimum_target_throughput_fraction", 0.01), "target-relative throughput admission drift")
    must_fail("partition ceiling loses same-tier binding", lambda s,p,l,st: p["partition_ceiling_policy"].__setitem__("minimum_target_throughput_fraction_meaning", "arbitrary_fixed_floor"), "same-tier target")
    must_fail("missing device cardinality", lambda s,p,l,st: p["tiers"][0].pop("device_cardinality_by_tenant"), "device cardinality tenant coverage drift")
    must_fail("device cardinality tenant mismatch", lambda s,p,l,st: p["tiers"][1]["device_cardinality_by_tenant"].pop("tenant-d"), "device cardinality tenant coverage drift")
    must_fail("device cardinality exceeds event allocation", lambda s,p,l,st: p["tiers"][0]["device_cardinality_by_tenant"].__setitem__("tenant-b", 81), "device cardinality exceeds exercised event allocation")
    must_fail("device pressure fails to grow", lambda s,p,l,st: p["tiers"][1].__setitem__("device_cardinality_by_tenant", {"tenant-a": 30, "tenant-b": 10, "tenant-c": 8, "tenant-d": 4}), "device cardinality pressure not increasing")
    must_fail("fake fallback trigger", lambda s,p,l,st: p["tenant_cohort_fallback"].__setitem__("trigger", "modeled_ceiling_plus_one_without_exercised_scopes"), "actually exercised over-ceiling scopes")
    must_fail("fallback not over-ceiling", lambda s,p,l,st: p["tenant_cohort_fallback"].__setitem__("exercise", "six_static_tenants"), "actual over-ceiling logical-scope workload")
    must_fail("fallback changes logical identity", lambda s,p,l,st: p["tenant_cohort_fallback"].__setitem__("logical_contract_identity_changes", True), "must not change logical contract identity")
    must_fail("source auto credit", lambda s,p,l,st: s.__setitem__("ledger_credit", ["capacity_envelope_baseline_growth_stress"]), "source package self-promotion")
    must_fail("source historical prior credit rewrite", lambda s,p,l,st: s["prior_promoted_ledger_credit"].append("capacity_envelope_baseline_growth_stress"), "source historical prior promoted credit drift")
    must_fail("historical source selection rewrite", lambda s,p,l,st: s.__setitem__("kafka_selection_state", "selected"), "premature Kafka selection")
    must_fail("remove final recovery global credit", lambda s,p,l,st: l["credited_evidence"].remove(FINAL_RECOVERY_ID), "global promoted seven-of-seven credit drift")
    must_fail("duplicate eighth global credit", lambda s,p,l,st: l["credited_evidence"].append(FINAL_RECOVERY_ID), "global promoted seven-of-seven credit multiplicity drift")
    must_fail("state loses final recovery credit", lambda s,p,l,st: d4a(st)["evidence_completed"].remove(FINAL_RECOVERY_ID), "completed seven-of-seven evidence drift")
    must_fail("state reopens recovery", lambda s,p,l,st: d4a(st)["evidence_remaining"].append(FINAL_RECOVERY_ID), "no remaining evidence")
    must_fail("historical outage recovery overclaim", lambda s,p,l,st: s.__setitem__("outage_recovery_benchmark_claimed", True), "historical source D4-A7 outage recovery overclaim")
    must_fail("global Kafka selection rollback", lambda s,p,l,st: l.__setitem__("selection_state", "not_selected"), "plan must keep Kafka selected")
    must_fail("global candidate-status rollback", lambda s,p,l,st: l.__setitem__("candidate_status", "leading_candidate_evidence_complete_selection_pending"), "selected C2 candidate")
    must_fail("skip separate D4 acceptance", lambda s,p,l,st: l.__setitem__("acceptance_state", "accepted"), "separate D4 acceptance")
    must_fail("transport authority grant", lambda s,p,l,st: st.__setitem__("d4_transport_authority", "granted"), "selected but ungranted")
    print("d4a_capacity_ordering_negative_controls=PASS source_history=immutable historical_result=6 global_seven_of_seven=exact kafka_selected_current=true selection_rollback=blocked transport_grant=blocked device_cardinality=blocked fake_fallback=blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
