from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE_MANIFEST = ROOT / "implementation/d4-eventing-async/source-evidence/semantic-boundary/source-evidence-manifest.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit resolved immutable D4-A source-run provenance")
    parser.add_argument("--repository-sha", required=True)
    parser.add_argument("--workflow-run-id", required=True, type=int)
    parser.add_argument("--workflow-run-attempt", required=True, type=int)
    parser.add_argument("--job-id", required=True, type=int)
    parser.add_argument("--job-name", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    manifest_bytes = SOURCE_MANIFEST.read_bytes()
    manifest = json.loads(manifest_bytes)
    provenance_contract = manifest["source_run_provenance"]
    if provenance_contract.get("mode") != "runtime_resolved_artifact_required":
        raise SystemExit("source manifest does not require runtime-resolved provenance")

    output = {
        "schema_version": 1,
        "artifact_schema": "d4a-source-run-provenance-v1",
        "repository_sha": args.repository_sha,
        "workflow_run_id": args.workflow_run_id,
        "workflow_run_attempt": args.workflow_run_attempt,
        "job_id": args.job_id,
        "job_name": args.job_name,
        "probe": "tools/assurance/d4a_semantic_boundary/test_semantic_boundary.py",
        "source_manifest_path": SOURCE_MANIFEST.relative_to(ROOT).as_posix(),
        "source_manifest_sha256": sha256(manifest_bytes).hexdigest(),
        "evidence_ids": manifest["evidence_ids"],
        "evidence_kinds": manifest["evidence_kinds"],
        "current_run_auto_credit": False,
        "ledger_credit": [],
        "promotion_rule": manifest["promotion_rule"],
    }
    required = set(provenance_contract["required_fields"])
    missing = sorted(required - set(output))
    if missing:
        raise SystemExit(f"resolved provenance missing fields: {missing}")
    if len(args.repository_sha) != 40 or any(ch not in "0123456789abcdef" for ch in args.repository_sha):
        raise SystemExit("repository SHA must be exact lowercase 40-hex commit")
    if args.workflow_run_id <= 0 or args.workflow_run_attempt <= 0 or args.job_id <= 0:
        raise SystemExit("workflow/job provenance identifiers must be positive")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "d4a_source_provenance=PASS "
        f"sha={args.repository_sha} run_id={args.workflow_run_id} job_id={args.job_id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
