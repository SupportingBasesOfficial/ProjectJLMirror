#!/usr/bin/env python3
"""Validate post-D2 OPEN-REL-030 / Wave 4 readiness-state consistency."""

from __future__ import annotations

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


def validate(root: Path) -> None:
    docs = {key: _read(root, key) for key in FILES}

    transition = docs["transition"]
    _require(transition, MERGE_SHA, "transition")
    _require(transition, "open_rel_030_track_b = accepted", "transition")
    _require(transition, "open_rel_030_profile = selected_and_conformed", "transition")
    _require(
        transition,
        "customer_telemetry_slice = eligible_for_implementation_authorization",
        "transition",
    )
    _require(
        transition,
        "wave4_monitoring = eligible_for_separate_explicit_authorization",
        "transition",
    )
    _require(
        transition,
        "wave4_implementation_authorization = not_granted",
        "transition",
    )
    _require(transition, "production_authority = none", "transition")
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
    _require(
        manifest,
        "`impl.customer-telemetry@1`",
        "slice manifest",
    )
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

    # These current-state surfaces must not regress to the pre-D2 blocker state.
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

    # Acceptance removes one C2 evidence blocker only; it must not silently grant Wave 4
    # on any current-state authority surface, including the consolidated OPEN register.
    for key in (
        "transition",
        "open_register",
        "blockers",
        "sequencing",
        "slice_manifest",
    ):
        _forbid(docs[key], "wave4_implementation_authorization = granted", key)
        _forbid(docs[key], "AUTHORIZED_TO_IMPLEMENT = true", key)


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    try:
        validate(root)
    except AssertionError as exc:
        print(f"post_d2_wave4_state_guard=FAIL reason={exc}", file=sys.stderr)
        return 1

    print(
        "post_d2_wave4_state_guard=PASS "
        "track_b=accepted telemetry_slice=eligible wave4_authorization=not_granted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))