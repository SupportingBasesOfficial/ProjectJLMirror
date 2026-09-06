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
EXPECTED_SOURCE_KEYS = {
    "schema_version",
    "gate_id",
    "track_id",
    "mode",
    "source_decision",
    "evidence_id",
    "candidate_classes",
    "must_prove",
    "candidate_results",
    "selection_state",
    "selection_authority",
    "current_run_auto_credit",
    "ledger_credit",
    "non_authority",
    "source_boundary",
}
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


def fail(msg: str) -> int:
    print(f"d4c_open_evt_014_source_validation=FAIL reason={msg}", file=sys.stderr)
    return 1


def main() -> int:
    try:
        source, plan, state = load(SOURCE), load(PLAN), load(STATE)
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
    if (
        source.get("source_decision") != "OPEN-EVT-014"
        or source.get("evidence_id")
        != "privileged_bounded_replay_with_original_identity_and_effect_safety"
    ):
        return fail("source identity drift")
    if tuple(source.get("candidate_classes", [])) != CANDIDATES:
        return fail("candidate inventory drift")
    if tuple(source.get("must_prove", [])) != PROOFS:
        return fail("proof inventory drift")
    if source.get("candidate_results") != {
        c: "eligible_for_evidence_execution" for c in CANDIDATES
    }:
        return fail("candidate result drift")
    if (
        source.get("selection_state") != "not_selected"
        or source.get("selection_authority") != "not_granted"
    ):
        return fail("selection leakage")
    if type(source.get("current_run_auto_credit")) is not bool:
        return fail("auto-credit type drift")
    if source["current_run_auto_credit"] is not False or source.get("ledger_credit") != []:
        return fail("source auto-credit leakage")
    if source.get("non_authority") != EXPECTED_NON_AUTHORITY:
        return fail("source non-authority boundary drift")
    if source.get("source_boundary") != EXPECTED_BOUNDARY:
        return fail("source semantic boundary drift")

    runtime = evaluate()
    if runtime["candidate_results"] != source["candidate_results"]:
        return fail("runtime candidate result drift")
    if runtime["selection"] != "not_selected" or runtime["selection_authority"] != "not_granted":
        return fail("runtime selection leakage")
    if runtime["ledger_credit"] != [] or runtime["current_run_auto_credit"] is not False:
        return fail("runtime source auto-credit leakage")
    for candidate in CANDIDATES:
        if set(runtime["proof_results"].get(candidate, {})) != set(PROOFS):
            return fail(f"runtime proof inventory drift for {candidate}")
        if not all(runtime["proof_results"][candidate].values()):
            return fail(f"runtime proof failure for {candidate}")
        if not all(runtime["check_results"][candidate].values()):
            return fail(f"runtime check failure for {candidate}")

    if (
        plan.get("ledger_credit_state") != "six_of_nine"
        or plan.get("credited_evidence") != CURRENT_CREDITS
        or plan.get("remaining_evidence") != CURRENT_REMAINING
    ):
        return fail("D4-C current ledger drift")
    if (
        source["evidence_id"] in plan.get("credited_evidence", [])
        or source["evidence_id"] not in plan.get("remaining_evidence", [])
    ):
        return fail("OPEN-EVT-014 must remain uncredited")
    if plan.get("candidate") is not None or plan.get("candidate_status") != "not_selected":
        return fail("D4-C candidate selection leakage")

    tracks = {t["track_id"]: t for t in state.get("tracks", [])}
    if set(tracks) != {"D4-A", "D4-B", "D4-C", "D4-D"}:
        return fail("D4 track inventory drift")
    d4c = tracks["D4-C"]
    if (
        d4c.get("evidence_completed") != CURRENT_CREDITS
        or d4c.get("evidence_remaining") != CURRENT_REMAINING
    ):
        return fail("D4-C global projection drift")
    if (
        d4c.get("candidate") is not None
        or d4c.get("candidate_status") != "not_selected"
        or d4c.get("state") != "candidate_selection_open"
    ):
        return fail("D4-C global selection leakage")
    if tracks["D4-D"].get("evidence_completed") != [] or tracks["D4-D"].get("candidate") is not None:
        return fail("D4-D leakage")
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

    print(
        "d4c_open_evt_014_source_validation=PASS candidates=3 proofs=8 "
        "source_schema=exact d4c=6/9 d4wide=18/26 open_evt_014=uncredited "
        "selection=none authorities=unchanged"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
