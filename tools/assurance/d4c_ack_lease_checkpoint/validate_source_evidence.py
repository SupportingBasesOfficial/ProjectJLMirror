#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

from evaluate_candidates import CANDIDATES, evaluate_all


SOURCE_PATH = Path("implementation/d4-eventing-async/source-evidence/d4-c-ack-lease-checkpoint-source.json")
PLAN_PATH = Path("implementation/d4-eventing-async/d4-c-candidate-evaluation-plan.json")
STATE_PATH = Path("implementation/d4-eventing-async/state-manifest.json")

EXPECTED_PROOFS = [
    "ack_or_checkpoint_never_precedes_durable_consumer_responsibility",
    "lease_or_visibility_expiry_is_treated_as_ambiguity_not_effect_absence",
    "broker_progress_is_never_business_effect_truth",
    "redelivery_or_offset_rewind_remains_safe_through_inbox_effect_idempotency",
    "offset_rewind_duplicate_handling_requires_scoped_id_content_equivalence_evidence_not_identity_alone",
    "same_scoped_identity_with_conflicting_immutable_content_fails_closed",
    "claim_ownership_and_takeover_are_fenced_against_concurrent_effect_execution",
    "crash_between_effect_responsibility_and_broker_ack_recovers_without_semantic_loss",
]

EXPECTED_ASSERTIONS = [
    "all_three_concrete_candidate_classes_use_the_same_platform_durable_responsibility_and_fencing_semantics",
    "premature_ack_or_checkpoint_before_durable_responsibility_is_rejected",
    "broker_ack_or_checkpoint_progress_without_effect_completion_does_not_report_business_effect_success",
    "lease_expiry_preserves_durable_receipt_and_is_processed_as_ambiguous_redelivery",
    "lease_expiry_takeover_requires_a_strictly_new_fence_epoch",
    "equivalent_redelivery_after_effect_completion_is_idempotent_and_produces_one_business_effect",
    "offset_rewind_with_missing_equivalence_authority_fails_closed_as_uncertainty",
    "same_scoped_identity_with_changed_immutable_content_is_rejected_as_integrity_failure",
    "stale_claim_owner_is_fenced_after_higher_epoch_takeover",
    "process_restart_reloads_durable_receipt_equivalence_fence_and_effect_state_before_redelivery",
    "crash_after_durable_responsibility_before_effect_or_ack_recovers_under_a_new_fenced_owner",
    "crash_after_effect_completion_before_ack_redelivers_without_repeating_the_business_effect",
    "candidate_source_evidence_does_not_select_a_candidate_or_broker_specific_business_truth",
]

EXPECTED_NON_AUTHORITY = {
    "d4c_mechanism_selection": "not_selected",
    "d4c_ledger_credit": "0_of_9",
    "d4d_ledger_credit": "0_of_5",
    "d4_gate": "scoped",
    "d4_transport_authority": "selected_not_granted",
    "canonical_product_implementation_authority": "not_granted",
    "wave4_implementation_authority": "not_granted",
    "production_authority": "none",
    "c3_numeric_topology_authority": "not_selected",
}


class DuplicateKeyError(ValueError):
    pass


def _no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise DuplicateKeyError(f"duplicate JSON member: {key}")
        out[key] = value
    return out


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicates)


def _tracks(state):
    return {track["track_id"]: track for track in state["tracks"]}


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        source = load_json(root / SOURCE_PATH)
        plan = load_json(root / PLAN_PATH)
        state = load_json(root / STATE_PATH)
    except Exception as exc:
        return [str(exc)]

    expected_scalars = {
        "schema_version": 1,
        "gate_id": "D4",
        "track_id": "D4-C",
        "axis": "ack_visibility_lease_and_checkpoint",
        "source_decision": "OPEN-EVT-008",
        "evidence_id": "ack_after_durable_responsibility_and_lease_ambiguity",
        "canonical_base": "c0b061eb3f9e42f63b9f4c05e7b8b2d2de75a987",
        "mode": "candidate_source_evidence_only",
        "selection_state": "not_selected",
        "selection_authority": "not_granted",
        "current_run_auto_credit": False,
    }
    for key, expected in expected_scalars.items():
        if source.get(key) != expected or type(source.get(key)) is not type(expected):
            errors.append(f"source scalar drift: {key}")

    if source.get("ledger_credit") != []:
        errors.append("source ledger credit must remain empty")

    candidate_results = source.get("candidate_results")
    expected_runtime = evaluate_all()
    if candidate_results != expected_runtime:
        errors.append("candidate results drift from executable source harness")
    if set(candidate_results or {}) != set(CANDIDATES):
        errors.append("candidate result inventory drift")
    if source.get("equivalent_reviewed_profile") != "insufficient_evidence":
        errors.append("reviewed equivalent must remain insufficient_evidence")

    proofs = source.get("required_proofs")
    if proofs != EXPECTED_PROOFS:
        errors.append("exact required proof inventory drift")
    if not isinstance(proofs, list) or any(type(item) is not str for item in proofs):
        errors.append("required proof runtime type drift")

    assertions = source.get("source_assertions")
    if assertions != EXPECTED_ASSERTIONS:
        errors.append("exact source assertion inventory drift")
    if not isinstance(assertions, list) or any(type(item) is not str for item in assertions):
        errors.append("source assertion runtime type drift")

    if source.get("non_authority") != EXPECTED_NON_AUTHORITY:
        errors.append("non-authority boundary drift")

    try:
        axis = plan["axes"]["ack_visibility_lease_and_checkpoint"]
    except Exception:
        errors.append("candidate plan axis missing")
        axis = {}
    if axis.get("decision") != "OPEN-EVT-008":
        errors.append("candidate plan source decision drift")
    if axis.get("evidence_id") != "ack_after_durable_responsibility_and_lease_ambiguity":
        errors.append("candidate plan evidence binding drift")
    if axis.get("must_prove") != EXPECTED_PROOFS:
        errors.append("source proof inventory no longer matches accepted candidate plan")
    concrete = [c for c in axis.get("candidate_classes", []) if c != "equivalent_reviewed_profile"]
    if concrete != list(CANDIDATES):
        errors.append("candidate class inventory no longer matches accepted candidate plan")

    try:
        tracks = _tracks(state)
        d4a, d4b, d4c, d4d = tracks["D4-A"], tracks["D4-B"], tracks["D4-C"], tracks["D4-D"]
        if d4a.get("candidate") != "kafka" or len(d4a.get("evidence_completed", [])) != 7:
            errors.append("D4-A accepted state drift")
        if d4b.get("candidate_status") != "selected_c2_profile" or len(d4b.get("evidence_completed", [])) != 5:
            errors.append("D4-B accepted state drift")
        if d4c.get("candidate") is not None or d4c.get("candidate_status") != "not_selected":
            errors.append("D4-C selection leakage")
        if d4c.get("evidence_completed") != [] or len(d4c.get("evidence_remaining", [])) != 9:
            errors.append("D4-C ledger credit leakage")
        if d4d.get("candidate") is not None or d4d.get("evidence_completed") != []:
            errors.append("D4-D state leakage")
        if sum(len(t.get("evidence_completed", [])) for t in state["tracks"]) != 12:
            errors.append("D4-wide evidence count drift")
        expected_state = {
            "gate_state": "scoped",
            "d4_transport_authority": "selected_not_granted",
            "canonical_product_implementation_authority": "not_granted",
            "wave4_implementation_authority": "not_granted",
            "production_authority": "none",
            "c3_numeric_topology_authority": "not_selected",
        }
        for key, expected in expected_state.items():
            if state.get(key) != expected:
                errors.append(f"global authority drift: {key}")
    except Exception as exc:
        errors.append(f"invalid global D4 state: {exc}")

    return errors


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("d4c_ack_lease_checkpoint_source=PASS candidates=3 durable_restart=true strict_epoch_fence=true d4c=0_of_9 d4wide=12_of_26 selection=not_selected auto_credit=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
