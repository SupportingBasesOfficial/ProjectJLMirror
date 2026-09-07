#!/usr/bin/env python3
from __future__ import annotations
import json,sys
from pathlib import Path
from d4d_message_protection_source import run_probes
MANIFEST=Path('implementation/d4-eventing-async/source-evidence/d4-d-message-protection-key-authority/source-evidence-manifest.json')
STATE=Path('implementation/d4-eventing-async/state-manifest.json')
PLAN=Path('implementation/d4-eventing-async/d4-d-candidate-evaluation-plan.json')
FIRST='workload_identity_to_broker_credential_adapter_least_privilege'
SECOND='tenant_and_contract_scoped_producer_consumer_authorization'
EXPECTED_ID='message_protection_key_authority_and_historical_verifier_continuity'
EXPECTED_DECISION='OPEN-EVT-017'
EXPECTED_AXIS=EXPECTED_ID
EXPECTED_MUST={
'data_classification_controls_protection_storage_delivery_logging_and_retention',
'key_material_remains_behind_secret_or_kms_authority',
'retained_evidence_contains_only_non_secret_profile_and_key_generation_references',
'historical_verifier_authority_remains_available_for_supported_equivalence_horizon_or_is_equality_preserving_migrated',
'verifier_loss_or_unknown_generation_fails_closed_for_duplicate_sensitive_effects',
'restored_old_verifier_or_profile_cannot_become_current_authority_for_unrelated_scope',
'key_or_profile_rotation_preserves_historical_comparison_without_secret_exposure',
'encryption_does_not_replace_minimization_or_authorization'}
REQUIRED=[FIRST,SECOND,EXPECTED_ID,'secret_credential_payload_exclusion_and_erasure_boundary','trace_context_observability_only_validation_and_redaction']

def validate(root:Path):
    e=[]
    m=json.loads((root/MANIFEST).read_text())
    state=json.loads((root/STATE).read_text())
    plan=json.loads((root/PLAN).read_text())
    if m.get('evidence_id')!=EXPECTED_ID or m.get('source_decision')!=EXPECTED_DECISION:e.append('wrong source evidence identity')
    if set(m.get('must_prove',[]))!=EXPECTED_MUST:e.append('must_prove drift')
    if m.get('message_protection_authority')!='secret_or_kms_authority_with_historical_verifier_continuity':e.append('message protection authority drift')
    if m.get('current_run_auto_credit') is not False or m.get('ledger_credit')!=[]:e.append('source evidence must remain non-promoting at source time')
    if m.get('candidate') is not None or m.get('candidate_status')!='not_selected' or m.get('selection_authority')!='not_granted':e.append('source evidence must not select D4-D')
    st=m.get('source_time_state',{})
    if st.get('d4d')!='2_of_5_unselected' or st.get('d4wide')!='23_of_26':e.append('source-time snapshot must remain 2/5 and 23/26')
    axis=plan['axes'][EXPECTED_AXIS]
    if axis.get('decision')!=EXPECTED_DECISION or set(axis.get('must_prove',[]))!=EXPECTED_MUST:e.append('candidate-plan/source must_prove mismatch')
    tracks={t['track_id']:t for t in state['tracks']}; d=tracks['D4-D']
    if d.get('candidate') is not None or d.get('candidate_status')!='not_selected' or d.get('state')!='candidate_selection_open':e.append('D4-D state must remain open/unselected')
    if d.get('required_evidence')!=REQUIRED or d.get('evidence_completed')!=[FIRST,SECOND] or d.get('evidence_remaining')!=REQUIRED[2:]:e.append('current D4-D state must remain exactly two promoted credits')
    if sum(len(t['evidence_completed']) for t in state['tracks'])!=23:e.append('D4-wide current state must remain 23/26')
    if state.get('gate_state')!='scoped' or state.get('d4_transport_authority')!='selected_not_granted' or state.get('canonical_product_implementation_authority')!='not_granted' or state.get('wave4_implementation_authority')!='not_granted' or state.get('production_authority')!='none' or state.get('c3_numeric_topology_authority')!='not_selected':e.append('authority leakage')
    bad=[k for k,v in run_probes().items() if not v]
    if bad:e.append('behavior probes failed: '+','.join(bad))
    return e

if __name__=='__main__':
    root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd()
    errors=validate(root)
    [print('D4D_MESSAGE_PROTECTION_SOURCE_ERROR:',x,file=sys.stderr) for x in errors]
    if errors:raise SystemExit(1)
    print('d4d_message_protection_source=PASS source_snapshot=2_of_5 source_auto_credit=false current_d4d=2_of_5 d4wide=23/26 selection=not_selected authorities=unchanged')
