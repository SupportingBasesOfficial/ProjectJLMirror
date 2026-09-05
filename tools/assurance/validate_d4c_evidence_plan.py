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


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        plan = load(root / PLAN)
        promotion = load(root / PROMOTION)
        source = load(root / SOURCE)
        state = load(root / STATE)
    except Exception as exc:
        return [str(exc)]

    expected_scalars = {
        "schema_version": 1,
        "gate_id": "D4",
        "track_id": "D4-C",
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
    for key, expected in expected_scalars.items():
        if plan.get(key) != expected or type(plan.get(key)) is not type(expected):
            errors.append(f"plan scalar drift: {key}")

    if plan.get("credited_evidence") != [CREDIT]:
        errors.append("D4-C credited evidence must be exactly OPEN-EVT-008 obligation")
    if plan.get("remaining_evidence") != EXPECTED_REMAINING:
        errors.append("D4-C remaining evidence inventory drift")
    required = plan.get("required_evidence")
    if not isinstance(required, list) or len(required) != 9 or set(required) != {CREDIT, *EXPECTED_REMAINING}:
        errors.append("D4-C required evidence inventory drift")

    if promotion.get("promotion_id") != "d4-c-open-evt-008-promotion-v1":
        errors.append("promotion identity drift")
    if promotion.get("promotion_base") != "69ad19e6129898e7fdf7e9d57e40a841cb0d4ef5":
        errors.append("promotion base drift")
    if promotion.get("source_pr") != 72:
        errors.append("source PR drift")
    if promotion.get("source_reviewed_head") != "02063da13a4a93fe6bc67521e4a7e4e0d4999045":
        errors.append("source reviewed HEAD drift")
    review = promotion.get("source_review", {})
    if review.get("review_id") != 5120040394 or review.get("material_threads_unresolved") != 0:
        errors.append("source review provenance drift")
    workflow = promotion.get("source_workflow", {})
    expected_workflow = {
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
    if workflow != expected_workflow:
        errors.append("source workflow provenance drift")
    if promotion.get("source_manifest") != {
        "path": str(SOURCE),
        "sha256": "5c085286b9b6cac8df524f87fa4043accc74cc0878939427abd5df7da16a7708",
    }:
        errors.append("source manifest provenance drift")
    if promotion.get("credited_evidence") != [CREDIT] or promotion.get("credit_count") != 1:
        errors.append("promotion credit drift")
    for key in ("selection_state", "selection_authority", "d4_gate_state", "d4_transport_authority", "canonical_product_implementation_authority", "wave4_implementation_authority", "production_authority", "c3_numeric_topology_authority"):
        expected = {
            "selection_state": "not_selected",
            "selection_authority": "not_granted",
            "d4_gate_state": "scoped",
            "d4_transport_authority": "selected_not_granted",
            "canonical_product_implementation_authority": "not_granted",
            "wave4_implementation_authority": "not_granted",
            "production_authority": "none",
            "c3_numeric_topology_authority": "not_selected",
        }[key]
        if promotion.get(key) != expected:
            errors.append(f"promotion authority drift: {key}")

    if source.get("source_decision") != "OPEN-EVT-008" or source.get("evidence_id") != CREDIT:
        errors.append("source evidence binding drift")
    if source.get("current_run_auto_credit") is not False or source.get("ledger_credit") != []:
        errors.append("source package must remain non-promoting")
    if source.get("selection_state") != "not_selected" or source.get("selection_authority") != "not_granted":
        errors.append("source package selection leakage")

    tracks = {t["track_id"]: t for t in state.get("tracks", []) if isinstance(t, dict) and "track_id" in t}
    try:
        d4c = tracks["D4-C"]
        if d4c.get("candidate") is not None or d4c.get("candidate_status") != "not_selected" or d4c.get("state") != "candidate_selection_open":
            errors.append("D4-C selection/state leakage")
        if d4c.get("evidence_completed") != [CREDIT]:
            errors.append("D4-C state credit drift")
        if d4c.get("evidence_remaining") != EXPECTED_REMAINING:
            errors.append("D4-C state remaining evidence drift")
        if sum(len(t.get("evidence_completed", [])) for t in tracks.values()) != 13:
            errors.append("D4-wide credited evidence must be exactly 13/26")
        if tracks["D4-D"].get("evidence_completed") != []:
            errors.append("D4-D credit leakage")
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
    print("d4c_open_evt_008_promotion=PASS d4c=1_of_9 d4wide=13_of_26 selection=not_selected authorities=unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
