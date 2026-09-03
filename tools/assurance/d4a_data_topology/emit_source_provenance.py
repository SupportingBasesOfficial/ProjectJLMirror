from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "implementation/d4-eventing-async/source-evidence/data-topology/source-evidence-manifest.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-sha", required=True)
    parser.add_argument("--workflow-run-id", type=int, required=True)
    parser.add_argument("--workflow-run-attempt", type=int, required=True)
    parser.add_argument("--job-id", type=int, required=True)
    parser.add_argument("--job-name", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    source_bytes = SOURCE.read_bytes()
    source = json.loads(source_bytes)
    payload = {
        "artifact_schema": "d4a-source-run-provenance-v1",
        "repository_sha": args.repository_sha,
        "workflow_run_id": args.workflow_run_id,
        "workflow_run_attempt": args.workflow_run_attempt,
        "job_id": args.job_id,
        "job_name": args.job_name,
        "probe": source["package_id"],
        "source_manifest_sha256": sha256(source_bytes).hexdigest(),
        "evidence_ids": source["evidence_ids"],
        "evidence_kinds": source["evidence_kinds"],
        "current_run_auto_credit": source["current_run_auto_credit"],
        "ledger_credit": source["ledger_credit"],
        "promotion_rule": source["promotion_rule"],
    }
    assert payload["current_run_auto_credit"] is False
    assert payload["ledger_credit"] == []

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "d4a_data_topology_provenance=PASS "
        f"repository_sha={args.repository_sha} run={args.workflow_run_id} attempt={args.workflow_run_attempt} job={args.job_id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
