#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


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

    results = Path(args.candidate_results)
    manifest = Path(
        "implementation/d4-eventing-async/source-evidence/d4-c-producer-generation-source.json"
    )
    data = json.loads(results.read_text(encoding="utf-8"))
    out = {
        "schema_version": 1,
        "source_decision": "OPEN-EVT-013",
        "evidence_id": "producer_generation_nonresurrection_across_failover_restore",
        "repository_sha": args.repository_sha,
        "workflow_run_id": args.workflow_run_id,
        "workflow_run_attempt": args.workflow_run_attempt,
        "job_id": args.job_id,
        "job_name": args.job_name,
        "source_manifest_sha256": sha256(manifest),
        "candidate_results_sha256": sha256(results),
        "candidate_results": data["candidate_results"],
        "proof_results": data["proof_results"],
        "selection": "not_selected",
        "selection_authority": "not_granted",
        "ledger_credit": [],
        "current_run_auto_credit": False,
    }
    Path(args.output).write_text(
        json.dumps(out, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
