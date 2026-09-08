#!/usr/bin/env python3
from __future__ import annotations
import json,tempfile
from pathlib import Path
import validate_d4d_trace_context_source as v
ROOT=Path(__file__).resolve().parents[2]
def clone(tmp):
    for p in [v.MANIFEST,v.STATE,v.PLAN]:
        dst=tmp/p; dst.parent.mkdir(parents=True,exist_ok=True); dst.write_text((ROOT/p).read_text())
def mutate_json(root,path,fn):
    p=root/path; d=json.loads(p.read_text()); fn(d); p.write_text(json.dumps(d))
def mutate_and_expect_failure(mutator):
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); clone(root); mutator(root); assert v.validate(root),'mutation unexpectedly accepted'
def main():
    assert not v.validate(ROOT)
    for field,bad in [
        ('schema_version',2),
        ('gate_id','D3'),
        ('track_id','D4-C'),
        ('source_decision','OPEN-EVT-017'),
        ('evidence_id','wrong-evidence'),
        ('mode','promotion'),
        ('source_base','0'*40),
    ]:
        mutate_and_expect_failure(lambda r,field=field,bad=bad:mutate_json(r,v.MANIFEST,lambda d,field=field,bad=bad:d.__setitem__(field,bad)))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d.__setitem__('current_run_auto_credit',True)))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d.__setitem__('ledger_credit',[v.EXPECTED_ID])))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d.__setitem__('trace_context_authority','tenant_authority')))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d['source_time_state'].__setitem__('d4d','5_of_5_unselected')))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d['source_time_state'].__setitem__('d4wide','26_of_26')))
    for field,bad in [
        ('d4_transport_authority','granted'),
        ('canonical_product_implementation_authority','granted'),
        ('wave4_implementation_authority','granted'),
        ('production_authority','granted'),
        ('c3_numeric_topology_authority','selected'),
    ]:
        mutate_and_expect_failure(lambda r,field=field,bad=bad:mutate_json(r,v.MANIFEST,lambda d,field=field,bad=bad:d['source_time_state'].__setitem__(field,bad)))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d['source_time_state'].__setitem__('unexpected_authority','granted')))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.PLAN,lambda d:d['axes'][v.EXPECTED_ID]['must_prove'].pop()))
    def grant_fifth(r):
        def fn(d):
            t=next(t for t in d['tracks'] if t['track_id']=='D4-D'); t['evidence_remaining'].remove(v.EXPECTED_ID); t['evidence_completed'].append(v.EXPECTED_ID)
        mutate_json(r,v.STATE,fn)
    mutate_and_expect_failure(grant_fifth)
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:(d.__setitem__('candidate',{'kind':'trace_profile'}),d.__setitem__('candidate_status','selected'))))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d.__setitem__('selection_authority','granted')))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.STATE,lambda d:d.__setitem__('canonical_product_implementation_authority','granted')))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.STATE,lambda d:d.__setitem__('production_authority','granted')))
    print('d4d_trace_context_source_falsification=PASS source_identity=exact source_snapshot=4_of_5_25_of_26_exact authorities_exact auto_credit=blocked fifth_credit_without_promotion=blocked selection=blocked authority_leakage=blocked')
if __name__=='__main__': main()
