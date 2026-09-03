from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "implementation/d4-eventing-async/source-evidence/capacity-ordering/source-evidence-manifest.json"
PROFILE = ROOT / "implementation/d4-eventing-async/source-evidence/capacity-ordering/benchmark-profile.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-sha", required=True)
    parser.add_argument("--workflow-run-id", required=True, type=int)
    parser.add_argument("--workflow-run-attempt", required=True, type=int)
    parser.add_argument("--job-id", required=True, type=int)
    parser.add_argument("--job-name", required=True)
    parser.add_argument("--kafka-image-digest", required=True)
    parser.add_argument("--benchmark-results", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    source = json.loads(MANIFEST.read_text())
    results_path = Path(args.benchmark_results)
    results = json.loads(results_path.read_text())
    assert results["numeric_authority"] == "test_values_only_not_production"

    out = {
        "schema": "d4a-capacity-ordering-source-run-provenance-v1",
        "repository_sha": args.repository_sha,
        "workflow_run_id": args.workflow_run_id,
        "workflow_run_attempt": args.workflow_run_attempt,
        "job_id": args.job_id,
        "job_name": args.job_name,
        "probe": "d4a_live_kafka_capacity_ordering",
        "candidate": source["candidate"],
        "candidate_image": source["candidate_image"],
        "candidate_image_digest": args.kafka_image_digest,
        "source_manifest_sha256": digest(MANIFEST),
        "benchmark_profile_sha256": digest(PROFILE),
        "benchmark_results_sha256": digest(results_path),
        "evidence_ids": source["evidence_ids"],
        "evidence_kinds": source["evidence_kinds"],
        "current_run_auto_credit": source["current_run_auto_credit"],
        "ledger_credit": source["ledger_credit"],
        "promotion_rule": source["promotion_rule"],
        "kafka_selection_state": source["kafka_selection_state"],
        "d4_transport_authority": source["d4_transport_authority"],
        "canonical_product_implementation_authority": source["canonical_product_implementation_authority"],
        "wave4_implementation_authority": source["wave4_implementation_authority"],
        "production_authority": source["production_authority"],
        "c3_numeric_topology_authority": source["c3_numeric_topology_authority"],
        "numeric_authority": results["numeric_authority"],
    }
    Path(args.output).write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(f"d4a_capacity_ordering_provenance=PASS sha={args.repository_sha} run={args.workflow_run_id} attempt={args.workflow_run_attempt} job={args.job_id} image_digest={args.kafka_image_digest}")


if __name__ == "__main__":
    main()
