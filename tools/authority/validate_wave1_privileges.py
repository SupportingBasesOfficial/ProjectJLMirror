#!/usr/bin/env python3
"""Observer-only validation for the Wave 1 IR-D-003 privilege boundary."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authority.fence_sql_contract import _executable_sql  # noqa: E402

PROFILE = "jlmirror-wave1-fence-privileges/v1"
SQL_PATH = ROOT / "sql" / "wave1" / "003_revalidate_authority_fence_privileges.sql"
BOUNDARY_PATH = ROOT / "implementation" / "wave-1" / "FENCE_PRIVILEGE_BOUNDARY.md"

REQUIRED_EXECUTABLE_FRAGMENTS = (
    "BEGIN;",
    "SET LOCAL search_path = pg_catalog;",
    "pg_catalog.to_regnamespace('platform')",
    "pg_catalog.to_regclass('platform.authority_fences')",
    "pg_catalog.to_regprocedure(\n        'platform.initialize_authority_fence(text,text,text)'\n    )",
    "pg_catalog.to_regprocedure(\n        'platform.advance_authority_fence(text,bigint,text,text,text)'\n    )",
    "FROM pg_catalog.pg_namespace n",
    "FROM pg_catalog.pg_class c",
    "FROM pg_catalog.pg_auth_members m",
    "pg_catalog.to_regrole('pg_read_all_data')::oid",
    "pg_catalog.to_regrole('pg_write_all_data')::oid",
    "RAISE EXCEPTION 'non-owner role can reach PostgreSQL predefined all-data authority'",
    "FROM pg_catalog.pg_attribute a",
    "pg_catalog.aclexplode(a.attacl)",
    "RAISE EXCEPTION 'authority_fences has inherited non-owner column privileges'",
    "FROM pg_catalog.pg_proc p",
    "p.proowner OPERATOR(pg_catalog.=) current_user::pg_catalog.regrole::oid",
    "RAISE EXCEPTION 'database contains migration-owner SECURITY DEFINER routine'",
    "p.proconfig IS DISTINCT FROM ARRAY['search_path=pg_catalog']::text[]",
    "RAISE EXCEPTION 'fence authority functions must retain exact pg_catalog-only search_path'",
    "COMMIT;",
)

REQUIRED_BOUNDARY_TOKENS = (
    "TABLE ACL CLEAN != COLUMN ACL CLEAN",
    "OBJECT ACL CLEAN != PREDEFINED ALL-DATA ROLE ABSENT",
    "EXPECTED FUNCTION ACL CLEAN != RESIDUAL DEFINER AUTHORITY ABSENT",
    "SCHEMA LOCATION != DEFINER AUTHORITY BOUNDARY",
    "LOCAL FENCE RULE CLEAN != EXTERNAL REWRITE REACHABILITY ABSENT",
    "pg_class.relacl",
    "pg_attribute.attacl",
    "pg_read_all_data",
    "pg_write_all_data",
    "pg_auth_members",
    "pg_proc.prosecdef",
    "pg_rewrite",
    "pg_depend",
    "attnum > 0",
    "NOT attisdropped",
    "PUBLIC (`oid 0`)",
    "SCHEMA/TABLE/COLUMN/FUNCTION ACL CLEAN != FUTURE C2 ROLE MAPPING",
    "PRIVILEGE REVALIDATION PASS != RUNTIME DATABASE AUTHORITY",
)

FORBIDDEN_EXECUTABLE_FRAGMENTS = (
    "GRANT ",
    "ALTER OWNER",
    "SET ROLE",
)


def validate_text(text: object) -> list[str]:
    if not isinstance(text, str):
        return ["Wave 1 fence privilege contract must be text"]
    code = _executable_sql(text)
    if not code:
        return ["Wave 1 fence privilege contract is malformed or cannot be parsed conservatively"]

    findings = [
        f"Wave 1 fence privilege invariant missing: {fragment}"
        for fragment in REQUIRED_EXECUTABLE_FRAGMENTS
        if fragment not in code
    ]
    if code.count("SET LOCAL search_path = pg_catalog;") != 1:
        findings.append("Wave 1 fence privilege migration must pin exactly one transaction-local pg_catalog search_path")
    upper_code = code.upper()
    findings.extend(
        f"Wave 1 fence privilege contract must not mutate C2 role mapping: {fragment.strip()}"
        for fragment in FORBIDDEN_EXECUTABLE_FRAGMENTS
        if fragment in upper_code
    )
    return findings


def validate_boundary_text(text: object) -> list[str]:
    if not isinstance(text, str):
        return ["Wave 1 fence privilege boundary must be text"]
    return [
        f"Wave 1 fence privilege boundary missing: {token}"
        for token in REQUIRED_BOUNDARY_TOKENS
        if token not in text
    ]


def validate() -> list[str]:
    findings: list[str] = []
    try:
        text = SQL_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        findings.append(f"Wave 1 fence privilege contract unreadable: {exc}")
    else:
        findings.extend(validate_text(text))
    try:
        boundary = BOUNDARY_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        findings.append(f"Wave 1 fence privilege boundary unreadable: {exc}")
    else:
        findings.extend(validate_boundary_text(boundary))
    return findings


def main() -> int:
    findings = validate()
    print(f"JLMIRROR Wave 1 fence privilege profile: {PROFILE}")
    print(f"Repository root: {ROOT}")
    if findings:
        print("RESULT: FAIL")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("RESULT: PASS — fence ownership/reachability/ACL/definer checks and exact pg_catalog-only function resolution fail closed before C2 role mapping")
    print("NOTE: PASS is conformance evidence only; it grants no runtime/database privilege.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
