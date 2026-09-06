#!/usr/bin/env python3
from __future__ import annotations

import copy
import sys
from pathlib import Path

import validate_d4a_evidence_plan_historical as historical
from validate_d4a_evidence_plan_historical import *  # noqa: F401,F403

D4C_CREDITS = [
    "ack_after_durable_responsibility_and_lease_ambiguity",
    "quarantine_redrive_current_authority_and_dedup_preservation",
    "bounded_message_batch_compression_and_parser_limits",
    "scoped_content_equivalence_confidentiality_and_conflict_rejection",
]
_legacy_validate_objects = historical.validate_objects


def _current_sibling_errors(entry: dict) -> list[str]:
    errors: list[str] = []
    tracks = {t.get("track_id"): t for t in entry.get("tracks", []) if isinstance(t, dict)}
    d4c = tracks.get("D4-C", {})
    required = d4c.get("required_evidence", [])
    expected_remaining = [item for item in required if item not in D4C_CREDITS]
    if d4c.get("candidate") is not None or d4c.get("candidate_status") != "not_selected" or d4c.get("state") != "candidate_selection_open":
        errors.append("D4-C current sibling state must remain open/unselected")
    if d4c.get("evidence_completed") != D4C_CREDITS:
        errors.append("D4-C current sibling credit must be exactly OPEN-EVT-008 through OPEN-EVT-011")
    if d4c.get("evidence_remaining") != expected_remaining:
        errors.append("D4-C current sibling remaining evidence drift")
    if tracks.get("D4-D", {}).get("evidence_completed") != []:
        errors.append("D4-D must remain uncredited")
    if sum(len(t.get("evidence_completed", [])) for t in tracks.values()) != 16:
        errors.append("D4-wide current evidence must remain 16/26")
    return errors


def _historical_projection(entry: dict) -> dict:
    projected = copy.deepcopy(entry)
    d4c = next(t for t in projected["tracks"] if t.get("track_id") == "D4-C")
    d4c["evidence_completed"] = []
    d4c["evidence_remaining"] = list(d4c["required_evidence"])
    return projected


def validate_objects(plan: dict, entry: dict, promotion: dict, selection: dict) -> list[str]:
    current = _current_sibling_errors(entry)
    if current:
        return current
    return _legacy_validate_objects(plan, _historical_projection(entry), promotion, selection)


def validate(root: Path) -> list[str]:
    plan, entry, promotion, selection = historical.load(root)
    current = _current_sibling_errors(entry)
    if current:
        return current
    original = historical.validate_objects
    try:
        historical.validate_objects = lambda p, e, r, s: _legacy_validate_objects(p, _historical_projection(e), r, s)
        return historical.validate(root)
    finally:
        historical.validate_objects = original


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"D4A_PLAN_ERROR: {error}", file=sys.stderr)
        return 1
    print("d4a_evidence_plan=PASS historical_oracle=preserved current_sibling_d4c=4_of_9 d4wide=16_of_26")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
