#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from validate_d4a_evidence_plan import validate, validate_objects

ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = ROOT / "implementation/d4-eventing-async/d4-a-evidence-plan.json"
ENTRY_PATH = ROOT / "implementation/d4-eventing-async/state-manifest.json"
PROMOTION_PATH = ROOT / "implementation/d4-eventing-async/ledger-promotions/d4-a-recovery-promotion-v1.json"
SELECTION_PATH = ROOT / "implementation/d4-eventing-async/d4-a-selection-record.json"
PREVIOUS_PROMOTION_REL = Path("implementation/d4-eventing-async/ledger-promotions/d4-a-capacity-ordering-promotion-v1.json")
SEMANTIC_PROMOTION_REL = Path("implementation/d4-eventing-async/ledger-promotions/d4-a-semantic-boundary-promotion-v1.json")
RECOVERY_SOURCE_REL = Path("implementation/d4-eventing-async/source-evidence/recovery/source-evidence-manifest.json")
DATA_SOURCE_REL = Path("implementation/d4-eventing-async/source-evidence/data-topology/source-evidence-manifest.json")


def load_objects() -> tuple[dict, dict, dict, dict]:
    return (
        json.loads(PLAN_PATH.read_text()),
        json.loads(ENTRY_PATH.read_text()),
        json.loads(PROMOTION_PATH.read_text()),
        json.loads(SELECTION_PATH.read_text()),
    )


def must_fail(name: str, mutate) -> None:
    plan, entry, promotion, selection = load_objects()
    mutate(plan, entry, promotion, selection)
    if not validate_objects(plan, entry, promotion, selection):
        raise AssertionError(f"negative control unexpectedly passed: {name}")


def must_fail_bytes(name: str, relative_path: Path, mutate_bytes) -> None:
    with tempfile.TemporaryDirectory(prefix="d4a-chain-") as tmp:
        tmp_root = Path(tmp)
        shutil.copytree(ROOT / "implementation", tmp_root / "implementation")
        target = tmp_root / relative_path
        target.write_bytes(mutate_bytes(target.read_bytes()))
        errors = validate(tmp_root)
        if not errors:
            raise AssertionError(f"byte-level negative control unexpectedly passed: {name}")


def d4a(entry: dict) -> dict:
    return next(t for t in entry["tracks"] if t["track_id"] == "D4-A")


def item(plan: dict, evidence_id: str) -> dict:
    return next(i for i in plan["required_evidence"] if i["evidence_id"] == evidence_id)


def remove_assertion(evidence_id: str, assertion: str):
    def mutate(plan: dict, entry: dict, promotion: dict, selection: dict) -> None:
        item(plan, evidence_id)["must_prove"].remove(assertion)
    return mutate


def flip_first_byte(data: bytes) -> bytes:
    if not data:
        raise AssertionError("cannot mutate empty evidence file")
    return bytes([data[0] ^ 1]) + data[1:]


def main() -> int:
    must_fail("auto credit", lambda p,e,r,s: p.update(current_run_auto_credit=True))
    must_fail("selection rollback", lambda p,e,r,s: p.update(selection_state="not_selected"))
    must_fail("full D4 acceptance smuggled into track selection", lambda p,e,r,s: p.update(acceptance_state="accepted"))
    must_fail("candidate status rollback", lambda p,e,r,s: p.update(candidate_status="leading_candidate_evidence_complete_selection_pending"))
    must_fail("production numeric escalation", lambda p,e,r,s: p.update(production_numeric_authority="granted"))
    must_fail("wrong selection record path", lambda p,e,r,s: p.update(selection_record="implementation/d4-eventing-async/other.json"))
    must_fail("collapse evidence inventory", lambda p,e,r,s: p.update(required_evidence=[{"evidence_id":"documentation","evidence_kind":"documentation_only","must_prove":["something"]}]))
    must_fail("weaken capacity kind", lambda p,e,r,s: item(p,"capacity_envelope_baseline_growth_stress").update(evidence_kind="documentation_only"))
    must_fail("remove capacity measurement proof", remove_assertion("capacity_envelope_baseline_growth_stress", "throughput_latency_backlog_and_recovery_are_measured"))
    must_fail("remove ordering component proof", remove_assertion("ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency", "named_and_cited_consumer_side_key_level_concurrency_component_is_exercised"))
    must_fail("remove recovery survival proof", remove_assertion("broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark", "committed_outbox_backlog_survives_broker_outage"))
    must_fail("remove recovery anti-starvation proof", remove_assertion("broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark", "recovery_drains_backlog_without_starving_current_protected_work"))
    must_fail("remove recovery ambiguity proof", remove_assertion("broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark", "broker_ack_ambiguity_reuses_same_logical_message_identity"))
    must_fail("remove recovery effect-boundary proof", remove_assertion("broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark", "broker_progress_is_not_business_effect_truth"))
    must_fail("remove promoted credit", lambda p,e,r,s: p["credited_evidence"].pop())
    must_fail("duplicate eighth credit", lambda p,e,r,s: p["credited_evidence"].append("broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark"))
    must_fail("state loses recovery credit", lambda p,e,r,s: d4a(e)["evidence_completed"].pop())
    must_fail("state reopens recovery", lambda p,e,r,s: d4a(e)["evidence_remaining"].append("broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark"))
    must_fail("state selection rollback", lambda p,e,r,s: d4a(e).update(state="evidence_complete_selection_pending"))
    must_fail("transport selection rollback", lambda p,e,r,s: e.update(d4_transport_authority="not_selected_not_granted"))
    must_fail("transport authority grant", lambda p,e,r,s: e.update(d4_transport_authority="granted"))
    must_fail("full D4 gate acceptance", lambda p,e,r,s: e.update(gate_state="separately_accepted"))
    must_fail("sibling candidate leak", lambda p,e,r,s: e["tracks"][1].update(candidate="protobuf"))

    # Historical promotion facts must remain exactly pre-selection.
    must_fail("rewrite historical promotion selection", lambda p,e,r,s: r.update(kafka_selection_state="selected"))
    must_fail("rewrite historical transport state", lambda p,e,r,s: r.update(d4_transport_authority="selected_not_granted"))
    must_fail("wrong source head", lambda p,e,r,s: r.update(source_reviewed_head="0"*40))
    must_fail("wrong source run", lambda p,e,r,s: r["source_workflow"].update(run_id=1))
    must_fail("wrong source attempt", lambda p,e,r,s: r["source_workflow"].update(run_attempt=2))
    must_fail("wrong source job", lambda p,e,r,s: r["source_workflow"].update(job_id=1))
    must_fail("wrong artifact id", lambda p,e,r,s: r["source_workflow"].update(artifact_id=1))
    must_fail("wrong artifact digest", lambda p,e,r,s: r["source_workflow"].update(artifact_digest="sha256:"+"0"*64))
    must_fail("wrong source manifest digest", lambda p,e,r,s: r.update(source_manifest_sha256="0"*64))
    must_fail("wrong previous promotion digest", lambda p,e,r,s: r["previous_promotion"].update(sha256="0"*64))
    must_fail("wrong CI count", lambda p,e,r,s: r["review_gate"].update(exact_head_ci_success_count=17))
    must_fail("wrong independent review", lambda p,e,r,s: r["review_gate"].update(independent_adversarial_review_node_id="PRR_wrong"))
    must_fail("wrong fresh Codex review", lambda p,e,r,s: r["review_gate"].update(fresh_codex_exact_head_review_node_id="PRR_wrong"))
    must_fail("wrong fresh reviewed head", lambda p,e,r,s: r["review_gate"].update(fresh_codex_reviewed_head="0"*40))
    must_fail("drop resolved finding", lambda p,e,r,s: r["review_gate"]["prior_material_findings_resolved"].clear())
    must_fail("unresolved thread", lambda p,e,r,s: r["review_gate"].update(unresolved_material_review_threads=1))
    must_fail("wrong final gate comment", lambda p,e,r,s: r["review_gate"].update(final_gate_comment_id=1))
    must_fail("older review reused", lambda p,e,r,s: r["review_gate"].update(older_review_reused_as_clean=True))
    must_fail("wrong prior credit chain", lambda p,e,r,s: r["prior_credited_evidence"].pop())
    must_fail("wrong new credit", lambda p,e,r,s: r["credited_evidence"][0].update(evidence_id="capacity_envelope_baseline_growth_stress"))
    must_fail("wrong resulting count", lambda p,e,r,s: r.update(resulting_credited_evidence_count=6))

    # Selection record is the only current selection authority.
    must_fail("wrong selection base", lambda p,e,r,s: s.update(selection_base_main_commit="0"*40))
    must_fail("wrong Kafka family", lambda p,e,r,s: s.update(candidate_family="rabbitmq"))
    must_fail("wrong Kafka version", lambda p,e,r,s: s.update(candidate_version="4.3.2"))
    must_fail("mutable Kafka image", lambda p,e,r,s: s.update(candidate_conformance_image="apache/kafka:4.3.1"))
    must_fail("wrong Kafka OCI digest", lambda p,e,r,s: s.update(candidate_oci_index_digest="sha256:"+"0"*64))
    must_fail("wrong Kafka amd64 digest", lambda p,e,r,s: s.update(candidate_linux_amd64_manifest_digest="sha256:"+"0"*64))
    must_fail("selection loses evidence", lambda p,e,r,s: s.update(credited_evidence_count=6))
    must_fail("selection scope widens", lambda p,e,r,s: s.update(selection_scope="production_transport_authority"))
    must_fail("selection grants D4", lambda p,e,r,s: s.update(d4_gate_state="separately_accepted"))
    must_fail("selection grants transport authority", lambda p,e,r,s: s.update(d4_transport_authority="granted"))
    must_fail("selection grants product", lambda p,e,r,s: s.update(canonical_product_implementation_authority="granted"))
    must_fail("selection grants wave4", lambda p,e,r,s: s.update(wave4_implementation_authority="granted"))
    must_fail("selection grants production", lambda p,e,r,s: s.update(production_authority="granted"))
    must_fail("selection grants C3", lambda p,e,r,s: s.update(c3_numeric_topology_authority="selected"))
    must_fail("selection drops sibling requirement", lambda p,e,r,s: s.update(d4_bc_d_completion_required=False))
    must_fail("selection drops separate acceptance", lambda p,e,r,s: s.update(separate_d4_acceptance_required=False))

    must_fail_bytes("tamper recovery source manifest", RECOVERY_SOURCE_REL, flip_first_byte)
    must_fail_bytes("tamper previous promotion record", PREVIOUS_PROMOTION_REL, flip_first_byte)
    must_fail_bytes("tamper semantic-boundary promotion record", SEMANTIC_PROMOTION_REL, flip_first_byte)
    must_fail_bytes("tamper data-topology source manifest", DATA_SOURCE_REL, flip_first_byte)
    print("d4a_evidence_plan_negative_controls=PASS ledger_credit=7 selection=kafka bounded_c2=locked historical_promotion=immutable full_d4_acceptance=blocked transport_grant=blocked product_wave4_production=blocked c3=blocked provenance_full_chain_tamper=blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
