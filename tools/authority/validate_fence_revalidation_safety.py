#!/usr/bin/env python3
"""Observer-only safety checks for Wave 1 fence DDL execution semantics."""

from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authority.fence_sql_contract import _executable_sql  # noqa: E402

BOOTSTRAP_SQL_PATH = ROOT / "sql" / "wave1" / "001_platform_authority_fence.sql"
REVALIDATION_SQL_PATH = ROOT / "sql" / "wave1" / "002_revalidate_authority_fence_contract.sql"

_EVENT_TRIGGER_SET = "SET LOCAL event_triggers = off;"
_TRUSTED_SEARCH_PATH_SET = "SET LOCAL search_path = pg_catalog;"
_DDL_PATTERN = re.compile(r"(?im)^\s*(?:CREATE|ALTER|DROP|COMMENT|GRANT|REVOKE)\b")


def _event_trigger_guard_pattern(alias: str) -> re.Pattern[str]:
    return re.compile(
        r"SELECT\s+1\s*/\s*CASE\s+"
        r"WHEN\s+pg_catalog\.current_setting\s*\(\s*'event_triggers'\s*\)\s+IS\s+DISTINCT\s+FROM\s+'off'\s+THEN\s+0\s+"
        r"WHEN\s+EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+pg_catalog\.pg_event_trigger\s+et\s+"
        r"WHERE\s+et\.evtenabled\s+OPERATOR\s*\(\s*pg_catalog\.<>\s*\)\s*'D'\s*\)\s+THEN\s+0\s+ELSE\s+1\s+END\s+AS\s+"
        + re.escape(alias)
        + r"\s*;",
        re.IGNORECASE | re.DOTALL,
    )


def _common_ddl_window_findings(text: str, *, label: str, guard_alias: str) -> tuple[str, list[str], re.Match[str] | None]:
    if not isinstance(text, str):
        return "", [f"Wave 1 fence {label} safety contract must be text"], None

    code = _executable_sql(text)
    if not code:
        return "", [f"Wave 1 fence {label} safety contract is malformed"], None

    findings: list[str] = []
    stripped = code.strip()
    begin_matches = re.findall(r"(?im)^\s*BEGIN\s*;\s*$", code)
    commit_matches = re.findall(r"(?im)^\s*COMMIT\s*;\s*$", code)
    rollback_matches = re.findall(r"(?im)^\s*ROLLBACK\s*;\s*$", code)

    if len(begin_matches) != 1 or not re.match(r"(?is)^BEGIN\s*;", stripped):
        findings.append(f"Wave 1 fence {label} must start with exactly one explicit BEGIN transaction boundary")
    if len(commit_matches) != 1 or not re.search(r"(?is)COMMIT\s*;\s*$", stripped):
        findings.append(f"Wave 1 fence {label} must end with exactly one explicit COMMIT transaction boundary")
    if rollback_matches:
        findings.append(f"Wave 1 fence {label} canonical script must not contain an intermediate ROLLBACK boundary")

    event_sets = re.findall(r"(?im)^\s*SET\s+(?:LOCAL\s+)?event_triggers\s*=\s*[^;]+;\s*$", code)
    if len(event_sets) != 1 or event_sets[0].strip() != _EVENT_TRIGGER_SET:
        findings.append(f"Wave 1 fence {label} must contain exactly one SET LOCAL event_triggers = off session guard")

    search_sets = re.findall(r"(?im)^\s*SET\s+(?:LOCAL\s+)?search_path\s*=\s*[^;]+;\s*$", code)
    if len(search_sets) != 1 or search_sets[0].strip() != _TRUSTED_SEARCH_PATH_SET:
        findings.append(f"Wave 1 fence {label} must contain exactly one SET LOCAL search_path = pg_catalog trusted-resolution guard")

    event_match = _event_trigger_guard_pattern(guard_alias).search(code)
    if event_match is None:
        findings.append(f"Wave 1 fence {label} must prove event_triggers is locally disabled and reject pre-existing non-disabled PostgreSQL event triggers")

    first_ddl = _DDL_PATTERN.search(code)
    if first_ddl is None:
        findings.append(f"Wave 1 fence {label} contains no protected DDL to validate")
    else:
        begin_pos = code.find("BEGIN;")
        event_set_pos = code.find(_EVENT_TRIGGER_SET)
        search_set_pos = code.find(_TRUSTED_SEARCH_PATH_SET)
        commit_pos = code.rfind("COMMIT;")
        if event_match is None or not (0 <= begin_pos < event_set_pos < search_set_pos < event_match.start() < first_ddl.start() < commit_pos):
            findings.append(f"Wave 1 fence {label} must establish transaction-local event-trigger disable, trusted pg_catalog search_path and catalog preflight before its first DDL")

    return code, findings, event_match


def validate_bootstrap_safety_text(text: str) -> list[str]:
    code, findings, event_match = _common_ddl_window_findings(
        text,
        label="bootstrap",
        guard_alias="wave1_bootstrap_event_trigger_guard",
    )
    if not code:
        return findings

    reuse_guard = re.compile(
        r"v_existing_table\s+pg_catalog\.regclass\s*:=\s*pg_catalog\.to_regclass\s*\(\s*'platform\.authority_fences'\s*\)\s*;.*?"
        r"IF\s+v_existing_table\s+IS\s+NOT\s+NULL\s+THEN\s+RETURN\s*;\s+END\s+IF\s*;",
        re.IGNORECASE | re.DOTALL,
    )
    reuse_match = reuse_guard.search(code)
    if reuse_match is None:
        findings.append("Wave 1 fence bootstrap must be fresh-only: existing authority_fences must return before persistent object mutation")
    else:
        first_execute = code.find("EXECUTE", reuse_match.end())
        first_ddl = _DDL_PATTERN.search(code)
        if first_execute < 0 or (first_ddl is not None and reuse_match.end() > first_ddl.start()):
            findings.append("Wave 1 fence bootstrap reuse guard must precede every persistent bootstrap mutation")

    required_fresh_only = (
        "EXECUTE 'CREATE SCHEMA IF NOT EXISTS platform'",
        "EXECUTE 'REVOKE CREATE ON SCHEMA platform FROM PUBLIC'",
        "SET search_path = pg_catalog",
        "OPERATOR(pg_catalog.~)",
        "pg_catalog.btrim",
        "pg_catalog.statement_timestamp()",
    )
    for token in required_fresh_only:
        if token not in code:
            findings.append(f"Wave 1 fence bootstrap trusted/fresh-only invariant missing: {token}")

    guard_pos = code.find("END AS wave1_bootstrap_event_trigger_guard;")
    do_pos = code.find("DO $wave1_bootstrap$")
    if event_match is None or not (0 <= guard_pos < do_pos):
        findings.append("Wave 1 fence bootstrap event-trigger guard must complete before the fresh/reuse branch")
    return findings


def validate_revalidation_safety_text(text: str) -> list[str]:
    code, findings, event_match = _common_ddl_window_findings(
        text,
        label="revalidation",
        guard_alias="wave1_event_trigger_guard",
    )
    if not code:
        return findings

    normalized = " ".join(code.split())
    lock = "LOCK TABLE platform.authority_fences IN ACCESS EXCLUSIVE MODE;"
    if lock not in code:
        findings.append("Wave 1 fence revalidation must hold ACCESS EXCLUSIVE lock across validation and canonicalization")
    else:
        begin_pos = code.find("BEGIN;")
        event_set_pos = code.find(_EVENT_TRIGGER_SET)
        search_set_pos = code.find(_TRUSTED_SEARCH_PATH_SET)
        lock_pos = code.find(lock)
        do_pos = code.find("DO $wave1_revalidate$")
        commit_pos = code.rfind("COMMIT;")
        if not (0 <= begin_pos < event_set_pos < search_set_pos < lock_pos < do_pos < commit_pos):
            findings.append("Wave 1 event-trigger/search-path/lock/validation/mutation ordering is not transactionally closed")
        if event_match is not None and not (search_set_pos < event_match.start() < lock_pos < do_pos):
            findings.append("Wave 1 event-trigger catalog preflight must execute before fence lock/validation and DDL")

    required = (
        "pg_catalog.pg_depend",
        "pg_catalog.pg_proc",
        "pg_catalog.pg_operator",
        "pg_catalog.pg_collation",
        "CHECK expression depends on noncanonical function/operator/collation authority",
        "SET search_path = pg_catalog",
        "OPERATOR(pg_catalog.~)",
        "pg_catalog.btrim",
        "CREATE OR REPLACE FUNCTION platform.initialize_authority_fence",
        "CREATE OR REPLACE FUNCTION platform.advance_authority_fence",
    )
    for token in required:
        if token not in code:
            findings.append(f"Wave 1 fence revalidation trusted-resolution invariant missing: {token}")

    replication_guard = re.compile(
        r"IF\s+EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+pg_catalog\.pg_subscription_rel\s+sr\s+"
        r"WHERE\s+sr\.srrelid\s+OPERATOR\s*\(\s*pg_catalog\.=\s*\)\s*v_table\s*\)\s*THEN",
        re.IGNORECASE | re.DOTALL,
    )
    if replication_guard.search(code) is None:
        findings.append("Wave 1 fence revalidation must reject logical-replication subscription mappings that can write authority_fences")

    drop_token = "DROP CONSTRAINT wave1_fence_scope_id_canonical"
    validate_token = "VALIDATE CONSTRAINT wave1_fence_state_canonical"
    if drop_token in normalized and validate_token in normalized:
        drop_pos = normalized.find(drop_token)
        validate_pos = normalized.find(validate_token)
        function_pos = normalized.find("CREATE OR REPLACE FUNCTION platform.initialize_authority_fence")
        commit_pos = normalized.rfind("COMMIT;")
        if not (drop_pos < validate_pos < function_pos < commit_pos):
            findings.append("Wave 1 fence reuse validation/canonicalization must finish before function replacement and transaction commit")

    return findings


def validate() -> list[str]:
    findings: list[str] = []
    try:
        bootstrap_text = BOOTSTRAP_SQL_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        findings.append(f"Wave 1 fence bootstrap safety migration unreadable: {exc}")
    else:
        findings.extend(validate_bootstrap_safety_text(bootstrap_text))

    try:
        revalidation_text = REVALIDATION_SQL_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        findings.append(f"Wave 1 fence revalidation safety migration unreadable: {exc}")
    else:
        findings.extend(validate_revalidation_safety_text(revalidation_text))
    return findings


def main() -> int:
    findings = validate()
    print("JLMIRROR Wave 1 fence DDL execution safety")
    if findings:
        for finding in findings:
            print(f"FINDING: {finding}")
        print(f"RESULT: FAIL — {len(findings)} finding(s)")
        return 1
    print("RESULT: PASS — bootstrap is fresh-only on reuse; both migrations pin pg_catalog resolution and close event-trigger DDL windows; revalidation validates reused authority before canonical mutation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
