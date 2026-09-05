#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PLAN = Path("implementation/d4-eventing-async/d4-c-evidence-plan.json")
PROMOTION_008 = Path("implementation/d4-eventing-async/ledger-promotions/d4-c-open-evt-008-promotion-v1.json")
PROMOTION_009 = Path("implementation/d4-eventing-async/ledger-promotions/d4-c-open-evt-009-promotion-v1.json")
SOURCE_008 = Path("implementation/d4-eventing-async/source-evidence/d4-c-ack-lease-checkpoint-source.json")
SOURCE_009 = Path("implementation/d4-eventing-async/source-evidence/d4-c-quarantine-redrive-source.json")
STATE = Path("implementation/d4-eventing-async/state-manifest.json")
CREDIT_008 = "ack_after_durable_responsibility_and_lease_ambiguity"
CREDIT_009 = "quarantine_redrive_current_authority_and_dedup_preservation"
EXPECTED_CREDITS = [CREDIT_008, CREDIT_009]
EXPECTED_REMAINING = [
    "bounded_message_batch_compression_and_parser_limits",
    "scoped_content_equivalence_confidentiality_and_conflict_rejection",
    "outbox_claim_dispatch_ack_ambiguity_and_recovery_continuity",
    "producer_generation_nonresurrection_across_failover_restore",
    "privileged_bounded_replay_with_original_identity_and_effect_safety",
    "historical_reader_upcaster_semantic_and_equivalence_continuity",
    "recovery_generation_rf_inventory_reconciliation_and_activation_gates",
]
EXPECTED_SOURCE_DECISIONS = [
    "OPEN-EVT-008", "OPEN-EVT-009", "OPEN-EVT-010", "OPEN-EVT-011", "OPEN-EVT-012",
    "OPEN-EVT-013", "OPEN-EVT-014", "OPEN-EVT-015", "OPEN-EVT-025",
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
REVIEW_MODE = "independent_exact_head_adversarial_clean_after_exact_head_ci"
PROMOTIONS = (
    {
        "path": PROMOTION_008,
        "source": SOURCE_008,
        "promotion_id": "d4-c-open-evt-008-promotion-v1",
        "promotion_base": "69ad19e6129898e7fdf7e9d57e40a841cb0d4ef5",
        "source_pr": 72,
        "source_head": "02063da13a4a93fe6bc67521e4a7e4e0d4999045",
        "source_merge": "69ad19e6129898e7fdf7e9d57e40a841cb0d4ef5",
        "review_id": 5120040394,
        "decision": "OPEN-EVT-008",
        "evidence": CREDIT_008,
        "workflow": {
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
        },
        "source_sha256": "5c085286b9b6cac8df524f87fa4043accc74cc0878939427abd5df7da16a7708",
    },
    {
        "path": PROMOTION_009,
        "source": SOURCE_009,
        "promotion_id": "d4-c-open-evt-009-promotion-v1",
        "promotion_base": "a238c82b8ddd4084b3ae80786e0e75b39111132e",
        "source_pr": 74,
        "source_head": "f3c5e49828160abde9fd99b25688456fa13408df",
        "source_merge": "a238c82b8ddd4084b3ae80786e0e75b39111132e",
        "review_id": 5123104259,
        "decision": "OPEN-EVT-009",
        "evidence": CREDIT_009,
        "workflow": {
            "workflow_id": 351163085,
            "workflow_path": ".github/workflows/d4-c-quarantine-redrive-source-evidence.yml",
            "workflow_event": "pull_request",
            "source_head_branch": "evidence/d4-c-quarantine-redrive-source",
            "run_id": 33992605858,
            "run_attempt": 1,
            "job_id": 101377381065,
            "job_name": "D4-C OPEN-EVT-009 source evidence",
            "artifact_id": 9977118464,
            "artifact_name": "d4-c-quarantine-redrive-source-f3c5e49828160abde9fd99b25688456fa13408df-33992605858-1",
            "artifact_digest": "sha256:680d0d965b965c7f44b4474a7725b3e6c23e143af8ed34f41aa37a0bbbdabaa1",
        },
        "source_sha256": "2e03e9a7ade9f6c379953b44ce7778846272948c30cd27336cb0c06f18483ddc",
    },
)


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


def _validate_promotion(root: Path, spec: dict, errors: list[str]) -> None:
    label = spec["decision"]
    try:
        promotion = load(root / spec["path"])
        source = load(root / spec["source"])
    except Exception as exc:
        errors.append(f"{label}: {exc}")
        return
    if not isinstance(promotion, dict) or set(promotion) != EXPECTED_PROMOTION_KEYS:
        errors.append(f"{label}: promotion exact key schema drift")
    if not _exact_int(promotion.get("schema_version"), 1):
        errors.append(f"{label}: promotion schema_version must be integer 1")
    for key, expected in {
        "promotion_id": spec["promotion_id"], "gate_id": "D4", "track_id": "D4-C",
        "promotion_base": spec["promotion_base"], "source_reviewed_head": spec["source_head"],
        "source_merge_commit": spec["source_merge"],
    }.items():
        if promotion.get(key) != expected:
            errors.append(f"{label}: promotion scalar drift: {key}")
    if not _exact_int(promotion.get("source_pr"), spec["source_pr"]):
        errors.append(f"{label}: source PR drift")
    review = promotion.get("source_review")
    if not isinstance(review, dict) or set(review) != EXPECTED_REVIEW_KEYS:
        errors.append(f"{label}: source review exact key schema drift")
    else:
        if not _exact_int(review.get("review_id"), spec["review_id"]):
            errors.append(f"{label}: source review id drift")
        if review.get("review_mode") != REVIEW_MODE:
            errors.append(f"{label}: source review mode drift")
        if not _exact_int(review.get("material_threads_unresolved"), 0):
            errors.append(f"{label}: source review unresolved-thread drift")
    workflow = promotion.get("source_workflow")
    if not isinstance(workflow, dict) or set(workflow) != EXPECTED_WORKFLOW_KEYS:
        errors.append(f"{label}: source workflow exact key schema drift")
    elif workflow != spec["workflow"]:
        errors.append(f"{label}: source workflow provenance drift")
    else:
        for key in ("workflow_id", "run_id", "run_attempt", "job_id", "artifact_id"):
            if type(workflow.get(key)) is not int:
                errors.append(f"{label}: source workflow integer type drift: {key}")
    manifest = promotion.get("source_manifest")
    expected_manifest = {"path": str(spec["source"]), "sha256": spec["source_sha256"]}
    if not isinstance(manifest, dict) or set(manifest) != EXPECTED_MANIFEST_KEYS:
        errors.append(f"{label}: source manifest exact key schema drift")
    elif manifest != expected_manifest:
        errors.append(f"{label}: source manifest provenance drift")
    elif hashlib.sha256((root / spec["source"]).read_bytes()).hexdigest() != spec["source_sha256"]:
        errors.append(f"{label}: source manifest bytes drift")
    if promotion.get("credited_evidence") != [spec["evidence"]] or not _exact_int(promotion.get("credit_count"), 1):
        errors.append(f"{label}: promotion credit drift")
    for key, expected in {
        "selection_state": "not_selected", "selection_authority": "not_granted", "d4_gate_state": "scoped",
        "d4_transport_authority": "selected_not_granted", "canonical_product_implementation_authority": "not_granted",
        "wave4_implementation_authority": "not_granted", "production_authority": "none",
        "c3_numeric_topology_authority": "not_selected",
    }.items():
        if promotion.get(key) != expected:
            errors.append(f"{label}: promotion authority drift: {key}")
    if not _exact_bool(promotion.get("separate_selection_required"), True):
        errors.append(f"{label}: separate-selection guard drift")
    if not _exact_bool(promotion.get("separate_d4_acceptance_required"), True):
        errors.append(f"{label}: separate-acceptance guard drift")
    if source.get("source_decision") != spec["decision"] or source.get("evidence_id") != spec["evidence"]:
        errors.append(f"{label}: source evidence binding drift")
    if source.get("current_run_auto_credit") is not False or source.get("ledger_credit") != []:
        errors.append(f"{label}: source package must remain non-promoting")
    if source.get("selection_state") != "not_selected" or source.get("selection_authority") != "not_granted":
        errors.append(f"{label}: source package selection leakage")


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        plan = load(root / PLAN)
        state = load(root / STATE)
    except Exception as exc:
        return [str(exc)]

    if not isinstance(plan, dict) or set(plan) != EXPECTED_PLAN_KEYS:
        errors.append("D4-C evidence-plan exact key schema drift")
    expected_plan_scalars = {
        "schema_version": 1, "gate_id": "D4", "track_id": "D4-C",
        "name": "delivery_ack_quarantine_equivalence_outbox_replay_history_recovery",
        "candidate": None, "candidate_status": "not_selected",
        "source_evidence_state": "reviewed_source_run_available", "ledger_credit_state": "two_of_nine",
        "current_run_auto_credit": False, "selection_state": "not_selected", "selection_authority": "not_granted",
        "separate_selection_required": True, "separate_d4_acceptance_required": True,
        "d4_transport_authority": "selected_not_granted", "canonical_product_implementation_authority": "not_granted",
        "wave4_implementation_authority": "not_granted", "production_authority": "none",
        "c3_numeric_topology_authority": "not_selected",
    }
    for key, expected in expected_plan_scalars.items():
        if plan.get(key) != expected or type(plan.get(key)) is not type(expected):
            errors.append(f"plan scalar drift: {key}")
    if plan.get("source_decisions") != EXPECTED_SOURCE_DECISIONS:
        errors.append("D4-C source decision inventory drift")
    if plan.get("credited_evidence") != EXPECTED_CREDITS:
        errors.append("D4-C credited evidence must be exactly OPEN-EVT-008 plus OPEN-EVT-009 obligations")
    if plan.get("remaining_evidence") != EXPECTED_REMAINING:
        errors.append("D4-C remaining evidence inventory drift")
    if plan.get("required_evidence") != [*EXPECTED_CREDITS, *EXPECTED_REMAINING]:
        errors.append("D4-C required evidence inventory drift")

    for spec in PROMOTIONS:
        _validate_promotion(root, spec, errors)

    tracks_raw = state.get("tracks", [])
    if not isinstance(tracks_raw, list) or len(tracks_raw) != 4 or not all(isinstance(t, dict) for t in tracks_raw):
        errors.append("D4 track structure drift")
        return errors
    ids = [t.get("track_id") for t in tracks_raw]
    if len(ids) != len(set(ids)) or set(ids) != {"D4-A", "D4-B", "D4-C", "D4-D"}:
        errors.append("D4 track identity drift")
        return errors
    tracks = {t["track_id"]: t for t in tracks_raw}
    d4a, d4b, d4c, d4d = tracks["D4-A"], tracks["D4-B"], tracks["D4-C"], tracks["D4-D"]
    if d4a.get("candidate") != "kafka" or len(d4a.get("evidence_completed", [])) != 7 or d4a.get("evidence_remaining") != []:
        errors.append("D4-A accepted 7/7 state drift")
    if d4b.get("candidate_status") != "selected_c2_profile" or len(d4b.get("evidence_completed", [])) != 5 or d4b.get("evidence_remaining") != []:
        errors.append("D4-B accepted 5/5 state drift")
    if d4c.get("candidate") is not None or d4c.get("candidate_status") != "not_selected" or d4c.get("state") != "candidate_selection_open":
        errors.append("D4-C selection/state leakage")
    if d4c.get("evidence_completed") != EXPECTED_CREDITS:
        errors.append("D4-C state credit drift")
    if d4c.get("evidence_remaining") != EXPECTED_REMAINING:
        errors.append("D4-C state remaining evidence drift")
    if d4d.get("candidate") is not None or d4d.get("candidate_status") != "not_selected" or d4d.get("evidence_completed") != []:
        errors.append("D4-D state/credit leakage")
    if sum(len(t.get("evidence_completed", [])) for t in tracks_raw) != 14:
        errors.append("D4-wide credited evidence must be exactly 14/26")
    for key, expected in {
        "gate_state": "scoped", "d4_transport_authority": "selected_not_granted",
        "canonical_product_implementation_authority": "not_granted", "wave4_implementation_authority": "not_granted",
        "production_authority": "none", "c3_numeric_topology_authority": "not_selected",
    }.items():
        if state.get(key) != expected:
            errors.append(f"global authority drift: {key}")
    return errors


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"D4C_PROMOTION_ERROR: {error}")
        return 1
    print("d4c_open_evt_009_promotion=PASS promotion_records=2 immutable_history=true d4c=2_of_9 d4wide=14_of_26 selection=not_selected authorities=unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
