#!/usr/bin/env python3
"""Observer-only logical-replication authority validation for Wave 1 fencing."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authority.fence_sql_contract import _executable_sql  # noqa: E402

PROFILE = "jlmirror-wave1-fence-logical-replication/v1"
BOOTSTRAP_PATH = ROOT / "sql" / "wave1" / "001_platform_authority_fence.sql"
REUSE_PATH = ROOT / "sql" / "wave1" / "002_revalidate_authority_fence_contract.sql"
BOUNDARY_PATH = ROOT / "implementation" / "wave-1" / "FENCE_LOGICAL_REPLICATION_BOUNDARY.md"

REQUIRED_LAWS = (
    "ACL CLEAN != LOGICAL REPLICATION DISCLOSURE ABSENT",
    "INBOUND REPLICATION WRITER ABSENT != OUTBOUND PUBLICATION ABSENT",
    "PUBLICATION CATALOG SNAPSHOT CLEAN != CONCURRENT SUPERUSER AUTHORITY ABSENT",
    "TABLE LOCK HELD != DATABASE ADMIN AUTHORITY REVOKED",
    "WAVE 1 REPLICATION PREFLIGHT != C2 DATABASE ROLE MAPPING",
    "STATIC PREFLIGHT PASS != FUTURE ADMINISTRATIVE AUTHORITY ABSENCE",
)


def _code(text: object, label: str) -> tuple[str, list[str]]:
    if not isinstance(text, str):
        return "", [f"{label} must be text"]
    code = _executable_sql(text)
    if not code:
        return "", [f"{label} is malformed or cannot be parsed conservatively"]
    return code, []


def validate_bootstrap_publication_text(text: object) -> list[str]:
    code, findings = _code(text, "Wave 1 fresh fence publication contract")
    if findings:
        return findings

    if code.count("BEGIN;") != 1:
        findings.append("Wave 1 fresh fence publication contract must have exactly one BEGIN")
    if code.count("COMMIT;") != 1:
        findings.append("Wave 1 fresh fence publication contract must have exactly one COMMIT")

    first_create = code.find("EXECUTE 'CREATE SCHEMA platform'")
    if first_create < 0:
        findings.append("Wave 1 fresh fence publication contract lost first persistent CREATE anchor")

    required = (
        "FROM pg_catalog.pg_publication p",
        "WHERE p.puballtables",
        "Wave 1 fence fresh bootstrap rejects FOR ALL TABLES publication authority before fence creation",
    )
    positions: list[int] = []
    for token in required:
        pos = code.find(token)
        if pos < 0:
            findings.append(f"Wave 1 fresh fence publication invariant missing: {token}")
        else:
            positions.append(pos)
    if first_create >= 0 and positions and max(positions) > first_create:
        findings.append("Wave 1 fresh publication disclosure preflight must execute before first persistent CREATE")
    return findings


def _reuse_structural_block(code: str) -> tuple[str, list[str]]:
    start_marker = "DO $wave1_revalidate$"
    end_marker = "$wave1_revalidate$;"
    start = code.find(start_marker)
    if start < 0:
        return "", ["Wave 1 reuse logical-replication contract lost structural preflight block"]
    end = code.find(end_marker, start)
    if end < 0:
        return "", ["Wave 1 reuse logical-replication contract structural preflight is unterminated"]
    return code[start : end + len(end_marker)], []


def validate_reuse_publication_text(text: object) -> list[str]:
    code, findings = _code(text, "Wave 1 reused fence publication contract")
    if findings:
        return findings

    if code.count("BEGIN;") != 1:
        findings.append("Wave 1 reused fence publication contract must have exactly one BEGIN")
    if code.count("COMMIT;") != 1:
        findings.append("Wave 1 reused fence publication contract must have exactly one COMMIT")

    lock = "LOCK TABLE platform.authority_fences IN ACCESS EXCLUSIVE MODE;"
    lock_pos = code.find(lock)
    if lock_pos < 0:
        findings.append("Wave 1 reused fence publication contract requires ACCESS EXCLUSIVE lock")

    block, block_findings = _reuse_structural_block(code)
    findings.extend(block_findings)
    if not block:
        return findings

    block_pos = code.find("DO $wave1_revalidate$")
    first_mutation = code.find("ALTER TABLE platform.authority_fences")
    if first_mutation < 0:
        findings.append("Wave 1 reused fence publication contract lost canonical mutation anchor")
    if lock_pos >= 0 and block_pos >= 0 and lock_pos > block_pos:
        findings.append("Wave 1 reused fence publication preflight must run under the held table lock")
    if first_mutation >= 0 and block_pos > first_mutation:
        findings.append("Wave 1 reused fence publication preflight must precede canonical mutation")

    required = (
        "FROM pg_catalog.pg_subscription_rel sr",
        "sr.srrelid OPERATOR(pg_catalog.=) v_table",
        "logical replication subscription can write authority_fences",
        "FROM pg_catalog.pg_publication_rel pr",
        "pr.prrelid OPERATOR(pg_catalog.=) v_table",
        "logical replication publication can disclose authority_fences explicitly",
        "FROM pg_catalog.pg_publication p",
        "WHERE p.puballtables",
        "FOR ALL TABLES publication can disclose authority_fences",
        "pg_catalog.to_regclass('pg_catalog.pg_publication_namespace') IS NOT NULL",
        "FROM pg_catalog.pg_publication_namespace pn",
        "pn.pnnspid OPERATOR(pg_catalog.=) $1",
        "USING v_schema",
        "schema publication can disclose platform.authority_fences",
    )
    for token in required:
        if token not in block:
            findings.append(f"Wave 1 reused fence publication invariant missing from locked pre-mutation block: {token}")
    return findings


def validate_boundary_text(text: object) -> list[str]:
    if not isinstance(text, str):
        return ["Wave 1 fence logical-replication boundary must be text"]
    return [
        f"Wave 1 fence logical-replication boundary missing law: {law}"
        for law in REQUIRED_LAWS
        if law not in text
    ]


def validate() -> list[str]:
    findings: list[str] = []
    try:
        bootstrap = BOOTSTRAP_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        findings.append(f"Wave 1 fresh fence SQL unreadable: {exc}")
    else:
        findings.extend(validate_bootstrap_publication_text(bootstrap))
    try:
        reuse = REUSE_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        findings.append(f"Wave 1 reused fence SQL unreadable: {exc}")
    else:
        findings.extend(validate_reuse_publication_text(reuse))
    try:
        boundary = BOUNDARY_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        findings.append(f"Wave 1 logical-replication boundary unreadable: {exc}")
    else:
        findings.extend(validate_boundary_text(boundary))
    return findings


def main() -> int:
    findings = validate()
    print(f"JLMIRROR Wave 1 fence logical-replication profile: {PROFILE}")
    print(f"Repository root: {ROOT}")
    if findings:
        print("RESULT: FAIL")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("RESULT: PASS — fresh/reused fence logical-replication writer and disclosure surfaces fail closed before authority mutation")
    print("NOTE: PASS proves static migration conformance only; C2 database/admin authority remains separately governed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())