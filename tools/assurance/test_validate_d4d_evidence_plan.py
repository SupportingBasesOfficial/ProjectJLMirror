#!/usr/bin/env python3
from __future__ import annotations
import json,shutil,tempfile
from pathlib import Path
import validate_d4d_evidence_plan as target
ROOT=Path(__file__).resolve().parents[2]
def clone(root):
 for p in (target.PLAN,target.STATE,target.SELECTION,target.P1,target.P2,target.P3,target.P4,target.P5,target.S1,target.S2,target.S3,target.S4,target.S5):
  dst=root/p; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(ROOT/p,dst)
def mutate(root,p,fn):
 q=root/p; v=json.loads(q.read_text()); fn(v); q.write_text(json.dumps(v,indent=2)+'\n')
def reject(name,p,fn):
 with tempfile.TemporaryDirectory() as td:
  root=Path(td); clone(root); mutate(root,p,fn); assert target.validate(root), name+' unexpectedly accepted'; print(name+'=REJECTED')
def main():
 assert target.validate(ROOT)==[],target.validate(ROOT)
 reject('regress_fifth_credit',target.PLAN,lambda p:(p['credited_evidence'].pop(),p.__setitem__('remaining_evidence',[target.E5]),p.__setitem__('ledger_credit_state','four_of_five')))
 reject('duplicate_fifth_credit',target.PLAN,lambda p:p['credited_evidence'].append(target.E5))
 reject('regress_current_selection',target.PLAN,lambda p:(p.__setitem__('candidate',None),p.__setitem__('candidate_status','not_selected'),p.__setitem__('selection_state','not_selected'),p.__setitem__('selection_authority','not_granted'),p.__setitem__('separate_selection_required',True)))
 reject('selected_profile_drift',target.PLAN,lambda p:p['candidate'].__setitem__('trace_context_observability_only_validation_and_redaction','vendor_neutral_trace_correlation_profile'))
 reject('selection_record_binding_drift',target.PLAN,lambda p:p.__setitem__('selection_record','implementation/d4-eventing-async/other-selection-record.json'))
 reject('selection_authority_leakage',target.PLAN,lambda p:p.__setitem__('selection_authority','granted'))
 reject('premature_d4_acceptance',target.PLAN,lambda p:p.__setitem__('separate_d4_acceptance_required',False))
 reject('wrong_fifth_source_review',target.P5,lambda p:p['source_review'].__setitem__('review_id',1))
 reject('wrong_fifth_source_head',target.P5,lambda p:p.__setitem__('source_reviewed_head','0'*40))
 reject('wrong_fifth_source_merge',target.P5,lambda p:p.__setitem__('source_merge_commit','0'*40))
 reject('wrong_fifth_source_run',target.P5,lambda p:p['source_workflow'].__setitem__('run_id',1))
 reject('wrong_fifth_source_job',target.P5,lambda p:p['source_workflow'].__setitem__('job_id',1))
 reject('wrong_fifth_source_artifact',target.P5,lambda p:p['source_workflow'].__setitem__('artifact_id',1))
 reject('wrong_fifth_artifact_digest',target.P5,lambda p:p['source_workflow'].__setitem__('artifact_digest','sha256:'+'0'*64))
 reject('wrong_fifth_manifest_binding',target.P5,lambda p:p['source_manifest'].__setitem__('sha256','0'*64))
 reject('fifth_source_auto_credit',target.S5,lambda p:p.__setitem__('current_run_auto_credit',True))
 reject('rewrite_fifth_source_snapshot',target.S5,lambda p:p['source_time_state'].__setitem__('d4d','5_of_5_unselected'))
 reject('rewrite_fourth_promotion_history',target.P4,lambda p:p.__setitem__('credit_count',5))
 reject('rewrite_third_promotion_history',target.P3,lambda p:p.__setitem__('credit_count',4))
 with tempfile.TemporaryDirectory() as td:
  root=Path(td); clone(root)
  def regress(s):
   d=next(t for t in s['tracks'] if t['track_id']=='D4-D'); d['evidence_completed'].pop(); d['evidence_remaining']=[target.E5]
  mutate(root,target.STATE,regress); assert target.validate(root); print('regress_current_state_fifth_credit=REJECTED')
 with tempfile.TemporaryDirectory() as td:
  root=Path(td); clone(root); mutate(root,target.STATE,lambda s:next(t for t in s['tracks'] if t['track_id']=='D4-D')['evidence_completed'].append(target.E5)); assert target.validate(root); print('duplicate_current_state_credit=REJECTED')
 with tempfile.TemporaryDirectory() as td:
  root=Path(td); clone(root); mutate(root,target.STATE,lambda s:next(t for t in s['tracks'] if t['track_id']=='D4-D').__setitem__('candidate',None)); assert target.validate(root); print('regress_current_state_selection=REJECTED')
 print('d4d_evidence_plan_falsification=PASS cumulative_history=P1-P5-bound fifth_credit=bound source_snapshot=immutable auto_credit=blocked selected_profile=bound acceptance=separate authorities=blocked')
if __name__=='__main__': main()
