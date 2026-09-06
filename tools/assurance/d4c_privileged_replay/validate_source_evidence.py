#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

from evaluate_candidates import CANDIDATES, PROOFS, evaluate

SOURCE = Path("implementation/d4-eventing-async/source-evidence/d4-c-privileged-replay-source.json")
PLAN = Path("implementation/d4-eventing-async/d4-c-evidence-plan.json")
STATE = Path("implementation/d4-eventing-async/state-manifest.json")

CURRENT_CREDITS = [
    "ack_after_durable_responsibility_and_lease_ambiguity",
    "quarantine_redrive_current_authority_and_dedup_preservation",
    "bounded_message_batch_compression_and_parser_limits",
    "scoped_content_equivalence_confidentiality_and_conflict_rejection",
    "outbox_claim_dispatch_ack_ambiguity_and_recovery_continuity",
    "producer_generation_nonresurrection_across_failover_restore",
]
CURRENT_REMAINING = [
    "privileged_bounded_replay_with_original_identity_and_effect_safety",
    "historical_reader_upcaster_semantic_and_equivalence_continuity",
    "recovery_generation_rf_inventory_reconciliation_and_activation_gates",
]
EXPECTED_BOUNDARY = {
    "authorization_rule": "current_privileged_authority_required_per_replay_request",
    "audit_rule": "every_replay_attempt_is_audited_before_effectful_execution",
    "identity_rule": "original_tenant_contract_message_identity_and_semantic_meaning_are_preserved",
    "comparison_rule": "duplicate_sensitive_effects_require_available_historical_equivalence_and_verifier_authority",
    "effect_rule": "dedup_bypass_is_forbidden_and_irreversible_effect_completion_is_never_repeatable",
    "projection_rule": "projection_rebuild_requires_isolated_target_and_replay_generation",
    "evidence_rule": "schema_data_dedup_equivalence_and_recovery_evidence_must_all_remain_safe",
    "storage_identity_rule": "history_storage_product_identity_is_never_message_or_contract_identity",
}
EXPECTED_NON_AUTHORITY = {
    "d4c_ledger_credit": "current_6_of_9_unchanged",
    "open_evt_014_ledger_credit": "uncredited",
    "d4c_candidate": "null_not_selected_candidate_selection_open",
    "d4d_ledger_credit": "zero_of_five",
    "d4_gate": "scoped",
    "d4_transport_authority": "selected_not_granted",
    "canonical_product_implementation_authority": "not_granted",
    "wave4_implementation_authority": "not_granted",
    "production_authority": "none",
    "c3_numeric_topology_authority": "not_selected",
}

def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def fail(msg: str) -> int:
    print(f"d4c_open_evt_014_source_validation=FAIL reason={msg}", file=sys.stderr)
    return 1

def main() -> int:
    try:
        source, plan, state = load(SOURCE), load(PLAN), load(STATE)
    except Exception as exc:
        return fail(str(exc))
    if source.get("source_decision") != "OPEN-EVT-014" or source.get("evidence_id") != "privileged_bounded_replay_with_original_identity_and_effect_safety":
        return fail("source identity drift")
    if tuple(source.get("candidate_classes", [])) != CANDIDATES or tuple(source.get("must_prove", [])) != PROOFS:
        return fail("candidate/proof inventory drift")
    if source.get("candidate_results") != {c: "eligible_for_evidence_execution" for c in CANDIDATES}:
        return fail("candidate result drift")
    if source.get("selection_state") != "not_selected" or source.get("selection_authority") != "not_granted":
        return fail("selection leakage")
    if source.get("ledger_credit") != [] or source.get("current_run_auto_credit") is not False:
        return fail("source auto-credit leakage")
    if source.get("non_authority") != EXPECTED_NON_AUTHORITY or source.get("source_boundary") != EXPECTED_BOUNDARY:
        return fail("source boundary drift")
    runtime = evaluate()
    if runtime["candidate_results"] != source["candidate_results"] or runtime["ledger_credit"] != [] or runtime["current_run_auto_credit"] is not False:
        return fail("runtime source drift")
    if not all(all(v.values()) for v in runtime["proof_results"].values()) or not all(all(v.values()) for v in runtime["check_results"].values()):
        return fail("runtime proof/check failure")
    if plan.get("ledger_credit_state") != "six_of_nine" or plan.get("credited_evidence") != CURRENT_CREDITS or plan.get("remaining_evidence") != CURRENT_REMAINING:
        return fail("D4-C current ledger drift")
    if source["evidence_id"] in plan.get("credited_evidence", []) or source["evidence_id"] not in plan.get("remaining_evidence", []):
        return fail("OPEN-EVT-014 must remain uncredited")
    tracks = {t["track_id"]: t for t in state.get("tracks", [])}
    d4c = tracks.get("D4-C", {})
    if d4c.get("evidence_completed") != CURRENT_CREDITS or d4c.get("evidence_remaining") != CURRENT_REMAINING:
        return fail("D4-C global projection drift")
    if sum(len(t.get("evidence_completed", [])) for t in tracks.values()) != 18:
        return fail("D4-wide current credit count must remain 18/26")
    expected = {
        "gate_state": "scoped",
        "d4_transport_authority": "selected_not_granted",
        "canonical_product_implementation_authority": "not_granted",
        "wave4_implementation_authority": "not_granted",
        "production_authority": "none",
        "c3_numeric_topology_authority": "not_selected",
    }
    for key, value in expected.items():
        if state.get(key) != value:
            return fail(f"authority drift: {key}")
    print("d4c_open_evt_014_source_validation=PASS candidates=3 proofs=8 d4c=6/9 d4wide=18/26 open_evt_014=uncredited selection=none authorities=unchanged")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
