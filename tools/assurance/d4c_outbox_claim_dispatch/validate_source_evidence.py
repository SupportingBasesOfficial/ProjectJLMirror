#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
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
        return ["global D4 track identity drift"]
    d4c = tracks["D4-C"]
    d4d = tracks["D4-D"]
    if d4c.get("evidence_completed") != historical.CURRENT_CREDITS or d4c.get("evidence_remaining") != []:
        errors.append("D4-C current state drift")
    if d4c.get("candidate") is not None or d4c.get("candidate_status") != "not_selected" or d4c.get("state") != "candidate_selection_open":
        errors.append("D4-C candidate leakage")
    expected_remaining = [x for x in d4d.get("required_evidence", []) if x != D4D_CREDIT]
    if d4d.get("evidence_completed") != [D4D_CREDIT] or d4d.get("evidence_remaining") != expected_remaining:
        errors.append("D4-D current state must remain exactly 1/5")
    if d4d.get("candidate") is not None or d4d.get("candidate_status") != "not_selected" or d4d.get("state") != "candidate_selection_open":
        errors.append("D4-D candidate leakage")
    if sum(len(t.get("evidence_completed", [])) for t in tracks.values()) != 22:
        errors.append("D4-wide evidence count drift")
    expected_authority = {
        "gate_state": "scoped",
        "d4_transport_authority": "selected_not_granted",
        "canonical_product_implementation_authority": "not_granted",
        "wave4_implementation_authority": "not_granted",
        "production_authority": "none",
        "c3_numeric_topology_authority": "not_selected",
    }
    for key, expected in expected_authority.items():
        if state.get(key) != expected:
            errors.append(f"global authority drift: {key}")
    return errors


def _historical_projection(state: dict) -> dict:
    projected = copy.deepcopy(state)
    d4d = next(t for t in projected["tracks"] if t.get("track_id") == "D4-D")
    d4d["evidence_completed"] = []
    d4d["evidence_remaining"] = list(d4d["required_evidence"])
    return projected


def validate(root: Path) -> list[str]:
    state = json.loads((root / historical.STATE).read_text(encoding="utf-8"))
    current = _current_errors(state)
    if current:
        return current
    original = historical.load
    try:
        def projected_load(path: Path):
            value = _legacy_load(path)
            try:
                if path.resolve() == (root / historical.STATE).resolve():
                    return _historical_projection(value)
            except Exception:
                pass
            return value
        historical.load = projected_load
        return historical.validate(root)
    finally:
        historical.load = original


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else historical.ROOT
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"D4C_OPEN_EVT_012_SOURCE_ERROR: {error}", file=sys.stderr)
        return 1
    print("d4c_open_evt_012_source=PASS historical_oracle=byte_preserved source_snapshot=4_of_9 current_d4c=9_of_9 current_d4d=1_of_5 current_d4wide=22_of_26 selection=not_selected authorities=unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
