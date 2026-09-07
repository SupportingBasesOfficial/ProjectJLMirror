#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
PLAN=Path('implementation/d4-eventing-async/d4-d-evidence-plan.json')
STATE=Path('implementation/d4-eventing-async/state-manifest.json')
P1=Path('implementation/d4-eventing-async/ledger-promotions/d4-d-open-evt-016-promotion-v1.json')
P2=Path('implementation/d4-eventing-async/ledger-promotions/d4-d-open-evt-016-tenant-contract-promotion-v1.json')
S1=Path('implementation/d4-eventing-async/source-evidence/d4-d-workload-identity/source-evidence-manifest.json')
S2=Path('implementation/d4-eventing-async/source-evidence/d4-d-tenant-contract-authorization/source-evidence-manifest.json')
E1='workload_identity_to_broker_credential_adapter_least_privilege'; E2='tenant_and_contract_scoped_producer_consumer_authorization'
REQUIRED=[E1,E2,'message_protection_key_authority_and_historical_verifier_continuity','secret_credential_payload_exclusion_and_erasure_boundary','trace_context_observability_only_validation_and_redaction']
SHA1='005b3943f7638e136150758d10d4ec6af1c6852d4e658127c7258ff546dce0ae'; SHA2='e22455580bba6eb71877a8308d5068d0d2a8caf895f9c1ce2c3aeadb724a7025'
def load(root,p): return json.loads((root/p).read_text())
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def validate(root):
 e=[]; plan=load(root,PLAN); state=load(root,STATE); p1=load(root,P1); p2=load(root,P2); s1=load(root,S1); s2=load(root,S2)
 if plan.get('credited_evidence')!=[E1,E2] or plan.get('remaining_evidence')!=REQUIRED[2:] or plan.get('ledger_credit_state')!='two_of_five': e.append('D4-D ledger must be exactly two-of-five')
 if plan.get('latest_promotion')!=str(P2): e.append('latest promotion pointer drift')
 if plan.get('candidate') is not None or plan.get('candidate_status')!='not_selected' or plan.get('selection_state')!='not_selected' or plan.get('selection_authority')!='not_granted': e.append('D4-D candidate selection leakage')
 if plan.get('current_run_auto_credit') is not False or plan.get('separate_selection_required') is not True or plan.get('separate_d4_acceptance_required') is not True: e.append('D4-D separation boundary drift')
 if s1.get('evidence_id')!=E1 or s1.get('ledger_credit')!=[] or s1.get('current_run_auto_credit') is not False or s1.get('source_time_state',{}).get('d4d')!='0_of_5_unselected' or digest(root/S1)!=SHA1: e.append('first source snapshot drift')
 if s2.get('evidence_id')!=E2 or s2.get('ledger_credit')!=[] or s2.get('current_run_auto_credit') is not False or s2.get('source_time_state',{}).get('d4d')!='1_of_5_unselected' or s2.get('source_time_state',{}).get('d4wide')!='22_of_26' or digest(root/S2)!=SHA2: e.append('second source snapshot drift')
 if p1.get('promotion_id')!='d4-d-open-evt-016-promotion-v1' or p1.get('credited_evidence')!=[E1] or p1.get('credit_count')!=1: e.append('first promotion history drift')
 if p2.get('promotion_id')!='d4-d-open-evt-016-tenant-contract-promotion-v1' or p2.get('promotion_base')!='43cc94d3052af1c7bbc178b4ea4c75e04526c115' or p2.get('source_pr')!=110 or p2.get('source_reviewed_head')!='42c11d29b4a221317149923a9f4dc394bdede21c' or p2.get('source_merge_commit')!='43cc94d3052af1c7bbc178b4ea4c75e04526c115': e.append('second promotion source identity drift')
 r=p2.get('source_review',{}); w=p2.get('source_workflow',{})
 if r.get('review_id')!=5127897709 or r.get('material_threads_unresolved')!=0: e.append('second promotion review provenance drift')
 expected={'workflow_id':351965210,'run_id':34080846886,'job_id':101615681837,'artifact_id':10003627002,'artifact_digest':'sha256:a776b98e6291fda879d4ad5597b3498d29802843d70cabfdb0ff455623f45bbe'}
 for k,v in expected.items():
  if w.get(k)!=v: e.append('second promotion workflow '+k+' drift')
 if p2.get('source_manifest',{}).get('path')!=str(S2) or p2.get('source_manifest',{}).get('sha256')!=SHA2 or p2.get('credited_evidence')!=[E1,E2] or p2.get('newly_credited_evidence')!=E2 or p2.get('credit_count')!=2: e.append('second promotion credit/provenance drift')
 tracks={t['track_id']:t for t in state.get('tracks',[])}; d=tracks.get('D4-D',{})
 if d.get('required_evidence')!=REQUIRED or d.get('evidence_completed')!=[E1,E2] or d.get('evidence_remaining')!=REQUIRED[2:]: e.append('D4-D current state must be exactly two-of-five')
 if d.get('candidate') is not None or d.get('candidate_status')!='not_selected' or d.get('state')!='candidate_selection_open': e.append('D4-D current candidate boundary drift')
 if sum(len(t.get('evidence_completed',[])) for t in tracks.values())!=23: e.append('D4-wide current state must be exactly 23/26')
 authority=(state.get('gate_state'),state.get('d4_transport_authority'),state.get('canonical_product_implementation_authority'),state.get('wave4_implementation_authority'),state.get('production_authority'),state.get('c3_numeric_topology_authority'))
 if authority!=('scoped','selected_not_granted','not_granted','not_granted','none','not_selected'): e.append('authority boundary changed')
 for p in (p1,p2):
  if p.get('selection_state')!='not_selected' or p.get('selection_authority')!='not_granted' or p.get('d4_gate_state')!='scoped' or p.get('canonical_product_implementation_authority')!='not_granted' or p.get('wave4_implementation_authority')!='not_granted' or p.get('production_authority')!='none' or p.get('c3_numeric_topology_authority')!='not_selected': e.append('promotion authority leakage')
 return e
if __name__=='__main__':
 root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd(); errors=validate(root)
 [print('D4D_LEDGER_ERROR:',x,file=sys.stderr) for x in errors]
 if errors: raise SystemExit(1)
 print('d4d_evidence_plan=PASS ledger=2_of_5 d4wide=23/26 selection=not_selected source_snapshots=0_of_5,1_of_5 authorities=unchanged')
