#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import validate_d4d_candidate_evaluation_plan as target

ROOT = Path(__file__).resolve().parents[2]

def write_case(root: Path, plan: dict, state: dict) -> None:
    (root / target.PLAN.parent).mkdir(parents=True, exist_ok=True)
    (root / target.PLAN).write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    (root / target.STATE).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

def expect_rejected(name: str, mutate) -> None:
    plan = json.loads((ROOT / target.PLAN).read_text(encoding="utf-8"))
    state = json.loads((ROOT / target.STATE).read_text(encoding="utf-8"))
    mutate(plan, state)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_case(root, plan, state)
        errors = target.validate(root)
        assert errors, f"{name}: mutation unexpectedly accepted"
        print(f"{name}=REJECTED")

def main() -> int:
    assert target.validate(ROOT) == [], target.validate(ROOT)
    expect_rejected("silent_selection", lambda p, s: p.__setitem__("selection_state", "selected"))
    expect_rejected("source_decision_drift", lambda p, s: p["source_decisions"].__setitem__(0, "OPEN-EVT-999"))
    expect_rejected("axis_removed", lambda p, s: p["axes"].pop("trace_context_observability_only_validation_and_redaction"))
    expect_rejected("must_prove_weakened", lambda p, s: p["axes"]["workload_identity_to_broker_credential_adapter"].__setitem__("must_prove", []))
    expect_rejected("forbidden_outputs_weakened", lambda p, s: p.__setitem__("forbidden_outputs", []))
    expect_rejected("d4d_auto_credit", lambda p, s: next(t for t in s["tracks"] if t["track_id"] == "D4-D")["evidence_completed"].append(target.D4D_REQUIRED[0]))
    expect_rejected("d4d_candidate_leakage", lambda p, s: next(t for t in s["tracks"] if t["track_id"] == "D4-D").__setitem__("candidate", "implicit_vendor_choice"))
    expect_rejected("authority_leakage", lambda p, s: s.__setitem__("d4_transport_authority", "granted"))
    print("d4d_candidate_evaluation_falsification=PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
