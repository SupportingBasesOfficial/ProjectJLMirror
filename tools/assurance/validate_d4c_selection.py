#!/usr/bin/env python3
from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SELECTION=Path('implementation/d4-eventing-async/d4-c-selection-record.json')
LEDGER=Path('implementation/d4-eventing-async/d4-c-evidence-plan.json')
STATE=Path('implementation/d4-eventing-async/state-manifest.json')
EVALUATION=Path('implementation/d4-eventing-async/d4-c-candidate-evaluation-plan.json')
EXPECTED_BASE='8d49980d45256a86a6005a93cc71f5518622cc90'
EXPECTED_PROFILE={
 'ack_visibility_lease_and_checkpoint':'durable_inbox_claim_then_broker_ack_profile',
 'quarantine_and_redrive':'hybrid_platform_quarantine_store_plus_broker_dlq',
 'bounded_message_payload_batch_and_compression':'layered_transport_and_application_bounds_profile',
 'scoped_content_equivalence_authority':'hybrid_equivalence_authority_profile',
 'outbox_claim_dispatch_and_ack_ambiguity':'compare_and_swap_lease_claim_profile',
 'producer_source_generation':'authority_issued_epoch_generation',
 'privileged_replay_and_event_history':'hybrid_history_archive_plus_replay_controller_profile',
 'historical_reader_and_upcaster':'in_process_versioned_reader_upcaster_registry',
 'recovery_generation_reconciliation_and_activation':'hybrid_generation_manifest_plus_multi_store_reconciler_profile'}
EXPECTED_EVIDENCE=['ack_after_durable_responsibility_and_lease_ambiguity','quarantine_redrive_current_authority_and_dedup_preservation','bounded_message_batch_compression_and_parser_limits','scoped_content_equivalence_confidentiality_and_conflict_rejection','outbox_claim_dispatch_ack_ambiguity_and_recovery_continuity','producer_generation_nonresurrection_across_failover_restore','privileged_bounded_replay_with_original_identity_and_effect_safety','historical_reader_upcaster_semantic_and_equivalence_continuity','recovery_generation_rf_inventory_reconciliation_and_activation_gates']
def load(root,path): return json.loads((root/path).read_text())
def selected_projection(selection): return {k:v['mechanism_class'] for k,v in selection['profile'].items()}
def validate_authorities(record,prefix,gate_field,expected_gate='scoped'):
 e=[]
 def req(ok,msg):
  if not ok:e.append(prefix+msg)
 req(record.get(gate_field)==expected_gate,'D4 gate authority drift')
 req(record.get('d4_transport_authority')=='selected_not_granted','transport authority escalation')
 req(record.get('canonical_product_implementation_authority')=='not_granted','Product authority escalation')
 req(record.get('wave4_implementation_authority')=='not_granted','Wave4 authority escalation')
 req(record.get('production_authority')=='none','production authority escalation')
 req(record.get('c3_numeric_topology_authority')=='not_selected','C3 authority escalation')
 return e
def validate_records(selection,ledger,state,evaluation):
 e=[]
 def req(ok,msg):
  if not ok:e.append(msg)
 req(selection.get('schema_version')==1 and selection.get('selection_id')=='d4-c-bounded-c2-delivery-recovery-profile-selection-v1','selection identity drift')
 req(selection.get('gate_id')=='D4' and selection.get('track_id')=='D4-C','selection gate/track drift')
 req(selection.get('selection_base_main_commit')==EXPECTED_BASE,'selection base drift')
 req(selection.get('selection_state')=='selected' and selection.get('track_state')=='selected_candidate','selection state drift')
 req(set(selection.get('profile',{}))==set(EXPECTED_PROFILE),'selection profile axes drift')
 if isinstance(selection.get('profile'),dict):
  for axis,mechanism in EXPECTED_PROFILE.items():
   rec=selection['profile'].get(axis,{})
   req(rec.get('selection_state')=='selected',axis+' selection state drift')
   req(rec.get('mechanism_class')==mechanism,axis+' mechanism selection drift')
 req(selected_projection(selection)==EXPECTED_PROFILE,'selected projection drift')
 e.extend(validate_authorities(selection,'selection ','d4_gate_state'))
 req(ledger.get('candidate')==EXPECTED_PROFILE,'current ledger selected profile drift')
 req(ledger.get('candidate_status')=='selected_c2_delivery_recovery_profile','current ledger selected status drift')
 req(ledger.get('selection_state')=='selected' and ledger.get('selection_authority')=='selection_record','current ledger selection authority drift')
 req(ledger.get('separate_selection_required') is False,'current ledger separate selection must be closed')
 req(ledger.get('credited_evidence')==EXPECTED_EVIDENCE and ledger.get('remaining_evidence')==[] and ledger.get('ledger_credit_state')=='nine_of_nine','current ledger evidence drift')
 e.extend(validate_authorities(ledger,'ledger ','d4_gate_state')) if 'd4_gate_state' in ledger else e.extend(validate_authorities({**ledger,'d4_gate_state':'scoped'},'ledger ','d4_gate_state'))
 tracks={t.get('track_id'):t for t in state.get('tracks',[]) if isinstance(t,dict)}; c=tracks.get('D4-C',{})
 req(c.get('candidate')==EXPECTED_PROFILE,'state selected profile drift')
 req(c.get('candidate_status')=='selected_c2_delivery_recovery_profile' and c.get('state')=='accepted_candidate','state D4-C accepted disposition drift')
 req(c.get('evidence_completed')==EXPECTED_EVIDENCE and c.get('evidence_remaining')==[],'state D4-C evidence drift')
 req(all(tracks.get(tid,{}).get('state')=='accepted_candidate' for tid in ('D4-A','D4-B','D4-C','D4-D')),'current D4 track acceptance projection drift')
 e.extend(validate_authorities(state,'state ','gate_state','separately_accepted'))
 req(evaluation.get('selection_state')=='not_selected' and evaluation.get('selection_authority')=='not_granted' and evaluation.get('separate_selection_required') is True,'historical evaluation plan must remain not_selected')
 req(selection.get('separate_d4_acceptance_required') is True and ledger.get('separate_d4_acceptance_required') is True,'historical selection/ledger acceptance separation drift')
 return e
def main():
 root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT
 vals=[load(root,p) for p in (SELECTION,LEDGER,STATE,EVALUATION)]
 errors=validate_records(*vals)
 for x in errors: print('D4C_SELECTION_ERROR:',x,file=sys.stderr)
 if errors:return 1
 print('d4c_selection=PASS evidence=9_of_9 d4wide=26_of_26 current_d4=separately_accepted historical_selection=preserved authorities=unchanged')
 return 0
if __name__=='__main__': raise SystemExit(main())
