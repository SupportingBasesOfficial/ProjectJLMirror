#!/usr/bin/env python3
"""Observer-only safety checks for Wave 1 fence revalidation execution semantics."""

from __future__ import annotations

from pathlib import Path
import re

from tools.authority.fence_sql_contract import _executable_sql

ROOT = Path(__file__).resolve().parents[2]
SQL_PATH = ROOT / "sql" / "wave1" / "002_revalidate_authority_fence_contract.sql"


def validate_revalidation_safety_text(text: str) -> list[str]:
    if not isinstance(text, str):
        return ["Wave 1 fence revalidation safety contract must be text"]

    code = _executable_sql(text)
    if not code:
        return ["Wave 1 fence revalidation safety contract is malformed"]

    findings: list[str] = []
    normalized = " ".join(code.split())
    stripped = code.strip()

    begin_matches = re.findall(r"(?im)^\s*BEGIN\s*;\s*$", code)
    commit_matches = re.findall(r"(?im)^\s*COMMIT\s*;\s*$", code)
    rollback_matches = re.findall(r"(?im)^\s*ROLLBACK\s*;\s*$", code)

    if len(begin_matches) != 1 or not re.match(r"(?is)^BEGIN\s*;", stripped):
        findings.append(
            "Wave 1 fence revalidation must start with exactly one explicit BEGIN transaction boundary"
        )
    if len(commit_matches) != 1 or not re.search(r"(?is)COMMIT\s*;\s*$", stripped):
        findings.append(
            "Wave 1 fence revalidation must end with exactly one explicit COMMIT transaction boundary"
        )
    if rollback_matches:
        findings.append(
            "Wave 1 fence revalidation canonical script must not contain an intermediate ROLLBACK boundary"
        )

    lock = "LOCK TABLE platform.authority_fences IN ACCESS EXCLUSIVE MODE;"
    if lock not in code:
        findings.append(
            "Wave 1 fence revalidation must hold ACCESS EXCLUSIVE lock across validation and constraint replacement"
        )
    else:
        begin_pos = code.find("BEGIN;")
        lock_pos = code.find(lock)
        do_pos = code.find("DO $$")
        commit_pos = code.rfind("COMMIT;")
        if not (0 <= begin_pos < lock_pos < do_pos < commit_pos):
            findings.append(
                "Wave 1 fence revalidation lock/validation/mutation ordering is not transactionally closed"
            )

    replication_guard = re.compile(
        r"IF\s+EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+pg_catalog\.pg_subscription_rel\s+sr\s+"
        r"WHERE\s+sr\.srrelid\s*=\s*v_table\s*\)\s*THEN",
        re.IGNORECASE | re.DOTALL,
    )
    if replication_guard.search(code) is None:
        findings.append(
            "Wave 1 fence revalidation must reject logical-replication subscription mappings that can write authority_fences"
        )
    if "logical replication subscription can write authority_fences" not in code:
        findings.append(
            "Wave 1 fence revalidation must expose an explicit fail-closed logical-replication exception"
        )

    # Constraint replacement is safe only inside the single explicit transaction.
    drop_token = "DROP CONSTRAINT wave1_fence_scope_id_canonical"
    validate_token = "VALIDATE CONSTRAINT wave1_fence_state_canonical"
    if drop_token in normalized and validate_token in normalized:
        drop_pos = normalized.find(drop_token)
        validate_pos = normalized.find(validate_token)
        commit_pos = normalized.rfind("COMMIT;")
        if not (drop_pos < validate_pos < commit_pos):
            findings.append(
                "Wave 1 fence constraint replacement must complete validation before transaction commit"
            )

    return findings


def validate() -> list[str]:
    try:
        text = SQL_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"Wave 1 fence revalidation safety migration unreadable: {exc}"]
    return validate_revalidation_safety_text(text)


def main() -> int:
    findings = validate()
    print("JLMIRROR Wave 1 fence revalidation safety")
    if findings:
        for finding in findings:
            print(f"FINDING: {finding}")
        print(f"RESULT: FAIL — {len(findings)} finding(s)")
        return 1
    print("RESULT: PASS — atomic constraint replacement and logical-replication writer exclusion are enforced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
