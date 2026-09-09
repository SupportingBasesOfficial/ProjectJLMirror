#!/usr/bin/env python3
from __future__ import annotations
import json,tempfile
from pathlib import Path
import validate_d4d_trace_context_source as v
import validate_d4d_evidence_plan as ledger
ROOT=Path(__file__).resolve().parents[2]
def clone(tmp):
    paths=[v.MANIFEST,v.STATE,v.PLAN,ledger.PLAN,ledger.P1,ledger.P2,ledger.P3,ledger.P4,ledger.P5,ledger.S1,ledger.S2,ledger.S3,ledger.S4,ledger.S5]
    for p in dict.fromkeys(paths):
        dst=tmp/p; dst.parent.mkdir(parents=True,exist_ok=True); dst.write_text((ROOT/p).read_text())
def mutate_json(root,path,fn):
    p=root/path; d=json.loads(p.read_text()); fn(d); p.write_text(json.dumps(d))
def mutate_and_expect_failure(mutator,validator=v.validate):
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); clone(root); mutator(root); assert validator(root),'mutation unexpectedly accepted'
def falsify_immutable_identity_envelope():
    for field,bad in [('schema_version',2),('gate_id','D3'),('track_id','D4-C'),('source_decision','OPEN-EVT-017'),('evidence_id','wrong-evidence'),('mode','promotion'),('source_base','0'*40)]:
        mutate_and_expect_failure(lambda r,field=field,bad=bad:mutate_json(r,v.MANIFEST,lambda d,field=field,bad=bad:d.__setitem__(field,bad)))
def falsify_source_time_state_exactness():
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d['source_time_state'].__setitem__('d4d','5_of_5_unselected')))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d['source_time_state'].__setitem__('d4wide','26_of_26')))
    for field,bad in [('d4_transport_authority','granted'),('canonical_product_implementation_authority','granted'),('wave4_implementation_authority','granted'),('production_authority','granted'),('c3_numeric_topology_authority','selected')]:
        mutate_and_expect_failure(lambda r,field=field,bad=bad:mutate_json(r,v.MANIFEST,lambda d,field=field,bad=bad:d['source_time_state'].__setitem__(field,bad)))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d['source_time_state'].__setitem__('unexpected_authority','granted')))
def falsify_promotion_separation_flags():
    for promotion_path,flag in (
        (ledger.P1,'separate_selection_required'),(ledger.P1,'separate_d4_acceptance_required'),
        (ledger.P2,'separate_selection_required'),(ledger.P2,'separate_d4_acceptance_required'),
        (ledger.P3,'separate_selection_required'),(ledger.P3,'separate_d4_acceptance_required'),
        (ledger.P4,'separate_selection_required'),(ledger.P4,'separate_d4_acceptance_required'),
        (ledger.P5,'separate_selection_required'),(ledger.P5,'separate_d4_acceptance_required'),
    ):
        mutate_and_expect_failure(
            lambda r,promotion_path=promotion_path,flag=flag:mutate_json(r,promotion_path,lambda d,flag=flag:d.__setitem__(flag,False)),
            validator=ledger.validate,
        )
def falsify_promotion_identity_envelopes():
    for promotion_path in (ledger.P1,ledger.P2,ledger.P3,ledger.P4,ledger.P5):
        for field,bad in (('schema_version',2),('gate_id','D3'),('track_id','D4-C'),('promotion_id','wrong-promotion')):
            mutate_and_expect_failure(
                lambda r,promotion_path=promotion_path,field=field,bad=bad:mutate_json(r,promotion_path,lambda d,field=field,bad=bad:d.__setitem__(field,bad)),
                validator=ledger.validate,
            )
        mutate_and_expect_failure(
            lambda r,promotion_path=promotion_path:mutate_json(r,promotion_path,lambda d:d['source_review'].__setitem__('review_mode','unbound-review-mode')),
            validator=ledger.validate,
        )
        mutate_and_expect_failure(
            lambda r,promotion_path=promotion_path:mutate_json(r,promotion_path,lambda d:d['source_review'].__setitem__('review_id',-1)),
            validator=ledger.validate,
        )
        mutate_and_expect_failure(
            lambda r,promotion_path=promotion_path:mutate_json(r,promotion_path,lambda d:d['source_workflow'].__setitem__('run_id',-1)),
            validator=ledger.validate,
        )
        mutate_and_expect_failure(
            lambda r,promotion_path=promotion_path:mutate_json(r,promotion_path,lambda d:d['source_manifest'].__setitem__('sha256','0'*64)),
            validator=ledger.validate,
        )
def main():
    assert not v.validate(ROOT)
    falsify_immutable_identity_envelope()
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d.__setitem__('current_run_auto_credit',True)))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d.__setitem__('ledger_credit',[v.EXPECTED_ID])))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d.__setitem__('trace_context_authority','tenant_authority')))
    falsify_source_time_state_exactness()
    mutate_and_expect_failure(lambda r:mutate_json(r,v.PLAN,lambda d:d['axes'][v.EXPECTED_ID]['must_prove'].pop()))
    def regress_fifth(r):
        def fn(d):
            t=next(t for t in d['tracks'] if t['track_id']=='D4-D'); t['evidence_completed'].remove(v.EXPECTED_ID); t['evidence_remaining']=[v.EXPECTED_ID]
        mutate_json(r,v.STATE,fn)
    mutate_and_expect_failure(regress_fifth)
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:(d.__setitem__('candidate',{'kind':'trace_profile'}),d.__setitem__('candidate_status','selected'))))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.MANIFEST,lambda d:d.__setitem__('selection_authority','granted')))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.STATE,lambda d:d.__setitem__('canonical_product_implementation_authority','granted')))
    mutate_and_expect_failure(lambda r:mutate_json(r,v.STATE,lambda d:d.__setitem__('production_authority','granted')))
    falsify_promotion_separation_flags()
    falsify_promotion_identity_envelopes()
    print('d4d_trace_context_source_falsification=PASS source_identity=exact source_snapshot=4_of_5_25_of_26_exact current_state=5_of_5_26_of_26 authorities_exact promotion_separation=bound promotion_identity=P1-P5-complete-envelope-bound auto_credit=blocked selection=blocked authority_leakage=blocked')
if __name__=='__main__': main()
