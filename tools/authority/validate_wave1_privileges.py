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

SCHEMA_OWNER_GUARD = """SELECT n.nspowner
          FROM pg_namespace n
         WHERE n.oid = v_schema
    ) IS DISTINCT FROM current_user::regrole::oid"""
TABLE_OWNER_GUARD = """SELECT c.relowner
          FROM pg_class c
         WHERE c.oid = v_table
    ) IS DISTINCT FROM current_user::regrole::oid"""
ROLE_MEMBERSHIP_GUARD = """WITH RECURSIVE owner_role_members(member_oid) AS (
            SELECT m.member
              FROM pg_auth_members m
             WHERE m.roleid = current_user::regrole::oid
            UNION
            SELECT m.member
              FROM pg_auth_members m
              JOIN owner_role_members r
                ON m.roleid = r.member_oid
        )
        SELECT 1
          FROM owner_role_members"""
COLUMN_ACL_GUARD = """FROM pg_attribute a
          CROSS JOIN LATERAL aclexplode(a.attacl) AS acl
         WHERE a.attrelid = v_table
           AND a.attnum > 0
           AND NOT a.attisdropped
           AND a.attacl IS NOT NULL
           AND acl.grantee <> current_user::regrole::oid"""

REQUIRED_EXECUTABLE_FRAGMENTS = (
    "to_regnamespace('platform')",
    "to_regclass('platform.authority_fences')",
    "to_regprocedure(\n        'platform.initialize_authority_fence(text,text,text)'\n    )",
    "to_regprocedure(\n        'platform.advance_authority_fence(text,bigint,text,text,text)'\n    )",
    SCHEMA_OWNER_GUARD,
    TABLE_OWNER_GUARD,
    ROLE_MEMBERSHIP_GUARD,
    "aclexplode(\n              COALESCE(c.relacl, acldefault('r', c.relowner))\n          )",
    "acl.grantee <> c.relowner",
    COLUMN_ACL_GUARD,
    "RAISE EXCEPTION 'authority_fences has inherited non-owner column privileges'",
    "aclexplode(\n              COALESCE(n.nspacl, acldefault('n', n.nspowner))\n          )",
    "acl.grantee <> n.nspowner",
    "FROM pg_proc p",
    "p.proowner <> current_user::regrole::oid",
    "aclexplode(\n              COALESCE(p.proacl, acldefault('f', p.proowner))\n          )",
    "acl.grantee <> p.proowner",
    "p.prosecdef",
)

REQUIRED_BOUNDARY_TOKENS = (
    "TABLE ACL CLEAN != COLUMN ACL CLEAN",
    "pg_class.relacl",
    "pg_attribute.attacl",
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
    print("RESULT: PASS — fence ownership, role-membership, object ACL and column ACL reuse fail closed before C2 role mapping")
    print("NOTE: PASS is conformance evidence only; it grants no runtime/database privilege.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
