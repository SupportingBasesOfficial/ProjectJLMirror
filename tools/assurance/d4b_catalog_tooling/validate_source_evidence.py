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
    d4a, d4b, d4c, d4d = (tracks[x] for x in ("D4-A", "D4-B", "D4-C", "D4-D"))
    if d4a.get("candidate") != "kafka" or len(d4a.get("evidence_completed", [])) != 7 or d4a.get("evidence_remaining") != []:
        errors.append("D4-A current state drift")
    if d4b.get("candidate_status") != "selected_c2_profile" or d4b.get("state") != "selected_candidate" or len(d4b.get("evidence_completed", [])) != 5 or d4b.get("evidence_remaining") != []:
        errors.append("D4-B current selected profile drift")
    if d4c.get("candidate") is not None or d4c.get("candidate_status") != "not_selected" or len(d4c.get("evidence_completed", [])) != 9 or d4c.get("evidence_remaining") != []:
        errors.append("D4-C current 9/9 drift")
    if d4d.get("candidate") is not None or d4d.get("candidate_status") != "not_selected" or d4d.get("state") != "candidate_selection_open":
        errors.append("D4-D current selection drift")
    if d4d.get("evidence_completed") != [D4D_CREDIT] or d4d.get("evidence_remaining") != [x for x in d4d.get("required_evidence", []) if x != D4D_CREDIT]:
        errors.append("D4-D current state must be exactly 1/5")
    if sum(len(t.get("evidence_completed", [])) for t in tracks.values()) != 22:
        errors.append("D4-wide current state must be 22/26")
    if (state.get("gate_state"), state.get("d4_transport_authority"), state.get("canonical_product_implementation_authority"), state.get("wave4_implementation_authority"), state.get("production_authority"), state.get("c3_numeric_topology_authority")) != ("scoped", "selected_not_granted", "not_granted", "not_granted", "none", "not_selected"):
        errors.append("authority boundary drift")
    return errors


def _historical_state(state: dict) -> dict:
    projected = copy.deepcopy(state)
    by = {t["track_id"]: t for t in projected["tracks"]}
    d4b = by["D4-B"]
    d4b["candidate"] = None
    d4b["candidate_status"] = "not_selected"
    d4b["state"] = "evidence_complete_selection_pending"
    for track_id in ("D4-C", "D4-D"):
        track = by[track_id]
        track["evidence_completed"] = []
        track["evidence_remaining"] = list(track["required_evidence"])
    return projected


def _historical_ledger(ledger: dict) -> dict:
    projected = copy.deepcopy(ledger)
    projected["candidate"] = None
    projected["candidate_status"] = "not_selected"
    projected["selection_state"] = "not_selected"
    return projected


def validate(root: Path) -> list[str]:
    state = json.loads((root / historical.STATE).read_text(encoding="utf-8"))
    current = _current_errors(state)
    if current:
        return current
    original = historical.load
    try:
        def projected_load(inner_root: Path, path: Path) -> dict:
            value = _legacy_load(inner_root, path)
            if path == historical.STATE:
                return _historical_state(value)
            if path == historical.LEDGER:
                return _historical_ledger(value)
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
            print(f"D4B_CATALOG_SOURCE_ERROR: {error}", file=sys.stderr)
        return 1
    print("d4b_catalog_tooling_source=PASS historical_oracle=preserved current_d4b=5_of_5_selected current_d4c=9_of_9 current_d4d=1_of_5 d4wide=22_of_26")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
