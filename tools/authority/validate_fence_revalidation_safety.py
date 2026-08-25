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

_SET_LOCAL_TOKEN = "SET LOCAL event_triggers = off;"
_DDL_PATTERN = re.compile(
    r"(?im)^\s*(?:CREATE|ALTER|DROP|COMMENT|GRANT|REVOKE)\b"
)


def _event_trigger_guard_pattern(alias: str) -> re.Pattern[str]:
    return re.compile(
        r"SELECT\s+1\s*/\s*CASE\s+"
        r"WHEN\s+current_setting\s*\(\s*'event_triggers'\s*\)\s+IS\s+DISTINCT\s+FROM\s+'off'\s+THEN\s+0\s+"
        r"WHEN\s+EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+pg_catalog\.pg_event_trigger\s+et\s+"
        r"WHERE\s+et\.evtenabled\s*<>\s*'D'\s*\)\s+THEN\s+0\s+ELSE\s+1\s+END\s+AS\s+"
        + re.escape(alias)
        + r"\s*;",
        re.IGNORECASE | re.DOTALL,
    )


def _common_ddl_window_findings(
    text: str,
    *,
    label: str,
    guard_alias: str,
) -> tuple[str, list[str], re.Match[str] | None]:
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
        findings.append(
            f"Wave 1 fence {label} must start with exactly one explicit BEGIN transaction boundary"
        )
    if len(commit_matches) != 1 or not re.search(r"(?is)COMMIT\s*;\s*$", stripped):
        findings.append(
            f"Wave 1 fence {label} must end with exactly one explicit COMMIT transaction boundary"
        )
    if rollback_matches:
        findings.append(
            f"Wave 1 fence {label} canonical script must not contain an intermediate ROLLBACK boundary"
        )

    event_trigger_set_matches = re.findall(
        r"(?im)^\s*SET\s+(?:LOCAL\s+)?event_triggers\s*=\s*[^;]+;\s*$",
        code,
    )
    if (
        len(event_trigger_set_matches) != 1
        or event_trigger_set_matches[0].strip() != _SET_LOCAL_TOKEN
    ):
        findings.append(
            f"Wave 1 fence {label} must contain exactly one SET LOCAL event_triggers = off session guard"
        )

    event_match = _event_trigger_guard_pattern(guard_alias).search(code)
    if event_match is None:
        findings.append(
            f"Wave 1 fence {label} must prove event_triggers is locally disabled and reject pre-existing non-disabled PostgreSQL event triggers"
        )

    first_ddl = _DDL_PATTERN.search(code)
    if first_ddl is None:
        findings.append(f"Wave 1 fence {label} contains no protected DDL to validate")
    else:
        begin_pos = code.find("BEGIN;")
        set_pos = code.find(_SET_LOCAL_TOKEN)
        commit_pos = code.rfind("COMMIT;")
        if event_match is None or not (
            0 <= begin_pos < set_pos < event_match.start() < first_ddl.start() < commit_pos
        ):
            findings.append(
                f"Wave 1 fence {label} must establish transaction-local event-trigger disable and catalog preflight before its first DDL"
            )

    return code, findings, event_match


def validate_bootstrap_safety_text(text: str) -> list[str]:
    code, findings, _ = _common_ddl_window_findings(
        text,
        label="bootstrap",
        guard_alias="wave1_bootstrap_event_trigger_guard",
    )
    if not code:
        return findings

    first_schema = code.find("CREATE SCHEMA IF NOT EXISTS platform;")
    guard_pos = code.find("END AS wave1_bootstrap_event_trigger_guard;")
    commit_pos = code.rfind("COMMIT;")
    if not (0 <= guard_pos < first_schema < commit_pos):
        findings.append(
            "Wave 1 fence bootstrap event-trigger guard must complete before CREATE SCHEMA and remain inside the bootstrap transaction"
        )
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
        findings.append(
            "Wave 1 fence revalidation must hold ACCESS EXCLUSIVE lock across validation and constraint replacement"
        )
    else:
        begin_pos = code.find("BEGIN;")
        set_pos = code.find(_SET_LOCAL_TOKEN)
        lock_pos = code.find(lock)
        do_pos = code.find("DO $$")
        commit_pos = code.rfind("COMMIT;")
        if not (0 <= begin_pos < set_pos < lock_pos < do_pos < commit_pos):
            findings.append(
                "Wave 1 event-trigger disable/lock/validation/mutation ordering is not transactionally closed"
            )
        if event_match is not None and not (
            begin_pos < set_pos < event_match.start() < lock_pos < do_pos
        ):
            findings.append(
                "Wave 1 event-trigger session guard and catalog preflight must execute before fence lock/validation and DDL"
            )

    first_alter = code.find("ALTER TABLE platform.authority_fences")
    if first_alter >= 0:
        set_pos = code.find(_SET_LOCAL_TOKEN)
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
    print(
        "RESULT: PASS — bootstrap and revalidation both close event-trigger execution before DDL; revalidation also preserves atomic constraint replacement and logical-replication writer exclusion"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
