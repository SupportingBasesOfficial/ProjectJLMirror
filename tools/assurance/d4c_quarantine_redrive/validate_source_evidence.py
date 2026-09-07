#!/usr/bin/env python3
from __future__ import annotations

import copy
import sys
from pathlib import Path

import validate_source_evidence_historical_current as historical
from validate_source_evidence_historical_current import *  # noqa: F401,F403

D4D_CREDIT = "workload_identity_to_broker_credential_adapter_least_privilege"
_legacy_load = historical.load


def _current_errors(state: dict) -> list[str]:
    errors: list[str] = []
    tracks = {t.get("track_id"): t for t in state.get("tracks", []) if isinstance(t, dict)}
    if set(tracks) != {"D4-A", "D4-B", "D4-C", "D4-D"}:
        return ["D4 track identity drift"]
    d4c, d4d = tracks["D4-C"], tracks["D4-D"]
    if d4c.get("evidence_completed") != historical.CURRENT_CREDITS or d4c.get("evidence_remaining") != []:
        errors.append("D4-C current 9/9 ledger drift")
    required = d4d.get("required_evidence", [])
    if d4d.get("candidate") is not None or d4d.get("candidate_status") != "not_selected" or d4d.get("state") != "candidate_selection_open":
        errors.append("D4-D selection leakage")
    if d4d.get("evidence_completed") != [D4D_CREDIT] or d4d.get("evidence_remaining") != [x for x in required if x != D4D_CREDIT]:
        errors.append("D4-D current state must be exactly 1/5")
    if sum(len(t.get("evidence_completed", [])) for t in tracks.values()) != 22:
        errors.append("D4-wide evidence count must be 22/26")
    return errors


def _project(state: dict) -> dict:
    projected = copy.deepcopy(state)
    d4d = next(t for t in projected["tracks"] if t.get("track_id") == "D4-D")
    d4d["evidence_completed"] = []
    d4d["evidence_remaining"] = list(d4d["required_evidence"])
    return projected


def validate(root: Path) -> list[str]:
    state = _legacy_load(root, historical.STATE)
    current = _current_errors(state)
    if current:
        return current
    original = historical.load
    try:
        def projected_load(inner_root: Path, path: Path):
            value = _legacy_load(inner_root, path)
            return _project(value) if path == historical.STATE else value
        historical.load = projected_load
        return historical.validate(root)
    finally:
        historical.load = original


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"D4C_OPEN_EVT_009_SOURCE_ERROR: {error}")
        return 1
    print("d4c_quarantine_redrive_source=PASS historical_oracle=preserved current_d4c=9_of_9 current_d4d=1_of_5 current_d4wide=22_of_26 selection=not_selected")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
