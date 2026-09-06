#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import validate_d4b_candidate_evaluation_plan_historical as historical
from validate_d4b_candidate_evaluation_plan_historical import *  # noqa: F401,F403

D4C_CREDITS = [
    "ack_after_durable_responsibility_and_lease_ambiguity",
    "quarantine_redrive_current_authority_and_dedup_preservation",
    "bounded_message_batch_compression_and_parser_limits",
    "scoped_content_equivalence_confidentiality_and_conflict_rejection",
    "outbox_claim_dispatch_ack_ambiguity_and_recovery_continuity",
    "producer_generation_nonresurrection_across_failover_restore",
    "privileged_bounded_replay_with_original_identity_and_effect_safety",
]
_legacy_load = historical.load


def _current_errors(state: dict) -> list[str]:
    tracks = {t.get("track_id"): t for t in state.get("tracks", []) if isinstance(t, dict)}
    d4c = tracks.get("D4-C", {})
    required = d4c.get("required_evidence", [])
    errors: list[str] = []
    if d4c.get("candidate") is not None or d4c.get("candidate_status") != "not_selected" or d4c.get("state") != "candidate_selection_open":
        errors.append("D4-C/D must remain open; current D4-C selection/state drift")
    if d4c.get("evidence_completed") != D4C_CREDITS:
        errors.append("D4-C/D must remain open; historical D4-C credit is zero while current promoted credits must be exactly OPEN-EVT-008 through OPEN-EVT-014")
    if d4c.get("evidence_remaining") != [x for x in required if x not in D4C_CREDITS]:
        errors.append("D4-C/D must remain open; current D4-C remaining evidence drift")
    d4d = tracks.get("D4-D", {})
    if d4d.get("candidate") is not None or d4d.get("candidate_status") != "not_selected" or d4d.get("evidence_completed") != []:
        errors.append("D4-C/D must remain open and D4-D uncredited")
    if sum(len(t.get("evidence_completed", [])) for t in tracks.values()) != 19:
        errors.append("D4-wide evidence must remain 12/26 in historical projection and exactly 19/26 in current promoted state")
    return errors


def _project(state: dict) -> dict:
    result = copy.deepcopy(state)
    d4c = next(t for t in result["tracks"] if t.get("track_id") == "D4-C")
    d4c["evidence_completed"] = []
    d4c["evidence_remaining"] = list(d4c["required_evidence"])
    return result


def validate(root: Path) -> list[str]:
    state = json.loads((root / STATE).read_text(encoding="utf-8"))
    current = _current_errors(state)
    if current:
        return current
    original = historical.load
    try:
        def projected_load(inner_root: Path, path: Path) -> dict:
            value = _legacy_load(inner_root, path)
            return _project(value) if path == STATE else value
        historical.load = projected_load
        return historical.validate(root)
    finally:
        historical.load = original


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"D4B_EVAL_ERROR: {error}", file=sys.stderr)
        return 1
    print("d4b_candidate_evaluation=PASS historical_oracle=preserved current_sibling_d4c=7_of_9 d4wide=19_of_26")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
