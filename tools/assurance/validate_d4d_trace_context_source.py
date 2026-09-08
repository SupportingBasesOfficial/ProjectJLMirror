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
EXPECTED_SCHEMA_VERSION=1
EXPECTED_GATE='D4'
EXPECTED_TRACK='D4-D'
EXPECTED_DECISION='OPEN-EVT-018'
EXPECTED_ID='trace_context_observability_only_validation_and_redaction'
EXPECTED_MODE='source_evidence_only'
EXPECTED_SOURCE_BASE='98fb99cc04fcf42e795596f68939149463645799'
REQUIRED=[E1,E2,E3,E4,EXPECTED_ID]
CURRENT_CREDITED=[E1,E2,E3,E4]
EXPECTED_SOURCE_TIME_STATE={
'd4a':'7_of_7_selected','d4b':'5_of_5_selected','d4c':'9_of_9_unselected','d4d':'4_of_5_unselected','d4wide':'25_of_26',
'd4_transport_authority':'selected_not_granted','canonical_product_implementation_authority':'not_granted','wave4_implementation_authority':'not_granted','production_authority':'none','c3_numeric_topology_authority':'not_selected'}
EXPECTED_MUST={
'trace_context_is_observability_only','trace_context_never_becomes_tenant_authorization_idempotency_ordering_or_message_identity_authority','trace_fields_are_bounded_and_canonically_validated','untrusted_or_malformed_trace_context_is_rejected_or_safely_regenerated_without_changing_message_semantics','sensitive_trace_attributes_are_redacted_by_policy','cross_tenant_trace_correlation_cannot_expose_or_join_protected_context','missing_trace_context_does_not_change_business_effect_or_delivery_semantics'}
EXPECTED_PROBES={
'trace_context_is_observability_only','trace_context_not_tenant_authority','trace_context_not_idempotency_authority','trace_context_not_ordering_authority','trace_context_not_message_identity_authority','trace_context_not_delivery_authority','valid_traceparent_accepted','accepted_traceparent_is_tenant_scoped','bounded_canonical_tracestate_validated_on_ingress','observable_export_discards_tracestate','allowlisted_trace_attributes_preserved','missing_trace_context_preserves_business_and_delivery_semantics','malformed_traceparent_1_rejected','malformed_traceparent_2_rejected','malformed_traceparent_3_rejected','malformed_traceparent_4_rejected','malformed_traceparent_5_rejected','unsupported_traceparent_version_rejected','orphan_tracestate_rejected','non_string_tracestate_rejected','oversized_tracestate_rejected','malformed_tracestate_member_rejected','duplicate_tracestate_key_rejected','excess_tracestate_members_rejected','excess_trace_attributes_rejected','unknown_trace_attribute_rejected','sensitive_value_under_allowlisted_key_rejected','non_string_trace_attributes_rejected','attribute_context_required','component_source_impersonation_rejected','untrusted_attribute_source_rejected','protected_classification_attribute_rejected','wrong_hop_scope_attribute_rejected','egress_attribute_rejected','malformed_traceparent_does_not_abort_business_processing','malformed_tracestate_does_not_abort_business_processing','malformed_attribute_does_not_abort_business_processing','malformed_propagation_context_source_does_not_abort_business_processing','malformed_propagation_context_trust_level_does_not_abort_business_processing','malformed_propagation_context_classification_does_not_abort_business_processing','malformed_propagation_context_hop_scope_does_not_abort_business_processing','malformed_propagation_context_leaving_jlmirror_does_not_abort_business_processing','same_tenant_trace_correlation_allowed','cross_tenant_trace_correlation_blocked','same_input_trace_id_is_stable_within_tenant','same_input_trace_id_is_different_across_tenants','copied_tracestate_is_not_exported_across_tenants','authenticated_scope_preserves_same_tenant_multi_hop_trace','authenticated_scope_is_rescoped_at_different_tenant_boundary','raw_scoped_bytes_are_not_scope_authority','forged_scope_proof_is_rejected_without_business_abort','known_short_marker_collision_cannot_bypass_tenant_rescoping','scope_proof_issuance_scopes_before_attesting','authenticated_trace_identity_allows_child_span_parent_change','malformed_scope_proof_tenant_id_does_not_abort_business_processing','malformed_scope_proof_trace_id_does_not_abort_business_processing','malformed_scope_proof_mac_hex_does_not_abort_business_processing','scope_and_issue_runtime_boundary_fail_closed','scope_and_issue_requires_context_for_attributes','scope_and_issue_rejects_unallowlisted_attributes','scope_and_issue_rejects_sensitive_allowlisted_value','scope_and_issue_rejects_component_source_impersonation','scope_and_issue_rejects_untrusted_attribute_context','scope_and_issue_rejects_duplicate_attribute_keys','scope_and_issue_rejects_noncanonical_attribute_order','trace_change_does_not_change_business_or_delivery_semantics'}
def validate(root:Path):
    e=[]; m=json.loads((root/MANIFEST).read_text()); state=json.loads((root/STATE).read_text()); plan=json.loads((root/PLAN).read_text())
    identity={'schema_version':m.get('schema_version'),'gate_id':m.get('gate_id'),'track_id':m.get('track_id'),'source_decision':m.get('source_decision'),'evidence_id':m.get('evidence_id'),'mode':m.get('mode'),'source_base':m.get('source_base')}
    expected_identity={'schema_version':EXPECTED_SCHEMA_VERSION,'gate_id':EXPECTED_GATE,'track_id':EXPECTED_TRACK,'source_decision':EXPECTED_DECISION,'evidence_id':EXPECTED_ID,'mode':EXPECTED_MODE,'source_base':EXPECTED_SOURCE_BASE}
    if identity!=expected_identity:e.append('source evidence immutable identity envelope drift')
    if set(m.get('must_prove',[]))!=EXPECTED_MUST:e.append('must_prove drift')
    if m.get('trace_context_authority')!='observability_only_validated_bounded_and_redacted':e.append('trace context authority drift')
    if m.get('current_run_auto_credit') is not False or m.get('ledger_credit')!=[]:e.append('source evidence must remain non-promoting at source time')
    if m.get('candidate') is not None or m.get('candidate_status')!='not_selected' or m.get('selection_authority')!='not_granted':e.append('source evidence must not select D4-D')
    if m.get('source_time_state',{})!=EXPECTED_SOURCE_TIME_STATE:e.append('source-time snapshot or authority state drift')
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
    print('d4d_trace_context_source=PASS source_identity=exact source_snapshot=4_of_5 source_auto_credit=false current_d4d=4_of_5 d4wide=25/26 selection=not_selected authorities=unchanged probes=66')
