#!/usr/bin/env python3
from __future__ import annotations
import json,shutil,tempfile
from pathlib import Path
import validate_d4d_evidence_plan as target
ROOT=Path(__file__).resolve().parents[2]
def clone(root):
 for p in (target.PLAN,target.STATE,target.P1,target.P2,target.P3,target.P4,target.S1,target.S2,target.S3,target.S4):
  dst=root/p; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(ROOT/p,dst)
def mutate(root,p,fn):
 q=root/p; v=json.loads(q.read_text()); fn(v); q.write_text(json.dumps(v,indent=2)+'\n')
def reject(name,p,fn):
 with tempfile.TemporaryDirectory() as td:
  root=Path(td); clone(root); mutate(root,p,fn); assert target.validate(root), name+' unexpectedly accepted'; print(name+'=REJECTED')
def main():
 assert target.validate(ROOT)==[],target.validate(ROOT)
 reject('regress_fourth_credit',target.PLAN,lambda p:(p['credited_evidence'].pop(),p.__setitem__('remaining_evidence',list(target.REQUIRED[3:])),p.__setitem__('ledger_credit_state','three_of_five')))
 reject('duplicate_fourth_credit',target.PLAN,lambda p:p['credited_evidence'].append(target.E4))
 reject('silent_candidate_selection',target.PLAN,lambda p:p.__setitem__('candidate','implicit-secret-profile'))
 reject('selection_authority_leakage',target.PLAN,lambda p:p.__setitem__('selection_authority','granted'))
 reject('wrong_fourth_source_review',target.P4,lambda p:p['source_review'].__setitem__('review_id',1))
 reject('wrong_codex_clean_comment',target.P4,lambda p:p['source_review'].__setitem__('codex_clean_comment_id',1))
 reject('wrong_fourth_source_artifact',target.P4,lambda p:p['source_workflow'].__setitem__('artifact_id',1))
 reject('promotion_fifth_credit',target.P4,lambda p:(p['credited_evidence'].append(target.E5),p.__setitem__('credit_count',5)))
 reject('fourth_source_auto_credit',target.S4,lambda p:p.__setitem__('current_run_auto_credit',True))
 reject('fourth_source_lineage_rewrite',target.S4,lambda p:p['correction_lineage'].__setitem__('supersedes_source_pr',113))
 reject('third_promotion_history_rewrite',target.P3,lambda p:p.__setitem__('credit_count',4))
 with tempfile.TemporaryDirectory() as td:
  root=Path(td); clone(root); mutate(root,target.STATE,lambda s:next(t for t in s['tracks'] if t['track_id']=='D4-D')['evidence_completed'].append(target.E4)); assert target.validate(root); print('duplicate_current_state_credit=REJECTED')
 print('d4d_evidence_plan_falsification=PASS cumulative_history=bound fourth_credit=bound fifth_credit=blocked auto_credit=blocked corrected_lineage=bound selection=blocked')
if __name__=='__main__': main()
