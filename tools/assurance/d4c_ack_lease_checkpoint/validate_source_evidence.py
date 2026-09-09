#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import validate_source_evidence_historical as historical
from validate_source_evidence_historical import *  # noqa: F401,F403

D4C_CREDIT_008 = "ack_after_durable_responsibility_and_lease_ambiguity"
D4C_CREDIT_009 = "quarantine_redrive_current_authority_and_dedup_preservation"
D4C_CREDIT_010 = "bounded_message_batch_compression_and_parser_limits"
D4C_CREDIT_011 = "scoped_content_equivalence_confidentiality_and_conflict_rejection"
D4C_CREDIT_012 = "outbox_claim_dispatch_ack_ambiguity_and_recovery_continuity"
D4C_CREDIT_013 = "producer_generation_nonresurrection_across_failover_restore"
D4C_CREDIT_014 = "privileged_bounded_replay_with_original_identity_and_effect_safety"
D4C_CREDIT_015 = "historical_reader_upcaster_semantic_and_equivalence_continuity"
D4C_CREDIT_025 = "recovery_generation_rf_inventory_reconciliation_and_activation_gates"
D4D_CREDITS = [
    "workload_identity_to_broker_credential_adapter_least_privilege",
    "tenant_and_contract_scoped_producer_consumer_authorization",
    "message_protection_key_authority_and_historical_verifier_continuity",
    "secret_credential_payload_exclusion_and_erasure_boundary",
    "trace_context_observability_only_validation_and_redaction",
]
CURRENT_CREDITS = [D4C_CREDIT_008,D4C_CREDIT_009,D4C_CREDIT_010,D4C_CREDIT_011,D4C_CREDIT_012,D4C_CREDIT_013,D4C_CREDIT_014,D4C_CREDIT_015,D4C_CREDIT_025]
_legacy_load_json = historical.load_json

def _current_errors(state: dict) -> list[str]:
    tracks={t.get("track_id"):t for t in state.get("tracks",[]) if isinstance(t,dict)}; d4c=tracks.get("D4-C",{}); d4d=tracks.get("D4-D",{}); required=d4c.get("required_evidence",[]); errors=[]
    if d4c.get("candidate") is not None or d4c.get("candidate_status")!="not_selected" or d4c.get("state")!="candidate_selection_open": errors.append("D4-C selection leakage")
    if d4c.get("evidence_completed")!=CURRENT_CREDITS or d4c.get("evidence_remaining")!=[x for x in required if x not in CURRENT_CREDITS]: errors.append("D4-C current ledger drift beyond separately promoted nine reviewed obligations")
    if d4d.get('candidate') != {'workload_identity_to_broker_credential_adapter': 'derived_short_lived_broker_native_credential_adapter', 'tenant_and_contract_scoped_producer_consumer_authorization': 'broker_acl_projection_adapter', 'message_protection_key_authority_and_historical_verifier_continuity': 'kms_backed_envelope_or_transport_protection_profile', 'secret_credential_payload_exclusion_and_erasure_boundary': 'reference_only_secret_authority_profile', 'trace_context_observability_only_validation_and_redaction': 'w3c_trace_context_bounded_profile'} or d4d.get('candidate_status') != 'selected_c2_security_profile' or d4d.get('state') != 'selected_candidate': errors.append("D4-D selection leakage")
    if d4d.get("evidence_completed")!=D4D_CREDITS or d4d.get("evidence_remaining")!=[]: errors.append("D4-D current ledger must be exactly five-of-five")
    if sum(len(t.get("evidence_completed",[])) for t in tracks.values())!=26: errors.append("D4-wide evidence count drift")
    return errors

def _project(state:dict)->dict:
    result=copy.deepcopy(state)
    for tid in ("D4-C","D4-D"):
        t=next(x for x in result["tracks"] if x.get("track_id")==tid); t["evidence_completed"]=[]; t["evidence_remaining"]=list(t["required_evidence"])
    _d4d = next(t for t in result['tracks'] if t.get('track_id') == 'D4-D'); _d4d.update(candidate=None, candidate_status='not_selected', state='candidate_selection_open'); return result

def validate(root:Path)->list[str]:
    state=json.loads((root/STATE_PATH).read_text(encoding="utf-8")); current=_current_errors(state)
    if current:return current
    original=historical.load_json
    try:
        def projected_load(path:Path):
            value=_legacy_load_json(path)
            try:
                if path.resolve()==(root/STATE_PATH).resolve(): return _project(value)
            except Exception: pass
            return value
        historical.load_json=projected_load; return historical.validate(root)
    finally: historical.load_json=original

def main()->int:
    root=Path(sys.argv[1]) if len(sys.argv)>1 else Path("."); errors=validate(root)
    if errors:
        for error in errors: print(f"ERROR: {error}")
        return 1
    print("d4c_ack_lease_checkpoint_source=PASS source_auto_credit=false historical_oracle=preserved current_d4c=9_of_9 current_d4d=5_of_5 d4wide=26_of_26 selection=not_selected")
    return 0
if __name__=="__main__": raise SystemExit(main())
