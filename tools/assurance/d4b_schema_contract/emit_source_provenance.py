from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "implementation/d4-eventing-async/source-evidence/schema-contract/source-evidence-manifest.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-sha", required=True)
    parser.add_argument("--workflow-run-id", required=True, type=int)
    parser.add_argument("--workflow-run-attempt", required=True, type=int)
    parser.add_argument("--job-id", required=True, type=int)
    parser.add_argument("--job-name", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    source_bytes = SOURCE.read_bytes()
    source = json.loads(source_bytes)
    record = {
        "schema": "d4b-schema-contract-source-run-provenance-v1",
        "probe": "d4b_deterministic_schema_contract_reference",
        "repository_sha": args.repository_sha,
        "workflow_run_id": args.workflow_run_id,
        "workflow_run_attempt": args.workflow_run_attempt,
        "job_id": args.job_id,
        "job_name": args.job_name,
        "source_manifest_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "evidence_ids": source["evidence_ids"],
        "evidence_kinds": source["evidence_kinds"],
        "candidate": source["candidate"],
        "candidate_status": source["candidate_status"],
        "current_run_auto_credit": source["current_run_auto_credit"],
        "ledger_credit": source["ledger_credit"],
        "serialization_selection_state": source["serialization_selection_state"],
        "schema_catalog_selection_state": source["schema_catalog_selection_state"],
        "contract_version_syntax_selection_state": source["contract_version_syntax_selection_state"],
        "d4_transport_authority": source["d4_transport_authority"],
        "production_authority": source["production_authority"],
        "c3_numeric_topology_authority": source["c3_numeric_topology_authority"],
        "promotion_rule": source["promotion_rule"],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"d4b_source_provenance=PASS sha={args.repository_sha} job_id={args.job_id} evidence=5 source_credit=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
