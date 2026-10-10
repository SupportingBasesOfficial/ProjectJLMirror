#!/usr/bin/env python3
"""
G11 scope validator: ensures all required deliverables exist and no scope
violations are present in the incident response gate implementation.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REQUIRED = [
    "apps/g11-incident-response/domain.py",
    "apps/g11-incident-response/service.py",
    "apps/g11-incident-response/pg_port.py",
    "apps/g11-incident-response/http_app.py",
    "apps/g11-incident-response/worker.py",
    "apps/g11-incident-response/runtime_entry.py",
    "sql/incident_response/001_incident_response.sql",
    "tests/g11/__init__.py",
    "tests/g11/test_domain.py",
    "tests/g11/test_http_e2e.py",
    "tests/g11/test_worker.py",
    "implementation/g11-incident-response/IMPLEMENTATION_CLAIM.json",
]

FORBIDDEN_IMPORTS = [
    ("apps/g11-incident-response/domain.py",  ["psycopg", "fastapi", "httpx", "requests"]),
    ("apps/g11-incident-response/service.py", ["psycopg", "fastapi", "httpx", "requests"]),
]

FORBIDDEN_SCHEMA_ACCESS = [
    # g11 domain files must not directly reference other gate schemas
    ("apps/g11-incident-response/domain.py",  ["alerting.", "itsm.", "notification.", "human_operations."]),
    ("apps/g11-incident-response/service.py", ["alerting.", "itsm.", "notification.", "human_operations."]),
    ("apps/g11-incident-response/pg_port.py", ["alerting.", "itsm.", "notification.", "human_operations."]),
]


def check_deliverables() -> list[str]:
    missing = []
    for rel in REQUIRED:
        if not (ROOT / rel).exists():
            missing.append(rel)
    return missing


def check_forbidden_imports() -> list[str]:
    violations = []
    for rel, forbidden in FORBIDDEN_IMPORTS:
        path = ROOT / rel
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        for pkg in forbidden:
            if f"import {pkg}" in content or f"from {pkg}" in content:
                violations.append(f"{rel}: forbidden import '{pkg}'")
    return violations


def check_schema_isolation() -> list[str]:
    violations = []
    for rel, forbidden_schemas in FORBIDDEN_SCHEMA_ACCESS:
        path = ROOT / rel
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        for schema in forbidden_schemas:
            if schema in content:
                violations.append(f"{rel}: direct reference to forbidden schema '{schema}'")
    return violations


def check_claim() -> list[str]:
    claim_path = ROOT / "implementation/g11-incident-response/IMPLEMENTATION_CLAIM.json"
    if not claim_path.exists():
        return ["IMPLEMENTATION_CLAIM.json missing"]
    try:
        claim = json.loads(claim_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"IMPLEMENTATION_CLAIM.json invalid JSON: {e}"]
    issues = []
    if claim.get("gate") != "g11-incident-response":
        issues.append("claim.gate mismatch")
    if claim.get("status") != "implemented":
        issues.append("claim.status not 'implemented'")
    if claim.get("test_results", {}).get("failed", 1) != 0:
        issues.append("claim.test_results.failed must be 0")
    return issues


def main() -> None:
    all_issues: list[str] = []
    all_issues.extend(check_deliverables())
    all_issues.extend(check_forbidden_imports())
    all_issues.extend(check_schema_isolation())
    all_issues.extend(check_claim())

    print(f"G11 scope validation: {len(REQUIRED)} deliverables checked")
    if all_issues:
        print(f"VIOLATIONS ({len(all_issues)}):")
        for v in all_issues:
            print(f"  - {v}")
        sys.exit(1)
    else:
        print("OK — 0 violations")


if __name__ == "__main__":
    main()
