#!/usr/bin/env python3
from __future__ import annotations
import json,tempfile
from pathlib import Path
import validate_d4d_message_protection_source as v
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
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d.__setitem__('message_protection_authority','broker_native_key_is_platform_authority')))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.PLAN,lambda d:d['axes'][v.EXPECTED_AXIS]['must_prove'].pop()))
    def grant_third(r):
        def fn(d):
            t=d['tracks'][3]; third=v.EXPECTED_ID; t['evidence_remaining'].remove(third); t['evidence_completed'].append(third)
        mutate_json(r,v.STATE,fn)
    mutate_and_expect_failure(grant_third)
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d['source_time_state'].__setitem__('d4d','3_of_5_unselected')))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:(d.__setitem__('candidate',{'kind':'kms_profile'}),d.__setitem__('candidate_status','selected'))))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.STATE,lambda d:d.__setitem__('production_authority','granted')))
    print('d4d_message_protection_source_falsification=PASS third_credit_without_promotion=blocked source_snapshot=preserved authority_leakage=blocked')

if __name__=='__main__': main()
