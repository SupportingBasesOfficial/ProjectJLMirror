#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

PACKAGE_FILES = (
    "implementation/d4-eventing-async/source-evidence/d4-c-bounded-parser-limits-source.json",
    "tools/assurance/d4c_bounded_parser_limits/evaluate_candidates.py",
    "tools/assurance/d4c_bounded_parser_limits/test_source_evidence.py",
    "tools/assurance/d4c_bounded_parser_limits/validate_source_evidence.py",
    "tools/assurance/d4c_bounded_parser_limits/emit_source_provenance.py",
    "docs/16-implementation-readiness/44-d4-c-bounded-parser-limits-source-evidence.md",
    ".github/workflows/d4-c-bounded-parser-limits-source-evidence.yml",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-sha", required=True)
    parser.add_argument("--workflow-run-id", required=True, type=int)
    parser.add_argument("--workflow-run-attempt", required=True, type=int)
    parser.add_argument("--job-id", required=True, type=int)
    parser.add_argument("--job-name", required=True)
    parser.add_argument("--candidate-results", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    root = Path.cwd()
    manifest = json.loads((root / PACKAGE_FILES[0]).read_text(encoding="utf-8"))
    results = json.loads(args.candidate_results.read_text(encoding="utf-8"))
    if manifest["source_decision"] != "OPEN-EVT-010" or results["source_decision"] != "OPEN-EVT-010":
        raise SystemExit("source decision drift")
    if manifest["evidence_id"] != results["evidence_id"]:
        raise SystemExit("evidence id drift")
    if manifest["candidate_results"] != results["candidate_results"]:
        raise SystemExit("candidate result drift")
    if results["selection"] != "not_selected" or results["ledger_credit"] != [] or results["current_run_auto_credit"] is not False:
        raise SystemExit("runtime authority leakage")

    file_sha256 = {path: sha256(root / path) for path in PACKAGE_FILES}
    file_sha256[str(args.candidate_results)] = sha256(args.candidate_results)
    provenance = {
        "schema_version": 1,
        "repository_sha": args.repository_sha,
        "workflow_run_id": args.workflow_run_id,
        "workflow_run_attempt": args.workflow_run_attempt,
        "job_id": args.job_id,
        "job_name": args.job_name,
        "source_decision": manifest["source_decision"],
        "evidence_id": manifest["evidence_id"],
        "axis": manifest["axis"],
        "canonical_base": manifest["canonical_base"],
        "candidate_results": results["candidate_results"],
        "equivalent_reviewed_profile": results["equivalent_reviewed_profile"],
        "required_proofs": manifest["required_proofs"],
        "source_assertions": manifest["source_assertions"],
        "non_authority": manifest["non_authority"],
        "limit_profile": results["limit_profile"],
        "selection_state": "not_selected",
        "selection_authority": "not_granted",
        "current_run_auto_credit": False,
        "ledger_credit": [],
        "file_sha256": file_sha256,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
