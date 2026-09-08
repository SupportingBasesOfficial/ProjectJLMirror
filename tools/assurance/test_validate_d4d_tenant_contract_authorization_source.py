#!/usr/bin/env python3
from __future__ import annotations
import json,tempfile
from pathlib import Path
import validate_d4d_tenant_contract_authorization_source as v
ROOT=Path(__file__).resolve().parents[2]
def clone(tmp):
 for p in [v.MANIFEST,v.STATE,v.PLAN]:
  dst=tmp/p; dst.parent.mkdir(parents=True,exist_ok=True); dst.write_text((ROOT/p).read_text())
def mutate_and_expect_failure(mutator):
 with tempfile.TemporaryDirectory() as td:
  root=Path(td); clone(root); mutator(root); assert v.validate(root),'mutation unexpectedly accepted'
def mutate_json(root,path,fn):
 p=root/path; d=json.loads(p.read_text()); fn(d); p.write_text(json.dumps(d))
def main():
 assert not v.validate(ROOT)
 mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d.__setitem__('current_run_auto_credit',True)))
 mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d.__setitem__('ledger_credit',[v.EXPECTED_ID])))
 mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d.__setitem__('broker_authorization_authority','broker_acl_is_authority')))
 mutate_and_expect_failure(lambda r:mutate_json(r,v.PLAN,lambda d:d['axes'][v.EXPECTED_AXIS]['must_prove'].pop()))
 def regress_fourth(r):
  def fn(d):
   t=d['tracks'][3]; fourth=v.FOURTH; t['evidence_completed'].remove(fourth); t['evidence_remaining'].insert(0,fourth)
  mutate_json(r,v.STATE,fn)
 mutate_and_expect_failure(regress_fourth)
 def grant_fifth(r):
  def fn(d):
   t=d['tracks'][3]; fifth=v.FIFTH; t['evidence_remaining'].remove(fifth); t['evidence_completed'].append(fifth)
  mutate_json(r,v.STATE,fn)
 mutate_and_expect_failure(grant_fifth)
 mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d['source_time_state'].__setitem__('d4d','2_of_5_unselected')))
 mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:(d.__setitem__('candidate',{'kind':'broker_acl'}),d.__setitem__('candidate_status','selected'))))
 print('d4d_tenant_contract_authorization_source_falsification=PASS source_snapshot=1_of_5_22_of_26_preserved current_fourth_credit=required fifth_credit_without_promotion=blocked')
if __name__=='__main__': main()
