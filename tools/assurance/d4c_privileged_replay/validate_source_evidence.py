#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import validate_source_evidence_historical_current as historical
from validate_source_evidence_historical_current import *  # noqa: F401,F403

D4D_CURRENT=[
    "workload_identity_to_broker_credential_adapter_least_privilege",
    "tenant_and_contract_scoped_producer_consumer_authorization",
    "message_protection_key_authority_and_historical_verifier_continuity",
    "secret_credential_payload_exclusion_and_erasure_boundary",
    "trace_context_observability_only_validation_and_redaction",
]
D4D_HISTORICAL_CURRENT=["workload_identity_to_broker_credential_adapter_least_privilege"]
_original_load=historical.load


def _current_errors(state:dict)->list[str]:
    tracks={t.get("track_id"):t for t in state.get("tracks",[]) if isinstance(t,dict)}
    if set(tracks)!={"D4-A","D4-B","D4-C","D4-D"}: return ["D4 track inventory drift"]
    d=tracks["D4-D"]; required=d.get("required_evidence",[]); errors=[]
    if d.get("candidate") is not None or d.get("candidate_status")!="not_selected" or d.get("state")!="candidate_selection_open": errors.append("D4-D selection leakage")
    if d.get("evidence_completed")!=D4D_CURRENT or d.get("evidence_remaining")!=[x for x in required if x not in D4D_CURRENT]: errors.append("D4-D current state must be exactly 5/5")
    if sum(len(t.get("evidence_completed",[])) for t in tracks.values())!=26: errors.append("D4-wide current credit count must be 26/26")
    return errors


def _project(state:dict)->dict:
    out=copy.deepcopy(state); d=next(t for t in out["tracks"] if t.get("track_id")=="D4-D")
    d["evidence_completed"]=list(D4D_HISTORICAL_CURRENT); d["evidence_remaining"]=[x for x in d["required_evidence"] if x not in D4D_HISTORICAL_CURRENT]
    return out


def main()->int:
    try: state=_original_load(STATE)
    except Exception as exc:
        print(f"d4c_open_evt_014_source_validation=FAIL reason={exc}",file=sys.stderr); return 1
    current=_current_errors(state)
    if current:
        for error in current: print(f"d4c_open_evt_014_source_validation=FAIL reason={error}",file=sys.stderr)
        return 1
    original=historical.load
    try:
        def projected_load(path:Path):
            value=_original_load(path)
            try:
                if path.resolve()==STATE.resolve(): return _project(value)
            except Exception: pass
            return value
        historical.load=projected_load
        result=historical.main()
    finally: historical.load=original
    if result==0: print("d4c_open_evt_014_current_projection=PASS current_d4d=5/5 current_d4wide=26/26 historical_current_oracle=byte_preserved")
    return result

if __name__=="__main__": raise SystemExit(main())
