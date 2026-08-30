#!/usr/bin/env python3
"""Validate post-D2 OPEN-REL-030 / Wave 4 readiness-state consistency.

Authority is machine-owned by the structured readiness block. The five current-state
Markdown surfaces are content-addressed governance snapshots: deterministic assurance
does not attempt free-form NLP. Any prose edit changes a governed blob and requires an
explicit reviewed re-baseline. Structured authority values remain independently checked,
so re-baselining prose cannot silently grant Wave 4, production authority, or close
OPEN-REL-020.
"""

from __future__ import annotations

import hashlib
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

# Git blob OIDs are content identities and survive branch deletion and squash merge.
# Updating any governed surface requires an explicit review-visible re-baseline here.
EXPECTED_SURFACE_BLOBS = {
    "transition": "9fd9408a4d6d4974a0e5aad5663b02f5aa85a366",
    "open_register": "577eea9144955f59e7ce9c3c0d444eb19de50220",
    "blockers": "083e218d26f57851c52ce7004d7aab78d3c6249a",
    "sequencing": "43ef17e9eee910e89024fea5c7c0cdb87fd80b31",
    "slice_manifest": "3f5f72e1b616ebac623e6f2f54d47cac79a93fe5",
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


def _git_blob_oid(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def compute_surface_blobs(root: Path) -> dict[str, str]:
    blobs: dict[str, str] = {}
    for key, relative in FILES.items():
        path = root / relative
        if not path.is_file():
            raise AssertionError(f"missing required post-D2 state file: {relative}")
        blobs[key] = _git_blob_oid(path.read_bytes())
    return blobs


def _validate_surface_blobs(
    root: Path,
    expected_surface_blobs: dict[str, str],
) -> None:
    if set(expected_surface_blobs) != set(FILES):
        raise AssertionError(
            "governed surface baseline keys must exactly match FILES: "
            f"expected={sorted(FILES)} actual={sorted(expected_surface_blobs)}"
        )

    actual = compute_surface_blobs(root)
    for key in FILES:
        expected = expected_surface_blobs[key]
        if not re.fullmatch(r"[0-9a-f]{40}", expected):
            raise AssertionError(f"{key}: invalid governed blob oid: {expected!r}")
        if actual[key] != expected:
            raise AssertionError(
                f"{key}: governed current-state surface drift: "
                f"expected_blob={expected} actual_blob={actual[key]}; "
                "authority prose/state edits require an explicit reviewed re-baseline"
            )


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


def _machine_line(raw: str) -> str:
    line = raw.casefold().replace("`", "").replace("*", "")
    return re.sub(r"\s+", " ", line).strip()


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


def validate(
    root: Path,
    *,
    expected_surface_blobs: dict[str, str] | None = None,
) -> None:
    baseline = EXPECTED_SURFACE_BLOBS if expected_surface_blobs is None else expected_surface_blobs
    _validate_surface_blobs(root, baseline)

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

    # Machine-looking overrides remain semantically checked even after an intentional
    # content re-baseline; prose itself is governed by exact content identity.
    for key, text in docs.items():
        for raw in text.splitlines():
            if raw.strip():
                _reject_machine_authority_overrides(key, raw)


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
        "governed_surfaces=content_addressed_v1"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
