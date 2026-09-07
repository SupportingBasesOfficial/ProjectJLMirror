#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import validate_d4d_evidence_plan as target

ROOT = Path(__file__).resolve().parents[2]


def clone(root: Path) -> None:
    for path in (target.PLAN, target.STATE, target.PROMOTION, target.SOURCE):
        dst = root / path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / path, dst)


def mutate_json(root: Path, path: Path, mutator) -> None:
    p = root / path
    value = json.loads(p.read_text(encoding="utf-8"))
    mutator(value)
    p.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def expect_rejected(name: str, path: Path, mutator) -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        clone(root)
        mutate_json(root, path, mutator)
        errors = target.validate(root)
        assert errors, f"{name}: mutation unexpectedly accepted"
        print(f"{name}=REJECTED")


def main() -> int:
    assert target.validate(ROOT) == [], target.validate(ROOT)

    expect_rejected("regress_first_credit", target.PLAN, lambda p: (p["credited_evidence"].clear(), p.__setitem__("remaining_evidence", list(target.REQUIRED))))
    expect_rejected("duplicate_first_credit", target.PLAN, lambda p: p["credited_evidence"].append(target.EVIDENCE))
    expect_rejected("silent_candidate_selection", target.PLAN, lambda p: p.__setitem__("candidate", "implicit_broker_identity_product"))
    expect_rejected("selection_authority_leakage", target.PLAN, lambda p: p.__setitem__("selection_authority", "granted"))
    expect_rejected("wrong_source_review", target.PROMOTION, lambda p: p["source_review"].__setitem__("review_id", 1))
    expect_rejected("wrong_source_artifact", target.PROMOTION, lambda p: p["source_workflow"].__setitem__("artifact_id", 1))
    expect_rejected("promotion_two_credits", target.PROMOTION, lambda p: (p["credited_evidence"].append(target.REQUIRED[1]), p.__setitem__("credit_count", 2)))
    expect_rejected("source_auto_credit_mutation", target.SOURCE, lambda p: p.__setitem__("current_run_auto_credit", True))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        clone(root)
        mutate_json(root, target.STATE, lambda s: next(t for t in s["tracks"] if t["track_id"] == "D4-D")["evidence_completed"].append(target.EVIDENCE))
        assert target.validate(root), "duplicate current-state credit unexpectedly accepted"
        print("duplicate_current_state_credit=REJECTED")

    print("d4d_evidence_plan_falsification=PASS regression=blocked duplication=blocked provenance=bound auto_credit=blocked selection=blocked")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
