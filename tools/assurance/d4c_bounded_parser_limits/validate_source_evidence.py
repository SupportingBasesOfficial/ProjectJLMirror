#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
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
D4D_CURRENT = [
    "workload_identity_to_broker_credential_adapter_least_privilege",
    "tenant_and_contract_scoped_producer_consumer_authorization",
    "message_protection_key_authority_and_historical_verifier_continuity",
    "secret_credential_payload_exclusion_and_erasure_boundary",
    "trace_context_observability_only_validation_and_redaction",
]
D4D_HISTORICAL_CURRENT = ["workload_identity_to_broker_credential_adapter_least_privilege"]
_original_load = historical.load


def _current_errors(state: dict) -> list[str]:
    tracks={t.get("track_id"):t for t in state.get("tracks",[]) if isinstance(t,dict)}
    if set(tracks)!={"D4-A","D4-B","D4-C","D4-D"}: return ["global D4 track identity drift"]
    d4c=tracks["D4-C"]; d4d=tracks["D4-D"]; errors=[]
    if d4c.get("candidate")!=D4C_SELECTED_PROFILE or d4c.get("candidate_status")!="selected_c2_delivery_recovery_profile" or d4c.get("state")!="selected_candidate": errors.append("D4-C current selected profile drift")
    if len(d4c.get("evidence_completed",[]))!=9 or d4c.get("evidence_remaining")!=[]: errors.append("D4-C current state must be exactly 9/9")
    if d4d.get("candidate")!=D4D_SELECTED_PROFILE or d4d.get("candidate_status")!="selected_c2_security_profile" or d4d.get("state")!="selected_candidate": errors.append("D4-D current state/selection drift")
    if d4d.get("evidence_completed")!=D4D_CURRENT or d4d.get("evidence_remaining")!=[]: errors.append("D4-D current state must be exactly 5/5")
    if sum(len(t.get("evidence_completed",[])) for t in tracks.values())!=26: errors.append("D4-wide evidence count must be exactly 26/26")
    return errors


def _project(state: dict) -> dict:
    out=copy.deepcopy(state)
    d4c=next(t for t in out["tracks"] if t.get("track_id")=="D4-C")
    d4c.update(candidate=None,candidate_status="not_selected",state="candidate_selection_open")
    d4d=next(t for t in out["tracks"] if t.get("track_id")=="D4-D")
    d4d["evidence_completed"]=list(D4D_HISTORICAL_CURRENT); d4d["evidence_remaining"]=[x for x in d4d["required_evidence"] if x not in D4D_HISTORICAL_CURRENT]
    d4d.update(candidate=None,candidate_status="not_selected",state="candidate_selection_open")
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
    print("d4c_open_evt_010_source=PASS historical_current_oracle=byte_preserved current_d4c=9_of_9_selected current_d4d=5_of_5_selected current_d4wide=26_of_26")
    return 0

if __name__=="__main__": raise SystemExit(main(sys.argv))
