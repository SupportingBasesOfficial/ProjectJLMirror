#!/usr/bin/env python3
"""Observer-only validation for the Wave 0 contract conformance substrate."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.contracts.core import (  # noqa: E402
    ContractProjectionError,
    build_bundle,
    canonical_json,
)

PROFILE = "jlmirror-contract-tooling/v1"


def validate(root: Path) -> list[str]:
    findings: list[str] = []
    try:
        first = build_bundle(root)
        second = build_bundle(root)
    except ContractProjectionError as exc:
        return [str(exc)]

    if canonical_json(first) != canonical_json(second):
        findings.append("generated contract bundle is not deterministic")

    records = first["profile_catalog"]["records"]
    ids = [record["id"] for record in records]
    if not ids:
        findings.append("generated profile catalog is empty")
    if len(ids) != len(set(ids)):
        findings.append("generated profile catalog contains duplicate IDs")

    required_catalog_ids = {
        "impl.contract-tooling@1",
        "runtime.web-bff@1",
        "environment.production@1",
    }
    missing = sorted(required_catalog_ids - set(ids))
    if missing:
        findings.append(
            f"required anchor IDs missing from generated catalog: {missing}"
        )

    http_required = set(first["http_endpoint_manifest_schema"]["required"])
    for field in (
        "owner_domain",
        "tenant_scope",
        "idempotency_class",
        "data_classification",
    ):
        if field not in http_required:
            findings.append(
                f"HTTP endpoint manifest projection missing required field: {field}"
            )

    event_required = set(first["event_contract_manifest_schema"]["required"])
    for field in (
        "contract_name",
        "contract_version",
        "message_class",
        "delivery_semantics",
        "data_classification",
    ):
        if field not in event_required:
            findings.append(
                f"event manifest projection missing required field: {field}"
            )

    if first["authority"] != "projection_only_reviewed_markdown_remains_normative":
        findings.append("generated bundle authority boundary is missing")

    return findings


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT
    findings = validate(root)
    print(f"JLMIRROR contract tooling profile: {PROFILE}")
    print(f"Repository root: {root}")
    if findings:
        for finding in findings:
            print(f"FINDING: {finding}")
        print(f"RESULT: FAIL — {len(findings)} finding(s)")
        return 1
    print(
        "RESULT: PASS — contract projections and anchor invariants are deterministic"
    )
    print(
        "NOTE: PASS is conformance evidence only; reviewed contracts remain normative."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
