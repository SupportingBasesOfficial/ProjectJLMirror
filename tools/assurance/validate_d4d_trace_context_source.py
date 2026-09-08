#!/usr/bin/env python3
from __future__ import annotations
import json,sys
from pathlib import Path
from d4d_trace_context_source import run_probes
MANIFEST=Path('implementation/d4-eventing-async/source-evidence/d4-d-trace-context-observability/source-evidence-manifest.json')
STATE=Path('implementation/d4-eventing-async/state-manifest.json')
PLAN=Path('implementation/d4-eventing-async/d4-d-candidate-evaluation-plan.json')
E1='workload_identity_to_broker_credential_adapter_least_privilege'
E2='tenant_and_contract_scoped_producer_consumer_authorization'
E3='message_protection_key_authority_and_historical_verifier_continuity'
E4='secret_credential_payload_exclusion_and_erasure_boundary'
EXPECTED_ID='trace_context_observability_only_validation_and_redaction'
EXPECTED_DECISION='OPEN-EVT-018'
REQUIRED=[E1,E2,E3,E4,EXPECTED_ID]
CURRENT_CREDITED=[E1,E2,E3,E4]
EXPECTED_MUST={
'trace_context_is_observability_only',
'trace_context_never_becomes_tenant_authorization_idempotency_ordering_or_message_identity_authority',
'trace_fields_are_bounded_and_canonically_validated',
'untrusted_or_malformed_trace_context_is_rejected_or_safely_regenerated_without_changing_message_semantics',
'sensitive_trace_attributes_are_redacted_by_policy',
'cross_tenant_trace_correlation_cannot_expose_or_join_protected_context',
'missing_trace_context_does_not_change_business_effect_or_delivery_semantics'}
EXPECTED_PROBES={
'trace_context_is_observability_only','trace_context_not_tenant_authority','trace_context_not_idempotency_authority','trace_context_not_ordering_authority','trace_context_not_message_identity_authority','valid_traceparent_accepted','bounded_tracestate_accepted','sensitive_trace_attribute_redacted','non_sensitive_trace_attribute_preserved','missing_trace_context_preserves_business_semantics','malformed_traceparent_1_rejected','malformed_traceparent_2_rejected','malformed_traceparent_3_rejected','malformed_traceparent_4_rejected','oversized_tracestate_rejected','excess_trace_attributes_rejected','same_tenant_trace_correlation_allowed','cross_tenant_trace_correlation_blocked','trace_change_does_not_change_business_effect'}
def validate(root:Path):
    e=[]; m=json.loads((root/MANIFEST).read_text()); state=json.loads((root/STATE).read_text()); plan=json.loads((root/PLAN).read_text())
    if m.get('evidence_id')!=EXPECTED_ID or m.get('source_decision')!=EXPECTED_DECISION:e.append('wrong source evidence identity')
    if set(m.get('must_prove',[]))!=EXPECTED_MUST:e.append('must_prove drift')
    if m.get('trace_context_authority')!='observability_only_validated_bounded_and_redacted':e.append('trace context authority drift')
    if m.get('current_run_auto_credit') is not False or m.get('ledger_credit')!=[]:e.append('source evidence must remain non-promoting at source time')
    if m.get('candidate') is not None or m.get('candidate_status')!='not_selected' or m.get('selection_authority')!='not_granted':e.append('source evidence must not select D4-D')
    st=m.get('source_time_state',{})
    if st.get('d4d')!='4_of_5_unselected' or st.get('d4wide')!='25_of_26':e.append('source-time snapshot must remain 4/5 and 25/26')
    axis=plan['axes'][EXPECTED_ID]
    if axis.get('decision')!=EXPECTED_DECISION or set(axis.get('must_prove',[]))!=EXPECTED_MUST:e.append('candidate-plan/source must_prove mismatch')
    tracks={t['track_id']:t for t in state['tracks']}; d=tracks['D4-D']
    if d.get('candidate') is not None or d.get('candidate_status')!='not_selected' or d.get('state')!='candidate_selection_open':e.append('D4-D state must remain open/unselected')
    if d.get('required_evidence')!=REQUIRED or d.get('evidence_completed')!=CURRENT_CREDITED or d.get('evidence_remaining')!=[EXPECTED_ID]:e.append('current D4-D state must remain exactly four separately promoted credits plus E5 remaining')
    if sum(len(t.get('evidence_completed',[])) for t in state['tracks'])!=25:e.append('D4-wide current state must remain 25/26')
    if state.get('gate_state')!='scoped' or state.get('d4_transport_authority')!='selected_not_granted' or state.get('canonical_product_implementation_authority')!='not_granted' or state.get('wave4_implementation_authority')!='not_granted' or state.get('production_authority')!='none' or state.get('c3_numeric_topology_authority')!='not_selected':e.append('authority leakage')
    proofs=run_probes()
    if set(proofs)!=EXPECTED_PROBES:e.append('executed probe set drift')
    bad=[k for k,v in proofs.items() if not v]
    if bad:e.append('behavior probes failed: '+','.join(bad))
    return e
if __name__=='__main__':
    root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd(); errors=validate(root)
    [print('D4D_TRACE_CONTEXT_SOURCE_ERROR:',x,file=sys.stderr) for x in errors]
    if errors:raise SystemExit(1)
    print('d4d_trace_context_source=PASS source_snapshot=4_of_5 source_auto_credit=false current_d4d=4_of_5 d4wide=25/26 selection=not_selected authorities=unchanged probes=19')
