#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
PLAN=Path('implementation/d4-eventing-async/d4-d-evidence-plan.json')
STATE=Path('implementation/d4-eventing-async/state-manifest.json')
SELECTION=Path('implementation/d4-eventing-async/d4-d-selection-record.json')
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
CURRENT_PROFILE={'workload_identity_to_broker_credential_adapter':'derived_short_lived_broker_native_credential_adapter','tenant_and_contract_scoped_producer_consumer_authorization':'broker_acl_projection_adapter','message_protection_key_authority_and_historical_verifier_continuity':'kms_backed_envelope_or_transport_protection_profile','secret_credential_payload_exclusion_and_erasure_boundary':'reference_only_secret_authority_profile','trace_context_observability_only_validation_and_redaction':'w3c_trace_context_bounded_profile'}
SHA1='005b3943f7638e136150758d10d4ec6af1c6852d4e658127c7258ff546dce0ae'; SHA2='e22455580bba6eb71877a8308d5068d0d2a8caf895f9c1ce2c3aeadb724a7025'; SHA3='8d33a50b8748382586aa5b13e2e7427a57b66d8319066acf09f0e09a4ca31c35'; SHA4='5639d4a5b70d89fd10c874689cd87346ca4742e9474763fd89bf809959664da1'; SHA5='2b80305593ebc06d10e4ae7862411518cdd250f7f35d21b52c8a2322950f1e49'
def load(root,p): return json.loads((root/p).read_text())
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
AUTHORITY_EXPECTED={
 'selection_state':'not_selected','selection_authority':'not_granted','d4_gate_state':'scoped','d4_transport_authority':'selected_not_granted','canonical_product_implementation_authority':'not_granted','wave4_implementation_authority':'not_granted','production_authority':'none','c3_numeric_topology_authority':'not_selected','separate_selection_required':True,'separate_d4_acceptance_required':True,
}
def authority_ok(p): return all(p.get(k)==v for k,v in AUTHORITY_EXPECTED.items())
PROMOTIONS=[
 (P1,{
  'schema_version':1,'promotion_id':'d4-d-open-evt-016-promotion-v1','gate_id':'D4','track_id':'D4-D','promotion_base':'491c99784637d20189034807a1722371a90a54ee','source_pr':108,'source_reviewed_head':'4442b4f2ca398eb92833c89abecc835a47598b59','source_merge_commit':'491c99784637d20189034807a1722371a90a54ee',
  'source_review':{'review_id':5127223369,'review_mode':'independent_exact_head_adversarial_clean_after_exact_head_ci','material_threads_unresolved':0},
  'source_workflow':{'workflow_id':351889856,'workflow_path':'.github/workflows/d4-d-workload-identity-source-evidence.yml','workflow_event':'pull_request','source_head_branch':'d4d/open-evt-016-workload-identity-source','run_id':34071132161,'run_attempt':1,'job_id':101588568591,'job_name':'D4-D workload identity broker adapter source evidence','artifact_id':10000484264,'artifact_name':'d4-d-workload-identity-source-4442b4f2ca398eb92833c89abecc835a47598b59-34071132161-1','artifact_digest':'sha256:abce705d64376dc29c61cf752b328a871bf5c01d11e26911f8903619ad53bc20'},
  'source_manifest':{'path':S1.as_posix(),'sha256':SHA1},'credited_evidence':[E1],'newly_credited_evidence':None,'credit_count':1}),
 (P2,{
  'schema_version':1,'promotion_id':'d4-d-open-evt-016-tenant-contract-promotion-v1','gate_id':'D4','track_id':'D4-D','promotion_base':'43cc94d3052af1c7bbc178b4ea4c75e04526c115','source_pr':110,'source_reviewed_head':'42c11d29b4a221317149923a9f4dc394bdede21c','source_merge_commit':'43cc94d3052af1c7bbc178b4ea4c75e04526c115',
  'source_review':{'review_id':5127897709,'review_mode':'independent_exact_head_adversarial_clean_after_exact_head_ci','material_threads_unresolved':0},
  'source_workflow':{'workflow_id':351965210,'workflow_path':'.github/workflows/d4-d-tenant-contract-authorization-source-evidence.yml','workflow_event':'pull_request','source_head_branch':'d4d/open-evt-016-tenant-contract-authorization-source','run_id':34080846886,'run_attempt':1,'job_id':101615681837,'job_name':'D4-D tenant contract authorization source evidence','artifact_id':10003627002,'artifact_name':'d4-d-tenant-contract-authorization-source-42c11d29b4a221317149923a9f4dc394bdede21c-34080846886-1','artifact_digest':'sha256:a776b98e6291fda879d4ad5597b3498d29802843d70cabfdb0ff455623f45bbe'},
  'source_manifest':{'path':S2.as_posix(),'sha256':SHA2},'credited_evidence':[E1,E2],'newly_credited_evidence':E2,'credit_count':2}),
 (P3,{
  'schema_version':1,'promotion_id':'d4-d-open-evt-017-message-protection-promotion-v1','gate_id':'D4','track_id':'D4-D','promotion_base':'28c5274b9ec99a5866eceaec1b76459c6b4ab4ef','source_pr':112,'source_reviewed_head':'7d0ca86a582d2b695858c9f4437b459b21194922','source_merge_commit':'28c5274b9ec99a5866eceaec1b76459c6b4ab4ef',
  'source_review':{'review_id':5134095776,'review_mode':'codex_exact_head_review_after_post_ready_clean_and_panorama','material_threads_unresolved':0},
  'source_workflow':{'workflow_id':352456873,'workflow_path':'.github/workflows/d4-d-message-protection-source-evidence.yml','workflow_event':'pull_request','source_head_branch':'d4d/open-evt-017-message-protection-source','run_id':34144652834,'run_attempt':1,'job_id':101813930120,'job_name':'D4-D message protection source evidence','artifact_id':10027183776,'artifact_name':'d4-d-message-protection-source-7d0ca86a582d2b695858c9f4437b459b21194922-34144652834-1','artifact_digest':'sha256:58f6e78324c924c4d41d8230b4e752e7ab64af5b2a95fe54115ded1890fdf9e6'},
  'source_manifest':{'path':S3.as_posix(),'sha256':SHA3},'credited_evidence':[E1,E2,E3],'newly_credited_evidence':E3,'credit_count':3}),
 (P4,{
  'schema_version':1,'promotion_id':'d4-d-open-evt-017-secret-exclusion-promotion-v1','gate_id':'D4','track_id':'D4-D','promotion_base':'c9cf2a4623b209c27283efb91d7c743efada71b6','source_pr':115,'source_reviewed_head':'31523e7d8d388af3d4f6a6adb309d4363a014884','source_merge_commit':'c9cf2a4623b209c27283efb91d7c743efada71b6',
  'source_review':{'review_id':5144105945,'codex_clean_comment_id':5587879590,'review_mode':'codex_exact_head_clean_issue_comment_plus_panorama_comment_review','material_threads_unresolved':0},
  'source_workflow':{'workflow_id':352564948,'workflow_path':'.github/workflows/d4-d-secret-exclusion-source-evidence.yml','workflow_event':'pull_request','source_head_branch':'d4d/open-evt-017-secret-exclusion-correction-source','run_id':34246165232,'run_attempt':1,'job_id':102128582025,'job_name':'D4-D secret exclusion source evidence','artifact_id':10064062867,'artifact_name':'d4-d-secret-exclusion-source-31523e7d8d388af3d4f6a6adb309d4363a014884-34246165232-1','artifact_digest':'sha256:b06e805a0940c6407e3d0687620e4e366f5283949742f069c2c245a679c636ea'},
  'source_manifest':{'path':S4.as_posix(),'sha256':SHA4},'credited_evidence':[E1,E2,E3,E4],'newly_credited_evidence':E4,'credit_count':4}),
 (P5,{
  'schema_version':1,'promotion_id':'d4-d-open-evt-018-trace-context-promotion-v1','gate_id':'D4','track_id':'D4-D','promotion_base':'5f5e231ae72f13f406a1420497bb7956e6c3cdf9','source_pr':118,'source_reviewed_head':'7522036e91582c8aeb95c34097be497d0e1c7ca1','source_merge_commit':'5f5e231ae72f13f406a1420497bb7956e6c3cdf9',
  'source_review':{'review_id':5149543760,'review_mode':'exact_head_assurance_baseline_v1_clean_after_external_red_team_remediation','material_threads_unresolved':0},
  'source_workflow':{'workflow_id':353438165,'workflow_path':'.github/workflows/d4-d-trace-context-source-evidence.yml','workflow_event':'pull_request','source_head_branch':'d4d/open-evt-018-trace-context-source','run_id':34308388920,'run_attempt':1,'job_id':102329740568,'job_name':'D4-D trace context source evidence','artifact_id':10087468670,'artifact_name':'d4-d-trace-context-source-7522036e91582c8aeb95c34097be497d0e1c7ca1-34308388920-1','artifact_digest':'sha256:9d5fc172a8324372ba37a5bae0a51ffdab9e5c16bc6208a195659148b80a8696'},
  'source_manifest':{'path':S5.as_posix(),'sha256':SHA5},'credited_evidence':REQUIRED,'newly_credited_evidence':E5,'credit_count':5}),
]
def expected_promotion_keys(expected):
 keys=set(expected)|set(AUTHORITY_EXPECTED)
 if expected['newly_credited_evidence'] is None: keys.remove('newly_credited_evidence')
 return keys
def promotion_identity_errors(label,p,expected):
 errors=[]
 if set(p)!=expected_promotion_keys(expected): errors.append(f'{label} promotion top-level schema drift')
 for field in ('schema_version','promotion_id','gate_id','track_id','promotion_base','source_pr','source_reviewed_head','source_merge_commit'):
  if p.get(field)!=expected[field]: errors.append(f'{label} promotion {field} drift')
 if p.get('source_review')!=expected['source_review']: errors.append(f'{label} promotion source review envelope drift')
 if p.get('source_workflow')!=expected['source_workflow']: errors.append(f'{label} promotion source workflow envelope drift')
 if p.get('source_manifest')!=expected['source_manifest']: errors.append(f'{label} promotion source manifest envelope drift')
 if p.get('credited_evidence')!=expected['credited_evidence'] or p.get('credit_count')!=expected['credit_count']: errors.append(f'{label} promotion credit envelope drift')
 if expected['newly_credited_evidence'] is None:
  if 'newly_credited_evidence' in p: errors.append(f'{label} promotion unexpected newly credited evidence field')
 elif p.get('newly_credited_evidence')!=expected['newly_credited_evidence']: errors.append(f'{label} promotion newly credited evidence drift')
 if not authority_ok(p): errors.append(f'{label} promotion authority/separation leakage')
 return errors
def validate(root):
 e=[]; plan=load(root,PLAN); state=load(root,STATE); promotions=[load(root,p) for p,_ in PROMOTIONS]; s1=load(root,S1); s2=load(root,S2); s3=load(root,S3); s4=load(root,S4); s5=load(root,S5)
 if plan.get('credited_evidence')!=REQUIRED or plan.get('remaining_evidence')!=[] or plan.get('ledger_credit_state')!='five_of_five': e.append('D4-D ledger must be exactly five-of-five')
 if plan.get('latest_promotion')!=P5.as_posix(): e.append('latest promotion pointer drift')
 if plan.get('candidate')!=CURRENT_PROFILE or plan.get('candidate_status')!='selected_c2_security_profile' or plan.get('selection_state')!='selected' or plan.get('selection_authority')!='selection_record' or plan.get('selection_record')!=SELECTION.as_posix(): e.append('D4-D current selected profile drift')
 if plan.get('current_run_auto_credit') is not False or plan.get('separate_selection_required') is not False or plan.get('separate_d4_acceptance_required') is not True: e.append('D4-D current selection/acceptance separation drift')
 snapshots=[(s1,E1,'0_of_5_unselected',None,SHA1,'first',S1),(s2,E2,'1_of_5_unselected','22_of_26',SHA2,'second',S2),(s3,E3,'2_of_5_unselected','23_of_26',SHA3,'third',S3),(s4,E4,'3_of_5_unselected','24_of_26',SHA4,'fourth',S4),(s5,E5,'4_of_5_unselected','25_of_26',SHA5,'fifth',S5)]
 for s,eid,d4d,d4wide,sha,label,path in snapshots:
  if s.get('evidence_id')!=eid or s.get('ledger_credit')!=[] or s.get('current_run_auto_credit') is not False or s.get('source_time_state',{}).get('d4d')!=d4d or (d4wide is not None and s.get('source_time_state',{}).get('d4wide')!=d4wide) or digest(root/path)!=sha: e.append(label+' source snapshot drift')
 lineage=s4.get('correction_lineage',{})
 if lineage.get('supersedes_source_pr')!=114 or lineage.get('supersedes_source_head')!='c8d49ccf05113f0274287578bbc6965d220a677d' or lineage.get('superseded_codex_review_id')!=5134974949 or lineage.get('promotion_eligible_source_must_be_this_corrected_lineage_or_later') is not True: e.append('fourth corrected source lineage drift')
 for index,((_,expected),promotion) in enumerate(zip(PROMOTIONS,promotions),start=1): e.extend(promotion_identity_errors(f'P{index}',promotion,expected))
 tracks={t['track_id']:t for t in state.get('tracks',[])}; d=tracks.get('D4-D',{})
 if d.get('required_evidence')!=REQUIRED or d.get('evidence_completed')!=REQUIRED or d.get('evidence_remaining')!=[]: e.append('D4-D current state must be exactly five-of-five')
 if d.get('candidate')!=CURRENT_PROFILE or d.get('candidate_status')!='selected_c2_security_profile' or d.get('state')!='selected_candidate': e.append('D4-D current selected profile state drift')
 if sum(len(t.get('evidence_completed',[])) for t in tracks.values())!=26: e.append('D4-wide current state must be exactly 26/26')
 authority=(state.get('gate_state'),state.get('d4_transport_authority'),state.get('canonical_product_implementation_authority'),state.get('wave4_implementation_authority'),state.get('production_authority'),state.get('c3_numeric_topology_authority'))
 if authority!=('scoped','selected_not_granted','not_granted','not_granted','none','not_selected'): e.append('authority boundary changed')
 return e
if __name__=='__main__':
 root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path.cwd(); errors=validate(root)
 [print('D4D_LEDGER_ERROR:',x,file=sys.stderr) for x in errors]
 if errors: raise SystemExit(1)
 print('d4d_evidence_plan=PASS ledger=5_of_5 d4wide=26/26 selection=selected_c2_security_profile source_snapshots=0_of_5,1_of_5,2_of_5,3_of_5,4_of_5 promotion_chain=P1-P5-closed-complete-identity-bound authorities=unchanged acceptance=separate')