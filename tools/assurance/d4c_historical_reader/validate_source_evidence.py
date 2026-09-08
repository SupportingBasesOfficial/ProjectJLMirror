#!/usr/bin/env python3
from __future__ import annotations

import copy
import sys

import validate_source_evidence_historical_current as historical
from validate_source_evidence_historical_current import *  # noqa: F401,F403

D4D_CREDITS = [
    "workload_identity_to_broker_credential_adapter_least_privilege",
    "tenant_and_contract_scoped_producer_consumer_authorization",
    "message_protection_key_authority_and_historical_verifier_continuity",
    "secret_credential_payload_exclusion_and_erasure_boundary",
]
_original_load = historical.load


def _current_errors(state: dict) -> list[str]:
    errors: list[str] = []
    tracks = {t.get("track_id"): t for t in state.get("tracks", []) if isinstance(t, dict)}
    if set(tracks) != {"D4-A", "D4-B", "D4-C", "D4-D"}:
        return ["D4 track inventory drift"]
    d4c, d4d = tracks["D4-C"], tracks["D4-D"]
    if d4c.get("evidence_completed") != historical.CURRENT_CREDITS or d4c.get("evidence_remaining") != historical.CURRENT_REMAINING:
        errors.append("D4-C global projection drift")
    required = d4d.get("required_evidence", [])
    if d4d.get("candidate") is not None or d4d.get("candidate_status") != "not_selected" or d4d.get("state") != "candidate_selection_open":
        errors.append("D4-D selection leakage")
    if d4d.get("evidence_completed") != D4D_CREDITS or d4d.get("evidence_remaining") != [x for x in required if x not in D4D_CREDITS]:
        errors.append("D4-D current state must be exactly 4/5")
    if sum(len(t.get("evidence_completed", [])) for t in tracks.values()) != 25:
        errors.append("D4-wide credit count must be 25/26")
    return errors


def _project(state: dict) -> dict:
    projected = copy.deepcopy(state)
    d4d = next(t for t in projected["tracks"] if t.get("track_id") == "D4-D")
    d4d["evidence_completed"] = []
    d4d["evidence_remaining"] = list(d4d["required_evidence"])
    return projected


def main() -> int:
    state = _original_load(historical.STATE)
    current = _current_errors(state)
    if current:
        for error in current:
            print(f"d4c_open_evt_015_source_validation=FAIL reason={error}", file=sys.stderr)
        return 1
    original = historical.load
    try:
        def projected_load(path):
            value = _original_load(path)
            return _project(value) if path == historical.STATE else value
        historical.load = projected_load
        result = historical.main()
    finally:
        historical.load = original
    if result == 0:
        print("d4c_open_evt_015_current_projection=PASS d4d=4_of_5 d4wide=25_of_26")
    return result

if __name__ == "__main__":
    raise SystemExit(main())
