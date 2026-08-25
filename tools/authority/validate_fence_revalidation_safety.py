#!/usr/bin/env python3
"""Observer-only safety checks for Wave 1 fence revalidation execution semantics."""

from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authority.fence_sql_contract import _executable_sql  # noqa: E402

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

    event_trigger_set_matches = re.findall(
        r"(?im)^\s*SET\s+(?:LOCAL\s+)?event_triggers\s*=\s*[^;]+;\s*$",
        code,
    )
    set_local_token = "SET LOCAL event_triggers = off;"
    if len(event_trigger_set_matches) != 1 or event_trigger_set_matches[0].strip() != set_local_token:
        findings.append(
            "Wave 1 fence revalidation must contain exactly one SET LOCAL event_triggers = off session guard"
        )

    event_trigger_guard = re.compile(
        r"SELECT\s+1\s*/\s*CASE\s+"
        r"WHEN\s+current_setting\s*\(\s*'event_triggers'\s*\)\s+IS\s+DISTINCT\s+FROM\s+'off'\s+THEN\s+0\s+"
        r"WHEN\s+EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+pg_catalog\.pg_event_trigger\s+et\s+"
        r"WHERE\s+et\.evtenabled\s*<>\s*'D'\s*\)\s+THEN\s+0\s+ELSE\s+1\s+END\s+AS\s+wave1_event_trigger_guard\s*;",
        re.IGNORECASE | re.DOTALL,
    )
    event_match = event_trigger_guard.search(code)
    if event_match is None:
        findings.append(
            "Wave 1 fence revalidation must prove event_triggers is locally disabled and reject pre-existing non-disabled PostgreSQL event triggers"
        )

    lock = "LOCK TABLE platform.authority_fences IN ACCESS EXCLUSIVE MODE;"
    if lock not in code:
        findings.append(
            "Wave 1 fence revalidation must hold ACCESS EXCLUSIVE lock across validation and constraint replacement"
        )
    else:
        begin_pos = code.find("BEGIN;")
        set_pos = code.find(set_local_token)
        lock_pos = code.find(lock)
        do_pos = code.find("DO $$")
        commit_pos = code.rfind("COMMIT;")
        if not (0 <= begin_pos < set_pos < lock_pos < do_pos < commit_pos):
            findings.append(
                "Wave 1 event-trigger disable/lock/validation/mutation ordering is not transactionally closed"
            )
        if event_match is not None and not (begin_pos < set_pos < event_match.start() < lock_pos < do_pos):
            findings.append(
                "Wave 1 event-trigger session guard and catalog preflight must execute before fence lock/validation and DDL"
            )

    first_alter = code.find("ALTER TABLE platform.authority_fences")
    if first_alter >= 0:
        set_pos = code.find(set_local_token)
        if set_pos < 0 or set_pos > first_alter:
            findings.append(
                "Wave 1 SET LOCAL event_triggers = off guard must execute before the first fence ALTER TABLE statement"
            )
        if event_match is not None and event_match.start() > first_alter:
            findings.append(
                "Wave 1 event-trigger catalog preflight must execute before the first fence ALTER TABLE statement"
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
    print(
        "RESULT: PASS — session-local event-trigger execution closure, catalog preflight, atomic constraint replacement and logical-replication writer exclusion are enforced"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
