#!/usr/bin/env python3
from __future__ import annotations
import json,sys
from pathlib import Path
MANIFEST=Path('implementation/d4-eventing-async/state-manifest.json'); EXPECTED_BASE='ee8775fc5e7a25b1c4e166a8bb48b53438f6bd42'
EXPECTED_TOTAL_EVIDENCE=26
EXPECTED_TOTAL_CREDITED=23
EXPECTED_TRACK_SOURCES={'D4-A':['OPEN-EVT-001','OPEN-EVT-005','OPEN-REL-012.A'],'D4-B':['OPEN-EVT-002','OPEN-EVT-003','OPEN-EVT-004'],'D4-C':['OPEN-EVT-008','OPEN-EVT-009','OPEN-EVT-010','OPEN-EVT-011','OPEN-EVT-012','OPEN-EVT-013','OPEN-EVT-014','OPEN-EVT-015','OPEN-EVT-025'],'D4-D':['OPEN-EVT-016','OPEN-EVT-017','OPEN-EVT-018']}
EXPECTED_REQUIRED_EVIDENCE={
'D4-A':['capacity_envelope_baseline_growth_stress','broker_neutral_anti_corruption_stub_swap','regulated_payload_erasure_granularity','exactly_once_guardrail_consumer_inbox_enforcement','ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency','physical_naming_routing_and_cell_topology_adapter_mapping','broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark'],
'D4-B':['canonical_bounded_serialization_profile','parser_ambiguity_and_duplicate_field_negative_vectors','schema_catalog_semantic_manifest_compatibility_ci','historical_reader_and_equivalence_profile_continuity','contract_version_representation_and_breaking_change_vectors'],
'D4-C':['ack_after_durable_responsibility_and_lease_ambiguity','quarantine_redrive_current_authority_and_dedup_preservation','bounded_message_batch_compression_and_parser_limits','scoped_content_equivalence_confidentiality_and_conflict_rejection','outbox_claim_dispatch_ack_ambiguity_and_recovery_continuity','producer_generation_nonresurrection_across_failover_restore','privileged_bounded_replay_with_original_identity_and_effect_safety','historical_reader_upcaster_semantic_and_equivalence_continuity','recovery_generation_rf_inventory_reconciliation_and_activation_gates'],
'D4-D':['workload_identity_to_broker_credential_adapter_least_privilege','tenant_and_contract_scoped_producer_consumer_authorization','message_protection_key_authority_and_historical_verifier_continuity','secret_credential_payload_exclusion_and_erasure_boundary','trace_context_observability_only_validation_and_redaction']}
EXPECTED_COMPLETED={'D4-A':list(EXPECTED_REQUIRED_EVIDENCE['D4-A']),'D4-B':list(EXPECTED_REQUIRED_EVIDENCE['D4-B']),'D4-C':list(EXPECTED_REQUIRED_EVIDENCE['D4-C']),'D4-D':EXPECTED_REQUIRED_EVIDENCE['D4-D'][:2]}
EXPECTED_D4B_CANDIDATE={'serialization':{'surface_policy':'explicit_surface_bound_profiles','internal_broker':'protobuf_profile','outbound_webhook':'bounded_json_plus_json_schema_profile'},'schema_catalog':'hybrid_reviewed_git_plus_registry_catalog','contract_version':'positive_integer_family_revision'}
EXPECTED_C3_EXCLUSIONS={'OPEN-EVT-006','OPEN-EVT-007','OPEN-EVT-019','OPEN-EVT-026','OPEN-EVT-027','OPEN-EVT-028','OPEN-REL-012.B','production_partition_counts','production_retry_backoff_jitter_numerics','production_retention_lag_replay_quarantine_horizons','production_realtime_buffer_session_numerics'}
EXPECTED_LATER_EXCLUSIONS={'OPEN-EVT-020','OPEN-EVT-021','OPEN-EVT-022','OPEN-EVT-023','OPEN-EVT-024','wave4_monitoring_product_implementation','production_deployment'}
def load_manifest(root): return json.loads((root/MANIFEST).read_text())
def validate_manifest(state):
 e=[]
 def req(ok,msg):
  if not ok:e.append(msg)
 req(state.get('schema_version')==1,'schema_version must be 1'); req(state.get('gate_id')=='D4' and state.get('gate_name')=='eventing_async_transport_c2','D4 identity drift'); req(state.get('canonical_base')==EXPECTED_BASE,'D4 canonical_base drift'); req(state.get('predecessor')=={'gate_id':'D3','state':'separately_accepted','canonical_commit':EXPECTED_BASE},'D3 predecessor drift')
 req(state.get('gate_state')=='scoped','D4 must remain scoped'); req(state.get('d4_transport_authority')=='selected_not_granted','D4 transport authority must remain ungranted'); req(state.get('canonical_product_implementation_authority')=='not_granted','D4 must not grant canonical Product implementation authority'); req(state.get('wave4_implementation_authority')=='not_granted','D4 must not grant Wave 4 implementation authority'); req(state.get('production_authority')=='none','D4 must not grant production authority'); req(state.get('c3_numeric_topology_authority')=='not_selected','D4 must not select C3 numeric/topology authority')
 tracks=state.get('tracks'); req(isinstance(tracks,list) and all(isinstance(t,dict) for t in tracks),'tracks must be object list')
 if not isinstance(tracks,list) or not all(isinstance(t,dict) for t in tracks): return e
 ids=[t.get('track_id') for t in tracks]; req(ids==['D4-A','D4-B','D4-C','D4-D'],'D4 track identity/order drift'); by={t['track_id']:t for t in tracks}
 for tid in ['D4-A','D4-B','D4-C','D4-D']:
  t=by[tid]; r=EXPECTED_REQUIRED_EVIDENCE[tid]; c=EXPECTED_COMPLETED[tid]; rem=[x for x in r if x not in c]
  req(t.get('source_decisions')==EXPECTED_TRACK_SOURCES[tid],tid+' source decision drift'); req(t.get('required_evidence')==r,tid+' required evidence drift'); req(t.get('evidence_completed')==c,tid+' completed evidence drift'); req(t.get('evidence_remaining')==rem,tid+' remaining evidence drift'); req(len(c)==len(set(c)),tid+' duplicate completed evidence')
 a,b,c,d=(by[x] for x in ['D4-A','D4-B','D4-C','D4-D']); req(a.get('candidate')=='kafka' and a.get('candidate_status')=='selected_c2_candidate' and a.get('state')=='selected_candidate','D4-A selected candidate drift'); req(b.get('candidate')==EXPECTED_D4B_CANDIDATE and b.get('candidate_status')=='selected_c2_profile' and b.get('state')=='selected_candidate','D4-B selected profile drift')
 for tid,t in [('D4-C',c),('D4-D',d)]: req(t.get('candidate') is None,f'{tid} must not silently select a candidate'); req(t.get('candidate_status')=='not_selected',f'{tid} candidate status must remain not_selected'); req(t.get('state')=='candidate_selection_open',f'{tid} scoped state drift')
 req(sum(len(t.get('required_evidence',[])) for t in tracks)==EXPECTED_TOTAL_EVIDENCE,'D4 required evidence total drift'); req(sum(len(t.get('evidence_completed',[])) for t in tracks)==EXPECTED_TOTAL_CREDITED,'D4 credited evidence total drift'); req(set(state.get('explicit_c3_exclusions',[]))==EXPECTED_C3_EXCLUSIONS,'D4 C3 exclusion set drift'); req(set(state.get('explicit_product_or_later_gate_exclusions',[]))==EXPECTED_LATER_EXCLUSIONS,'D4 Product/later-gate exclusion set drift'); req('separate_acceptance' in state.get('acceptance_rule',''),'D4 acceptance must remain separate'); req('separate_explicit_user_authorization' in state.get('merge_rule',''),'D4 merge must remain separately authorized')
 return e
if __name__=='__main__':
 root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd(); errors=validate_manifest(load_manifest(root)); [print('D4_STATE_ERROR:',x,file=sys.stderr) for x in errors]
 if errors: raise SystemExit(1)
 print('d4_eventing_async_state=PASS evidence_required=26 evidence_credited=23 d4a=7_of_7 d4b=5_of_5 d4c=9_of_9 d4d=2_of_5 selection_open authorities=unchanged')
