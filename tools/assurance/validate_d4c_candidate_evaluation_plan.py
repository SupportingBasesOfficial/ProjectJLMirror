#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import validate_d4c_candidate_evaluation_plan_historical as historical
from validate_d4c_candidate_evaluation_plan_historical import *  # noqa: F401,F403

D4C_CREDITS = [
    "ack_after_durable_responsibility_and_lease_ambiguity",
    "quarantine_redrive_current_authority_and_dedup_preservation",
    "bounded_message_batch_compression_and_parser_limits",
    "scoped_content_equivalence_confidentiality_and_conflict_rejection",
    "outbox_claim_dispatch_ack_ambiguity_and_recovery_continuity",
    "producer_generation_nonresurrection_across_failover_restore",
    "privileged_bounded_replay_with_original_identity_and_effect_safety",
    "historical_reader_upcaster_semantic_and_equivalence_continuity",
    "recovery_generation_rf_inventory_reconciliation_and_activation_gates",
]
D4D_CREDITS = [
    "workload_identity_to_broker_credential_adapter_least_privilege",
    "tenant_and_contract_scoped_producer_consumer_authorization",
    "message_protection_key_authority_and_historical_verifier_continuity",
]
_legacy_load = historical.load


def _current_errors(state: dict) -> list[str]:
    tracks = {t.get("track_id"): t for t in state.get("tracks", []) if isinstance(t, dict)}
    d4c = tracks.get("D4-C", {})
    d4d = tracks.get("D4-D", {})
    errors: list[str] = []
    if d4c.get("candidate") is not None or d4c.get("candidate_status") != "not_selected" or d4c.get("state") != "candidate_selection_open":
        errors.append("D4-C state must remain open/unselected")
    if d4c.get("evidence_completed") != D4C_CREDITS or d4c.get("evidence_remaining") != []:
        errors.append("D4-C current evidence must remain exactly 9/9")
    if d4d.get("candidate") is not None or d4d.get("candidate_status") != "not_selected" or d4d.get("state") != "candidate_selection_open":
        errors.append("D4-D must remain open/unselected")
    if d4d.get("evidence_completed") != D4D_CREDITS or d4d.get("evidence_remaining") != [x for x in d4d.get("required_evidence", []) if x not in D4D_CREDITS]:
        errors.append("D4-D current evidence must be exactly 3/5")
    if sum(len(t.get("evidence_completed", [])) for t in tracks.values()) != 24:
        errors.append("D4-wide evidence must be exactly 24/26 in current promoted state")
    return errors


def _historical_projection(state: dict) -> dict:
    projected = copy.deepcopy(state)
    for track_id in ("D4-C", "D4-D"):
        track = next(t for t in projected["tracks"] if t.get("track_id") == track_id)
        track["evidence_completed"] = []
        track["evidence_remaining"] = list(track["required_evidence"])
    return projected


def validate(root: Path) -> list[str]:
    state = json.loads((root / STATE).read_text(encoding="utf-8"))
    current = _current_errors(state)
    if current:
        return current
    original = historical.load
    try:
        def projected_load(inner_root: Path, path: Path) -> dict:
            value = _legacy_load(inner_root, path)
            return _historical_projection(value) if path == STATE else value
        historical.load = projected_load
        return historical.validate(root)
    finally:
        historical.load = original


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"D4C_EVAL_ERROR: {error}", file=sys.stderr)
        return 1
    print("d4c_candidate_evaluation_plan=PASS historical_baseline_oracle=preserved current_d4c=9_of_9 current_d4d=3_of_5 selection=not_selected d4wide=24/26")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
