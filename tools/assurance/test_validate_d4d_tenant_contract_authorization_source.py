#!/usr/bin/env python3
from __future__ import annotations
import json, tempfile
from pathlib import Path
import validate_d4d_tenant_contract_authorization_source as v

ROOT=Path(__file__).resolve().parents[2]

def clone(tmp:Path):
    for p in [v.MANIFEST,v.STATE,v.PLAN]:
        dst=tmp/p
        dst.parent.mkdir(parents=True,exist_ok=True)
        dst.write_text((ROOT/p).read_text())

def mutate_and_expect_failure(mutator):
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        clone(root)
        mutator(root)
        assert v.validate(root), "mutation unexpectedly accepted"

def main():
    assert not v.validate(ROOT)
    mutate_and_expect_failure(lambda r: (lambda p,d:(d.__setitem__("current_run_auto_credit",True),p.write_text(json.dumps(d))))(r/v.MANIFEST,json.loads((r/v.MANIFEST).read_text())))
    mutate_and_expect_failure(lambda r: (lambda p,d:(d.__setitem__("ledger_credit",[v.EXPECTED_ID]),p.write_text(json.dumps(d))))(r/v.MANIFEST,json.loads((r/v.MANIFEST).read_text())))
    mutate_and_expect_failure(lambda r: (lambda p,d:(d.__setitem__("broker_authorization_authority","broker_acl_is_authority"),p.write_text(json.dumps(d))))(r/v.MANIFEST,json.loads((r/v.MANIFEST).read_text())))
    mutate_and_expect_failure(lambda r: (lambda p,d:(d["axes"][v.EXPECTED_AXIS]["must_prove"].pop(),p.write_text(json.dumps(d))))(r/v.PLAN,json.loads((r/v.PLAN).read_text())))
    mutate_and_expect_failure(lambda r: (lambda p,d:(d["tracks"][3]["evidence_completed"].append(v.EXPECTED_ID),d["tracks"][3]["evidence_remaining"].remove(v.EXPECTED_ID),p.write_text(json.dumps(d))))(r/v.STATE,json.loads((r/v.STATE).read_text())))
    mutate_and_expect_failure(lambda r: (lambda p,d:(d["source_time_state"].__setitem__("d4d","2_of_5_unselected"),p.write_text(json.dumps(d))))(r/v.MANIFEST,json.loads((r/v.MANIFEST).read_text())))
    mutate_and_expect_failure(lambda r: (lambda p,d:(d.__setitem__("candidate",{"kind":"broker_acl"}),d.__setitem__("candidate_status","selected"),p.write_text(json.dumps(d))))(r/v.MANIFEST,json.loads((r/v.MANIFEST).read_text())))
    print("d4d_tenant_contract_authorization_source_falsification=PASS")

if __name__=="__main__":
    main()
