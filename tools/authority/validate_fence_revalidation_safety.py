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

    local_search_sets = re.findall(r"(?im)^\s*SET\s+LOCAL\s+search_path\s*=\s*[^;]+;\s*$", code)
    if len(local_search_sets) != 1 or local_search_sets[0].strip() != _TRUSTED_SEARCH_PATH_SET:
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
    code, findings, event_match = _common_ddl_window_findings(text, label="bootstrap", guard_alias="wave1_bootstrap_event_trigger_guard")
    if not code:
        return findings

    required_objects = (
        "v_existing_schema oid := pg_catalog.to_regnamespace('platform')",
        "v_existing_table pg_catalog.regclass := pg_catalog.to_regclass('platform.authority_fences')",
        "platform.initialize_authority_fence(text,text,text)",
        "platform.advance_authority_fence(text,bigint,text,text,text)",
    )
    for token in required_objects:
        if token not in code:
            findings.append(f"Wave 1 fence bootstrap complete-object freshness invariant missing: {token}")

    table_reuse_guard = re.compile(
        r"IF\s+v_existing_table\s+IS\s+NOT\s+NULL\s+THEN\s+RETURN\s*;\s+END\s+IF\s*;",
        re.IGNORECASE | re.DOTALL,
    )
    table_match = table_reuse_guard.search(code)
    if table_match is None:
        findings.append("Wave 1 fence bootstrap must return on an existing authority_fences relation before persistent object mutation")

    partial_guard = re.compile(
        r"IF\s+v_existing_schema\s+IS\s+NOT\s+NULL\s+OR\s+v_existing_initialize\s+IS\s+NOT\s+NULL\s+OR\s+v_existing_advance\s+IS\s+NOT\s+NULL\s+THEN\s+"
        r"RAISE\s+EXCEPTION\s+'Wave 1 fence fresh bootstrap requires complete authority object absence'\s*;\s+END\s+IF\s*;",
        re.IGNORECASE | re.DOTALL,
    )
    partial_match = partial_guard.search(code)
    if partial_match is None:
        findings.append("Wave 1 fence bootstrap must fail closed when schema/functions pre-exist without the authority table")

    default_acl_required = (
        "FROM pg_catalog.pg_default_acl d",
        "pg_catalog.aclexplode(d.defaclacl) AS acl",
        "d.defaclrole OPERATOR(pg_catalog.=) current_user::pg_catalog.regrole::oid",
        "d.defaclnamespace OPERATOR(pg_catalog.=) 0",
        "d.defaclobjtype IN ('n', 'r', 'f')",
        "acl.grantee OPERATOR(pg_catalog.<>) d.defaclrole",
        "Wave 1 fence fresh bootstrap rejects non-owner default ACL grants for authority object creation",
    )
    for token in default_acl_required:
        if token not in code:
            findings.append(f"Wave 1 fence bootstrap default-ACL preflight invariant missing: {token}")

    fresh_reachability_required = (
        "WITH RECURSIVE owner_role_members(member_oid) AS (",
        "Wave 1 fresh bootstrap rejects migration-owner role reachability before authority object creation",
        "WITH RECURSIVE all_data_role_members(role_oid, member_oid) AS (",
        "pg_catalog.to_regrole('pg_read_all_data')::oid",
        "pg_catalog.to_regrole('pg_write_all_data')::oid",
        "Wave 1 fresh bootstrap rejects non-owner predefined all-data authority before fence creation",
        "p.proowner OPERATOR(pg_catalog.=) current_user::pg_catalog.regrole::oid",
        "AND p.prosecdef",
        "Wave 1 fresh bootstrap rejects migration-owner SECURITY DEFINER authority before fence creation",
    )
    for token in fresh_reachability_required:
        if token not in code:
            findings.append(f"Wave 1 fence bootstrap privilege-reachability preflight invariant missing: {token}")

    first_execute = code.find("EXECUTE")
    default_acl_pos = code.find("FROM pg_catalog.pg_default_acl d")
    owner_reachability_pos = code.find("WITH RECURSIVE owner_role_members(member_oid) AS (")
    all_data_pos = code.find("WITH RECURSIVE all_data_role_members(role_oid, member_oid) AS (")
    definer_pos = code.find("Wave 1 fresh bootstrap rejects migration-owner SECURITY DEFINER authority before fence creation")
    if first_execute < 0:
        findings.append("Wave 1 fence bootstrap fresh branch contains no persistent object creation")
    elif table_match is not None and partial_match is not None and not (
        table_match.end() < partial_match.end() < default_acl_pos < owner_reachability_pos < all_data_pos < definer_pos < first_execute
    ):
        findings.append("Wave 1 fence freshness/default-ACL/owner/all-data/definer preflights must execute before persistent bootstrap mutation")

    required_fresh_only = (
        "EXECUTE 'CREATE SCHEMA platform'",
        "EXECUTE 'REVOKE CREATE ON SCHEMA platform FROM PUBLIC'",
        "SET search_path = pg_catalog",
        "OPERATOR(pg_catalog.~)",
        "pg_catalog.btrim",
        "pg_catalog.statement_timestamp()",
    )
    for token in required_fresh_only:
        if token not in code:
            findings.append(f"Wave 1 fence bootstrap trusted/fresh-only invariant missing: {token}")
    if "CREATE SCHEMA IF NOT EXISTS platform" in code:
        findings.append("Wave 1 fence bootstrap must not use IF NOT EXISTS to launder a pre-existing authority namespace")

    post_assert_marker = "DO $wave1_bootstrap_privilege_assert$"
    post_assert_pos = code.find(post_assert_marker)
    post_assert_required = (
        post_assert_marker,
        "pg_catalog.COALESCE(n.nspacl, pg_catalog.acldefault('n', n.nspowner))",
        "pg_catalog.COALESCE(c.relacl, pg_catalog.acldefault('r', c.relowner))",
        "pg_catalog.aclexplode(a.attacl) AS acl",
        "pg_catalog.COALESCE(p.proacl, pg_catalog.acldefault('f', p.proowner))",
        "fresh fence authority routine materialized non-owner privileges",
    )
    for token in post_assert_required:
        if token not in code:
            findings.append(f"Wave 1 fence bootstrap materialized-ACL assertion invariant missing: {token}")
    if post_assert_pos < 0 or not (first_execute < post_assert_pos < code.rfind("COMMIT;")):
        findings.append("Wave 1 fence bootstrap must assert materialized schema/table/column/function ACLs before commit")

    guard_pos = code.find("END AS wave1_bootstrap_event_trigger_guard;")
    do_pos = code.find("DO $wave1_bootstrap$")
    if event_match is None or not (0 <= guard_pos < do_pos):
        findings.append("Wave 1 fence bootstrap event-trigger guard must complete before the fresh/reuse branch")
    return findings


def validate_revalidation_safety_text(text: str) -> list[str]:
    code, findings, event_match = _common_ddl_window_findings(text, label="revalidation", guard_alias="wave1_event_trigger_guard")
    if not code:
        return findings

    normalized = " ".join(code.split())
    lock = "LOCK TABLE platform.authority_fences IN ACCESS EXCLUSIVE MODE;"
    privilege_marker = "DO $wave1_reuse_privilege_preflight$"
    privilege_end_marker = "$wave1_reuse_privilege_preflight$;"
    structural_marker = "DO $wave1_revalidate$"
    mutation_marker = "ALTER TABLE platform.authority_fences"

    privilege_start = code.find(privilege_marker)
    privilege_end = code.find(privilege_end_marker, privilege_start + len(privilege_marker)) if privilege_start >= 0 else -1
    if privilege_start < 0 or privilege_end < 0:
        privilege_block = ""
        findings.append("Wave 1 fence reuse privilege preflight block is missing or malformed")
    else:
        privilege_end += len(privilege_end_marker)
        privilege_block = code[privilege_start:privilege_end]

    privilege_required = (
        "IF v_schema IS NULL OR v_table IS NULL OR v_initialize IS NULL OR v_advance IS NULL THEN",
        "Wave 1 reuse requires the complete canonical fence authority object set before mutation",
        "WITH RECURSIVE owner_role_members(member_oid) AS (",
        "WITH RECURSIVE all_data_role_members(role_oid, member_oid) AS (",
        "pg_catalog.to_regrole('pg_read_all_data')::oid",
        "pg_catalog.to_regrole('pg_write_all_data')::oid",
        "pg_catalog.aclexplode(a.attacl) AS acl",
        "p.proowner OPERATOR(pg_catalog.=) current_user::pg_catalog.regrole::oid",
        "AND p.prosecdef",
        "p.proconfig IS DISTINCT FROM ARRAY['search_path=pg_catalog']::text[]",
        "pg_catalog.aclexplode(\n              pg_catalog.COALESCE(c.relacl, pg_catalog.acldefault('r', c.relowner))\n          ) AS acl",
        "pg_catalog.aclexplode(\n              pg_catalog.COALESCE(n.nspacl, pg_catalog.acldefault('n', n.nspowner))\n          ) AS acl",
    )
    for token in privilege_required:
        if token not in privilege_block:
            findings.append(f"Wave 1 fence reuse privilege preflight invariant missing from privilege block: {token}")

    if lock not in code:
        findings.append("Wave 1 fence revalidation must hold ACCESS EXCLUSIVE lock across privilege+structural validation and canonicalization")
    else:
        begin_pos = code.find("BEGIN;")
        event_set_pos = code.find(_EVENT_TRIGGER_SET)
        search_set_pos = code.find(_TRUSTED_SEARCH_PATH_SET)
        lock_pos = code.find(lock)
        structural_pos = code.find(structural_marker)
        mutation_pos = code.find(mutation_marker)
        commit_pos = code.rfind("COMMIT;")
        if not (0 <= begin_pos < event_set_pos < search_set_pos < lock_pos < privilege_start < structural_pos < mutation_pos < commit_pos):
            findings.append("Wave 1 event-trigger/search-path/lock/privilege/structural/mutation ordering is not transactionally closed")
        if event_match is not None and not (search_set_pos < event_match.start() < lock_pos):
            findings.append("Wave 1 event-trigger catalog preflight must execute before fence lock/privilege/structural validation and DDL")

    required = (
        "pg_catalog.pg_depend",
        "pg_catalog.pg_proc",
        "pg_catalog.pg_operator",
        "pg_catalog.pg_collation",
        "CHECK expression depends on noncanonical function/operator/collation authority",
        "SET search_path = pg_catalog",
        "OPERATOR(pg_catalog.~)",
        "pg_catalog.btrim",
        "FROM pg_catalog.pg_opclass opc",
        "opc.opcname OPERATOR(pg_catalog.=) 'text_ops'",
        "i.indcollation[0] OPERATOR(pg_catalog.=) 'pg_catalog.\"C\"'::pg_catalog.regcollation::oid",
        "i.indclass[0] OPERATOR(pg_catalog.=) v_text_btree_opclass",
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

    post_assert_marker = "DO $wave1_postcanonical_privilege_assert$"
    post_assert_pos = code.find(post_assert_marker)
    post_assert_required = (
        post_assert_marker,
        "Wave 1 reuse canonical routine set became incomplete before commit",
        "Wave 1 reuse canonical routine materialized non-owner privileges before commit",
        "Wave 1 reuse canonical routine authority drifted before commit",
    )
    for token in post_assert_required:
        if token not in code:
            findings.append(f"Wave 1 fence reuse post-canonical privilege assertion missing: {token}")

    drop_token = "DROP CONSTRAINT wave1_fence_scope_id_canonical"
    validate_token = "VALIDATE CONSTRAINT wave1_fence_state_canonical"
    if drop_token in normalized and validate_token in normalized:
        structural_pos = normalized.find(structural_marker)
        privilege_pos = normalized.find(privilege_marker)
        drop_pos = normalized.find(drop_token)
        validate_pos = normalized.find(validate_token)
        function_pos = normalized.find("CREATE OR REPLACE FUNCTION platform.initialize_authority_fence")
        post_assert_normalized = normalized.find(post_assert_marker)
        commit_pos = normalized.rfind("COMMIT;")
        if not (privilege_pos < structural_pos < drop_pos < validate_pos < function_pos < post_assert_normalized < commit_pos):
            findings.append("Wave 1 fence reuse privilege+structural validation/canonicalization must finish in one transaction before function replacement and post-ACL assertion/commit")
    if post_assert_pos < 0 or post_assert_pos > code.rfind("COMMIT;"):
        findings.append("Wave 1 fence reuse must reassert canonical routine ACL/current-authority state before commit")

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
    print("RESULT: PASS — fresh bootstrap binds default ACL + privilege-reachability preflight + materialized ACL proof; reused authority requires a complete routine set and binds privilege+structure+canonical mutation+post-ACL assertion in one locked transaction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
