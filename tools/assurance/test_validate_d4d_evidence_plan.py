#!/usr/bin/env python3
from __future__ import annotations
import json,shutil,tempfile
from pathlib import Path
import validate_d4d_evidence_plan as target
ROOT=Path(__file__).resolve().parents[2]
def clone(root):
 for p in (target.PLAN,target.STATE,target.P1,target.P2,target.P3,target.S1,target.S2,target.S3):
  dst=root/p; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(ROOT/p,dst)
def mutate(root,p,fn):
 q=root/p; v=json.loads(q.read_text()); fn(v); q.write_text(json.dumps(v,indent=2)+'\n')
def reject(name,p,fn):
 with tempfile.TemporaryDirectory() as td:
  root=Path(td); clone(root); mutate(root,p,fn); assert target.validate(root), name+' unexpectedly accepted'; print(name+'=REJECTED')
def main():
 assert target.validate(ROOT)==[],target.validate(ROOT)
 reject('regress_third_credit',target.PLAN,lambda p:(p['credited_evidence'].pop(),p.__setitem__('remaining_evidence',list(target.REQUIRED[2:])),p.__setitem__('ledger_credit_state','two_of_five')))
 reject('duplicate_third_credit',target.PLAN,lambda p:p['credited_evidence'].append(target.E3))
 reject('silent_candidate_selection',target.PLAN,lambda p:p.__setitem__('candidate','implicit-kms-profile'))
 reject('selection_authority_leakage',target.PLAN,lambda p:p.__setitem__('selection_authority','granted'))
 reject('wrong_third_source_review',target.P3,lambda p:p['source_review'].__setitem__('review_id',1))
 reject('wrong_third_source_artifact',target.P3,lambda p:p['source_workflow'].__setitem__('artifact_id',1))
 reject('promotion_fourth_credit',target.P3,lambda p:(p['credited_evidence'].append(target.REQUIRED[3]),p.__setitem__('credit_count',4)))
 reject('third_source_auto_credit',target.S3,lambda p:p.__setitem__('current_run_auto_credit',True))
 reject('second_promotion_history_rewrite',target.P2,lambda p:p.__setitem__('credit_count',3))
 with tempfile.TemporaryDirectory() as td:
  root=Path(td); clone(root); mutate(root,target.STATE,lambda s:next(t for t in s['tracks'] if t['track_id']=='D4-D')['evidence_completed'].append(target.E3)); assert target.validate(root); print('duplicate_current_state_credit=REJECTED')
 print('d4d_evidence_plan_falsification=PASS cumulative_history=bound third_credit=bound fourth_credit=blocked auto_credit=blocked selection=blocked')
if __name__=='__main__': main()
