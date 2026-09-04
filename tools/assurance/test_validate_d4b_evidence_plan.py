#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "assurance"))
import validate_d4b_evidence_plan as validator

FILES = [validator.PLAN, validator.STATE, validator.PROMOTION, validator.SOURCE]


def snapshot() -> dict[Path, object]:
    out: dict[Path, object] = {}
    for path in FILES:
        raw = (ROOT / path).read_bytes()
        out[path] = raw if path == validator.SOURCE else json.loads(raw)
    return out


def validate_mutated(mutator) -> list[str]:
    data = snapshot()
    mutator(data)
    with TemporaryDirectory() as td:
        root = Path(td)
        for path, value in data.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(value, bytes):
                target.write_bytes(value)
            else:
                target.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        return validator.validate(root)


def must_fail(mutator, fragment: str) -> None:
    errors = validate_mutated(mutator)
    if not any(fragment in e for e in errors):
        raise AssertionError(f"expected failure containing {fragment!r}, got {errors!r}")


def main() -> int:
    errors = validator.validate(ROOT)
    if errors:
        raise AssertionError(f"canonical D4-B promotion failed: {errors!r}")

    must_fail(lambda d: d[validator.PLAN]["credited_evidence"].pop(), "credited evidence drift")
    must_fail(lambda d: d[validator.PLAN].__setitem__("selection_state", "selected"), "selection must remain not_selected")
    must_fail(lambda d: d[validator.PROMOTION]["source_workflow"].__setitem__("artifact_digest", "sha256:deadbeef"), "artifact digest drift")
    must_fail(lambda d: d[validator.PROMOTION].__setitem__("source_reviewed_head", "0" * 40), "source reviewed HEAD drift")
    must_fail(lambda d: d[validator.PROMOTION]["source_review"].__setitem__("material_threads_unresolved", 1), "zero unresolved material threads")
    must_fail(lambda d: d[validator.STATE].__setitem__("gate_state", "separately_accepted"), "D4 must remain scoped")
    must_fail(lambda d: next(t for t in d[validator.STATE]["tracks"] if t["track_id"] == "D4-B").__setitem__("candidate", "protobuf"), "must not silently select")
    must_fail(lambda d: next(t for t in d[validator.STATE]["tracks"] if t["track_id"] == "D4-B")["evidence_completed"].pop(), "state credit drift")
    must_fail(lambda d: d.__setitem__(validator.SOURCE, d[validator.SOURCE] + b"\n"), "source manifest byte drift")
    print("d4b_ledger_falsification=PASS overcredit=blocked undercredit=blocked selection=blocked provenance_tamper=blocked source_mutation=blocked authority_escalation=blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
