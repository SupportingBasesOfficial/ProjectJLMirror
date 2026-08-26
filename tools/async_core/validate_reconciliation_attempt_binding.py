#!/usr/bin/env python3
"""Observer-only Wave 2 reconciliation attempt-generation binding validation."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
PROFILE = "jlmirror-wave2-reconciliation-attempt-binding/v1"


def require(text: str, anchor: str, owner: str, findings: list[str]) -> None:
    if anchor not in text:
        findings.append(f"{owner} missing attempt-binding anchor: {anchor}")


def validate(root: Path = ROOT) -> list[str]:
    findings: list[str] = []
    model = (root / "src/jlmirror_async/model.py").read_text(encoding="utf-8")
    reconciliation = (root / "src/jlmirror_async/reconciliation.py").read_text(encoding="utf-8")
    sql = (root / "sql/wave2/005_reconciliation_attempt_generation_binding.sql").read_text(
        encoding="utf-8"
    )
    boundary = (root / "implementation/wave-2/RECONCILIATION_AUTHORITY_BOUNDARY.md").read_text(
        encoding="utf-8"
    )
    attempt_tests = (root / "tests/wave2/test_reconciliation_attempt_binding.py").read_text(
        encoding="utf-8"
    )
    snapshot_tests = (root / "tests/wave2/test_operation_authority_snapshot.py").read_text(
        encoding="utf-8"
    )

    for anchor in (
        "reconciliation_attempt_generation: int | None = None",
        "reconciliation resolution, revision and attempt generation must be present together",
        "reconciliation evidence must bind the current operation attempt generation",
    ):
        require(model, anchor, "canonical operation snapshot", findings)

    for anchor in (
        "attempt_generation: int",
        "attempt_generation=operation.attempt_generation",
        "reconciliation_attempt_generation = evidence.attempt_generation",
        "reconciliation_attempt_generation=reconciliation_attempt_generation",
        "reconciliation revision cannot be reused for different evidence",
    ):
        require(reconciliation, anchor, "operation reconciliation model", findings)

    for anchor in (
        "ADD COLUMN attempt_generation BIGINT NULL",
        "NEW.attempt_generation IS DISTINCT FROM op_attempt_generation",
        "reconciliation evidence must bind the current ambiguous attempt generation",
        "evidence_attempt_generation IS DISTINCT FROM OLD.attempt_generation",
        "evidence_attempt_generation IS DISTINCT FROM op_attempt_generation",
        "wave2_operation_reconciliation_attempt_binding_guard",
        "wave2_inbox_reconciliation_attempt_binding_guard",
    ):
        require(sql, anchor, "durable SQL attempt binding", findings)

    for anchor in (
        "PRIOR ATTEMPT RECONCILIATION EVIDENCE != LATER ATTEMPT RETRY AUTHORITY",
        "RECONCILIATION REVISION != ATTEMPT-GENERATION-AGNOSTIC CAPABILITY",
        "attempt 1 -> effect_proven_absent revision R1",
        "reuse R1 -> attempt 3 eligible",
    ):
        require(boundary, anchor, "reconciliation authority boundary", findings)

    for anchor in (
        "test_prior_attempt_absence_revision_cannot_reauthorize_later_ambiguity",
        "self.assertEqual(first_evidence.attempt_generation, 1)",
        "with self.assertRaises(InvalidTransition)",
    ):
        require(attempt_tests, anchor, "attempt-binding falsification", findings)

    for anchor in (
        "test_snapshot_rejects_reconciliation_evidence_from_another_attempt",
        "reconciliation_attempt_generation=1",
        "attempt_generation=2",
        "test_snapshot_requires_generation_with_reconciliation_revision",
    ):
        require(snapshot_tests, anchor, "snapshot falsification", findings)

    return findings


def main() -> int:
    findings = validate()
    if findings:
        print(f"RESULT: FAIL — {PROFILE}")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print(
        f"RESULT: PASS — {PROFILE} — reconciliation authority is bound to the exact ambiguous attempt generation"
    )
    print("NOTE: PASS is conformance evidence only; it is not merge or Product authority.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
