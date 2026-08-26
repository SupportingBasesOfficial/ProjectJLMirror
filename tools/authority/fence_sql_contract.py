#!/usr/bin/env python3
"""Fail-closed structural checks for the Wave 1 IR-D-003 PostgreSQL fence contract."""

from __future__ import annotations

import re

CANONICAL_IDENTIFIER_REGEX = "^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$"
CANONICAL_REGEX_OPERATOR = 'COLLATE "C" OPERATOR(pg_catalog.~)'
CANONICAL_TEXT_COLLATION_DECL = 'text COLLATE "C"'
CANONICAL_REVALIDATION_COLLATION = "attcollation IS DISTINCT FROM 'pg_catalog.\"C\"'::pg_catalog.regcollation"
EFFECT_ELIGIBLE_PREDECESSOR_PREDICATE = "authority_fences.authority_state COLLATE \"C\" OPERATOR(pg_catalog.=) 'active' COLLATE \"C\""
TRUSTED_MIGRATION_SEARCH_PATH = "SET LOCAL search_path = pg_catalog;"
CANONICAL_FUNCTION_SEARCH_PATH = "SET search_path = pg_catalog"
CANONICAL_FENCE_CONSTRAINT_NAMES = (
    "wave1_authority_fences_pkey",
    "wave1_fence_epoch_positive",
    "wave1_fence_generation_canonical",
    "wave1_fence_scope_id_canonical",
    "wave1_fence_state_canonical",
)


def _predicate(name: str) -> str:
    return f"{name} {CANONICAL_REGEX_OPERATOR} '{CANONICAL_IDENTIFIER_REGEX}'"


def _executable_sql(text: str) -> str:
    """Remove SQL comments so comments cannot launder required invariants."""
    out: list[str] = []
    i = 0
    in_single = False
    in_double = False
    block_depth = 0
    while i < len(text):
        if block_depth:
            if text.startswith("/*", i):
                block_depth += 1
                i += 2
                continue
            if text.startswith("*/", i):
                block_depth -= 1
                i += 2
                continue
            i += 1
            continue
        char = text[i]
        if in_single:
            out.append(char)
            if char == "'":
                if i + 1 < len(text) and text[i + 1] == "'":
                    out.append("'")
                    i += 2
                    continue
                in_single = False
            i += 1
            continue
        if in_double:
            out.append(char)
            if char == '"':
                if i + 1 < len(text) and text[i + 1] == '"':
                    out.append('"')
                    i += 2
                    continue
                in_double = False
            i += 1
            continue
        if text.startswith("--", i):
            newline = text.find("\n", i + 2)
            if newline < 0:
                break
            out.append("\n")
            i = newline + 1
            continue
        if text.startswith("/*", i):
            block_depth = 1
            i += 2
            continue
        if char == "'":
            in_single = True
        elif char == '"':
            in_double = True
        out.append(char)
        i += 1
    if block_depth or in_single or in_double:
        return ""
    return "".join(out)


def validate_fence_sql_text(text: str) -> list[str]:
    if not isinstance(text, str):
        return ["IR-D-003 SQL contract must be text"]
    code = _executable_sql(text)
    if not code:
        return ["IR-D-003 SQL contract is malformed or cannot be parsed conservatively"]

    findings: list[str] = []
    required = (
        'fence_scope_id text COLLATE "C" NOT NULL',
        'current_generation_id text COLLATE "C" NOT NULL',
        'authority_state text COLLATE "C" NOT NULL',
        "CONSTRAINT wave1_authority_fences_pkey",
        "PRIMARY KEY (fence_scope_id)",
        "CONSTRAINT wave1_fence_scope_id_canonical",
        "CONSTRAINT wave1_fence_epoch_positive",
        "CONSTRAINT wave1_fence_generation_canonical",
        "CONSTRAINT wave1_fence_state_canonical",
        "pg_catalog.btrim(fence_scope_id) OPERATOR(pg_catalog.<>) ''",
        _predicate("fence_scope_id"),
        "pg_catalog.btrim(current_generation_id) OPERATOR(pg_catalog.<>) ''",
        _predicate("current_generation_id"),
        "pg_catalog.btrim(authority_state) OPERATOR(pg_catalog.<>) ''",
        _predicate("authority_state"),
        'authority_fences.fence_scope_id COLLATE "C" OPERATOR(pg_catalog.=) p_fence_scope_id COLLATE "C"',
        'authority_fences.current_generation_id COLLATE "C" OPERATOR(pg_catalog.=) p_expected_predecessor_generation_id COLLATE "C"',
        _predicate("p_expected_predecessor_generation_id"),
        _predicate("p_successor_generation_id"),
        _predicate("p_successor_state"),
        EFFECT_ELIGIBLE_PREDECESSOR_PREDICATE,
        "pg_catalog.statement_timestamp()",
        CANONICAL_FUNCTION_SEARCH_PATH,
    )
    for fragment in required:
        if fragment not in code:
            findings.append(f"IR-D-003 SQL canonical/effect-authority invariant missing: {fragment}")

    if code.count(CANONICAL_FUNCTION_SEARCH_PATH) != 2:
        findings.append("IR-D-003 exactly both canonical fence routines must pin pg_catalog-only function search_path")
    if code.count("pg_catalog.btrim(") < 6:
        findings.append("IR-D-003 every stored/effect identifier emptiness check must bind pg_catalog.btrim")
    if code.count(f"{CANONICAL_REGEX_OPERATOR} '{CANONICAL_IDENTIFIER_REGEX}'") < 6:
        findings.append("IR-D-003 SQL canonical identifier grammar is not C-collated/catalog-bound at every required storage/effect boundary")
    if code.count("pg_catalog.statement_timestamp()") < 2:
        findings.append("IR-D-003 evidence timestamps must use catalog-bound statement_timestamp at default and advance paths")
    for name in CANONICAL_FENCE_CONSTRAINT_NAMES:
        if code.count(name) < 1:
            findings.append(f"IR-D-003 SQL canonical fence constraint name missing: {name}")
    return findings


def validate_fence_revalidation_sql_text(text: str) -> list[str]:
    """Require reused persisted fence state to prove the exact canonical contract."""
    if not isinstance(text, str):
        return ["IR-D-003 fence revalidation migration must be text"]
    code = _executable_sql(text)
    if not code:
        return ["IR-D-003 fence revalidation migration is malformed or cannot be parsed conservatively"]
    normalized = " ".join(code.split())
    findings: list[str] = []

    required = (
        TRUSTED_MIGRATION_SEARCH_PATH,
        "DO $wave1_reuse_privilege_preflight$",
        "pg_catalog.to_regnamespace('platform')",
        "WITH RECURSIVE owner_role_members(member_oid) AS (",
        "WITH RECURSIVE all_data_role_members(role_oid, member_oid) AS (",
        "pg_catalog.to_regrole('pg_read_all_data')::oid",
        "pg_catalog.to_regrole('pg_write_all_data')::oid",
        "pg_catalog.aclexplode(a.attacl) AS acl",
        "p.proowner OPERATOR(pg_catalog.=) current_user::pg_catalog.regrole::oid",
        "AND p.prosecdef",
        "v_pk_index oid",
        "v_btree_am oid",
        "v_text_btree_opclass oid",
        "FROM pg_catalog.pg_am am",
        "FROM pg_catalog.pg_opclass opc",
        "opc.opcnamespace OPERATOR(pg_catalog.=) 'pg_catalog'::pg_catalog.regnamespace",
        "opc.opcname OPERATOR(pg_catalog.=) 'text_ops'",
        "opc.opcintype OPERATOR(pg_catalog.=) 'text'::pg_catalog.regtype",
        "opc.opcdefault",
        "pg_catalog.to_regclass('platform.authority_fences')",
        "SELECT ROW(relkind, relpersistence, relispartition, relrowsecurity, relforcerowsecurity)",
        "ROW('r'::\"char\", 'p'::\"char\", false, false, false)",
        "FROM pg_catalog.pg_inherits",
        "FROM pg_catalog.pg_policy",
        "SELECT pg_catalog.array_agg(attname::text ORDER BY attnum)",
        "'int8'::pg_catalog.regtype",
        "'timestamptz'::pg_catalog.regtype",
        "FROM pg_catalog.pg_attrdef d",
        "a.attname OPERATOR(pg_catalog.<>) 'updated_at'",
        "attgenerated OPERATOR(pg_catalog.<>) '' OR attidentity OPERATOR(pg_catalog.<>) ''",
        "pg_catalog.pg_get_expr(d.adbin, d.adrelid)",
        "IS DISTINCT FROM 'statement_timestamp()'",
        CANONICAL_REVALIDATION_COLLATION,
        "authority_fences contains noncanonical or missing write constraints",
        "c.conkey OPERATOR(pg_catalog.=) ARRAY[a.attnum]::smallint[]",
        "NOT c.condeferrable",
        "NOT c.condeferred",
        "i.indnkeyatts OPERATOR(pg_catalog.=) 1",
        "i.indnatts OPERATOR(pg_catalog.=) 1",
        "i.indexprs IS NULL",
        "i.indpred IS NULL",
        "JOIN pg_catalog.pg_class index_class",
        "index_class.relam OPERATOR(pg_catalog.=) v_btree_am",
        "i.indcollation[0] OPERATOR(pg_catalog.=) 'pg_catalog.\"C\"'::pg_catalog.regcollation::oid",
        "i.indclass[0] OPERATOR(pg_catalog.=) v_text_btree_opclass",
        "authority_fences contains noncanonical index metadata",
        "c.conrelid OPERATOR(pg_catalog.=) v_table OR c.confrelid OPERATOR(pg_catalog.=) v_table",
        "authority_fences cannot participate in foreign-key referential actions",
        "FROM pg_catalog.pg_trigger t",
        "NOT t.tgisinternal",
        "FROM pg_catalog.pg_rewrite r",
        "r.ev_class OPERATOR(pg_catalog.=) v_table",
        "JOIN pg_catalog.pg_depend d",
        "d.refobjid OPERATOR(pg_catalog.=) v_table",
        "r.ev_class OPERATOR(pg_catalog.<>) v_table",
        "external rewrite dependency can reach authority_fences",
        "pg_catalog.pg_subscription_rel",
        "logical replication subscription can write authority_fences",
        "LEFT JOIN pg_catalog.pg_proc p",
        "LEFT JOIN pg_catalog.pg_operator o",
        "'pg_catalog.pg_collation'::pg_catalog.regclass",
        "p.pronamespace OPERATOR(pg_catalog.<>) 'pg_catalog'::pg_catalog.regnamespace",
        "o.oprnamespace OPERATOR(pg_catalog.<>) 'pg_catalog'::pg_catalog.regnamespace",
        "d.refobjid OPERATOR(pg_catalog.<>) 'pg_catalog.\"C\"'::pg_catalog.regcollation",
        "CHECK expression depends on noncanonical function/operator/collation authority",
        "ALTER COLUMN fence_scope_id SET NOT NULL",
        "ALTER COLUMN current_fence_epoch SET NOT NULL",
        "ALTER COLUMN current_generation_id SET NOT NULL",
        "ALTER COLUMN authority_state SET NOT NULL",
        "ALTER COLUMN updated_at SET NOT NULL",
        "DROP CONSTRAINT wave1_fence_scope_id_canonical",
        "DROP CONSTRAINT wave1_fence_epoch_positive",
        "DROP CONSTRAINT wave1_fence_generation_canonical",
        "DROP CONSTRAINT wave1_fence_state_canonical",
        "ADD CONSTRAINT wave1_fence_scope_id_canonical",
        _predicate("fence_scope_id"),
        "ADD CONSTRAINT wave1_fence_epoch_positive",
        "CHECK (current_fence_epoch OPERATOR(pg_catalog.>) 0) NOT VALID",
        "ADD CONSTRAINT wave1_fence_generation_canonical",
        _predicate("current_generation_id"),
        "ADD CONSTRAINT wave1_fence_state_canonical",
        _predicate("authority_state"),
        "VALIDATE CONSTRAINT wave1_fence_scope_id_canonical",
        "VALIDATE CONSTRAINT wave1_fence_epoch_positive",
        "VALIDATE CONSTRAINT wave1_fence_generation_canonical",
        "VALIDATE CONSTRAINT wave1_fence_state_canonical",
        "CREATE OR REPLACE FUNCTION platform.initialize_authority_fence",
        "CREATE OR REPLACE FUNCTION platform.advance_authority_fence",
        CANONICAL_FUNCTION_SEARCH_PATH,
    )
    for name in CANONICAL_FENCE_CONSTRAINT_NAMES:
        if name not in code:
            findings.append(f"IR-D-003 persisted fence canonical constraint missing: {name}")
    for fragment in required:
        if fragment not in code:
            findings.append(f"IR-D-003 persisted fence revalidation invariant missing: {fragment}")

    for field in ("indisprimary", "indisunique", "indimmediate", "indisvalid", "indisready", "indislive"):
        if re.search(rf"(?m)^\s+AND\s+i\.{re.escape(field)}\s*$", code) is None:
            findings.append(f"IR-D-003 persisted fence primary-key index must require exact positive i.{field}")

    constraint_set_guard = re.compile(
        r"SELECT\s+pg_catalog\.array_agg\(conname::text\s+ORDER\s+BY\s+conname\).*?"
        r"FROM\s+pg_catalog\.pg_constraint.*?WHERE\s+conrelid.*?v_table.*?"
        r"IS\s+DISTINCT\s+FROM\s+ARRAY\s*\[.*?wave1_authority_fences_pkey.*?"
        r"wave1_fence_epoch_positive.*?wave1_fence_generation_canonical.*?"
        r"wave1_fence_scope_id_canonical.*?wave1_fence_state_canonical.*?\]::text\[\]",
        re.IGNORECASE | re.DOTALL,
    )
    if constraint_set_guard.search(code) is None:
        findings.append("IR-D-003 persisted fence revalidation must prove the exact finite constraint set")

    dependency_guard = re.compile(
        r"FROM\s+pg_catalog\.pg_constraint\s+c\s+JOIN\s+pg_catalog\.pg_depend\s+d.*?"
        r"LEFT\s+JOIN\s+pg_catalog\.pg_proc\s+p.*?LEFT\s+JOIN\s+pg_catalog\.pg_operator\s+o.*?"
        r"pg_catalog\.pg_collation.*?noncanonical function/operator/collation authority",
        re.IGNORECASE | re.DOTALL,
    )
    if dependency_guard.search(code) is None:
        findings.append("IR-D-003 reused CHECK expressions must prove catalog-bound function/operator/collation dependencies")

    pk_guard = re.compile(
        r"SELECT\s+c\.conindid\s+INTO\s+v_pk_index.*?FROM\s+pg_catalog\.pg_constraint\s+c.*?"
        r"JOIN\s+pg_catalog\.pg_index\s+i.*?JOIN\s+pg_catalog\.pg_class\s+index_class.*?"
        r"c\.conname.*?wave1_authority_fences_pkey.*?NOT\s+c\.condeferrable.*?"
        r"NOT\s+c\.condeferred.*?c\.convalidated.*?i\.indisprimary.*?i\.indisunique.*?"
        r"i\.indimmediate.*?i\.indisvalid.*?i\.indisready.*?i\.indislive.*?"
        r"i\.indnkeyatts.*?1.*?i\.indnatts.*?1.*?i\.indexprs\s+IS\s+NULL.*?"
        r"i\.indpred\s+IS\s+NULL.*?index_class\.relam.*?v_btree_am.*?"
        r"i\.indcollation\[0\].*?pg_catalog.*?C.*?i\.indclass\[0\].*?v_text_btree_opclass",
        re.IGNORECASE | re.DOTALL,
    )
    if pk_guard.search(code) is None:
        findings.append("IR-D-003 persisted fence primary key must bind canonical C collation and pg_catalog btree text_ops conflict semantics")

    if code.count(CANONICAL_FUNCTION_SEARCH_PATH) != 2:
        findings.append("IR-D-003 revalidation must canonicalize exactly both fence routines with pg_catalog-only search_path")

    function_marker = "CREATE OR REPLACE FUNCTION platform.initialize_authority_fence"
    pre_function = code.split(function_marker, 1)[0]
    if "UPDATE platform.authority_fences" in pre_function or "DELETE FROM platform.authority_fences" in pre_function:
        findings.append("IR-D-003 reuse validation must not normalize/delete historical authority rows to make validation pass")

    privilege_pos = normalized.find("DO $wave1_reuse_privilege_preflight$")
    structural_pos = normalized.find("DO $wave1_revalidate$")
    mutation_pos = normalized.find("ALTER TABLE platform.authority_fences")
    drop_pos = normalized.find("DROP CONSTRAINT wave1_fence_scope_id_canonical")
    validate_pos = normalized.find("VALIDATE CONSTRAINT wave1_fence_state_canonical")
    function_pos = normalized.find(function_marker)
    commit_pos = normalized.rfind("COMMIT;")
    if min(privilege_pos, structural_pos, mutation_pos, drop_pos, validate_pos, function_pos, commit_pos) >= 0:
        if not (privilege_pos < structural_pos < mutation_pos <= drop_pos < validate_pos < function_pos < commit_pos):
            findings.append("IR-D-003 reuse privilege+structural admission must complete before any canonical mutation and commit")

    return findings
