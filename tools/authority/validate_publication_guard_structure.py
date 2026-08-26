#!/usr/bin/env python3
"""Structural reachability assurance for Wave 1 publication guards.

This complements validate_fence_publication_safety.py. It proves required guards are
statements in the intended PL/pgSQL DO body, not text hidden in ordinary/dollar-quoted
literals or nested behind conditional/repetition wrappers.
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authority.fence_sql_contract import _executable_sql  # noqa: E402
from tools.authority.validate_fence_publication_safety import (  # noqa: E402
    BOOTSTRAP_PATH,
    REUSE_PATH,
    _bootstrap_publication_guard,
    _expected_schema_publication_query,
    _find_sequence,
    _reuse_static_guard,
    _schema_catalog_guard,
    _schema_result_guard,
    _word,
    _symbol,
    _string,
    _number,
    _parameter,
)

PROFILE = "jlmirror-wave1-publication-guard-structure/v1"
Token = tuple[str, str]


def _extract_do_body(code: str, tag: str) -> tuple[str, list[str]]:
    opener = f"DO ${tag}$"
    closer = f"${tag}$;"

    # Mask ordinary SQL strings so a marker mentioned inside one cannot become the
    # structural DO boundary. Character positions are preserved.
    masked = list(code)
    i = 0
    while i < len(masked):
        if masked[i] != "'":
            i += 1
            continue
        masked[i] = " "
        i += 1
        while i < len(masked):
            if masked[i] == "'":
                masked[i] = " "
                if i + 1 < len(masked) and masked[i + 1] == "'":
                    masked[i + 1] = " "
                    i += 2
                    continue
                i += 1
                break
            if masked[i] != "\n":
                masked[i] = " "
            i += 1
    structural = "".join(masked)

    start = structural.find(opener)
    if start < 0:
        return "", [f"missing structural DO opener {opener}"]
    body_start = start + len(opener)
    end = structural.find(closer, body_start)
    if end < 0:
        return "", [f"missing structural DO closer {closer}"]
    if structural.find(opener, body_start) >= 0 and structural.find(opener, body_start) < end:
        return "", [f"nested/duplicate structural DO opener {opener}"]
    return code[body_start:end], []


def _body_tokens(text: str) -> list[Token]:
    """Tokenize one extracted PL/pgSQL body; nested dollar quotes are opaque data."""

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
                    delimiter = text[i : j + 1]
                    close = text.find(delimiter, j + 1)
                    if close < 0:
                        raise ValueError("unterminated dollar-quoted literal")
                    tokens.append(("dollar_string", text[j + 1 : close]))
                    i = close + len(delimiter)
                    continue

        if ch == '"':
            i += 1
            value: list[str] = []
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


def _control_depth_before(tokens: list[Token]) -> list[int]:
    """Return IF/CASE/LOOP nesting depth before each token.

    Required publication guards are intentionally top-level statements in their DO
    body. The schema-publication query/result are the only accepted nested statements,
    directly inside the version-tolerant catalog IF.
    """

    depth = 0
    result: list[int] = []
    i = 0
    while i < len(tokens):
        result.append(depth)
        token = tokens[i]
        next_token = tokens[i + 1] if i + 1 < len(tokens) else None
        prev_token = tokens[i - 1] if i else None

        if token == _word("END") and next_token in {_word("IF"), _word("LOOP"), _word("CASE")}:
            depth = max(0, depth - 1)
        elif token == _word("IF") and prev_token != _word("END"):
            depth += 1
        elif token == _word("LOOP") and prev_token != _word("END"):
            depth += 1
        elif token == _word("CASE") and prev_token != _word("END"):
            depth += 1
        i += 1
    return result


def _sequence_at_depth(
    tokens: list[Token],
    expected: tuple[Token, ...],
    depth: int,
    label: str,
) -> tuple[int, list[str]]:
    pos = _find_sequence(tokens, expected)
    if pos < 0:
        return -1, [f"{label} is missing from parsed PL/pgSQL body"]
    depths = _control_depth_before(tokens)
    if depths[pos] != depth:
        return pos, [
            f"{label} must execute at control depth {depth}, found depth {depths[pos]}"
        ]
    return pos, []


def _dynamic_schema_query(tokens: list[Token]) -> tuple[int, str | None]:
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
            return index, "".join(parts)
    return -1, None


def validate_bootstrap_structure(text: object) -> list[str]:
    if not isinstance(text, str):
        return ["Wave 1 bootstrap publication structure must be text"]
    code = _executable_sql(text)
    if not code:
        return ["Wave 1 bootstrap publication structure is malformed"]
    body, findings = _extract_do_body(code, "wave1_bootstrap")
    if findings:
        return findings
    try:
        tokens = _body_tokens(body)
    except ValueError as exc:
        return [f"Wave 1 bootstrap publication structure cannot be tokenized: {exc}"]

    guard_pos, guard_findings = _sequence_at_depth(
        tokens,
        _bootstrap_publication_guard(),
        0,
        "fresh FOR ALL TABLES publication guard",
    )
    findings.extend(guard_findings)
    create_pos, create_findings = _sequence_at_depth(
        tokens,
        (_word("EXECUTE"), _string("CREATE SCHEMA platform"), _symbol(";")),
        0,
        "fresh first persistent CREATE",
    )
    findings.extend(create_findings)
    if guard_pos >= 0 and create_pos >= 0 and guard_pos > create_pos:
        findings.append("fresh publication guard must execute before first persistent CREATE")
    return findings


def validate_reuse_structure(text: object) -> list[str]:
    if not isinstance(text, str):
        return ["Wave 1 reuse publication structure must be text"]
    code = _executable_sql(text)
    if not code:
        return ["Wave 1 reuse publication structure is malformed"]
    body, findings = _extract_do_body(code, "wave1_revalidate")
    if findings:
        return findings
    try:
        tokens = _body_tokens(body)
    except ValueError as exc:
        return [f"Wave 1 reuse publication structure cannot be tokenized: {exc}"]

    guards = (
        (
            "inbound subscription guard",
            _reuse_static_guard(
                "pg_subscription_rel",
                "sr",
                "srrelid",
                "v_table",
                "logical replication subscription can write authority_fences",
            ),
        ),
        (
            "explicit publication relation guard",
            _reuse_static_guard(
                "pg_publication_rel",
                "pr",
                "prrelid",
                "v_table",
                "logical replication publication can disclose authority_fences explicitly",
            ),
        ),
        (
            "FOR ALL TABLES publication guard",
            _reuse_static_guard(
                "pg_publication",
                "p",
                None,
                None,
                "FOR ALL TABLES publication can disclose authority_fences",
            ),
        ),
    )
    for label, expected in guards:
        _, guard_findings = _sequence_at_depth(tokens, expected, 0, label)
        findings.extend(guard_findings)

    catalog_pos, catalog_findings = _sequence_at_depth(
        tokens,
        _schema_catalog_guard(),
        0,
        "schema-publication version-tolerant catalog guard",
    )
    findings.extend(catalog_findings)

    dynamic_pos, dynamic_query = _dynamic_schema_query(tokens)
    depths = _control_depth_before(tokens)
    if dynamic_pos < 0 or dynamic_query is None:
        findings.append("schema-publication dynamic query binding is missing")
    else:
        if depths[dynamic_pos] != 1:
            findings.append(
                f"schema-publication dynamic query must execute directly inside catalog guard, found control depth {depths[dynamic_pos]}"
            )
        try:
            query_tokens = _body_tokens(dynamic_query)
        except ValueError as exc:
            findings.append(f"schema-publication dynamic query cannot be tokenized: {exc}")
        else:
            if tuple(query_tokens) != _expected_schema_publication_query():
                findings.append("schema-publication dynamic query predicate drifted from exact namespace binding")

    result_pos, result_findings = _sequence_at_depth(
        tokens,
        _schema_result_guard(),
        1,
        "schema-publication fail-closed result guard",
    )
    findings.extend(result_findings)

    if catalog_pos >= 0 and dynamic_pos >= 0 and dynamic_pos < catalog_pos:
        findings.append("schema-publication dynamic query executes before its version-tolerant catalog guard")
    if dynamic_pos >= 0 and result_pos >= 0 and result_pos < dynamic_pos:
        findings.append("schema-publication result guard executes before its dynamic query")

    # A top-level RETURN would skip the remainder of this preflight while canonical
    # ALTER statements outside the DO block would still execute.
    depths = _control_depth_before(tokens)
    for index, token in enumerate(tokens):
        if token == _word("RETURN") and depths[index] == 0:
            findings.append("reuse publication preflight contains top-level RETURN bypass")
            break
    return findings


def validate() -> list[str]:
    findings: list[str] = []
    try:
        bootstrap = BOOTSTRAP_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        findings.append(f"Wave 1 bootstrap SQL unreadable: {exc}")
    else:
        findings.extend(validate_bootstrap_structure(bootstrap))
    try:
        reuse = REUSE_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        findings.append(f"Wave 1 reuse SQL unreadable: {exc}")
    else:
        findings.extend(validate_reuse_structure(reuse))
    return findings


def main() -> int:
    findings = validate()
    print(f"JLMIRROR Wave 1 publication guard structure: {PROFILE}")
    print(f"Repository root: {ROOT}")
    if findings:
        print("RESULT: FAIL")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("RESULT: PASS — publication guards are reachable at the required PL/pgSQL control depth and cannot be laundered through ordinary/dollar-quoted dead text")
    print("NOTE: PASS is static conformance evidence only; C2 database/admin authority remains separately governed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
