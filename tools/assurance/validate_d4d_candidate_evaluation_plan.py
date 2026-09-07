#!/usr/bin/env python3
from __future__ import annotations
import json,sys
from pathlib import Path
PLAN=Path('implementation/d4-eventing-async/d4-d-candidate-evaluation-plan.json'); STATE=Path('implementation/d4-eventing-async/state-manifest.json')
EXPECTED_SOURCE_DECISIONS=['OPEN-EVT-016','OPEN-EVT-017','OPEN-EVT-018']
EXPECTED_AXES={'workload_identity_to_broker_credential_adapter':'OPEN-EVT-016','tenant_and_contract_scoped_producer_consumer_authorization':'OPEN-EVT-016','message_protection_key_authority_and_historical_verifier_continuity':'OPEN-EVT-017','secret_credential_payload_exclusion_and_erasure_boundary':'OPEN-EVT-017','trace_context_observability_only_validation_and_redaction':'OPEN-EVT-018'}
D4C_CREDITS=['ack_after_durable_responsibility_and_lease_ambiguity','quarantine_redrive_current_authority_and_dedup_preservation','bounded_message_batch_compression_and_parser_limits','scoped_content_equivalence_confidentiality_and_conflict_rejection','outbox_claim_dispatch_ack_ambiguity_and_recovery_continuity','producer_generation_nonresurrection_across_failover_restore','privileged_bounded_replay_with_original_identity_and_effect_safety','historical_reader_upcaster_semantic_and_equivalence_continuity','recovery_generation_rf_inventory_reconciliation_and_activation_gates']
D4D_REQUIRED=['workload_identity_to_broker_credential_adapter_least_privilege','tenant_and_contract_scoped_producer_consumer_authorization','message_protection_key_authority_and_historical_verifier_continuity','secret_credential_payload_exclusion_and_erasure_boundary','trace_context_observability_only_validation_and_redaction']; D4D_CREDITS=D4D_REQUIRED[:2]
FORBIDDEN_OUTPUTS=['selected','preferred_without_evidence','production_ready','authority_granted']; ALLOWED_OUTPUTS=['eligible_for_evidence_execution','ineligible_by_contract','insufficient_evidence']
def load(root,p): return json.loads((root/p).read_text())
def validate(root):
 e=[]; plan=load(root,PLAN); state=load(root,STATE)
 if plan.get('schema_version')!=1 or plan.get('gate_id')!='D4' or plan.get('track_id')!='D4-D': e.append('plan identity must be schema v1 / D4 / D4-D')
 if plan.get('mode')!='candidate_evaluation_only' or plan.get('selection_state')!='not_selected' or plan.get('selection_authority')!='not_granted': e.append('candidate evaluation must remain non-selecting')
 if plan.get('separate_selection_required') is not True or plan.get('separate_d4_acceptance_required') is not True: e.append('selection and D4 acceptance must remain separate')
 if plan.get('source_decisions')!=EXPECTED_SOURCE_DECISIONS: e.append('source decision inventory drift')
 axes=plan.get('axes',{})
 if list(axes)!=list(EXPECTED_AXES): e.append('D4-D must expose exactly five ordered axes')
 else:
  for n,d in EXPECTED_AXES.items():
   a=axes[n]
   if a.get('decision')!=d: e.append(n+': wrong source decision')
   c=a.get('candidate_classes'); m=a.get('must_prove')
   if not isinstance(c,list) or len(c)<3 or len(c)!=len(set(c)): e.append(n+': candidate classes incomplete')
   if not isinstance(m,list) or len(m)<6 or len(m)!=len(set(m)): e.append(n+': must_prove incomplete')
 if 'adapter_consumes_ir_d_002_canonical_workload_identity_without_reopening_issuer_or_attestation_authority' not in axes.get('workload_identity_to_broker_credential_adapter',{}).get('must_prove',[]): e.append('IR-D-002 boundary drift')
 if plan.get('evaluation_output_states')!=ALLOWED_OUTPUTS or plan.get('forbidden_outputs')!=FORBIDDEN_OUTPUTS: e.append('evaluation output authority drift')
 inv=plan.get('cross_axis_invariants',[])
 for x in ['ir_d_002_canonical_workload_authentication_baseline_is_consumed_not_reopened','broker_vendor_identity_never_becomes_platform_workload_or_tenant_identity','broker_authorization_is_projection_of_current_platform_authority_not_a_parallel_business_authority','message_protection_never_weakens_minimization_authorization_or_historical_equivalence_requirements','trace_context_is_never_security_or_business_effect_authority','d4d_candidate_remains_unselected_and_selection_authority_not_granted']:
  if x not in inv: e.append('cross-axis invariant missing: '+x)
 tracks={t['track_id']:t for t in state.get('tracks',[])}
 if set(tracks)!={'D4-A','D4-B','D4-C','D4-D'}: return e+['global D4 track inventory changed']
 a,b,c,d=(tracks[x] for x in ['D4-A','D4-B','D4-C','D4-D'])
 if a.get('candidate')!='kafka' or len(a.get('evidence_completed',[]))!=7 or a.get('evidence_remaining')!=[]: e.append('D4-A must remain 7/7')
 if b.get('candidate_status')!='selected_c2_profile' or len(b.get('evidence_completed',[]))!=5 or b.get('evidence_remaining')!=[]: e.append('D4-B must remain 5/5')
 if c.get('candidate') is not None or c.get('candidate_status')!='not_selected' or c.get('state')!='candidate_selection_open' or c.get('evidence_completed')!=D4C_CREDITS or c.get('evidence_remaining')!=[]: e.append('D4-C must remain 9/9 open/unselected')
 if d.get('source_decisions')!=EXPECTED_SOURCE_DECISIONS or d.get('candidate') is not None or d.get('candidate_status')!='not_selected' or d.get('state')!='candidate_selection_open': e.append('D4-D state boundary drift')
 if d.get('required_evidence')!=D4D_REQUIRED or d.get('evidence_completed')!=D4D_CREDITS or d.get('evidence_remaining')!=D4D_REQUIRED[2:]: e.append('current D4-D state must reflect exactly two separately promoted credits')
 if sum(len(t.get('evidence_completed',[])) for t in tracks.values())!=23: e.append('D4-wide evidence must be exactly 23/26')
 if (state.get('gate_state'),state.get('d4_transport_authority'),state.get('canonical_product_implementation_authority'),state.get('wave4_implementation_authority'),state.get('production_authority'),state.get('c3_numeric_topology_authority'))!=('scoped','selected_not_granted','not_granted','not_granted','none','not_selected'): e.append('global authority boundary changed')
 return e
if __name__=='__main__':
 root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd(); errors=validate(root); [print('D4D_EVAL_ERROR:',x,file=sys.stderr) for x in errors]
 if errors: raise SystemExit(1)
 print('d4d_candidate_evaluation_plan=PASS axes=5 selection=not_selected current_d4d=2_of_5 d4wide=23/26 authorities=unchanged')
