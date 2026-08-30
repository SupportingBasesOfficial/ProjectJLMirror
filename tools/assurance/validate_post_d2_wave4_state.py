#!/usr/bin/env python3
"""Validate post-D2 OPEN-REL-030 / Wave 4 readiness-state consistency."""

from __future__ import annotations

import re
import sys
from pathlib import Path

MERGE_SHA = "2ffec007d7dff32e0a45116b0bc875d5c2743b12"

FILES = {
    "transition": Path("docs/16-implementation-readiness/18-d2-track-b-acceptance-propagation.md"),
    "open_register": Path("docs/16-implementation-readiness/03-consolidated-open-decision-register.md"),
    "blockers": Path("docs/16-implementation-readiness/10-implementation-conformance-and-blockers.md"),
    "sequencing": Path("docs/16-implementation-readiness/11-initial-implementation-sequencing.md"),
    "slice_manifest": Path("docs/16-implementation-readiness/15-implementation-slice-readiness-manifest.md"),
}

AUTHORITY_STATE_HEADING = "## Readiness propagation requirements"
EXPECTED_AUTHORITY_STATE = {
    "open_rel_030_track_b": "accepted",
    "open_rel_030_profile": "selected_and_conformed",
    "customer_telemetry_slice": "eligible_for_implementation_authorization",
    "wave4_monitoring": "eligible_for_separate_explicit_authorization",
    "wave4_implementation_authorization": "not_granted",
    "production_authority": "none",
    "open_rel_020_production_state": "open_c3",
}

_ASSIGNMENT_RE = re.compile(r"^([a-z][a-z0-9_]*)\s*=\s*([a-z][a-z0-9_]*)$")
_WAVE4_SUBJECT_RE = re.compile(
    r"(?:\bwave\s*4\b|\bwave4\b|monitoring\s*/\s*zabbix|customer[ -]telemetry)"
)
_PRODUCTION_SUBJECT_RE = re.compile(r"\bproduction\b")
_CLAUSE_SPLIT_RE = re.compile(
    r"(?:\s*;\s*|\s*[.!?]\s+|\s*,\s*(?:but|however|yet)\s+|\s+\b(?:but|however|yet|and)\b\s+)"
)
_PRESENT_GRANT_RE = re.compile(
    r"(?:"
    r"\b(?:is|are|was|were|has been|have been)\s+"
    r"(?:authorized|authorised|granted|approved|activated|permitted|allowed)\b"
    r"(?:\s+(?:to\s+implement|for\s+implementation|to\s+proceed|for\s+deployment))?"
    r"|"
    r"\b(?:authorized|authorised|granted|permitted|allowed)\s+to\s+implement\b"
    r"|"
    r"\b(?:may|can)\s+(?:now\s+)?(?:proceed|deploy|implement)\b"
    r"|"
    r"\b(?:implementation|production deployment|deployment)\s+"
    r"(?:is|are|has been|have been)\s+"
    r"(?:authorized|authorised|granted|approved|activated|permitted|allowed)\b"
    r")"
)
_NON_GRANT_RE = re.compile(
    r"(?:"
    r"\b(?:not|never)\s+(?:currently\s+)?"
    r"(?:authorized|authorised|granted|approved|activated|permitted|allowed)\b"
    r"|"
    r"\b(?:cannot|can't|may not|must not)\s+(?:now\s+)?(?:proceed|deploy|implement)\b"
    r"|"
    r"\bdoes\s+not\s+authorize\b"
    r"|"
    r"\b(?:authorized|authorised|granted|approved|activated|permitted|allowed)\b"
    r"(?:\s+to\s+implement|\s+for\s+implementation|\s+to\s+proceed|\s+for\s+deployment)?"
    r"\s+only\s+(?:after|if|when|once|upon|subject to)\b"
    r"|"
    r"\b(?:may|can)\s+(?:now\s+)?(?:proceed|deploy|implement)\s+only\s+"
    r"(?:after|if|when|once|upon|subject to)\b"
    r"|"
    r"\bwhether\b.*\b(?:authorized|authorised|granted|approved|permitted|allowed)\b"
    r".*\b(?:undecided|unknown|open|pending|unresolved)\b"
    r")"
)
_OPEN_REL_020_CLOSURE_RE = re.compile(
    r"(?:"
    r"\bopen-rel-020\b\s*(?:=|:)\s*(?:closed|resolved|accepted|complete|completed)\b"
    r"|"
    r"\bopen-rel-020\b\s+(?:is|was|has been|became)\s+"
    r"(?:closed|resolved|accepted|complete|completed)\b"
    r")"
)


def _read(root: Path, key: str) -> str:
    path = root / FILES[key]
    if not path.is_file():
        raise AssertionError(f"missing required post-D2 state file: {FILES[key]}")
    return path.read_text(encoding="utf-8")


def _require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"{label}: missing required marker: {needle!r}")


def _forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"{label}: stale/forbidden marker remains: {needle!r}")


def _parse_authority_state(transition: str) -> dict[str, str]:
    heading_index = transition.find(AUTHORITY_STATE_HEADING)
    if heading_index < 0:
        raise AssertionError("transition: missing structured authority-state heading")

    section_start = heading_index + len(AUTHORITY_STATE_HEADING)
    next_heading = transition.find("\n## ", section_start)
    section = transition[section_start:] if next_heading < 0 else transition[section_start:next_heading]
    fence = re.search(r"```text\s*\n(.*?)\n```", section, re.DOTALL)
    if fence is None:
        raise AssertionError("transition: missing structured authority-state block")

    state: dict[str, str] = {}
    for raw in fence.group(1).splitlines():
        line = raw.strip()
        if not line:
            continue
        match = _ASSIGNMENT_RE.fullmatch(line)
        if match is None:
            raise AssertionError(
                f"transition: non-canonical authority-state line: {line!r}"
            )
        key, value = match.groups()
        if key in state:
            raise AssertionError(f"transition: duplicate authority-state key: {key}")
        state[key] = value

    if state != EXPECTED_AUTHORITY_STATE:
        raise AssertionError(
            f"transition: authority-state mismatch: expected={EXPECTED_AUTHORITY_STATE} actual={state}"
        )
    return state


def _plain_line(raw: str) -> str:
    line = raw.casefold()
    line = line.replace("`", "").replace("*", "").replace("_", " ")
    return re.sub(r"\s+", " ", line).strip()


def _machine_line(raw: str) -> str:
    line = raw.casefold().replace("`", "").replace("*", "")
    return re.sub(r"\s+", " ", line).strip()


def _iter_clauses(line: str) -> tuple[str, ...]:
    clauses = tuple(
        part.strip(" ,;:-")
        for part in _CLAUSE_SPLIT_RE.split(line)
        if part.strip(" ,;:-")
    )
    return clauses or (line,)


def _is_question_or_conditional_non_grant(clause: str, raw: str) -> bool:
    if raw.strip().endswith("?"):
        return True
    return _NON_GRANT_RE.search(clause) is not None


def _reject_machine_authority_overrides(key: str, raw: str) -> None:
    line = _machine_line(raw)

    wave4 = re.search(
        r"\bwave4_implementation_authorization\s*(?:=|:)\s*([a-z][a-z0-9_]*)\b",
        line,
    )
    if wave4 and wave4.group(1) != "not_granted":
        raise AssertionError(
            f"{key}: contradictory Wave 4 authority assignment: {raw.strip()!r}"
        )

    production = re.search(
        r"\bproduction_authority\s*(?:=|:)\s*([a-z][a-z0-9_]*)\b",
        line,
    )
    if production and production.group(1) != "none":
        raise AssertionError(
            f"{key}: contradictory production authority assignment: {raw.strip()!r}"
        )

    open_rel = re.search(
        r"\bopen_rel_020_production_state\s*(?:=|:)\s*([a-z][a-z0-9_]*)\b",
        line,
    )
    if open_rel and open_rel.group(1) != "open_c3":
        raise AssertionError(
            f"{key}: contradictory OPEN-REL-020 structured state: {raw.strip()!r}"
        )


def _reject_contradictory_authority_prose(docs: dict[str, str]) -> None:
    """Reject present-tense grants while allowing scoped denial/conditions/questions.

    The structured transition block owns machine authority. Descriptive prose must not
    contradict it. We parse clauses rather than using an 80-character prefix so a safe
    statement in one clause cannot conceal a positive grant in a later clause.
    """

    for key, text in docs.items():
        for raw in text.splitlines():
            if not raw.strip():
                continue
            _reject_machine_authority_overrides(key, raw)

            line = _plain_line(raw)
            if not line:
                continue

            if _OPEN_REL_020_CLOSURE_RE.search(line):
                raise AssertionError(
                    f"{key}: contradictory OPEN-REL-020 closure claim: {raw.strip()!r}"
                )

            wave4_scope = _WAVE4_SUBJECT_RE.search(line) is not None
            production_scope = _PRODUCTION_SUBJECT_RE.search(line) is not None

            if not (wave4_scope or production_scope):
                continue

            for clause in _iter_clauses(line):
                grant = _PRESENT_GRANT_RE.search(clause)
                if grant is None:
                    continue
                if _is_question_or_conditional_non_grant(clause, raw):
                    continue

                if wave4_scope:
                    raise AssertionError(
                        f"{key}: positive Wave 4/Monitoring authority prose is forbidden: "
                        f"{raw.strip()!r}"
                    )
                if production_scope:
                    raise AssertionError(
                        f"{key}: positive production authority prose is forbidden: "
                        f"{raw.strip()!r}"
                    )


def validate(root: Path) -> None:
    docs = {key: _read(root, key) for key in FILES}

    transition = docs["transition"]
    _require(transition, MERGE_SHA, "transition")
    authority_state = _parse_authority_state(transition)
    if authority_state["wave4_implementation_authorization"] != "not_granted":
        raise AssertionError("transition: Wave 4 implementation authority must remain not_granted")
    if authority_state["production_authority"] != "none":
        raise AssertionError("transition: production authority must remain none")
    if authority_state["open_rel_020_production_state"] != "open_c3":
        raise AssertionError("transition: OPEN-REL-020 production state must remain open_c3")
    _require(transition, "READY_TO_AUTHORIZE != AUTHORIZED_TO_IMPLEMENT", "transition")

    open_register = docs["open_register"]
    _require(open_register, "`OPEN-REL-030` | C2 | **ACCEPTED / selected + conformed", "open register")
    _require(open_register, MERGE_SHA, "open register")
    _require(open_register, "`OPEN-REL-020`", "open register")

    blockers = docs["blockers"]
    _require(blockers, "former `OPEN-REL-030` evidence blocker is **satisfied", "blockers")
    _require(blockers, "`eligible_for_implementation_authorization`", "blockers")
    _require(blockers, "not authorized to implement", "blockers")
    _require(blockers, "`OPEN-REL-020`", "blockers")

    sequencing = docs["sequencing"]
    _require(sequencing, "Track A accepted + Track B accepted", "sequencing")
    _require(sequencing, "eligible_for_separate_explicit_authorization", "sequencing")
    _require(sequencing, "READY_TO_AUTHORIZE != AUTHORIZED_TO_IMPLEMENT", "sequencing")

    manifest = docs["slice_manifest"]
    _require(manifest, "`impl.customer-telemetry@1`", "slice manifest")
    _require(
        manifest,
        "`eligible_for_implementation_authorization` for the accepted Track B profile merged by PR #40",
        "slice manifest",
    )
    _require(
        manifest,
        "accepted Monitoring/Zabbix subprofile is `eligible_for_implementation_authorization`",
        "slice manifest",
    )
    _require(
        manifest,
        "every other concrete provider/effectful subprofile remains `deferred_product_gated`",
        "slice manifest",
    )

    current_state_text = "\n".join(
        docs[key] for key in ("open_register", "blockers", "sequencing", "slice_manifest")
    )
    for stale in (
        "`OPEN-REL-030` NOT conformed",
        "`bounded_evidence_spike_eligible`; canonical ingestion/projection implementation blocked",
        "Blocked until `OPEN-REL-030` C2 durable acceptance/projection mechanism",
        "remains blocked until the C2 durable acceptance/projection mechanism required by `OPEN-REL-030`",
    ):
        _forbid(current_state_text, stale, "post-D2 current-state surfaces")

    _reject_contradictory_authority_prose(docs)


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    try:
        validate(root)
    except AssertionError as exc:
        print(f"post_d2_wave4_state_guard=FAIL reason={exc}", file=sys.stderr)
        return 1

    print(
        "post_d2_wave4_state_guard=PASS "
        "track_b=accepted telemetry_slice=eligible wave4_authorization=not_granted "
        "production_authority=none open_rel_020=open_c3 authority_state=structured "
        "prose_guard=clause_scoped"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
