#!/usr/bin/env python3
from __future__ import annotations

import copy
import sys
from pathlib import Path

import validate_source_evidence_historical_current as historical
from validate_source_evidence_historical_current import *  # noqa: F401,F403

D4C_SELECTED_PROFILE = {
    "ack_visibility_lease_and_checkpoint": "durable_inbox_claim_then_broker_ack_profile",
    "quarantine_and_redrive": "hybrid_platform_quarantine_store_plus_broker_dlq",
    "bounded_message_payload_batch_and_compression": "layered_transport_and_application_bounds_profile",
    "scoped_content_equivalence_authority": "hybrid_equivalence_authority_profile",
    "outbox_claim_dispatch_and_ack_ambiguity": "compare_and_swap_lease_claim_profile",
    "producer_source_generation": "authority_issued_epoch_generation",
    "privileged_replay_and_event_history": "hybrid_history_archive_plus_replay_controller_profile",
    "historical_reader_and_upcaster": "in_process_versioned_reader_upcaster_registry",
    "recovery_generation_reconciliation_and_activation": "hybrid_generation_manifest_plus_multi_store_reconciler_profile",
}
D4D_SELECTED_PROFILE = {
    "workload_identity_to_broker_credential_adapter": "derived_short_lived_broker_native_credential_adapter",
    "tenant_and_contract_scoped_producer_consumer_authorization": "broker_acl_projection_adapter",
    "message_protection_key_authority_and_historical_verifier_continuity": "kms_backed_envelope_or_transport_protection_profile",
    "secret_credential_payload_exclusion_and_erasure_boundary": "reference_only_secret_authority_profile",
    "trace_context_observability_only_validation_and_redaction": "w3c_trace_context_bounded_profile",
}
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
    c=tracks["D4-C"]; d=tracks["D4-D"]; required=d.get("required_evidence",[]); errors=[]
    if c.get("candidate")!=D4C_SELECTED_PROFILE or c.get("candidate_status")!="selected_c2_delivery_recovery_profile" or c.get("state")!="selected_candidate": errors.append("D4-C current selected profile drift")
    if len(c.get("evidence_completed",[]))!=9 or c.get("evidence_remaining")!=[]: errors.append("D4-C current state must be exactly 9/9")
    if d.get("candidate")!=D4D_SELECTED_PROFILE or d.get("candidate_status")!="selected_c2_security_profile" or d.get("state")!="selected_candidate": errors.append("D4-D current selected profile drift")
    if d.get("evidence_completed")!=D4D_CURRENT or d.get("evidence_remaining")!=[x for x in required if x not in D4D_CURRENT]: errors.append("D4-D current state must be exactly 5/5")
    if sum(len(t.get("evidence_completed",[])) for t in tracks.values())!=26: errors.append("D4-wide current credit count must be 26/26")
    return errors


def _project_state(state:dict)->dict:
    out=copy.deepcopy(state)
    c=next(t for t in out["tracks"] if t.get("track_id")=="D4-C")
    c.update(candidate=None,candidate_status="not_selected",state="candidate_selection_open")
    d=next(t for t in out["tracks"] if t.get("track_id")=="D4-D")
    d["evidence_completed"]=list(D4D_HISTORICAL_CURRENT)
    d["evidence_remaining"]=[x for x in d["required_evidence"] if x not in D4D_HISTORICAL_CURRENT]
    d.update(candidate=None,candidate_status="not_selected",state="candidate_selection_open")
    return out


def _project_plan(plan:dict)->dict:
    out=copy.deepcopy(plan)
    out["candidate"]=None
    out["candidate_status"]="not_selected"
    out["selection_state"]="not_selected"
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
                resolved=path.resolve()
                if resolved==STATE.resolve(): return _project_state(value)
                if resolved==PLAN.resolve(): return _project_plan(value)
            except Exception: pass
            return value
        historical.load=projected_load
        result=historical.main()
    finally: historical.load=original
    if result==0: print("d4c_open_evt_014_current_projection=PASS current_d4c=9/9_selected current_d4d=5/5_selected current_d4wide=26/26 historical_oracle=state_and_ledger_preserved")
    return result

if __name__=="__main__": raise SystemExit(main())
