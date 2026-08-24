#!/usr/bin/env python3
"""Fail-closed structural checks for the Wave 1 IR-D-003 PostgreSQL fence contract."""

from __future__ import annotations

CANONICAL_IDENTIFIER_REGEX = "^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$"
CANONICAL_REGEX_OPERATOR = 'COLLATE "C" ~'
EFFECT_ELIGIBLE_PREDECESSOR_PREDICATE = "authority_fences.authority_state = 'active'"


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
        EFFECT_ELIGIBLE_PREDECESSOR_PREDICATE,
    )
    for fragment in required:
        if fragment not in text:
            findings.append(f"IR-D-003 SQL canonical/effect-authority invariant missing: {fragment}")

    executable_uses = text.count(
        f"{CANONICAL_REGEX_OPERATOR} '{CANONICAL_IDENTIFIER_REGEX}'"
    )
    if executable_uses < 6:
        findings.append(
            "IR-D-003 SQL canonical identifier grammar is not C-collated/enforced at every required storage/effect boundary"
        )

    return findings


def validate_fence_revalidation_sql_text(text: str) -> list[str]:
    """Require existing persisted fence state to prove the same canonical contract."""

    if not isinstance(text, str):
        return ["IR-D-003 fence revalidation migration must be text"]

    findings: list[str] = []
    required = (
        "to_regclass('platform.authority_fences')",
        "authority_fences is absent; apply 001 before revalidation",
        "attname = 'fence_scope_id'",
        "IS DISTINCT FROM 'text'::regtype",
        "attname = 'current_fence_epoch'",
        "IS DISTINCT FROM 'int8'::regtype",
        "attname = 'current_generation_id'",
        "attname = 'authority_state'",
        "attname = 'updated_at'",
        "IS DISTINCT FROM 'timestamptz'::regtype",
        "c.contype = 'p'",
        "c.conkey = ARRAY[a.attnum]::smallint[]",
        "single-column primary key on fence_scope_id",
        "ALTER TABLE platform.authority_fences",
        "ALTER COLUMN fence_scope_id SET NOT NULL",
        "ALTER COLUMN current_fence_epoch SET NOT NULL",
        "ALTER COLUMN current_generation_id SET NOT NULL",
        "ALTER COLUMN authority_state SET NOT NULL",
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
        if fragment not in text:
            findings.append(
                f"IR-D-003 persisted fence revalidation invariant missing: {fragment}"
            )

    if "UPDATE platform.authority_fences" in text or "DELETE FROM platform.authority_fences" in text:
        findings.append(
            "IR-D-003 revalidation migration must not normalize/delete historical authority rows to make validation pass"
        )
    return findings
