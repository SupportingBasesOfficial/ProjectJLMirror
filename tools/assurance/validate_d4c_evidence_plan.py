#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import validate_d4c_evidence_plan_historical_current as historical

PLAN = historical.PLAN
STATE = historical.STATE
PROMOTION_025 = historical.PROMOTION_025
SOURCE_025 = historical.SOURCE_025
CREDIT_025 = historical.CREDIT_025
CREDITS = historical.CREDITS
HISTORICAL_PROMOTIONS = historical.HISTORICAL_PROMOTIONS
D4D_CREDITS = [
    "workload_identity_to_broker_credential_adapter_least_privilege",
    "tenant_and_contract_scoped_producer_consumer_authorization",
    "message_protection_key_authority_and_historical_verifier_continuity",
]


def _current_errors(state: dict) -> list[str]:
    errors: list[str] = []
    tracks = {t.get("track_id"): t for t in state.get("tracks", []) if isinstance(t, dict)}
    if set(tracks) != {"D4-A", "D4-B", "D4-C", "D4-D"}:
        return ["D4 track inventory drift"]
    d4c = tracks["D4-C"]
    d4d = tracks["D4-D"]
    if d4c.get("candidate") is not None or d4c.get("candidate_status") != "not_selected" or d4c.get("state") != "candidate_selection_open":
        errors.append("D4-C selection/state leakage")
    if d4c.get("evidence_completed") != historical.CREDITS or d4c.get("evidence_remaining") != []:
        errors.append("D4-C state credit drift: must remain exactly 9/9")
    required = d4d.get("required_evidence", [])
    if d4d.get("candidate") is not None or d4d.get("candidate_status") != "not_selected" or d4d.get("state") != "candidate_selection_open":
        errors.append("D4-D selection/state leakage")
    if d4d.get("evidence_completed") != D4D_CREDITS or d4d.get("evidence_remaining") != [x for x in required if x not in D4D_CREDITS]:
        errors.append("D4-D state/credit leakage: current state must be exactly 3/5")
    if sum(len(t.get("evidence_completed", [])) for t in tracks.values()) != 24:
        errors.append("D4-wide credited evidence must be exactly 24/26")
    authority = (
        state.get("gate_state"), state.get("d4_transport_authority"),
        state.get("canonical_product_implementation_authority"), state.get("wave4_implementation_authority"),
        state.get("production_authority"), state.get("c3_numeric_topology_authority"),
    )
    if authority != ("scoped", "selected_not_granted", "not_granted", "not_granted", "none", "not_selected"):
        errors.append("global authority drift")
    return errors


def _historical_projection(state: dict) -> dict:
    projected = copy.deepcopy(state)
    d4d = next(t for t in projected["tracks"] if t.get("track_id") == "D4-D")
    d4d["evidence_completed"] = []
    d4d["evidence_remaining"] = list(d4d["required_evidence"])
    return projected


def validate(root: Path) -> list[str]:
    state = json.loads((root / STATE).read_text(encoding="utf-8"))
    current = _current_errors(state)
    if current:
        return current
    original_load = historical.load
    try:
        def projected_load(path: Path):
            value = original_load(path)
            return _historical_projection(value) if path == root / STATE else value
        historical.load = projected_load
        return historical.validate(root)
    finally:
        historical.load = original_load


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"D4C_PROMOTION_ERROR: {error}")
        return 1
    print("d4c_open_evt_025_promotion=PASS historical_oracle=byte_preserved d4c=9_of_9 d4d=3_of_5 d4wide=24_of_26 selection=not_selected authorities=unchanged")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
