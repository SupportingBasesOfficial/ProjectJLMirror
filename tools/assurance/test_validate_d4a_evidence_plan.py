#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from validate_d4a_evidence_plan import validate_objects

ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = ROOT / "implementation/d4-eventing-async/d4-a-evidence-plan.json"
ENTRY_PATH = ROOT / "implementation/d4-eventing-async/state-manifest.json"
PROMOTION_PATH = ROOT / "implementation/d4-eventing-async/ledger-promotions/d4-a-capacity-ordering-promotion-v1.json"


def must_fail(name: str, mutate) -> None:
    plan = json.loads(PLAN_PATH.read_text())
    entry = json.loads(ENTRY_PATH.read_text())
    promotion = json.loads(PROMOTION_PATH.read_text())
    mutate(plan, entry, promotion)
    if not validate_objects(plan, entry, promotion):
        raise AssertionError(f"negative control unexpectedly passed: {name}")


def d4a(entry: dict) -> dict:
    return next(t for t in entry["tracks"] if t["track_id"] == "D4-A")


def main() -> int:
    must_fail("auto credit", lambda p,e,r: p.update(current_run_auto_credit=True))
    must_fail("premature Kafka selection", lambda p,e,r: p.update(selection_state="selected"))
    must_fail("production numeric escalation", lambda p,e,r: p.update(production_numeric_authority="granted"))
    must_fail("remove promoted credit", lambda p,e,r: p["credited_evidence"].pop())
    must_fail("unauthorized seventh credit", lambda p,e,r: p["credited_evidence"].append("broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark"))
    must_fail("state grants recovery early", lambda p,e,r: d4a(e)["evidence_completed"].append("broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark"))
    must_fail("state loses promoted credit", lambda p,e,r: d4a(e)["evidence_completed"].pop())
    must_fail("state removes remaining recovery", lambda p,e,r: d4a(e)["evidence_remaining"].clear())
    must_fail("wrong source head", lambda p,e,r: r.update(source_reviewed_head="0"*40))
    must_fail("wrong source run", lambda p,e,r: r["source_workflow"].update(run_id=1))
    must_fail("wrong source attempt", lambda p,e,r: r["source_workflow"].update(run_attempt=2))
    must_fail("wrong source job", lambda p,e,r: r["source_workflow"].update(job_id=1))
    must_fail("wrong artifact id", lambda p,e,r: r["source_workflow"].update(artifact_id=1))
    must_fail("wrong artifact digest", lambda p,e,r: r["source_workflow"].update(artifact_digest="sha256:"+"0"*64))
    must_fail("wrong source manifest digest", lambda p,e,r: r.update(source_manifest_sha256="0"*64))
    must_fail("wrong previous promotion digest", lambda p,e,r: r["previous_promotion"].update(sha256="0"*64))
    must_fail("wrong CI count", lambda p,e,r: r["review_gate"].update(exact_head_ci_success_count=16))
    must_fail("wrong independent review", lambda p,e,r: r["review_gate"].update(independent_adversarial_review_node_id="PRR_wrong"))
    must_fail("wrong fresh Codex review", lambda p,e,r: r["review_gate"].update(fresh_codex_exact_head_review_node_id="PRR_wrong"))
    must_fail("wrong fresh reviewed head", lambda p,e,r: r["review_gate"].update(fresh_codex_reviewed_head="0"*40))
    must_fail("drop resolved P1", lambda p,e,r: r["review_gate"]["prior_material_findings_resolved"].pop())
    must_fail("unresolved thread", lambda p,e,r: r["review_gate"].update(unresolved_material_review_threads=1))
    must_fail("wrong final gate comment", lambda p,e,r: r["review_gate"].update(final_gate_comment_id=1))
    must_fail("older review reused", lambda p,e,r: r["review_gate"].update(older_review_reused_as_clean=True))
    must_fail("wrong prior credit chain", lambda p,e,r: r["prior_credited_evidence"].pop())
    must_fail("promotion adds recovery", lambda p,e,r: r["credited_evidence"].append({"evidence_id":"broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark","evidence_kind":"real_candidate_failure_recovery_benchmark"}))
    must_fail("wrong resulting count", lambda p,e,r: r.update(resulting_credited_evidence_count=7))
    must_fail("promotion removes live Kafka source fact", lambda p,e,r: r.update(live_kafka_broker_claimed=False))
    must_fail("promotion claims recovery", lambda p,e,r: r.update(recovery_benchmark_claimed=True))
    must_fail("promotion grants transport", lambda p,e,r: r.update(d4_transport_authority="granted"))
    print("d4a_evidence_plan_negative_controls=PASS ledger_credit=6 remaining=1 provenance_chain_tamper=blocked review_tamper=blocked seventh_credit=blocked recovery_overclaim=blocked authority_escalation=blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
