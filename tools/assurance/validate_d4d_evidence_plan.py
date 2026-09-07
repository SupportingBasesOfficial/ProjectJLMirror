#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
PLAN=Path('implementation/d4-eventing-async/d4-d-evidence-plan.json')
STATE=Path('implementation/d4-eventing-async/state-manifest.json')
P1=Path('implementation/d4-eventing-async/ledger-promotions/d4-d-open-evt-016-promotion-v1.json')
P2=Path('implementation/d4-eventing-async/ledger-promotions/d4-d-open-evt-016-tenant-contract-promotion-v1.json')
P3=Path('implementation/d4-eventing-async/ledger-promotions/d4-d-open-evt-017-message-protection-promotion-v1.json')
S1=Path('implementation/d4-eventing-async/source-evidence/d4-d-workload-identity/source-evidence-manifest.json')
S2=Path('implementation/d4-eventing-async/source-evidence/d4-d-tenant-contract-authorization/source-evidence-manifest.json')
S3=Path('implementation/d4-eventing-async/source-evidence/d4-d-message-protection-key-authority/source-evidence-manifest.json')
E1='workload_identity_to_broker_credential_adapter_least_privilege'; E2='tenant_and_contract_scoped_producer_consumer_authorization'; E3='message_protection_key_authority_and_historical_verifier_continuity'
REQUIRED=[E1,E2,E3,'secret_credential_payload_exclusion_and_erasure_boundary','trace_context_observability_only_validation_and_redaction']
SHA1='005b3943f7638e136150758d10d4ec6af1c6852d4e658127c7258ff546dce0ae'; SHA2='e22455580bba6eb71877a8308d5068d0d2a8caf895f9c1ce2c3aeadb724a7025'; SHA3='8d33a50b8748382586aa5b13e2e7427a57b66d8319066acf09f0e09a4ca31c35'
def load(root,p): return json.loads((root/p).read_text())
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def validate(root):
 e=[]; plan=load(root,PLAN); state=load(root,STATE); p1=load(root,P1); p2=load(root,P2); p3=load(root,P3); s1=load(root,S1); s2=load(root,S2); s3=load(root,S3)
 if plan.get('credited_evidence')!=[E1,E2,E3] or plan.get('remaining_evidence')!=REQUIRED[3:] or plan.get('ledger_credit_state')!='three_of_five': e.append('D4-D ledger must be exactly three-of-five')
 if plan.get('latest_promotion')!=str(P3): e.append('latest promotion pointer drift')
 if plan.get('candidate') is not None or plan.get('candidate_status')!='not_selected' or plan.get('selection_state')!='not_selected' or plan.get('selection_authority')!='not_granted': e.append('D4-D candidate selection leakage')
 if plan.get('current_run_auto_credit') is not False or plan.get('separate_selection_required') is not True or plan.get('separate_d4_acceptance_required') is not True: e.append('D4-D separation boundary drift')
 if s1.get('evidence_id')!=E1 or s1.get('ledger_credit')!=[] or s1.get('current_run_auto_credit') is not False or s1.get('source_time_state',{}).get('d4d')!='0_of_5_unselected' or digest(root/S1)!=SHA1: e.append('first source snapshot drift')
 if s2.get('evidence_id')!=E2 or s2.get('ledger_credit')!=[] or s2.get('current_run_auto_credit') is not False or s2.get('source_time_state',{}).get('d4d')!='1_of_5_unselected' or s2.get('source_time_state',{}).get('d4wide')!='22_of_26' or digest(root/S2)!=SHA2: e.append('second source snapshot drift')
 if s3.get('evidence_id')!=E3 or s3.get('ledger_credit')!=[] or s3.get('current_run_auto_credit') is not False or s3.get('source_time_state',{}).get('d4d')!='2_of_5_unselected' or s3.get('source_time_state',{}).get('d4wide')!='23_of_26' or digest(root/S3)!=SHA3: e.append('third source snapshot drift')
 if p1.get('promotion_id')!='d4-d-open-evt-016-promotion-v1' or p1.get('credited_evidence')!=[E1] or p1.get('credit_count')!=1: e.append('first promotion history drift')
 if p2.get('promotion_id')!='d4-d-open-evt-016-tenant-contract-promotion-v1' or p2.get('credited_evidence')!=[E1,E2] or p2.get('credit_count')!=2: e.append('second promotion history drift')
 if p3.get('promotion_id')!='d4-d-open-evt-017-message-protection-promotion-v1' or p3.get('promotion_base')!='28c5274b9ec99a5866eceaec1b76459c6b4ab4ef' or p3.get('source_pr')!=112 or p3.get('source_reviewed_head')!='7d0ca86a582d2b695858c9f4437b459b21194922' or p3.get('source_merge_commit')!='28c5274b9ec99a5866eceaec1b76459c6b4ab4ef': e.append('third promotion source identity drift')
 r=p3.get('source_review',{}); w=p3.get('source_workflow',{})
 if r.get('review_id')!=5134095776 or r.get('material_threads_unresolved')!=0: e.append('third promotion review provenance drift')
 expected={'workflow_id':352456873,'run_id':34144652834,'job_id':101813930120,'artifact_id':10027183776,'artifact_digest':'sha256:58f6e78324c924c4d41d8230b4e752e7ab64af5b2a95fe54115ded1890fdf9e6'}
 for k,v in expected.items():
  if w.get(k)!=v: e.append('third promotion workflow '+k+' drift')
 if p3.get('source_manifest',{}).get('path')!=str(S3) or p3.get('source_manifest',{}).get('sha256')!=SHA3 or p3.get('credited_evidence')!=[E1,E2,E3] or p3.get('newly_credited_evidence')!=E3 or p3.get('credit_count')!=3: e.append('third promotion credit/provenance drift')
 tracks={t['track_id']:t for t in state.get('tracks',[])}; d=tracks.get('D4-D',{})
 if d.get('required_evidence')!=REQUIRED or d.get('evidence_completed')!=[E1,E2,E3] or d.get('evidence_remaining')!=REQUIRED[3:]: e.append('D4-D current state must be exactly three-of-five')
 if d.get('candidate') is not None or d.get('candidate_status')!='not_selected' or d.get('state')!='candidate_selection_open': e.append('D4-D current candidate boundary drift')
 if sum(len(t.get('evidence_completed',[])) for t in tracks.values())!=24: e.append('D4-wide current state must be exactly 24/26')
 authority=(state.get('gate_state'),state.get('d4_transport_authority'),state.get('canonical_product_implementation_authority'),state.get('wave4_implementation_authority'),state.get('production_authority'),state.get('c3_numeric_topology_authority'))
 if authority!=('scoped','selected_not_granted','not_granted','not_granted','none','not_selected'): e.append('authority boundary changed')
 for p in (p1,p2,p3):
  if p.get('selection_state')!='not_selected' or p.get('selection_authority')!='not_granted' or p.get('d4_gate_state')!='scoped' or p.get('canonical_product_implementation_authority')!='not_granted' or p.get('wave4_implementation_authority')!='not_granted' or p.get('production_authority')!='none' or p.get('c3_numeric_topology_authority')!='not_selected': e.append('promotion authority leakage')
 return e
if __name__=='__main__':
 root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd(); errors=validate(root)
 [print('D4D_LEDGER_ERROR:',x,file=sys.stderr) for x in errors]
 if errors: raise SystemExit(1)
 print('d4d_evidence_plan=PASS ledger=3_of_5 d4wide=24/26 selection=not_selected source_snapshots=0_of_5,1_of_5,2_of_5 authorities=unchanged')
