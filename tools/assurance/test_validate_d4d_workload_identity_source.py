#!/usr/bin/env python3
from __future__ import annotations
import json, tempfile
from pathlib import Path
import validate_d4d_workload_identity_source as v

ROOT=Path(__file__).resolve().parents[2]

def clone(tmp:Path):
    for p in [v.MANIFEST,v.STATE,v.PLAN]:
        dst=tmp/p; dst.parent.mkdir(parents=True,exist_ok=True); dst.write_text((ROOT/p).read_text())

def mutate_and_expect_failure(mutator):
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); clone(root); mutator(root)
        assert v.validate(root), "mutation unexpectedly accepted"

def main():
    assert not v.validate(ROOT)
    mutate_and_expect_failure(lambda r: (lambda p,d:(d.__setitem__("current_run_auto_credit",True),p.write_text(json.dumps(d))))(r/v.MANIFEST,json.loads((r/v.MANIFEST).read_text())))
    mutate_and_expect_failure(lambda r: (lambda p,d:(d.__setitem__("canonical_identity_authority","broker_vendor"),p.write_text(json.dumps(d))))(r/v.MANIFEST,json.loads((r/v.MANIFEST).read_text())))
    mutate_and_expect_failure(lambda r: (lambda p,d:(d["tracks"][3]["evidence_completed"].append(v.EXPECTED_ID),p.write_text(json.dumps(d))))(r/v.STATE,json.loads((r/v.STATE).read_text())))
    mutate_and_expect_failure(lambda r: (lambda p,d:(d["axes"]["workload_identity_to_broker_credential_adapter"]["must_prove"].pop(),p.write_text(json.dumps(d))))(r/v.PLAN,json.loads((r/v.PLAN).read_text())))
    print("d4d_workload_identity_source_falsification=PASS")
if __name__=="__main__": main()
