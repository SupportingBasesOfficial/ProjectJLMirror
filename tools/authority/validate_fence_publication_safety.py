#!/usr/bin/env python3
"""Observer-only logical-replication authority validation for Wave 1 fencing."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authority.fence_sql_contract import _executable_sql  # noqa: E402

PROFILE = "jlmirror-wave1-fence-logical-replication/v1"
C2_DATABASE_ADMIN_CHOICE = "database_admin_role_and_operational_mapping"
BOOTSTRAP_PATH = ROOT / "sql" / "wave1" / "001_platform_authority_fence.sql"
REUSE_PATH = ROOT / "sql" / "wave1" / "002_revalidate_authority_fence_contract.sql"
BOUNDARY_PATH = ROOT / "implementation" / "wave-1" / "FENCE_LOGICAL_REPLICATION_BOUNDARY.md"
MANIFEST_PATH = ROOT / "implementation" / "wave-1" / "FENCE_LOGICAL_REPLICATION_MANIFEST.json"

REQUIRED_LAWS = (
    "ACL CLEAN != LOGICAL REPLICATION DISCLOSURE ABSENT",
    "INBOUND REPLICATION WRITER ABSENT != OUTBOUND PUBLICATION ABSENT",
    "PUBLICATION CATALOG SNAPSHOT CLEAN != CONCURRENT SUPERUSER AUTHORITY ABSENT",
    "TABLE LOCK HELD != DATABASE ADMIN AUTHORITY REVOKED",
    "WAVE 1 REPLICATION PREFLIGHT != C2 DATABASE ROLE MAPPING",
    "STATIC PREFLIGHT PASS != FUTURE ADMINISTRATIVE AUTHORITY ABSENCE",
)

EXPECTED_MANIFEST = {
    "profile": PROFILE,
    "authority_scope": "platform.authority_fences",
    "fresh_bootstrap_required_guards": [
        "for_all_tables_publication_absent_before_first_persistent_create"
    ],
    "reuse_required_guards": [
        "inbound_subscription_mapping_absent",
        "explicit_publication_relation_absent",
        "for_all_tables_publication_absent",
        "schema_publication_absent_when_catalog_supported",
    ],
    "reuse_execution_boundary": {
        "single_transaction": True,
        "access_exclusive_before_preflight": True,
        "publication_preflight_before_canonical_mutation": True,
    },
    "forbidden_substitutions": [
        "acl_clean_for_logical_replication_disclosure_absent",
        "inbound_replication_writer_absent_for_outbound_publication_absent",
        "publication_catalog_snapshot_clean_for_concurrent_superuser_authority_absent",
        "table_lock_held_for_database_admin_authority_revoked",
    ],
    "c2_database_admin_boundary": {
        "choice_id": C2_DATABASE_ADMIN_CHOICE,
        "concurrent_superuser_or_equivalent_admin_exclusion_selected": False,
        "catalog_preflight_claims_permanent_admin_absence": False,
        "requires_separate_reviewed_role_and_operational_mapping": True,
    },
    "product_feature_activation": "none",
    "wave_2_authorized": False,
}

Token = tuple[str, str]


def _word(value: str) -> Token:
    return ("word", value.lower())


def _symbol(value: str) -> Token:
    return ("symbol", value)


def _string(value: str) -> Token:
    return ("string", value)


def _number(value: str) -> Token:
    return ("number", value)


def _parameter(value: str) -> Token:
    return ("parameter", value)


def _sql_tokens(text: str) -> list[Token]:
    """Tokenize enough SQL/PLpgSQL to distinguish syntax from string literals.

    Dollar-quote delimiters are syntax markers, not opaque strings here: their bodies
    contain the PL/pgSQL predicates this validator must inspect. Ordinary SQL string
    literals remain typed tokens so dead strings cannot satisfy executable predicates.
    """

    tokens: list[Token] = []
    i = 0
    length = len(text)
    while i < length:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue

        if ch == "'":
            i += 1
            value: list[str] = []
            while i < length:
                if text[i] == "'":
                    if i + 1 < length and text[i + 1] == "'":
                        value.append("'")
                        i += 2
                        continue
                    i += 1
                    break
                value.append(text[i])
                i += 1
            else:
                raise ValueError("unterminated SQL string literal")
            tokens.append(_string("".join(value)))
            continue

        if ch == '"':
            i += 1
            value = []
            while i < length:
                if text[i] == '"':
                    if i + 1 < length and text[i + 1] == '"':
                        value.append('"')
                        i += 2
                        continue
                    i += 1
                    break
                value.append(text[i])
                i += 1
            else:
                raise ValueError("unterminated quoted identifier")
            tokens.append(("quoted_identifier", "".join(value)))
            continue

        if ch == "$":
            if i + 1 < length and text[i + 1].isdigit():
                j = i + 2
                while j < length and text[j].isdigit():
                    j += 1
                tokens.append(_parameter(text[i:j]))
                i = j
                continue
            j = text.find("$", i + 1)
            if j >= 0:
                tag = text[i + 1 : j]
                if all(c.isalnum() or c == "_" for c in tag):
                    i = j + 1
                    continue

        if ch.isalpha() or ch == "_":
            j = i + 1
            while j < length and (text[j].isalnum() or text[j] in "_$"):
                j += 1
            tokens.append(_word(text[i:j]))
            i = j
            continue

        if ch.isdigit():
            j = i + 1
            while j < length and text[j].isdigit():
                j += 1
            tokens.append(_number(text[i:j]))
            i = j
            continue

        if ch in "=<>~!+-*/":
            j = i + 1
            while j < length and text[j] in "=<>~!+-*/":
                j += 1
            tokens.append(_symbol(text[i:j]))
            i = j
            continue

        tokens.append(_symbol(ch))
        i += 1
    return tokens


def _find_sequence(tokens: list[Token], expected: tuple[Token, ...], start: int = 0) -> int:
    if not expected:
        return start
    limit = len(tokens) - len(expected) + 1
    for index in range(max(start, 0), max(limit, 0)):
        if tuple(tokens[index : index + len(expected)]) == expected:
            return index
    return -1


def _mask_single_quoted_literals(text: str) -> str:
    """Preserve character positions while removing ordinary string-literal contents."""

    chars = list(text)
    i = 0
    while i < len(chars):
        if chars[i] != "'":
            i += 1
            continue
        chars[i] = " "
        i += 1
        while i < len(chars):
            if chars[i] == "'":
                chars[i] = " "
                if i + 1 < len(chars) and chars[i + 1] == "'":
                    chars[i + 1] = " "
                    i += 2
                    continue
                i += 1
                break
            if chars[i] != "\n":
                chars[i] = " "
            i += 1
    return "".join(chars)


def _code(text: object, label: str) -> tuple[str, list[str]]:
    if not isinstance(text, str):
        return "", [f"{label} must be text"]
    code = _executable_sql(text)
    if not code:
        return "", [f"{label} is malformed or cannot be parsed conservatively"]
    try:
        _sql_tokens(code)
    except ValueError as exc:
        return "", [f"{label} cannot be tokenized conservatively: {exc}"]
    return code, []


def _bootstrap_publication_guard() -> tuple[Token, ...]:
    return (
        _word("IF"), _word("EXISTS"), _symbol("("),
        _word("SELECT"), _number("1"), _word("FROM"),
        _word("pg_catalog"), _symbol("."), _word("pg_publication"), _word("p"),
        _word("WHERE"), _word("p"), _symbol("."), _word("puballtables"),
        _symbol(")"), _word("THEN"), _word("RAISE"), _word("EXCEPTION"),
        _string("Wave 1 fence fresh bootstrap rejects FOR ALL TABLES publication authority before fence creation"),
        _symbol(";"), _word("END"), _word("IF"), _symbol(";"),
    )


def validate_bootstrap_publication_text(text: object) -> list[str]:
    code, findings = _code(text, "Wave 1 fresh fence publication contract")
    if findings:
        return findings

    tokens = _sql_tokens(code)
    if code.count("BEGIN;") != 1:
        findings.append("Wave 1 fresh fence publication contract must have exactly one BEGIN")
    if code.count("COMMIT;") != 1:
        findings.append("Wave 1 fresh fence publication contract must have exactly one COMMIT")

    guard_pos = _find_sequence(tokens, _bootstrap_publication_guard())
    if guard_pos < 0:
        findings.append(
            "Wave 1 fresh fence publication contract lost parsed FOR ALL TABLES fail-closed predicate"
        )

    create_anchor = (_word("EXECUTE"), _string("CREATE SCHEMA platform"), _symbol(";"))
    first_create = _find_sequence(tokens, create_anchor)
    if first_create < 0:
        findings.append("Wave 1 fresh fence publication contract lost first persistent CREATE anchor")
    if guard_pos >= 0 and first_create >= 0 and guard_pos > first_create:
        findings.append("Wave 1 fresh publication disclosure preflight must execute before first persistent CREATE")
    return findings


def _reuse_structural_block(code: str) -> tuple[str, list[str]]:
    start_marker = "DO $wave1_revalidate$"
    end_marker = "$wave1_revalidate$;"
    syntax_only = _mask_single_quoted_literals(code)
    start = syntax_only.find(start_marker)
    if start < 0:
        return "", ["Wave 1 reuse logical-replication contract lost structural preflight block"]
    end = syntax_only.find(end_marker, start + len(start_marker))
    if end < 0:
        return "", ["Wave 1 reuse logical-replication contract structural preflight is unterminated"]
    return code[start : end + len(end_marker)], []


def _reuse_static_guard(
    catalog: str,
    alias: str,
    left_column: str | None,
    target: str | None,
    message: str,
) -> tuple[Token, ...]:
    sequence: list[Token] = [
        _word("IF"), _word("EXISTS"), _symbol("("),
        _word("SELECT"), _number("1"), _word("FROM"),
        _word("pg_catalog"), _symbol("."), _word(catalog), _word(alias),
    ]
    if left_column is None:
        sequence.extend((_word("WHERE"), _word(alias), _symbol("."), _word("puballtables")))
    else:
        sequence.extend((
            _word("WHERE"), _word(alias), _symbol("."), _word(left_column),
            _word("OPERATOR"), _symbol("("), _word("pg_catalog"), _symbol("."), _symbol("="), _symbol(")"),
            _word(target or ""),
        ))
    sequence.extend((
        _symbol(")"), _word("THEN"), _word("RAISE"), _word("EXCEPTION"),
        _string(message), _symbol(";"), _word("END"), _word("IF"), _symbol(";"),
    ))
    return tuple(sequence)


def _schema_catalog_guard() -> tuple[Token, ...]:
    return (
        _word("IF"), _word("pg_catalog"), _symbol("."), _word("to_regclass"), _symbol("("),
        _string("pg_catalog.pg_publication_namespace"), _symbol(")"),
        _word("IS"), _word("NOT"), _word("NULL"), _word("THEN"),
    )


def _dynamic_schema_publication_query(tokens: list[Token]) -> str | None:
    for index, token in enumerate(tokens):
        if token != _word("EXECUTE"):
            continue
        cursor = index + 1
        parts: list[str] = []
        while cursor < len(tokens) and tokens[cursor][0] == "string":
            parts.append(tokens[cursor][1])
            cursor += 1
        if not parts or cursor + 3 >= len(tokens):
            continue
        if (
            tokens[cursor] == _word("INTO")
            and tokens[cursor + 1] == _word("v_schema_publication_exists")
            and tokens[cursor + 2] == _word("USING")
            and tokens[cursor + 3] == _word("v_schema")
        ):
            return "".join(parts)
    return None


def _expected_schema_publication_query() -> tuple[Token, ...]:
    return (
        _word("SELECT"), _word("EXISTS"), _symbol("("),
        _word("SELECT"), _number("1"), _word("FROM"),
        _word("pg_catalog"), _symbol("."), _word("pg_publication_namespace"), _word("pn"),
        _word("WHERE"), _word("pn"), _symbol("."), _word("pnnspid"),
        _word("OPERATOR"), _symbol("("), _word("pg_catalog"), _symbol("."), _symbol("="), _symbol(")"),
        _parameter("$1"), _symbol(")"),
    )


def _schema_result_guard() -> tuple[Token, ...]:
    return (
        _word("IF"), _word("v_schema_publication_exists"), _word("THEN"),
        _word("RAISE"), _word("EXCEPTION"),
        _string("schema publication can disclose platform.authority_fences"),
        _symbol(";"), _word("END"), _word("IF"), _symbol(";"),
    )


def validate_reuse_publication_text(text: object) -> list[str]:
    code, findings = _code(text, "Wave 1 reused fence publication contract")
    if findings:
        return findings

    if code.count("BEGIN;") != 1:
        findings.append("Wave 1 reused fence publication contract must have exactly one BEGIN")
    if code.count("COMMIT;") != 1:
        findings.append("Wave 1 reused fence publication contract must have exactly one COMMIT")

    syntax_only = _mask_single_quoted_literals(code)
    lock = "LOCK TABLE platform.authority_fences IN ACCESS EXCLUSIVE MODE;"
    lock_pos = syntax_only.find(lock)
    if lock_pos < 0:
        findings.append("Wave 1 reused fence publication contract requires ACCESS EXCLUSIVE lock")

    block, block_findings = _reuse_structural_block(code)
    findings.extend(block_findings)
    if not block:
        return findings

    block_tokens = _sql_tokens(block)
    block_syntax = _mask_single_quoted_literals(block)
    block_pos = syntax_only.find("DO $wave1_revalidate$")
    first_mutation = syntax_only.find("ALTER TABLE platform.authority_fences")
    if first_mutation < 0:
        findings.append("Wave 1 reused fence publication contract lost canonical mutation anchor")
    if lock_pos >= 0 and block_pos >= 0 and lock_pos > block_pos:
        findings.append("Wave 1 reused fence publication preflight must run under the held table lock")
    if first_mutation >= 0 and block_pos > first_mutation:
        findings.append("Wave 1 reused fence publication preflight must precede canonical mutation")

    guards = (
        (
            "inbound subscription",
            _reuse_static_guard(
                "pg_subscription_rel",
                "sr",
                "srrelid",
                "v_table",
                "logical replication subscription can write authority_fences",
            ),
        ),
        (
            "explicit publication relation",
            _reuse_static_guard(
                "pg_publication_rel",
                "pr",
                "prrelid",
                "v_table",
                "logical replication publication can disclose authority_fences explicitly",
            ),
        ),
        (
            "FOR ALL TABLES publication",
            _reuse_static_guard(
                "pg_publication",
                "p",
                None,
                None,
                "FOR ALL TABLES publication can disclose authority_fences",
            ),
        ),
    )
    for label, guard in guards:
        if _find_sequence(block_tokens, guard) < 0:
            findings.append(
                f"Wave 1 reused fence publication contract lost parsed {label} fail-closed predicate"
            )

    catalog_guard_pos = _find_sequence(block_tokens, _schema_catalog_guard())
    if catalog_guard_pos < 0:
        findings.append(
            "Wave 1 reused fence publication contract lost parsed version-tolerant schema-publication catalog guard"
        )

    dynamic_query = _dynamic_schema_publication_query(block_tokens)
    if dynamic_query is None:
        findings.append(
            "Wave 1 reused fence publication contract lost schema-publication EXECUTE/INTO/USING binding"
        )
    else:
        try:
            dynamic_tokens = _sql_tokens(dynamic_query)
        except ValueError:
            findings.append("Wave 1 reused fence schema-publication dynamic query is malformed")
        else:
            if tuple(dynamic_tokens) != _expected_schema_publication_query():
                findings.append(
                    "Wave 1 reused fence schema-publication dynamic predicate drifted from exact namespace binding"
                )

    if _find_sequence(block_tokens, _schema_result_guard()) < 0:
        findings.append(
            "Wave 1 reused fence publication contract lost fail-closed schema-publication result guard"
        )

    # The block itself must remain before canonical mutation. Parsing guards only inside
    # this block prevents matching a correct predicate in dead/later executable text.
    if first_mutation >= 0:
        block_end = block_pos + len(block)
        if block_end > first_mutation:
            findings.append("Wave 1 reused fence publication preflight must finish before canonical mutation")

    if "pg_catalog.pg_publication" not in block_syntax:
        findings.append("Wave 1 reused fence publication contract lost executable publication catalog references")
    return findings


def validate_boundary_text(text: object) -> list[str]:
    if not isinstance(text, str):
        return ["Wave 1 fence logical-replication boundary must be text"]
    return [
        f"Wave 1 fence logical-replication boundary missing law: {law}"
        for law in REQUIRED_LAWS
        if law not in text
    ]


def validate_manifest_object(value: object) -> list[str]:
    if not isinstance(value, dict):
        return ["Wave 1 fence logical-replication manifest must be a JSON object"]
    return [] if value == EXPECTED_MANIFEST else [
        "Wave 1 fence logical-replication manifest drifted from the exact accepted implementation boundary"
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
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(f"Wave 1 logical-replication manifest unreadable: {exc}")
    else:
        findings.extend(validate_manifest_object(manifest))
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
    print("RESULT: PASS — parsed fresh/reused fence logical-replication writer and disclosure predicates fail closed before authority mutation")
    print("NOTE: PASS proves static migration conformance only; C2 database/admin authority remains separately governed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
