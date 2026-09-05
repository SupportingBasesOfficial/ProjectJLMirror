#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import validate_d4b_evidence_plan_historical as historical
from validate_d4b_evidence_plan_historical import *  # noqa: F401,F403

D4C_CREDIT = "ack_after_durable_responsibility_and_lease_ambiguity"
_legacy_load = historical.load


def _current_errors(state: dict) -> list[str]:
    tracks = {t.get("track_id"): t for t in state.get("tracks", []) if isinstance(t, dict)}
    d4c = tracks.get("D4-C", {})
    required = d4c.get("required_evidence", [])
    errors: list[str] = []
    if d4c.get("candidate") is not None or d4c.get("candidate_status") != "not_selected" or d4c.get("state") != "candidate_selection_open":
        errors.append("D4-C current sibling state must remain open/unselected")
    if d4c.get("evidence_completed") != [D4C_CREDIT]:
        errors.append("D4-C current sibling credit must be exactly OPEN-EVT-008")
    if d4c.get("evidence_remaining") != [x for x in required if x != D4C_CREDIT]:
        errors.append("D4-C current sibling remaining evidence drift")
    if tracks.get("D4-D", {}).get("evidence_completed") != []:
        errors.append("D4-D must remain uncredited")
    if sum(len(t.get("evidence_completed", [])) for t in tracks.values()) != 13:
        errors.append("D4-wide current evidence must remain 13/26")
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
            print(f"D4B_PLAN_ERROR: {error}", file=sys.stderr)
        return 1
    print("d4b_evidence_plan=PASS historical_oracle=preserved current_sibling_d4c=1_of_9 d4wide=13_of_26")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
