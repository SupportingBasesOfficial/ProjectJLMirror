#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

from evaluate_candidates import CANDIDATES, PROOFS, evaluate

SOURCE = Path("implementation/d4-eventing-async/source-evidence/d4-c-producer-generation-source.json")
PLAN = Path("implementation/d4-eventing-async/d4-c-evidence-plan.json")
STATE = Path("implementation/d4-eventing-async/state-manifest.json")

EXPECTED_CURRENT_CREDITS = [
    "ack_after_durable_responsibility_and_lease_ambiguity",
    "quarantine_redrive_current_authority_and_dedup_preservation",
    "bounded_message_batch_compression_and_parser_limits",
    "scoped_content_equivalence_confidentiality_and_conflict_rejection",
    "outbox_claim_dispatch_ack_ambiguity_and_recovery_continuity",
    "producer_generation_nonresurrection_across_failover_restore",
    "privileged_bounded_replay_with_original_identity_and_effect_safety",
    "historical_reader_upcaster_semantic_and_equivalence_continuity",
]
EXPECTED_CURRENT_REMAINING = [
    "recovery_generation_rf_inventory_reconciliation_and_activation_gates",
]
EXPECTED_SOURCE_KEYS = {
    "schema_version", "gate_id", "track_id", "mode", "source_decision", "evidence_id",
    "candidate_classes", "must_prove", "candidate_results", "selection_state",
    "selection_authority", "current_run_auto_credit", "ledger_credit", "non_authority",
    "source_boundary",
}
EXPECTED_NON_AUTHORITY = {
    "d4c_ledger_credit": "current_5_of_9_unchanged",
    "open_evt_013_ledger_credit": "uncredited",
    "d4c_candidate": "null_not_selected_candidate_selection_open",
    "d4d_ledger_credit": "zero_of_five",
    "d4_gate": "scoped",
    "d4_transport_authority": "selected_not_granted",
    "canonical_product_implementation_authority": "not_granted",
    "wave4_implementation_authority": "not_granted",
    "production_authority": "none",
    "c3_numeric_topology_authority": "not_selected",
}
EXPECTED_BOUNDARY = {
    "platform_generation_authority": "explicit_current_generation_only",
    "historical_generation": "historical_fact_metadata_not_current_authority",
    "restore_rule": "surviving_current_authority_and_retirement_fences_cannot_be_lowered_by_restored_snapshot",
    "failover_rule": "placement_change_does_not_change_logical_source_identity_or_revive_retired_generation",
    "comparison_rule": "exact_current_generation_equality_only_no_numeric_or_lexical_ordering_authority",
    "external_generation_rule": "provider_and_broker_generations_are_observations_not_platform_source_generation",
}


class DuplicateKeyError(ValueError):
    pass


def no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise DuplicateKeyError(f"duplicate JSON member: {key}")
        out[key] = value
    return out


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)


def fail(message: str) -> int:
    print(f"d4c_open_evt_013_source_validation=FAIL reason={message}", file=sys.stderr)
    return 1


def main() -> int:
    try:
        source = load(SOURCE)
        plan = load(PLAN)
        state = load(STATE)
    except Exception as exc:
        return fail(str(exc))

    if not isinstance(source, dict) or set(source) != EXPECTED_SOURCE_KEYS:
        return fail("source exact key schema drift")
    if type(source.get("schema_version")) is not int or source["schema_version"] != 1:
        return fail("schema_version must be exact integer 1")
    if source.get("gate_id") != "D4" or source.get("track_id") != "D4-C":
        return fail("gate or track drift")
    if source.get("mode") != "candidate_source_evidence_only":
        return fail("source mode drift")
    if source.get("source_decision") != "OPEN-EVT-013":
        return fail("source decision drift")
    if source.get("evidence_id") != "producer_generation_nonresurrection_across_failover_restore":
        return fail("evidence id drift")
    if tuple(source.get("candidate_classes", [])) != CANDIDATES:
        return fail("candidate class drift")
    if tuple(source.get("must_prove", [])) != PROOFS:
        return fail("proof inventory drift")
    if source.get("candidate_results") != {c: "eligible_for_evidence_execution" for c in CANDIDATES}:
        return fail("declared candidate result drift")
    if source.get("selection_state") != "not_selected" or source.get("selection_authority") != "not_granted":
        return fail("selection leakage")
    if type(source.get("current_run_auto_credit")) is not bool or source["current_run_auto_credit"] is not False:
        return fail("auto-credit leakage")
    if source.get("ledger_credit") != []:
        return fail("source run must remain historically non-promoting")

    non_authority = source.get("non_authority")
    if not isinstance(non_authority, dict) or non_authority != EXPECTED_NON_AUTHORITY:
        return fail("historical source non-authority exact boundary drift")

    boundary = source.get("source_boundary")
    if not isinstance(boundary, dict) or boundary != EXPECTED_BOUNDARY:
        return fail("source boundary exact value drift")

    runtime = evaluate()
    if runtime["candidate_results"] != source["candidate_results"]:
        return fail("runtime candidate results differ from source manifest")
    if runtime["selection"] != "not_selected" or runtime["selection_authority"] != "not_granted":
        return fail("runtime selection leakage")
    if runtime["ledger_credit"] != [] or runtime["current_run_auto_credit"] is not False:
        return fail("runtime source auto-credit leakage")
    for candidate in CANDIDATES:
        if not all(runtime["proof_results"][candidate].values()):
            return fail(f"proof failure for {candidate}")
        if not all(runtime["check_results"][candidate].values()):
            return fail(f"check failure for {candidate}")

    if plan.get("ledger_credit_state") != "eight_of_nine":
        return fail("D4-C current ledger must be eight_of_nine after separate promotions")
    if plan.get("credited_evidence") != EXPECTED_CURRENT_CREDITS:
        return fail("D4-C current credited evidence drift")
    if plan.get("remaining_evidence") != EXPECTED_CURRENT_REMAINING:
        return fail("D4-C current remaining evidence drift")
    if source["evidence_id"] not in plan["credited_evidence"] or source["evidence_id"] in plan["remaining_evidence"]:
        return fail("OPEN-EVT-013 current ledger projection must reflect separate reviewed promotion")
    if plan.get("candidate") is not None or plan.get("candidate_status") != "not_selected":
        return fail("D4-C candidate selection leakage")

    tracks = {track["track_id"]: track for track in state.get("tracks", [])}
    if set(tracks) != {"D4-A", "D4-B", "D4-C", "D4-D"}:
        return fail("D4 track inventory drift")
    d4c = tracks["D4-C"]
    if d4c.get("evidence_completed") != EXPECTED_CURRENT_CREDITS or d4c.get("evidence_remaining") != EXPECTED_CURRENT_REMAINING:
        return fail("D4-C current global evidence projection drift")
    if d4c.get("candidate") is not None or d4c.get("candidate_status") != "not_selected" or d4c.get("state") != "candidate_selection_open":
        return fail("D4-C global selection leakage")
    if tracks["D4-D"].get("evidence_completed") != [] or tracks["D4-D"].get("candidate") is not None:
        return fail("D4-D leakage")
    if sum(len(track.get("evidence_completed", [])) for track in tracks.values()) != 20:
        return fail("D4-wide current credit count must be 20/26")

    expected_authority = {
        "gate_state": "scoped",
        "d4_transport_authority": "selected_not_granted",
        "canonical_product_implementation_authority": "not_granted",
        "wave4_implementation_authority": "not_granted",
        "production_authority": "none",
        "c3_numeric_topology_authority": "not_selected",
    }
    for key, expected in expected_authority.items():
        if state.get(key) != expected:
            return fail(f"authority drift: {key}")

    print(
        "d4c_open_evt_013_source_validation=PASS candidates=3 proofs=7 boundary=exact "
        "source_history=non_promoting_at_5_of_9 current_d4c=8/9 d4wide=20/26 "
        "open_evt_013=current_promoted_by_separate_review selection=none authorities=unchanged"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
