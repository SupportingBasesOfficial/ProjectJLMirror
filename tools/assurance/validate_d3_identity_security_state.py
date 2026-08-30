#!/usr/bin/env python3
"""Validate the machine-owned D3 Identity/Security C2 gate state.

The JSON manifest is the authority surface. Markdown is explanatory only and is
not interpreted to grant or revoke implementation/production authority.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

MANIFEST = Path("implementation/d3-identity-security/state-manifest.json")
GATE_DOC = Path("docs/16-implementation-readiness/19-d3-identity-security-c2-entry-gate.md")
EXPECTED_BASE = "b70d0c20873f92ca0a6040a3cbcd1dfcdace6828"
EXPECTED_TRACKS = {
    "D3-A": ("human_idp", True),
    "D3-B": ("bff_session_security_cache", True),
    "D3-C": ("browser_csrf_key_rotation", True),
    "D3-D": ("workload_identity_issuer_attestation", True),
    "D3-E": ("cryptographic_replay_historical_verifier_authority", True),
}
REQUIRED_SOURCE_ANCHORS = {
    "D3-A": {"IR-D-001-keycloak-idp", "IR-D-001"},
    "D3-B": {"OPEN-REL-031.A", "OPEN-REL-015", "OPEN-REL-008.A"},
    "D3-C": {"OPEN-API-002"},
    "D3-D": {"OPEN-PRT-008.B", "IR-D-002"},
    "D3-E": {"OPEN-REL-016.A", "IR-D-001", "OPEN-EVT-011"},
}
FORBIDDEN_D4_SOURCES = {
    "OPEN-EVT-001",
    "OPEN-EVT-002",
    "OPEN-EVT-003",
    "OPEN-EVT-004",
    "OPEN-EVT-005",
    "OPEN-EVT-006",
    "OPEN-EVT-007",
    "OPEN-EVT-008",
    "OPEN-EVT-009",
    "OPEN-EVT-010",
    "OPEN-EVT-012",
    "OPEN-EVT-013",
    "OPEN-EVT-014",
    "OPEN-EVT-015",
}
ALLOWED_STATES = {
    "candidate_selected_conformance_pending",
    "candidate_evaluation_required",
    "candidate_evidence_running",
    "per_track_conformed",
    "accepted_candidate",
}
ALLOWED_GATE_STATES = {
    "scoped",
    "candidate_evidence_running",
    "per_track_conformed",
    "d3_acceptance_eligible",
    "separately_accepted",
}
ACCEPTANCE_GATED_STATES = {"d3_acceptance_eligible", "separately_accepted"}
TERMINAL_TRACK_STATES = {"per_track_conformed", "accepted_candidate"}


def _load(root: Path) -> dict:
    path = root / MANIFEST
    if not path.is_file():
        raise AssertionError(f"missing D3 state manifest: {MANIFEST}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AssertionError(f"invalid D3 state manifest: {exc}") from exc
    if not isinstance(data, dict):
        raise AssertionError("D3 state manifest root must be an object")
    return data


def _require_equal(data: dict, key: str, expected: object) -> None:
    actual = data.get(key)
    if actual != expected:
        raise AssertionError(f"{key}: expected={expected!r} actual={actual!r}")


def _source_anchor(value: str) -> str:
    return value.split(":", 1)[0]


def validate(root: Path) -> None:
    data = _load(root)
    gate_doc = root / GATE_DOC
    if not gate_doc.is_file():
        raise AssertionError(f"missing D3 gate document: {GATE_DOC}")

    _require_equal(data, "schema_version", 1)
    _require_equal(data, "gate_id", "D3")
    _require_equal(data, "gate_name", "identity_security_authority_c2")
    _require_equal(data, "canonical_base", EXPECTED_BASE)
    _require_equal(data, "canonical_product_implementation_authority", "not_granted")
    _require_equal(data, "wave4_implementation_authority", "not_granted")
    _require_equal(data, "production_authority", "none")
    _require_equal(data, "d4_transport_authority", "not_selected_not_granted")
    _require_equal(
        data,
        "merge_rule",
        "separate_explicit_user_authorization_after_final_exact_head_clean_gate",
    )

    gate_state = data.get("gate_state")
    if gate_state not in ALLOWED_GATE_STATES:
        raise AssertionError(f"gate_state: invalid state {gate_state!r}")

    tracks = data.get("tracks")
    if not isinstance(tracks, list) or len(tracks) != len(EXPECTED_TRACKS):
        raise AssertionError(
            f"tracks: expected exactly {len(EXPECTED_TRACKS)} entries, got "
            f"{len(tracks) if isinstance(tracks, list) else type(tracks).__name__}"
        )

    seen: set[str] = set()
    for track in tracks:
        if not isinstance(track, dict):
            raise AssertionError("every D3 track must be an object")
        track_id = track.get("track_id")
        if track_id not in EXPECTED_TRACKS:
            raise AssertionError(f"unknown/missing D3 track id: {track_id!r}")
        if track_id in seen:
            raise AssertionError(f"duplicate D3 track id: {track_id}")
        seen.add(track_id)

        expected_name, required = EXPECTED_TRACKS[track_id]
        if track.get("name") != expected_name:
            raise AssertionError(
                f"{track_id}: expected name {expected_name!r}, got {track.get('name')!r}"
            )
        if track.get("required_before_d3_acceptance") is not required:
            raise AssertionError(f"{track_id}: required_before_d3_acceptance must remain true")
        state = track.get("state")
        if state not in ALLOWED_STATES:
            raise AssertionError(f"{track_id}: invalid state {state!r}")

        sources = track.get("source_decisions")
        if not isinstance(sources, list) or not sources or not all(isinstance(x, str) and x for x in sources):
            raise AssertionError(f"{track_id}: source_decisions must be a non-empty string list")
        anchors = {_source_anchor(source) for source in sources}
        if len(anchors) != len(sources):
            raise AssertionError(f"{track_id}: duplicate source-decision anchor is forbidden")

        expected_anchors = REQUIRED_SOURCE_ANCHORS[track_id]
        if anchors != expected_anchors:
            missing = sorted(expected_anchors - anchors)
            unexpected = sorted(anchors - expected_anchors)
            raise AssertionError(
                f"{track_id}: source-decision anchors mismatch; "
                f"missing={missing} unexpected={unexpected}"
            )

        forbidden = sorted(anchors & FORBIDDEN_D4_SOURCES)
        if forbidden:
            raise AssertionError(
                f"{track_id}: D4 event-transport source leaked into D3: {forbidden}"
            )

        # OPEN-EVT-011 is intentionally allowed only for D3-E's cryptographic
        # comparison-authority join. No other event OPEN belongs to D3.
        evt_sources = sorted(anchor for anchor in anchors if anchor.startswith("OPEN-EVT-"))
        if evt_sources:
            if track_id != "D3-E" or evt_sources != ["OPEN-EVT-011"]:
                raise AssertionError(
                    f"{track_id}: event OPEN ownership exceeds D3 crypto-only join: {evt_sources}"
                )

    if seen != set(EXPECTED_TRACKS):
        raise AssertionError(f"D3 track set mismatch: {sorted(seen)}")

    exclusions = data.get("explicit_exclusions")
    if not isinstance(exclusions, list):
        raise AssertionError("explicit_exclusions must be a list")
    required_exclusions = {
        "OPEN-EVT-001:transport",
        "OPEN-EVT-002:serialization",
        "OPEN-EVT-003:catalog",
        "OPEN-EVT-004:version_syntax",
        "OPEN-EVT-005:physical_topology",
        "wave4_monitoring_product_implementation",
        "production_c3_numerics",
    }
    missing_exclusions = sorted(required_exclusions - set(exclusions))
    if missing_exclusions:
        raise AssertionError(f"missing mandatory D3 exclusions: {missing_exclusions}")

    c3_open = data.get("c3_remains_open")
    if not isinstance(c3_open, list):
        raise AssertionError("c3_remains_open must be a list")
    for required_c3 in ("OPEN-REL-031.B", "OPEN-REL-008.B", "OPEN-REL-016.B"):
        if required_c3 not in c3_open:
            raise AssertionError(f"D3 attempted to lose required C3 boundary: {required_c3}")

    # Acceptance eligibility and final separate acceptance both require every
    # required D3 track to have reached a terminal evidence disposition.
    if gate_state in ACCEPTANCE_GATED_STATES:
        nonterminal = [
            track["track_id"]
            for track in tracks
            if track.get("state") not in TERMINAL_TRACK_STATES
        ]
        if nonterminal:
            raise AssertionError(
                f"D3 gate cannot enter {gate_state!r} with nonterminal tracks: {nonterminal}"
            )


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    try:
        validate(root)
    except AssertionError as exc:
        print(f"d3_identity_security_state=FAIL reason={exc}", file=sys.stderr)
        return 1
    print(
        "d3_identity_security_state=PASS tracks=5 "
        "wave4=not_granted production=none d4=not_selected_not_granted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
