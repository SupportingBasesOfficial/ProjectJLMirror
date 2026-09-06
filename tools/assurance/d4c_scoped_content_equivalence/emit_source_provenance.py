#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

FILES = [
    "implementation/d4-eventing-async/source-evidence/d4-c-scoped-content-equivalence-source.json",
    "tools/assurance/d4c_scoped_content_equivalence/evaluate_candidates.py",
    "tools/assurance/d4c_scoped_content_equivalence/test_source_evidence.py",
    "tools/assurance/d4c_scoped_content_equivalence/validate_source_evidence.py",
    "tools/assurance/d4c_scoped_content_equivalence/emit_source_provenance.py",
    "docs/16-implementation-readiness/46-d4-c-scoped-content-equivalence-source-evidence.md",
    ".github/workflows/d4-c-scoped-content-equivalence-source-evidence.yml",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-sha", required=True)
    parser.add_argument("--workflow-run-id", required=True, type=int)
    parser.add_argument("--workflow-run-attempt", required=True, type=int)
    parser.add_argument("--job-id", required=True, type=int)
    parser.add_argument("--job-name", required=True)
    parser.add_argument("--candidate-results", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    root = Path.cwd()
    source_path = root / FILES[0]
    source = json.loads(source_path.read_text(encoding="utf-8"))
    results_path = Path(args.candidate_results)
    results = json.loads(results_path.read_text(encoding="utf-8"))

    file_hashes = {path: sha256(root / path) for path in FILES}
    file_hashes[str(results_path)] = sha256(results_path)
    provenance = {
        "schema": "d4c-scoped-content-equivalence-source-run-provenance-v1",
        "repository_sha": args.repository_sha,
        "workflow_run_id": args.workflow_run_id,
        "workflow_run_attempt": args.workflow_run_attempt,
        "job_id": args.job_id,
        "job_name": args.job_name,
        "source_decision": source["source_decision"],
        "evidence_id": source["evidence_id"],
        "axis": source["axis"],
        "canonical_base": source["canonical_base"],
        "candidate_results": results["candidate_results"],
        "equivalent_reviewed_profile": results["equivalent_reviewed_profile"],
        "required_proofs": source["required_proofs"],
        "source_assertions": source["source_assertions"],
        "non_authority": source["non_authority"],
        "fixture_profile": results["fixture_profile"],
        "selection_state": source["selection_state"],
        "selection_authority": source["selection_authority"],
        "current_run_auto_credit": source["current_run_auto_credit"],
        "ledger_credit": source["ledger_credit"],
        "file_sha256": file_hashes,
    }
    Path(args.output).write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"d4c_open_evt_011_source_provenance=PASS output={args.output} files={len(file_hashes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
