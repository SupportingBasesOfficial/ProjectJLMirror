#!/usr/bin/env python3
"""Fail-closed ancestry/exception assurance for Wave 1 publication guards."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.authority.fence_sql_contract import _executable_sql  # noqa: E402
from tools.authority.validate_fence_publication_safety import (  # noqa: E402
    BOOTSTRAP_PATH,
    REUSE_PATH,
    _find_sequence,
    _schema_catalog_guard,
    _schema_result_guard,
    _string,
    _symbol,
    _word,
)
from tools.authority.validate_publication_guard_structure import (  # noqa: E402
    _body_tokens,
    _control_depth_before,
    _extract_do_body,
)

PROFILE = "jlmirror-wave1-publication-guard-ancestry/v1"
MANIFEST_PATH = ROOT / "implementation" / "wave-1" / "FENCE_PUBLICATION_GUARD_MANIFEST.json"
EXPECTED_MANIFEST = {
    "profile": PROFILE,
    "authority_scope": "platform.authority_fences",
    "fresh_preflight": {
        "required_static_guard_control_depth": 0,
        "exception_handlers_allowed": False,
    },
    "reuse_preflight": {
        "required_static_guard_control_depth": 0,
        "schema_catalog_guard_control_depth": 0,
        "schema_query_and_result_are_exact_children": True,
        "exception_handlers_allowed": False,
        "top_level_return_allowed": False,
    },
    "forbidden_substitutions": [
        "numeric_control_depth_for_block_ancestry",
        "raise_exception_presence_for_unsuppressed_failure",
    ],
    "product_feature_activation": "none",
    "wave_2_authorized": False,
}
Token = tuple[str, str]


def _complete_schema_publication_guard() -> tuple[Token, ...]:
    return (
        *_schema_catalog_guard(),
        _word("EXECUTE"),
        _string("SELECT EXISTS ("),
        _string("SELECT 1 FROM pg_catalog.pg_publication_namespace pn "),
        _string("WHERE pn.pnnspid OPERATOR(pg_catalog.=) $1)"),
        _word("INTO"),
        _word("v_schema_publication_exists"),
        _word("USING"),
        _word("v_schema"),
        _symbol(";"),
        *_schema_result_guard(),
        _word("END"),
        _word("IF"),
        _symbol(";"),
    )


def _exception_handler_findings(tokens: list[Token], label: str) -> list[str]:
    findings: list[str] = []
    for index, token in enumerate(tokens):
        if token != _word("EXCEPTION"):
            continue
        previous = tokens[index - 1] if index else None
        if previous != _word("RAISE"):
            findings.append(
                f"{label} contains a PL/pgSQL EXCEPTION handler that can swallow fail-closed publication denial"
            )
            break
    return findings


def _parsed_do_tokens(text: object, tag: str, label: str) -> tuple[list[Token], list[str]]:
    if not isinstance(text, str):
        return [], [f"{label} must be text"]
    code = _executable_sql(text)
    if not code:
        return [], [f"{label} is malformed or cannot be parsed conservatively"]
    body, findings = _extract_do_body(code, tag)
    if findings:
        return [], [f"{label}: {finding}" for finding in findings]
    try:
        return _body_tokens(body), []
    except ValueError as exc:
        return [], [f"{label} cannot be tokenized conservatively: {exc}"]


def validate_bootstrap_ancestry(text: object) -> list[str]:
    tokens, findings = _parsed_do_tokens(
        text, "wave1_bootstrap", "Wave 1 fresh publication preflight"
    )
    if findings:
        return findings
    findings.extend(_exception_handler_findings(tokens, "Wave 1 fresh publication preflight"))
    return findings


def validate_reuse_ancestry(text: object) -> list[str]:
    tokens, findings = _parsed_do_tokens(
        text, "wave1_revalidate", "Wave 1 reused publication preflight"
    )
    if findings:
        return findings
    findings.extend(_exception_handler_findings(tokens, "Wave 1 reused publication preflight"))

    complete = _complete_schema_publication_guard()
    position = _find_sequence(tokens, complete)
    if position < 0:
        findings.append(
            "schema-publication dynamic query/result are not exact children of the version-tolerant pg_publication_namespace catalog guard"
        )
        return findings

    depths = _control_depth_before(tokens)
    if depths[position] != 0:
        findings.append(
            "complete schema-publication catalog guard must execute at top-level control depth 0"
        )
    return findings


def validate_manifest_object(value: object) -> list[str]:
    if not isinstance(value, dict):
        return ["Wave 1 publication ancestry manifest must be a JSON object"]
    if value != EXPECTED_MANIFEST:
        return ["Wave 1 publication ancestry manifest drifted from exact fail-closed boundary"]
    return []


def validate() -> list[str]:
    findings: list[str] = []
    try:
        bootstrap = BOOTSTRAP_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        findings.append(f"Wave 1 bootstrap SQL unreadable: {exc}")
    else:
        findings.extend(validate_bootstrap_ancestry(bootstrap))
    try:
        reuse = REUSE_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        findings.append(f"Wave 1 reuse SQL unreadable: {exc}")
    else:
        findings.extend(validate_reuse_ancestry(reuse))
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(f"Wave 1 publication ancestry manifest unreadable: {exc}")
    else:
        findings.extend(validate_manifest_object(manifest))
    return findings


def main() -> int:
    findings = validate()
    print(f"JLMIRROR Wave 1 publication guard ancestry: {PROFILE}")
    print(f"Repository root: {ROOT}")
    if findings:
        print("RESULT: FAIL")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print(
        "RESULT: PASS — schema-publication query/result are bound to the exact catalog guard and publication preflights cannot suppress denial through PL/pgSQL exception handlers"
    )
    print("NOTE: PASS is static conformance evidence only; database/admin segregation remains C2.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
