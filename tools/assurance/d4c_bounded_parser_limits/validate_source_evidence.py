#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import validate_source_evidence_historical_current as historical
from validate_source_evidence_historical_current import *  # noqa: F401,F403

D4D_CURRENT = [
    "workload_identity_to_broker_credential_adapter_least_privilege",
    "tenant_and_contract_scoped_producer_consumer_authorization",
    "message_protection_key_authority_and_historical_verifier_continuity",
    "secret_credential_payload_exclusion_and_erasure_boundary",
]
D4D_HISTORICAL_CURRENT = ["workload_identity_to_broker_credential_adapter_least_privilege"]
_original_load = historical.load


def _current_errors(state: dict) -> list[str]:
    tracks={t.get("track_id"):t for t in state.get("tracks",[]) if isinstance(t,dict)}
    if set(tracks)!={"D4-A","D4-B","D4-C","D4-D"}: return ["global D4 track identity drift"]
    d4d=tracks["D4-D"]; required=d4d.get("required_evidence",[]); errors=[]
    if d4d.get("candidate") is not None or d4d.get("candidate_status")!="not_selected" or d4d.get("state")!="candidate_selection_open": errors.append("D4-D current state/selection drift")
    if d4d.get("evidence_completed")!=D4D_CURRENT or d4d.get("evidence_remaining")!=[x for x in required if x not in D4D_CURRENT]: errors.append("D4-D current state must be exactly 4/5")
    if sum(len(t.get("evidence_completed",[])) for t in tracks.values())!=25: errors.append("D4-wide evidence count must be exactly 25/26")
    return errors


def _project(state: dict) -> dict:
    out=copy.deepcopy(state); d=next(t for t in out["tracks"] if t.get("track_id")=="D4-D")
    d["evidence_completed"]=list(D4D_HISTORICAL_CURRENT); d["evidence_remaining"]=[x for x in d["required_evidence"] if x not in D4D_HISTORICAL_CURRENT]
    return out


def validate(root: Path) -> list[str]:
    state=json.loads((root/STATE).read_text(encoding="utf-8")); current=_current_errors(state)
    if current: return current
    original=historical.load
    try:
        def projected_load(path: Path):
            value=_original_load(path)
            try:
                if path.resolve()==(root/STATE).resolve(): return _project(value)
            except Exception: pass
            return value
        historical.load=projected_load
        return historical.validate(root)
    finally: historical.load=original


def main(argv: list[str]) -> int:
    root=Path(argv[1]).resolve() if len(argv)>1 else ROOT; errors=validate(root)
    if errors:
        for error in errors: print(f"D4C_OPEN_EVT_010_SOURCE_ERROR: {error}",file=sys.stderr)
        return 1
    print("d4c_open_evt_010_source=PASS historical_current_oracle=byte_preserved current_d4d=4_of_5 current_d4wide=25_of_26")
    return 0

if __name__=="__main__": raise SystemExit(main(sys.argv))
