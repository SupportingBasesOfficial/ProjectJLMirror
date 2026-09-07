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
        return ["D4 track inventory drift"]
    d4c = tracks["D4-C"]
    d4d = tracks["D4-D"]
    if d4c.get("evidence_completed") != historical.EXPECTED_CURRENT_CREDITS or d4c.get("evidence_remaining") != historical.EXPECTED_CURRENT_REMAINING:
        errors.append("D4-C current global evidence projection drift")
    if d4c.get("candidate") is not None or d4c.get("candidate_status") != "not_selected" or d4c.get("state") != "candidate_selection_open":
        errors.append("D4-C global selection leakage")
    expected_remaining = [x for x in d4d.get("required_evidence", []) if x != D4D_CREDIT]
    if d4d.get("evidence_completed") != [D4D_CREDIT] or d4d.get("evidence_remaining") != expected_remaining:
        errors.append("D4-D current state must remain exactly 1/5")
    if d4d.get("candidate") is not None or d4d.get("candidate_status") != "not_selected" or d4d.get("state") != "candidate_selection_open":
        errors.append("D4-D selection leakage")
    if sum(len(t.get("evidence_completed", [])) for t in tracks.values()) != 22:
        errors.append("D4-wide current credit count must be 22/26")
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
            errors.append(f"authority drift: {key}")
    return errors


def _historical_projection(state: dict) -> dict:
    projected = copy.deepcopy(state)
    d4d = next(t for t in projected["tracks"] if t.get("track_id") == "D4-D")
    d4d["evidence_completed"] = []
    d4d["evidence_remaining"] = list(d4d["required_evidence"])
    return projected


def main() -> int:
    try:
        state = json.loads(Path(historical.STATE).read_text(encoding="utf-8"))
    except Exception as exc:
        return historical.fail(str(exc))
    current = _current_errors(state)
    if current:
        return historical.fail("; ".join(current))

    original = historical.load
    try:
        def projected_load(path: Path):
            value = _legacy_load(path)
            try:
                if path.resolve() == Path(historical.STATE).resolve():
                    return _historical_projection(value)
            except Exception:
                pass
            return value
        historical.load = projected_load
        result = historical.main()
    finally:
        historical.load = original
    if result == 0:
        print("d4c_open_evt_013_current_projection=PASS current_d4d=1/5 current_d4wide=22/26 historical_oracle=byte_preserved")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
