#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import validate_adversarial_learning as v

ROOT = Path(__file__).resolve().parents[2]
FILES = [v.TAXONOMY, v.INVARIANTS, v.LEDGER, v.BOOTSTRAP_EXCEPTIONS, v.STOP_POLICY]
GUARDRAIL_FILES = [
    v.WORKFLOW,
    Path("tools/assurance/d4d_trace_context_source.py"),
    Path("tools/assurance/test_validate_d4d_trace_context_source.py"),
    Path("tools/assurance/test_validate_adversarial_learning.py"),
]


def clone(tmp: Path) -> None:
    for rel in FILES + GUARDRAIL_FILES:
        dst = tmp / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text((ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    shard_src = ROOT / v.LEDGER_SHARDS
    if shard_src.is_dir():
        for src in shard_src.glob("*.json"):
            rel = v.LEDGER_SHARDS / src.name
            dst = tmp / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def mutate_json(root: Path, rel: Path, fn) -> None:
    path = root / rel
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def mutate_text(root: Path, rel: Path, old: str, new: str) -> None:
    path = root / rel
    text = path.read_text(encoding="utf-8")
    assert old in text, f"expected mutation marker missing: {old}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


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


def falsify_top_level_review_surface_coverage() -> None:
    expect_failure(
        lambda r: mutate_text(
            r,
            v.WORKFLOW,
            "repos/${GITHUB_REPOSITORY}/issues/${PR_NUMBER}/comments?per_page=100",
            "repos/${GITHUB_REPOSITORY}/issues/${PR_NUMBER}/labels?per_page=100",
        )
    )


def falsify_incidental_guardrail_substring() -> None:
    expect_failure(
        lambda r: mutate_json(
            r,
            v.LEDGER,
            lambda d: d["entries"][0]["guardrails"][0].__setitem__("probe", "TraceContext"),
        )
    )


def falsify_unreachable_guardrail_call() -> None:
    def mutate(root: Path) -> None:
        mutate_text(
            root,
            Path("tools/assurance/test_validate_adversarial_learning.py"),
            "    falsify_incidental_guardrail_substring()\n",
            "    if False:\n        falsify_incidental_guardrail_substring()\n",
        )
    expect_failure(mutate)


def falsify_missing_falsifier_entrypoint() -> None:
    def mutate(root: Path) -> None:
        mutate_text(
            root,
            Path("tools/assurance/test_validate_adversarial_learning.py"),
            'if __name__ == "__main__":\n    main()\n',
            'if False:\n    main()\n',
        )
    expect_failure(mutate)


def falsify_bootstrap_exception_scope() -> None:
    expect_failure(
        lambda r: mutate_json(
            r,
            v.BOOTSTRAP_EXCEPTIONS,
            lambda d: d["exceptions"][0].__setitem__("pr", 119),
        )
    )


def falsify_stop_policy_relaxation() -> None:
    expect_failure(
        lambda r: mutate_json(
            r,
            v.STOP_POLICY,
            lambda d: d.__setitem__("merge_blocking_severities", ["P0"]),
        )
    )


def main() -> None:
    assert not v.validate(ROOT)

    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][0].__setitem__("class_id", "UNKNOWN")))
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][0].__setitem__("invariant_ids", ["UNKNOWN"])))
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][0].__setitem__("root_cause", "local patch")))
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][0].__setitem__("horizontal_audit", [])))
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][0].__setitem__("guardrails", [])))
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][0]["guardrails"][0].__setitem__("path", "missing/file.py")))
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][0]["guardrails"][0].__setitem__("probe", "fictional_probe_that_does_not_exist")))
    falsify_incidental_guardrail_substring()
    falsify_unreachable_guardrail_call()
    falsify_missing_falsifier_entrypoint()
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][1].__setitem__("review_comment_id", 3961647090)))
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][6].__setitem__("guardrail_generation", 1)))
    expect_failure(lambda r: mutate_json(r, v.LEDGER, lambda d: d["entries"][0].__setitem__("systemic_guardrail_updated", False)))
    falsify_top_level_review_surface_coverage()
    falsify_bootstrap_exception_scope()
    falsify_stop_policy_relaxation()
    expect_failure(
        lambda r: None,
        comments=[[{"id": 9999999999, "body": "**P1 Badge** unmapped material finding"}]],
    )

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        clone(root)
        comments = root / "comments.json"
        comments.write_text(json.dumps([[[{"id": 3961647090, "body": "**P1 Badge** mapped finding"}]]]), encoding="utf-8")
        assert not v.validate(root, comments)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        clone(root)
        comments = root / "comments.json"
        comments.write_text(json.dumps([[{"id": 3963734258, "body": "**P1 Badge** exact bootstrap finding"}]]), encoding="utf-8")
        assert not v.validate(root, comments)

    print("adversarial_learning_falsification=PASS unknown_class=blocked invariant_drift=blocked weak_root_cause=blocked missing_horizontal_audit=blocked missing_guardrail=blocked nonexistent_guardrail=blocked fictional_probe=blocked incidental_substring=blocked unreachable_guardrail_call=blocked missing_falsifier_entrypoint=blocked duplicate_review_identity=blocked recurrence_without_guardrail_advance=blocked top_level_review_surface_omission=blocked bootstrap_exception_scope=exact stop_policy_relaxation=blocked unmapped_material_finding=blocked nested_review_pages=handled")


if __name__ == "__main__":
    main()
