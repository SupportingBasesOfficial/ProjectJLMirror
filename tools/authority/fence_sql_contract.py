#!/usr/bin/env python3
"""Fail-closed structural checks for the Wave 1 IR-D-003 PostgreSQL fence contract."""

from __future__ import annotations

CANONICAL_IDENTIFIER_REGEX = "^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$"
CANONICAL_REGEX_OPERATOR = 'COLLATE "C" ~'


def _predicate(name: str) -> str:
    return f"{name} {CANONICAL_REGEX_OPERATOR} '{CANONICAL_IDENTIFIER_REGEX}'"


def validate_fence_sql_text(text: str) -> list[str]:
    if not isinstance(text, str):
        return ["IR-D-003 SQL contract must be text"]

    findings: list[str] = []
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
    )
    for fragment in required:
        if fragment not in text:
            findings.append(f"IR-D-003 SQL canonical identifier invariant missing: {fragment}")

    # A prose mention of the regex is not sufficient. Each authoritative persisted
    # identifier and each effectful successor input needs an executable C-collated predicate.
    executable_uses = text.count(
        f"{CANONICAL_REGEX_OPERATOR} '{CANONICAL_IDENTIFIER_REGEX}'"
    )
    if executable_uses < 6:
        findings.append(
            "IR-D-003 SQL canonical identifier grammar is not C-collated/enforced at every required storage/effect boundary"
        )

    return findings
