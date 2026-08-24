#!/usr/bin/env python3
"""Fail-closed structural checks for the Wave 1 IR-D-003 PostgreSQL fence contract."""

from __future__ import annotations

import re

CANONICAL_IDENTIFIER_REGEX = "^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$"
CANONICAL_REGEX_OPERATOR = 'COLLATE "C" ~'
EFFECT_ELIGIBLE_PREDECESSOR_PREDICATE = "authority_fences.authority_state = 'active'"


def _predicate(name: str) -> str:
    return f"{name} {CANONICAL_REGEX_OPERATOR} '{CANONICAL_IDENTIFIER_REGEX}'"


def _executable_sql(text: str) -> str:
    """Remove SQL comments so comments cannot launder required executable invariants."""

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
    findings: list[str] = []
    if not code:
        findings.append("IR-D-003 SQL contract is malformed or cannot be parsed conservatively")
        return findings

    required = (
        "CHECK (btrim(fence_scope_id) <> '')",
        f"CHECK ({_predicate('fence_scope_id')})",
        "CHECK (btrim(current_generation_id) <> '')",
        f"CHECK ({_predicate('current_generation_id')})",
        "CHECK (btrim(authority_state) <> '')",
        f"CHECK ({_predicate('authority_state')})",
        _predicate("p_expected_predecessor_generation_id"),
        _predicate("p_successor_generation_id"),
        _predicate("p_successor_state"),
        EFFECT_ELIGIBLE_PREDECESSOR_PREDICATE,
    )
    for fragment in required:
        if fragment not in code:
            findings.append(f"IR-D-003 SQL canonical/effect-authority invariant missing: {fragment}")

    executable_uses = code.count(
        f"{CANONICAL_REGEX_OPERATOR} '{CANONICAL_IDENTIFIER_REGEX}'"
    )
    if executable_uses < 6:
        findings.append(
            "IR-D-003 SQL canonical identifier grammar is not C-collated/enforced at every required storage/effect boundary"
        )

    return findings


def validate_fence_revalidation_sql_text(text: str) -> list[str]:
    """Require existing persisted fence state to prove the exact canonical contract."""

    if not isinstance(text, str):
        return ["IR-D-003 fence revalidation migration must be text"]

    code = _executable_sql(text)
    if not code:
        return ["IR-D-003 fence revalidation migration is malformed or cannot be parsed conservatively"]
    normalized = " ".join(code.split())

    findings: list[str] = []
    required = (
        "to_regclass('platform.authority_fences')",
        "SELECT ROW(relkind, relpersistence, relispartition, relrowsecurity, relforcerowsecurity)",
        "IS DISTINCT FROM ROW('r'::\"char\", 'p'::\"char\", false, false, false)",
        "FROM pg_inherits",
        "inhrelid = v_table",
        "inhparent = v_table",
        "FROM pg_policy",
        "polrelid = v_table",
        "SELECT array_agg(attname::text ORDER BY attnum)",
        "'fence_scope_id'",
        "'current_fence_epoch'",
        "'current_generation_id'",
        "'authority_state'",
        "'updated_at'",
        "IS DISTINCT FROM ARRAY[",
        "attname = 'fence_scope_id'",
        "IS DISTINCT FROM 'text'::regtype",
        "attname = 'current_fence_epoch'",
        "IS DISTINCT FROM 'int8'::regtype",
        "attname = 'current_generation_id'",
        "attname = 'authority_state'",
        "attname = 'updated_at'",
        "IS DISTINCT FROM 'timestamptz'::regtype",
        "attgenerated <> '' OR attidentity <> ''",
        "FROM pg_attrdef d",
        "a.attname <> 'updated_at'",
        "pg_get_expr(d.adbin, d.adrelid)",
        "IS DISTINCT FROM 'statement_timestamp()'",
        "c.contype = 'p'",
        "c.conkey = ARRAY[a.attnum]::smallint[]",
        "ALTER TABLE platform.authority_fences",
        "ALTER COLUMN fence_scope_id SET NOT NULL",
        "ALTER COLUMN current_fence_epoch SET NOT NULL",
        "ALTER COLUMN current_generation_id SET NOT NULL",
        "ALTER COLUMN authority_state SET NOT NULL",
        "ALTER COLUMN updated_at SET NOT NULL",
        "ADD CONSTRAINT wave1_fence_scope_id_canonical",
        _predicate("fence_scope_id"),
        "ADD CONSTRAINT wave1_fence_epoch_positive",
        "CHECK (current_fence_epoch > 0) NOT VALID",
        "ADD CONSTRAINT wave1_fence_generation_canonical",
        _predicate("current_generation_id"),
        "ADD CONSTRAINT wave1_fence_state_canonical",
        _predicate("authority_state"),
        "VALIDATE CONSTRAINT wave1_fence_scope_id_canonical",
        "VALIDATE CONSTRAINT wave1_fence_epoch_positive",
        "VALIDATE CONSTRAINT wave1_fence_generation_canonical",
        "VALIDATE CONSTRAINT wave1_fence_state_canonical",
    )
    for fragment in required:
        if fragment not in code:
            findings.append(
                f"IR-D-003 persisted fence revalidation invariant missing: {fragment}"
            )

    trigger_guard = re.compile(
        r"IF\s+EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+pg_trigger\s+t\s+"
        r"WHERE\s+t\.tgrelid\s*=\s*v_table\s+AND\s+NOT\s+t\.tgisinternal\s*\)\s*THEN",
        re.IGNORECASE | re.DOTALL,
    )
    if trigger_guard.search(code) is None:
        findings.append(
            "IR-D-003 persisted fence revalidation must reject non-internal trigger behavior"
        )

    rule_guard = re.compile(
        r"IF\s+EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+pg_rewrite\s+r\s+"
        r"WHERE\s+r\.ev_class\s*=\s*v_table\s*\)\s*THEN",
        re.IGNORECASE | re.DOTALL,
    )
    if rule_guard.search(code) is None:
        findings.append(
            "IR-D-003 persisted fence revalidation must reject rewrite-rule behavior"
        )

    if "UPDATE platform.authority_fences" in normalized or "DELETE FROM platform.authority_fences" in normalized:
        findings.append(
            "IR-D-003 revalidation migration must not normalize/delete historical authority rows to make validation pass"
        )
    return findings
