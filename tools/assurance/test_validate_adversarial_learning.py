#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import validate_adversarial_learning as v

ROOT = Path(__file__).resolve().parents[2]
FILES = [v.TAXONOMY, v.INVARIANTS, v.LEDGER]


def clone(tmp: Path) -> None:
    for rel in FILES:
        dst = tmp / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text((ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    for guardrail in {
        "tools/assurance/d4d_trace_context_source.py",
        "tools/assurance/test_validate_d4d_trace_context_source.py",
    }:
        dst = tmp / guardrail
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text((ROOT / guardrail).read_text(encoding="utf-8"), encoding="utf-8")


def mutate_json(root: Path, rel: Path, fn) -> None:
    path = root / rel
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def expect_failure(mutator, *, comments=None) -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        clone(root)
        mutator(root)
        review_comments = None
        if comments is not None:
            review_comments = root / "comments.json"
            review_comments.write_text(json.dumps(comments), encoding="utf-8")
        assert v.validate(root, review_comments), "mutation unexpectedly accepted"


def main() -> None:
    assert not v.validate(ROOT)

    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][0].__setitem__("class_id", "UNKNOWN")))
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][0].__setitem__("invariant_ids", ["UNKNOWN"])))
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][0].__setitem__("root_cause", "local patch")))
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][0].__setitem__("horizontal_audit", [])))
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][0].__setitem__("guardrails", [])))
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][0]["guardrails"][0].__setitem__("path", "missing/file.py")))
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][1].__setitem__("review_comment_id", 3961647090)))
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][6].__setitem__("guardrail_generation", 1)))
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][0].__setitem__("systemic_guardrail_updated", False)))
    expect_failure(
        lambda r: None,
        comments=[[{"id": 9999999999, "body": "**P1 Badge** unmapped material finding"}]],
    )

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        clone(root)
        comments = root / "comments.json"
        comments.write_text(json.dumps([[{"id": 3961647090, "body": "**P1 Badge** mapped finding"}]]), encoding="utf-8")
        assert not v.validate(root, comments)

    print("adversarial_learning_falsification=PASS unknown_class=blocked invariant_drift=blocked weak_root_cause=blocked missing_horizontal_audit=blocked missing_guardrail=blocked nonexistent_guardrail=blocked duplicate_review_identity=blocked recurrence_without_guardrail_advance=blocked unmapped_material_finding=blocked")


if __name__ == "__main__":
    main()
