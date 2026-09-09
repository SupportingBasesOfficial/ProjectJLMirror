#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path

import validate_source_evidence_historical_current as historical
from validate_source_evidence_historical_current import *  # noqa: F401,F403

D4D_CREDITS = [
    "workload_identity_to_broker_credential_adapter_least_privilege",
    "tenant_and_contract_scoped_producer_consumer_authorization",
    "message_protection_key_authority_and_historical_verifier_continuity",
    "secret_credential_payload_exclusion_and_erasure_boundary",
    "trace_context_observability_only_validation_and_redaction",
]
_legacy_load = historical.load


def _current_errors(state: dict) -> list[str]:
    errors: list[str] = []
    tracks = {t.get("track_id"): t for t in state.get("tracks", []) if isinstance(t, dict)}
    if set(tracks) != {"D4-A", "D4-B", "D4-C", "D4-D"}:
        return ["D4 track inventory drift"]
    d4c = tracks["D4-C"]; d4d = tracks["D4-D"]
    if d4c.get("evidence_completed") != historical.EXPECTED_CURRENT_CREDITS or d4c.get("evidence_remaining") != historical.EXPECTED_CURRENT_REMAINING: errors.append("D4-C current global evidence projection drift")
    if d4c.get("candidate") is not None or d4c.get("candidate_status") != "not_selected" or d4c.get("state") != "candidate_selection_open": errors.append("D4-C global selection leakage")
    if d4d.get("evidence_completed") != D4D_CREDITS or d4d.get("evidence_remaining") != []: errors.append("D4-D current state must remain exactly 5/5")
    if d4d.get('candidate') != {'workload_identity_to_broker_credential_adapter': 'derived_short_lived_broker_native_credential_adapter', 'tenant_and_contract_scoped_producer_consumer_authorization': 'broker_acl_projection_adapter', 'message_protection_key_authority_and_historical_verifier_continuity': 'kms_backed_envelope_or_transport_protection_profile', 'secret_credential_payload_exclusion_and_erasure_boundary': 'reference_only_secret_authority_profile', 'trace_context_observability_only_validation_and_redaction': 'w3c_trace_context_bounded_profile'} or d4d.get('candidate_status') != 'selected_c2_security_profile' or d4d.get('state') != 'selected_candidate': errors.append("D4-D selection leakage")
    if sum(len(t.get("evidence_completed", [])) for t in tracks.values()) != 26: errors.append("D4-wide current credit count must be 26/26")
    expected_authority={"gate_state":"scoped","d4_transport_authority":"selected_not_granted","canonical_product_implementation_authority":"not_granted","wave4_implementation_authority":"not_granted","production_authority":"none","c3_numeric_topology_authority":"not_selected"}
    for key,expected in expected_authority.items():
        if state.get(key)!=expected: errors.append(f"authority drift: {key}")
    return errors


def _historical_projection(state: dict) -> dict:
    projected=copy.deepcopy(state); d4d=next(t for t in projected["tracks"] if t.get("track_id")=="D4-D"); d4d["evidence_completed"]=[]; d4d["evidence_remaining"]=list(d4d["required_evidence"]); _d4d = next(t for t in projected['tracks'] if t.get('track_id') == 'D4-D'); _d4d.update(candidate=None, candidate_status='not_selected', state='candidate_selection_open'); return projected


def main() -> int:
    try: state=json.loads(Path(historical.STATE).read_text(encoding="utf-8"))
    except Exception as exc: return historical.fail(str(exc))
    current=_current_errors(state)
    if current: return historical.fail("; ".join(current))
    original=historical.load
    try:
        def projected_load(path:Path):
            value=_legacy_load(path)
            try:
                if path.resolve()==Path(historical.STATE).resolve(): return _historical_projection(value)
            except Exception: pass
            return value
        historical.load=projected_load; result=historical.main()
    finally: historical.load=original
    if result==0: print("d4c_open_evt_013_current_projection=PASS current_d4d=5/5 current_d4wide=26/26 historical_oracle=byte_preserved")
    return result
if __name__=="__main__": raise SystemExit(main())
