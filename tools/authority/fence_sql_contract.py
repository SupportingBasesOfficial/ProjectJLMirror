#!/usr/bin/env python3
"""Fail-closed structural checks for the Wave 1 IR-D-003 PostgreSQL fence contract."""

from __future__ import annotations

CANONICAL_IDENTIFIER_REGEX = "^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$"


def validate_fence_sql_text(text: str) -> list[str]:
    if not isinstance(text, str):
        return ["IR-D-003 SQL contract must be text"]

    findings: list[str] = []
    required = (
        "CHECK (btrim(fence_scope_id) <> '')",
        f"CHECK (fence_scope_id ~ '{CANONICAL_IDENTIFIER_REGEX}')",
        "CHECK (btrim(current_generation_id) <> '')",
        f"CHECK (current_generation_id ~ '{CANONICAL_IDENTIFIER_REGEX}')",
        "CHECK (btrim(authority_state) <> '')",
        f"CHECK (authority_state ~ '{CANONICAL_IDENTIFIER_REGEX}')",
        f"p_expected_predecessor_generation_id ~ '{CANONICAL_IDENTIFIER_REGEX}'",
        f"p_successor_generation_id ~ '{CANONICAL_IDENTIFIER_REGEX}'",
        f"p_successor_state ~ '{CANONICAL_IDENTIFIER_REGEX}'",
    )
    for fragment in required:
        if fragment not in text:
            findings.append(f"IR-D-003 SQL canonical identifier invariant missing: {fragment}")

    # A prose mention of the regex is not sufficient. Each authoritative persisted
    # identifier and each effectful successor input needs an executable predicate.
    executable_uses = text.count(f"~ '{CANONICAL_IDENTIFIER_REGEX}'")
    if executable_uses < 6:
        findings.append(
            "IR-D-003 SQL canonical identifier grammar is not enforced at every required storage/effect boundary"
        )

    return findings
