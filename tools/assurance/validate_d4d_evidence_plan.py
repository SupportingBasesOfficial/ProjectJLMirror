#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
PLAN=Path('implementation/d4-eventing-async/d4-d-evidence-plan.json')
STATE=Path('implementation/d4-eventing-async/state-manifest.json')
P1=Path('implementation/d4-eventing-async/ledger-promotions/d4-d-open-evt-016-promotion-v1.json')
P2=Path('implementation/d4-eventing-async/ledger-promotions/d4-d-open-evt-016-tenant-contract-promotion-v1.json')
P3=Path('implementation/d4-eventing-async/ledger-promotions/d4-d-open-evt-017-message-protection-promotion-v1.json')
P4=Path('implementation/d4-eventing-async/ledger-promotions/d4-d-open-evt-017-secret-exclusion-promotion-v1.json')
S1=Path('implementation/d4-eventing-async/source-evidence/d4-d-workload-identity/source-evidence-manifest.json')
S2=Path('implementation/d4-eventing-async/source-evidence/d4-d-tenant-contract-authorization/source-evidence-manifest.json')
S3=Path('implementation/d4-eventing-async/source-evidence/d4-d-message-protection-key-authority/source-evidence-manifest.json')
S4=Path('implementation/d4-eventing-async/source-evidence/d4-d-secret-credential-exclusion/source-evidence-manifest.json')
E1='workload_identity_to_broker_credential_adapter_least_privilege'; E2='tenant_and_contract_scoped_producer_consumer_authorization'; E3='message_protection_key_authority_and_historical_verifier_continuity'; E4='secret_credential_payload_exclusion_and_erasure_boundary'; E5='trace_context_observability_only_validation_and_redaction'
REQUIRED=[E1,E2,E3,E4,E5]
SHA1='005b3943f7638e136150758d10d4ec6af1c6852d4e658127c7258ff546dce0ae'; SHA2='e22455580bba6eb71877a8308d5068d0d2a8caf895f9c1ce2c3aeadb724a7025'; SHA3='8d33a50b8748382586aa5b13e2e7427a57b66d8319066acf09f0e09a4ca31c35'; SHA4='5639d4a5b70d89fd10c874689cd87346ca4742e9474763fd89bf809959664da1'
def load(root,p): return json.loads((root/p).read_text())
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def validate(root):
 e=[]; plan=load(root,PLAN); state=load(root,STATE); p1=load(root,P1); p2=load(root,P2); p3=load(root,P3); p4=load(root,P4); s1=load(root,S1); s2=load(root,S2); s3=load(root,S3); s4=load(root,S4)
 if plan.get('credited_evidence')!=[E1,E2,E3,E4] or plan.get('remaining_evidence')!=[E5] or plan.get('ledger_credit_state')!='four_of_five': e.append('D4-D ledger must be exactly four-of-five')
 if plan.get('latest_promotion')!=str(P4): e.append('latest promotion pointer drift')
 if plan.get('candidate') is not None or plan.get('candidate_status')!='not_selected' or plan.get('selection_state')!='not_selected' or plan.get('selection_authority')!='not_granted': e.append('D4-D candidate selection leakage')
 if plan.get('current_run_auto_credit') is not False or plan.get('separate_selection_required') is not True or plan.get('separate_d4_acceptance_required') is not True: e.append('D4-D separation boundary drift')
 if s1.get('evidence_id')!=E1 or s1.get('ledger_credit')!=[] or s1.get('current_run_auto_credit') is not False or s1.get('source_time_state',{}).get('d4d')!='0_of_5_unselected' or digest(root/S1)!=SHA1: e.append('first source snapshot drift')
 if s2.get('evidence_id')!=E2 or s2.get('ledger_credit')!=[] or s2.get('current_run_auto_credit') is not False or s2.get('source_time_state',{}).get('d4d')!='1_of_5_unselected' or s2.get('source_time_state',{}).get('d4wide')!='22_of_26' or digest(root/S2)!=SHA2: e.append('second source snapshot drift')
 if s3.get('evidence_id')!=E3 or s3.get('ledger_credit')!=[] or s3.get('current_run_auto_credit') is not False or s3.get('source_time_state',{}).get('d4d')!='2_of_5_unselected' or s3.get('source_time_state',{}).get('d4wide')!='23_of_26' or digest(root/S3)!=SHA3: e.append('third source snapshot drift')
 if s4.get('evidence_id')!=E4 or s4.get('ledger_credit')!=[] or s4.get('current_run_auto_credit') is not False or s4.get('source_time_state',{}).get('d4d')!='3_of_5_unselected' or s4.get('source_time_state',{}).get('d4wide')!='24_of_26' or digest(root/S4)!=SHA4: e.append('fourth source snapshot drift')
 lineage=s4.get('correction_lineage',{})
 if lineage.get('supersedes_source_pr')!=114 or lineage.get('supersedes_source_head')!='c8d49ccf05113f0274287578bbc6965d220a677d' or lineage.get('superseded_codex_review_id')!=5134974949 or lineage.get('promotion_eligible_source_must_be_this_corrected_lineage_or_later') is not True: e.append('fourth corrected source lineage drift')
 if p1.get('promotion_id')!='d4-d-open-evt-016-promotion-v1' or p1.get('credited_evidence')!=[E1] or p1.get('credit_count')!=1: e.append('first promotion history drift')
 if p2.get('promotion_id')!='d4-d-open-evt-016-tenant-contract-promotion-v1' or p2.get('credited_evidence')!=[E1,E2] or p2.get('credit_count')!=2: e.append('second promotion history drift')
 if p3.get('promotion_id')!='d4-d-open-evt-017-message-protection-promotion-v1' or p3.get('credited_evidence')!=[E1,E2,E3] or p3.get('credit_count')!=3: e.append('third promotion history drift')
 if p4.get('promotion_id')!='d4-d-open-evt-017-secret-exclusion-promotion-v1' or p4.get('promotion_base')!='c9cf2a4623b209c27283efb91d7c743efada71b6' or p4.get('source_pr')!=115 or p4.get('source_reviewed_head')!='31523e7d8d388af3d4f6a6adb309d4363a014884' or p4.get('source_merge_commit')!='c9cf2a4623b209c27283efb91d7c743efada71b6': e.append('fourth promotion source identity drift')
 r=p4.get('source_review',{}); w=p4.get('source_workflow',{})
 if r.get('review_id')!=5144105945 or r.get('codex_clean_comment_id')!=5587879590 or r.get('material_threads_unresolved')!=0: e.append('fourth promotion review provenance drift')
 expected={'workflow_id':352564948,'workflow_path':'.github/workflows/d4-d-secret-exclusion-source-evidence.yml','workflow_event':'pull_request','source_head_branch':'d4d/open-evt-017-secret-exclusion-correction-source','run_id':34246165232,'run_attempt':1,'job_id':102128582025,'job_name':'D4-D secret exclusion source evidence','artifact_id':10064062867,'artifact_name':'d4-d-secret-exclusion-source-31523e7d8d388af3d4f6a6adb309d4363a014884-34246165232-1','artifact_digest':'sha256:b06e805a0940c6407e3d0687620e4e366f5283949742f069c2c245a679c636ea'}
 for k,v in expected.items():
  if w.get(k)!=v: e.append('fourth promotion workflow '+k+' drift')
 if p4.get('source_manifest',{}).get('path')!=str(S4) or p4.get('source_manifest',{}).get('sha256')!=SHA4 or p4.get('credited_evidence')!=[E1,E2,E3,E4] or p4.get('newly_credited_evidence')!=E4 or p4.get('credit_count')!=4: e.append('fourth promotion credit/provenance drift')
 tracks={t['track_id']:t for t in state.get('tracks',[])}; d=tracks.get('D4-D',{})
 if d.get('required_evidence')!=REQUIRED or d.get('evidence_completed')!=[E1,E2,E3,E4] or d.get('evidence_remaining')!=[E5]: e.append('D4-D current state must be exactly four-of-five')
 if d.get('candidate') is not None or d.get('candidate_status')!='not_selected' or d.get('state')!='candidate_selection_open': e.append('D4-D current candidate boundary drift')
 if sum(len(t.get('evidence_completed',[])) for t in tracks.values())!=25: e.append('D4-wide current state must be exactly 25/26')
 authority=(state.get('gate_state'),state.get('d4_transport_authority'),state.get('canonical_product_implementation_authority'),state.get('wave4_implementation_authority'),state.get('production_authority'),state.get('c3_numeric_topology_authority'))
 if authority!=('scoped','selected_not_granted','not_granted','not_granted','none','not_selected'): e.append('authority boundary changed')
 for p in (p1,p2,p3,p4):
  if p.get('selection_state')!='not_selected' or p.get('selection_authority')!='not_granted' or p.get('d4_gate_state')!='scoped' or p.get('d4_transport_authority')!='selected_not_granted' or p.get('canonical_product_implementation_authority')!='not_granted' or p.get('wave4_implementation_authority')!='not_granted' or p.get('production_authority')!='none' or p.get('c3_numeric_topology_authority')!='not_selected': e.append('promotion authority leakage')
 return e
if __name__=='__main__':
 root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd(); errors=validate(root)
 [print('D4D_LEDGER_ERROR:',x,file=sys.stderr) for x in errors]
 if errors: raise SystemExit(1)
 print('d4d_evidence_plan=PASS ledger=4_of_5 d4wide=25/26 selection=not_selected source_snapshots=0_of_5,1_of_5,2_of_5,3_of_5 corrected_lineage=bound authorities=unchanged')
