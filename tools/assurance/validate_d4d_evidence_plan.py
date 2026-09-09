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
P5=Path('implementation/d4-eventing-async/ledger-promotions/d4-d-open-evt-018-trace-context-promotion-v1.json')
S1=Path('implementation/d4-eventing-async/source-evidence/d4-d-workload-identity/source-evidence-manifest.json')
S2=Path('implementation/d4-eventing-async/source-evidence/d4-d-tenant-contract-authorization/source-evidence-manifest.json')
S3=Path('implementation/d4-eventing-async/source-evidence/d4-d-message-protection-key-authority/source-evidence-manifest.json')
S4=Path('implementation/d4-eventing-async/source-evidence/d4-d-secret-credential-exclusion/source-evidence-manifest.json')
S5=Path('implementation/d4-eventing-async/source-evidence/d4-d-trace-context-observability/source-evidence-manifest.json')
E1='workload_identity_to_broker_credential_adapter_least_privilege'; E2='tenant_and_contract_scoped_producer_consumer_authorization'; E3='message_protection_key_authority_and_historical_verifier_continuity'; E4='secret_credential_payload_exclusion_and_erasure_boundary'; E5='trace_context_observability_only_validation_and_redaction'
REQUIRED=[E1,E2,E3,E4,E5]
SHA1='005b3943f7638e136150758d10d4ec6af1c6852d4e658127c7258ff546dce0ae'; SHA2='e22455580bba6eb71877a8308d5068d0d2a8caf895f9c1ce2c3aeadb724a7025'; SHA3='8d33a50b8748382586aa5b13e2e7427a57b66d8319066acf09f0e09a4ca31c35'; SHA4='5639d4a5b70d89fd10c874689cd87346ca4742e9474763fd89bf809959664da1'; SHA5='2b80305593ebc06d10e4ae7862411518cdd250f7f35d21b52c8a2322950f1e49'
def load(root,p): return json.loads((root/p).read_text())
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def authority_ok(p):
 return p.get('selection_state')=='not_selected' and p.get('selection_authority')=='not_granted' and p.get('d4_gate_state')=='scoped' and p.get('d4_transport_authority')=='selected_not_granted' and p.get('canonical_product_implementation_authority')=='not_granted' and p.get('wave4_implementation_authority')=='not_granted' and p.get('production_authority')=='none' and p.get('c3_numeric_topology_authority')=='not_selected'
def validate(root):
 e=[]; plan=load(root,PLAN); state=load(root,STATE); p1=load(root,P1); p2=load(root,P2); p3=load(root,P3); p4=load(root,P4); p5=load(root,P5); s1=load(root,S1); s2=load(root,S2); s3=load(root,S3); s4=load(root,S4); s5=load(root,S5)
 if plan.get('credited_evidence')!=REQUIRED or plan.get('remaining_evidence')!=[] or plan.get('ledger_credit_state')!='five_of_five': e.append('D4-D ledger must be exactly five-of-five')
 if plan.get('latest_promotion')!=str(P5): e.append('latest promotion pointer drift')
 if plan.get('candidate') is not None or plan.get('candidate_status')!='not_selected' or plan.get('selection_state')!='not_selected' or plan.get('selection_authority')!='not_granted': e.append('D4-D candidate selection leakage')
 if plan.get('current_run_auto_credit') is not False or plan.get('separate_selection_required') is not True or plan.get('separate_d4_acceptance_required') is not True: e.append('D4-D separation boundary drift')
 snapshots=[
  (s1,E1,'0_of_5_unselected',None,SHA1,'first'),
  (s2,E2,'1_of_5_unselected','22_of_26',SHA2,'second'),
  (s3,E3,'2_of_5_unselected','23_of_26',SHA3,'third'),
  (s4,E4,'3_of_5_unselected','24_of_26',SHA4,'fourth'),
  (s5,E5,'4_of_5_unselected','25_of_26',SHA5,'fifth'),
 ]
 for s,eid,d4d,d4wide,sha,label in snapshots:
  if s.get('evidence_id')!=eid or s.get('ledger_credit')!=[] or s.get('current_run_auto_credit') is not False or s.get('source_time_state',{}).get('d4d')!=d4d or (d4wide is not None and s.get('source_time_state',{}).get('d4wide')!=d4wide) or digest(root/{'first':S1,'second':S2,'third':S3,'fourth':S4,'fifth':S5}[label])!=sha: e.append(label+' source snapshot drift')
 lineage=s4.get('correction_lineage',{})
 if lineage.get('supersedes_source_pr')!=114 or lineage.get('supersedes_source_head')!='c8d49ccf05113f0274287578bbc6965d220a677d' or lineage.get('superseded_codex_review_id')!=5134974949 or lineage.get('promotion_eligible_source_must_be_this_corrected_lineage_or_later') is not True: e.append('fourth corrected source lineage drift')
 if p1.get('promotion_id')!='d4-d-open-evt-016-promotion-v1' or p1.get('credited_evidence')!=[E1] or p1.get('credit_count')!=1: e.append('first promotion history drift')
 if p2.get('promotion_id')!='d4-d-open-evt-016-tenant-contract-promotion-v1' or p2.get('credited_evidence')!=[E1,E2] or p2.get('credit_count')!=2: e.append('second promotion history drift')
 if p3.get('promotion_id')!='d4-d-open-evt-017-message-protection-promotion-v1' or p3.get('promotion_base')!='28c5274b9ec99a5866eceaec1b76459c6b4ab4ef' or p3.get('source_pr')!=112 or p3.get('source_reviewed_head')!='7d0ca86a582d2b695858c9f4437b459b21194922' or p3.get('source_merge_commit')!='28c5274b9ec99a5866eceaec1b76459c6b4ab4ef': e.append('third promotion source identity drift')
 r3=p3.get('source_review',{}); w3=p3.get('source_workflow',{})
 if r3.get('review_id')!=5134095776 or r3.get('material_threads_unresolved')!=0: e.append('third promotion review provenance drift')
 expected3={'workflow_id':352456873,'workflow_path':'.github/workflows/d4-d-message-protection-source-evidence.yml','workflow_event':'pull_request','source_head_branch':'d4d/open-evt-017-message-protection-source','run_id':34144652834,'run_attempt':1,'job_id':101813930120,'job_name':'D4-D message protection source evidence','artifact_id':10027183776,'artifact_name':'d4-d-message-protection-source-7d0ca86a582d2b695858c9f4437b459b21194922-34144652834-1','artifact_digest':'sha256:58f6e78324c924c4d41d8230b4e752e7ab64af5b2a95fe54115ded1890fdf9e6'}
 for k,v in expected3.items():
  if w3.get(k)!=v: e.append('third promotion workflow '+k+' drift')
 if p3.get('source_manifest',{}).get('path')!=str(S3) or p3.get('source_manifest',{}).get('sha256')!=SHA3 or p3.get('credited_evidence')!=[E1,E2,E3] or p3.get('newly_credited_evidence')!=E3 or p3.get('credit_count')!=3: e.append('third promotion credit/provenance drift')
 if p4.get('promotion_id')!='d4-d-open-evt-017-secret-exclusion-promotion-v1' or p4.get('promotion_base')!='c9cf2a4623b209c27283efb91d7c743efada71b6' or p4.get('source_pr')!=115 or p4.get('source_reviewed_head')!='31523e7d8d388af3d4f6a6adb309d4363a014884' or p4.get('source_merge_commit')!='c9cf2a4623b209c27283efb91d7c743efada71b6': e.append('fourth promotion source identity drift')
 r4=p4.get('source_review',{}); w4=p4.get('source_workflow',{})
 if r4.get('review_id')!=5144105945 or r4.get('codex_clean_comment_id')!=5587879590 or r4.get('material_threads_unresolved')!=0: e.append('fourth promotion review provenance drift')
 expected4={'workflow_id':352564948,'workflow_path':'.github/workflows/d4-d-secret-exclusion-source-evidence.yml','workflow_event':'pull_request','source_head_branch':'d4d/open-evt-017-secret-exclusion-correction-source','run_id':34246165232,'run_attempt':1,'job_id':102128582025,'job_name':'D4-D secret exclusion source evidence','artifact_id':10064062867,'artifact_name':'d4-d-secret-exclusion-source-31523e7d8d388af3d4f6a6adb309d4363a014884-34246165232-1','artifact_digest':'sha256:b06e805a0940c6407e3d0687620e4e366f5283949742f069c2c245a679c636ea'}
 for k,v in expected4.items():
  if w4.get(k)!=v: e.append('fourth promotion workflow '+k+' drift')
 if p4.get('source_manifest',{}).get('path')!=str(S4) or p4.get('source_manifest',{}).get('sha256')!=SHA4 or p4.get('credited_evidence')!=[E1,E2,E3,E4] or p4.get('newly_credited_evidence')!=E4 or p4.get('credit_count')!=4: e.append('fourth promotion credit/provenance drift')
 if p5.get('promotion_id')!='d4-d-open-evt-018-trace-context-promotion-v1' or p5.get('promotion_base')!='5f5e231ae72f13f406a1420497bb7956e6c3cdf9' or p5.get('source_pr')!=118 or p5.get('source_reviewed_head')!='7522036e91582c8aeb95c34097be497d0e1c7ca1' or p5.get('source_merge_commit')!='5f5e231ae72f13f406a1420497bb7956e6c3cdf9': e.append('fifth promotion source identity drift')
 r5=p5.get('source_review',{}); w5=p5.get('source_workflow',{})
 if r5.get('review_id')!=5149543760 or r5.get('material_threads_unresolved')!=0: e.append('fifth promotion review provenance drift')
 expected5={'workflow_id':353438165,'workflow_path':'.github/workflows/d4-d-trace-context-source-evidence.yml','workflow_event':'pull_request','source_head_branch':'d4d/open-evt-018-trace-context-source','run_id':34308388920,'run_attempt':1,'job_id':102329740568,'job_name':'D4-D trace context source evidence','artifact_id':10087468670,'artifact_name':'d4-d-trace-context-source-7522036e91582c8aeb95c34097be497d0e1c7ca1-34308388920-1','artifact_digest':'sha256:9d5fc172a8324372ba37a5bae0a51ffdab9e5c16bc6208a195659148b80a8696'}
 for k,v in expected5.items():
  if w5.get(k)!=v: e.append('fifth promotion workflow '+k+' drift')
 if p5.get('source_manifest',{}).get('path')!=str(S5) or p5.get('source_manifest',{}).get('sha256')!=SHA5 or p5.get('credited_evidence')!=REQUIRED or p5.get('newly_credited_evidence')!=E5 or p5.get('credit_count')!=5: e.append('fifth promotion credit/provenance drift')
 tracks={t['track_id']:t for t in state.get('tracks',[])}; d=tracks.get('D4-D',{})
 if d.get('required_evidence')!=REQUIRED or d.get('evidence_completed')!=REQUIRED or d.get('evidence_remaining')!=[]: e.append('D4-D current state must be exactly five-of-five')
 if d.get('candidate') is not None or d.get('candidate_status')!='not_selected' or d.get('state')!='candidate_selection_open': e.append('D4-D current candidate boundary drift')
 if sum(len(t.get('evidence_completed',[])) for t in tracks.values())!=26: e.append('D4-wide current state must be exactly 26/26')
 authority=(state.get('gate_state'),state.get('d4_transport_authority'),state.get('canonical_product_implementation_authority'),state.get('wave4_implementation_authority'),state.get('production_authority'),state.get('c3_numeric_topology_authority'))
 if authority!=('scoped','selected_not_granted','not_granted','not_granted','none','not_selected'): e.append('authority boundary changed')
 for p in (p1,p2,p3,p4,p5):
  if not authority_ok(p): e.append('promotion authority leakage')
 return e
if __name__=='__main__':
 root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd(); errors=validate(root)
 [print('D4D_LEDGER_ERROR:',x,file=sys.stderr) for x in errors]
 if errors: raise SystemExit(1)
 print('d4d_evidence_plan=PASS ledger=5_of_5 d4wide=26/26 selection=not_selected source_snapshots=0_of_5,1_of_5,2_of_5,3_of_5,4_of_5 promotion_chain=P1-P5-bound authorities=unchanged')
