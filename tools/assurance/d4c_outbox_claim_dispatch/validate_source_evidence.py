#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from evaluate_candidates import CANDIDATES, PROOFS, PROOF_CHECKS, evaluate_all  # noqa: E402

MANIFEST = Path("implementation/d4-eventing-async/source-evidence/d4-c-outbox-claim-dispatch-source.json")
PLAN = Path("implementation/d4-eventing-async/d4-c-candidate-evaluation-plan.json")
LEDGER = Path("implementation/d4-eventing-async/d4-c-evidence-plan.json")
STATE = Path("implementation/d4-eventing-async/state-manifest.json")
AXIS = "outbox_claim_dispatch_and_ack_ambiguity"
EVIDENCE = "outbox_claim_dispatch_ack_ambiguity_and_recovery_continuity"
CURRENT_CREDITS = [
    "ack_after_durable_responsibility_and_lease_ambiguity",
    "quarantine_redrive_current_authority_and_dedup_preservation",
    "bounded_message_batch_compression_and_parser_limits",
    "scoped_content_equivalence_confidentiality_and_conflict_rejection",
]

class DuplicateKeyError(ValueError): pass

def _pairs(pairs:list[tuple[str,Any]])->dict[str,Any]:
    out={}
    for k,v in pairs:
        if k in out: raise DuplicateKeyError(f"duplicate JSON member: {k}")
        out[k]=v
    return out

def load(path:Path)->Any:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs)

def validate(root:Path)->list[str]:
    errors=[]
    try:
        manifest=load(root/MANIFEST); plan=load(root/PLAN); ledger=load(root/LEDGER); state=load(root/STATE)
    except Exception as exc:
        return [str(exc)]
    axes=plan.get("axes",{}) if isinstance(plan,dict) else {}
    axis=axes.get(AXIS)
    if not isinstance(axis,dict): errors.append("accepted OPEN-EVT-012 axis missing")
    else:
        if axis.get("decision")!="OPEN-EVT-012" or axis.get("evidence_id")!=EVIDENCE: errors.append("axis decision/evidence drift")
        expected_candidates=[x for x in axis.get("candidate_classes",[]) if x!="equivalent_reviewed_profile"]
        if expected_candidates!=list(CANDIDATES): errors.append("candidate inventory drift")
        if axis.get("must_prove")!=list(PROOFS): errors.append("proof inventory drift")
    expected_results={c:"eligible_for_evidence_execution" for c in CANDIDATES}
    if manifest.get("candidate_results")!=expected_results: errors.append("manifest candidate results drift")
    if manifest.get("required_proofs")!=list(PROOFS): errors.append("manifest required proofs drift")
    if manifest.get("mode")!="candidate_source_evidence_only" or manifest.get("current_run_auto_credit") is not False or manifest.get("ledger_credit")!=[]: errors.append("source must remain non-promoting")
    if manifest.get("selection_state")!="not_selected" or manifest.get("selection_authority")!="not_granted": errors.append("source selection leakage")
    if manifest.get("equivalent_reviewed_profile")!="insufficient_evidence": errors.append("equivalent profile drift")
    runtime=evaluate_all()
    if runtime.get("candidate_results")!=expected_results: errors.append("runtime candidate results drift")
    if runtime.get("selection")!="not_selected" or runtime.get("selection_authority")!="not_granted": errors.append("runtime selection leakage")
    if runtime.get("ledger_credit")!=[] or runtime.get("current_run_auto_credit") is not False: errors.append("runtime auto-credit leakage")
    checks=runtime.get("checks"); proofs=runtime.get("proof_results")
    expected_check_names={name for names in PROOF_CHECKS.values() for name in names}
    if not isinstance(checks,dict) or set(checks)!=set(CANDIDATES): errors.append("runtime candidate check inventory drift")
    else:
        for c,v in checks.items():
            if not isinstance(v,dict) or set(v)!=expected_check_names: errors.append(f"runtime exact check inventory drift for {c}")
            elif not all(v.values()): errors.append(f"runtime check failure for {c}")
    if not isinstance(proofs,dict) or set(proofs)!=set(CANDIDATES): errors.append("runtime proof inventory drift")
    else:
        for c,v in proofs.items():
            if not isinstance(v,dict) or set(v)!=set(PROOFS): errors.append(f"runtime exact proof inventory drift for {c}")
            elif not all(v.values()): errors.append(f"runtime proof failure for {c}")
    if ledger.get("ledger_credit_state")!="four_of_nine" or ledger.get("credited_evidence")!=CURRENT_CREDITS: errors.append("current D4-C ledger drift")
    if EVIDENCE not in ledger.get("remaining_evidence",[]) or len(ledger.get("remaining_evidence",[]))!=5: errors.append("OPEN-EVT-012 must remain uncredited")
    tracks={t.get("track_id"):t for t in state.get("tracks",[]) if isinstance(t,dict)}
    if set(tracks)!={"D4-A","D4-B","D4-C","D4-D"}: errors.append("global D4 track identity drift")
    else:
        d4c=tracks["D4-C"]
        if d4c.get("evidence_completed")!=CURRENT_CREDITS or d4c.get("evidence_remaining")!=ledger.get("remaining_evidence"): errors.append("D4-C current state drift")
        if d4c.get("candidate") is not None or d4c.get("candidate_status")!="not_selected" or d4c.get("state")!="candidate_selection_open": errors.append("D4-C candidate leakage")
        if tracks["D4-D"].get("evidence_completed")!=[] or tracks["D4-D"].get("candidate") is not None: errors.append("D4-D leakage")
        if sum(len(t.get("evidence_completed",[])) for t in state.get("tracks",[]))!=16: errors.append("D4-wide evidence count drift")
    for k,e in {"gate_state":"scoped","d4_transport_authority":"selected_not_granted","canonical_product_implementation_authority":"not_granted","wave4_implementation_authority":"not_granted","production_authority":"none","c3_numeric_topology_authority":"not_selected"}.items():
        if state.get(k)!=e: errors.append(f"global authority drift: {k}")
    return errors

def main(argv:list[str])->int:
    root=Path(argv[1]).resolve() if len(argv)>1 else ROOT
    errors=validate(root)
    if errors:
        for e in errors: print(f"D4C_OPEN_EVT_012_SOURCE_ERROR: {e}",file=sys.stderr)
        return 1
    print("d4c_open_evt_012_source=PASS candidates=3 proofs=7 source_auto_credit=false current_d4c=4_of_9 current_d4wide=16_of_26 selection=not_selected")
    return 0

if __name__=="__main__": raise SystemExit(main(sys.argv))
