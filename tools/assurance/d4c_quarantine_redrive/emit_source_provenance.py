#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SOURCE = Path("implementation/d4-eventing-async/source-evidence/d4-c-quarantine-redrive-source.json")
PINNED_FILES = (
    SOURCE,
    Path("tools/assurance/d4c_quarantine_redrive/evaluate_candidates.py"),
    Path("tools/assurance/d4c_quarantine_redrive/validate_source_evidence.py"),
    Path("tools/assurance/d4c_quarantine_redrive/test_source_evidence.py"),
    Path("tools/assurance/d4c_quarantine_redrive/emit_source_provenance.py"),
    Path("docs/16-implementation-readiness/42-d4-c-quarantine-redrive-source-evidence.md"),
    Path(".github/workflows/d4-c-quarantine-redrive-source-evidence.yml"),
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

    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    runtime = json.loads(args.candidate_results.read_text(encoding="utf-8"))
    if source["current_run_auto_credit"] is not False or source["ledger_credit"] != []:
        raise SystemExit("source manifest is not non-promoting")
    if source["selection_state"] != "not_selected" or source["selection_authority"] != "not_granted":
        raise SystemExit("source manifest contains selection authority")
    if runtime.get("candidate_results") != source["candidate_results"]:
        raise SystemExit("runtime candidate results do not match source manifest")
    if runtime.get("equivalent_reviewed_profile") != source["equivalent_reviewed_profile"]:
        raise SystemExit("runtime equivalent profile state drift")
    if runtime.get("selection") != "not_selected" or runtime.get("ledger_credit") != []:
        raise SystemExit("runtime output escaped source-only boundary")
    if runtime.get("test_retry_budget_is_noncanonical_fixture") is not True:
        raise SystemExit("test retry budget must remain explicitly noncanonical")

    payload = {
        "schema_version": 1,
        "repository_sha": args.repository_sha,
        "workflow_run_id": args.workflow_run_id,
        "workflow_run_attempt": args.workflow_run_attempt,
        "job_id": args.job_id,
        "job_name": args.job_name,
        "source_decision": source["source_decision"],
        "evidence_id": source["evidence_id"],
        "axis": source["axis"],
        "mode": source["mode"],
        "selection_state": source["selection_state"],
        "selection_authority": source["selection_authority"],
        "current_run_auto_credit": source["current_run_auto_credit"],
        "ledger_credit": source["ledger_credit"],
        "candidate_results": runtime["candidate_results"],
        "equivalent_reviewed_profile": runtime["equivalent_reviewed_profile"],
        "required_proofs": source["required_proofs"],
        "source_assertions": source["source_assertions"],
        "non_authority": source["non_authority"],
        "file_sha256": {str(path): sha256(path) for path in PINNED_FILES},
        "candidate_results_sha256": sha256(args.candidate_results),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"d4c_quarantine_redrive_provenance=PASS sha={args.repository_sha} run={args.workflow_run_id} attempt={args.workflow_run_attempt} job={args.job_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
