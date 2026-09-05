#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

PLAN = Path("implementation/d4-eventing-async/d4-c-evidence-plan.json")
PROMOTION = Path("implementation/d4-eventing-async/ledger-promotions/d4-c-open-evt-008-promotion-v1.json")
SOURCE = Path("implementation/d4-eventing-async/source-evidence/d4-c-ack-lease-checkpoint-source.json")
STATE = Path("implementation/d4-eventing-async/state-manifest.json")
CREDIT = "ack_after_durable_responsibility_and_lease_ambiguity"
SOURCE_HEAD = "02063da13a4a93fe6bc67521e4a7e4e0d4999045"
SOURCE_MERGE = "69ad19e6129898e7fdf7e9d57e40a841cb0d4ef5"
REVIEW_MODE = "independent_exact_head_adversarial_clean_after_exact_head_ci"
EXPECTED_SOURCE_DECISIONS = [
    "OPEN-EVT-008", "OPEN-EVT-009", "OPEN-EVT-010", "OPEN-EVT-011", "OPEN-EVT-012",
    "OPEN-EVT-013", "OPEN-EVT-014", "OPEN-EVT-015", "OPEN-EVT-025",
]
EXPECTED_REMAINING = [
    "quarantine_redrive_current_authority_and_dedup_preservation",
    "bounded_message_batch_compression_and_parser_limits",
    "scoped_content_equivalence_confidentiality_and_conflict_rejection",
    "outbox_claim_dispatch_ack_ambiguity_and_recovery_continuity",
    "producer_generation_nonresurrection_across_failover_restore",
    "privileged_bounded_replay_with_original_identity_and_effect_safety",
    "historical_reader_upcaster_semantic_and_equivalence_continuity",
    "recovery_generation_rf_inventory_reconciliation_and_activation_gates",
]
EXPECTED_PLAN_KEYS = {
    "schema_version", "gate_id", "track_id", "name", "source_decisions", "candidate", "candidate_status",
    "source_evidence_state", "ledger_credit_state", "required_evidence", "credited_evidence", "remaining_evidence",
    "current_run_auto_credit", "selection_state", "selection_authority", "separate_selection_required",
    "separate_d4_acceptance_required", "d4_transport_authority", "canonical_product_implementation_authority",
    "wave4_implementation_authority", "production_authority", "c3_numeric_topology_authority",
}
EXPECTED_PROMOTION_KEYS = {
    "schema_version", "promotion_id", "gate_id", "track_id", "promotion_base", "source_pr",
    "source_reviewed_head", "source_merge_commit", "source_review", "source_workflow", "source_manifest",
    "credited_evidence", "credit_count", "selection_state", "selection_authority", "d4_gate_state",
    "d4_transport_authority", "canonical_product_implementation_authority", "wave4_implementation_authority",
    "production_authority", "c3_numeric_topology_authority", "separate_selection_required",
    "separate_d4_acceptance_required",
}
EXPECTED_REVIEW_KEYS = {"review_id", "review_mode", "material_threads_unresolved"}
EXPECTED_WORKFLOW_KEYS = {
    "workflow_id", "workflow_path", "workflow_event", "source_head_branch", "run_id", "run_attempt",
    "job_id", "job_name", "artifact_id", "artifact_name", "artifact_digest",
}
EXPECTED_MANIFEST_KEYS = {"path", "sha256"}
EXPECTED_WORKFLOW = {
    "workflow_id": 350722209,
    "workflow_path": ".github/workflows/d4-c-ack-lease-checkpoint-source-evidence.yml",
    "workflow_event": "pull_request",
    "source_head_branch": "evidence/d4-c-ack-lease-checkpoint-source",
    "run_id": 33948472401,
    "run_attempt": 1,
    "job_id": 101258703919,
    "job_name": "D4-C OPEN-EVT-008 source evidence",
    "artifact_id": 9964116208,
    "artifact_name": "d4-c-ack-lease-checkpoint-source-02063da13a4a93fe6bc67521e4a7e4e0d4999045-33948472401-1",
    "artifact_digest": "sha256:2a7a38caff4ddb6e7740ee079bb0c3cffb2f3e29acacb842ce84c0ab987786d6",
}
EXPECTED_SOURCE_MANIFEST = {
    "path": str(SOURCE),
    "sha256": "5c085286b9b6cac8df524f87fa4043accc74cc0878939427abd5df7da16a7708",
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


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicates)


def _exact_int(value: object, expected: int) -> bool:
    return type(value) is int and value == expected


def _exact_bool(value: object, expected: bool) -> bool:
    return type(value) is bool and value is expected


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        plan = load(root / PLAN)
        promotion = load(root / PROMOTION)
        source = load(root / SOURCE)
        state = load(root / STATE)
    except Exception as exc:
        return [str(exc)]

    if not isinstance(plan, dict) or set(plan) != EXPECTED_PLAN_KEYS:
        errors.append("D4-C evidence-plan exact key schema drift")
    expected_plan_scalars = {
        "schema_version": 1,
        "gate_id": "D4",
        "track_id": "D4-C",
        "name": "delivery_ack_quarantine_equivalence_outbox_replay_history_recovery",
        "candidate": None,
        "candidate_status": "not_selected",
        "source_evidence_state": "reviewed_source_run_available",
        "ledger_credit_state": "one_of_nine",
        "current_run_auto_credit": False,
        "selection_state": "not_selected",
        "selection_authority": "not_granted",
        "separate_selection_required": True,
        "separate_d4_acceptance_required": True,
        "d4_transport_authority": "selected_not_granted",
        "canonical_product_implementation_authority": "not_granted",
        "wave4_implementation_authority": "not_granted",
        "production_authority": "none",
        "c3_numeric_topology_authority": "not_selected",
    }
    for key, expected in expected_plan_scalars.items():
        if plan.get(key) != expected or type(plan.get(key)) is not type(expected):
            errors.append(f"plan scalar drift: {key}")
    if plan.get("source_decisions") != EXPECTED_SOURCE_DECISIONS:
        errors.append("D4-C source decision inventory drift")
    if plan.get("credited_evidence") != [CREDIT]:
        errors.append("D4-C credited evidence must be exactly OPEN-EVT-008 obligation")
    if plan.get("remaining_evidence") != EXPECTED_REMAINING:
        errors.append("D4-C remaining evidence inventory drift")
    required = plan.get("required_evidence")
    if not isinstance(required, list) or len(required) != 9 or required != [CREDIT, *EXPECTED_REMAINING]:
        errors.append("D4-C required evidence inventory drift")

    if not isinstance(promotion, dict) or set(promotion) != EXPECTED_PROMOTION_KEYS:
        errors.append("promotion exact key schema drift")
    if not _exact_int(promotion.get("schema_version"), 1):
        errors.append("promotion schema_version must be integer 1")
    if promotion.get("promotion_id") != "d4-c-open-evt-008-promotion-v1" or promotion.get("gate_id") != "D4" or promotion.get("track_id") != "D4-C":
        errors.append("promotion identity drift")
    if promotion.get("promotion_base") != SOURCE_MERGE:
        errors.append("promotion base drift")
    if not _exact_int(promotion.get("source_pr"), 72):
        errors.append("source PR drift")
    if promotion.get("source_reviewed_head") != SOURCE_HEAD:
        errors.append("source reviewed HEAD drift")
    if promotion.get("source_merge_commit") != SOURCE_MERGE:
        errors.append("source merge commit drift")

    review = promotion.get("source_review")
    if not isinstance(review, dict) or set(review) != EXPECTED_REVIEW_KEYS:
        errors.append("source review exact key schema drift")
    else:
        if not _exact_int(review.get("review_id"), 5120040394):
            errors.append("source review id drift")
        if review.get("review_mode") != REVIEW_MODE:
            errors.append("source review mode drift")
        if not _exact_int(review.get("material_threads_unresolved"), 0):
            errors.append("source review unresolved-thread drift")

    workflow = promotion.get("source_workflow")
    if not isinstance(workflow, dict) or set(workflow) != EXPECTED_WORKFLOW_KEYS:
        errors.append("source workflow exact key schema drift")
    elif workflow != EXPECTED_WORKFLOW:
        errors.append("source workflow provenance drift")
    else:
        for key in ("workflow_id", "run_id", "run_attempt", "job_id", "artifact_id"):
            if type(workflow.get(key)) is not int:
                errors.append(f"source workflow integer type drift: {key}")

    source_manifest = promotion.get("source_manifest")
    if not isinstance(source_manifest, dict) or set(source_manifest) != EXPECTED_MANIFEST_KEYS:
        errors.append("source manifest exact key schema drift")
    elif source_manifest != EXPECTED_SOURCE_MANIFEST:
        errors.append("source manifest provenance drift")

    if promotion.get("credited_evidence") != [CREDIT] or not _exact_int(promotion.get("credit_count"), 1):
        errors.append("promotion credit drift")
    if not _exact_bool(promotion.get("separate_selection_required"), True):
        errors.append("promotion separate-selection guard drift")
    if not _exact_bool(promotion.get("separate_d4_acceptance_required"), True):
        errors.append("promotion separate-acceptance guard drift")
    expected_authority = {
        "selection_state": "not_selected",
        "selection_authority": "not_granted",
        "d4_gate_state": "scoped",
        "d4_transport_authority": "selected_not_granted",
        "canonical_product_implementation_authority": "not_granted",
        "wave4_implementation_authority": "not_granted",
        "production_authority": "none",
        "c3_numeric_topology_authority": "not_selected",
    }
    for key, expected in expected_authority.items():
        if promotion.get(key) != expected or type(promotion.get(key)) is not str:
            errors.append(f"promotion authority drift: {key}")

    if source.get("source_decision") != "OPEN-EVT-008" or source.get("evidence_id") != CREDIT:
        errors.append("source evidence binding drift")
    if source.get("current_run_auto_credit") is not False or type(source.get("current_run_auto_credit")) is not bool or source.get("ledger_credit") != []:
        errors.append("source package must remain non-promoting")
    if source.get("selection_state") != "not_selected" or source.get("selection_authority") != "not_granted":
        errors.append("source package selection leakage")

    tracks_raw = state.get("tracks", [])
    if not isinstance(tracks_raw, list) or len(tracks_raw) != 4 or not all(isinstance(t, dict) for t in tracks_raw):
        errors.append("D4 track structure drift")
        tracks = {}
    else:
        ids = [t.get("track_id") for t in tracks_raw]
        if len(ids) != len(set(ids)) or set(ids) != {"D4-A", "D4-B", "D4-C", "D4-D"}:
            errors.append("D4 track identity drift")
        tracks = {t["track_id"]: t for t in tracks_raw if t.get("track_id") in {"D4-A", "D4-B", "D4-C", "D4-D"}}
    try:
        d4a, d4b, d4c, d4d = tracks["D4-A"], tracks["D4-B"], tracks["D4-C"], tracks["D4-D"]
        if d4a.get("candidate") != "kafka" or len(d4a.get("evidence_completed", [])) != 7 or d4a.get("evidence_remaining") != []:
            errors.append("D4-A accepted 7/7 state drift")
        if d4b.get("candidate_status") != "selected_c2_profile" or len(d4b.get("evidence_completed", [])) != 5 or d4b.get("evidence_remaining") != []:
            errors.append("D4-B accepted 5/5 state drift")
        if d4c.get("candidate") is not None or d4c.get("candidate_status") != "not_selected" or d4c.get("state") != "candidate_selection_open":
            errors.append("D4-C selection/state leakage")
        if d4c.get("evidence_completed") != [CREDIT]:
            errors.append("D4-C state credit drift")
        if d4c.get("evidence_remaining") != EXPECTED_REMAINING:
            errors.append("D4-C state remaining evidence drift")
        if d4d.get("candidate") is not None or d4d.get("candidate_status") != "not_selected" or d4d.get("evidence_completed") != []:
            errors.append("D4-D state/credit leakage")
        if sum(len(t.get("evidence_completed", [])) for t in tracks_raw) != 13:
            errors.append("D4-wide credited evidence must be exactly 13/26")
    except Exception as exc:
        errors.append(f"invalid D4 state: {exc}")

    return errors


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"D4C_PROMOTION_ERROR: {error}")
        return 1
    print("d4c_open_evt_008_promotion=PASS exact_schemas=true source_merge_bound=true d4c=1_of_9 d4wide=13_of_26 selection=not_selected authorities=unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
