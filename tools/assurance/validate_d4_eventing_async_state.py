#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

MANIFEST = Path("implementation/d4-eventing-async/state-manifest.json")
EXPECTED_BASE = "ee8775fc5e7a25b1c4e166a8bb48b53438f6bd42"
EXPECTED_TRACK_SOURCES = {
    "D4-A": {"OPEN-EVT-001", "OPEN-EVT-005", "OPEN-REL-012.A"},
    "D4-B": {"OPEN-EVT-002", "OPEN-EVT-003", "OPEN-EVT-004"},
    "D4-C": {
        "OPEN-EVT-008",
        "OPEN-EVT-009",
        "OPEN-EVT-010",
        "OPEN-EVT-011",
        "OPEN-EVT-012",
        "OPEN-EVT-013",
        "OPEN-EVT-014",
        "OPEN-EVT-015",
        "OPEN-EVT-025",
    },
    "D4-D": {"OPEN-EVT-016", "OPEN-EVT-017", "OPEN-EVT-018"},
}
EXPECTED_ENTRY_STATES = {
    "D4-A": "candidate_leading_closure_pending",
    "D4-B": "candidate_selection_open",
    "D4-C": "candidate_selection_open",
    "D4-D": "candidate_selection_open",
}
EXPECTED_C3_EXCLUSIONS = {
    "OPEN-EVT-006",
    "OPEN-EVT-007",
    "OPEN-EVT-019",
    "OPEN-EVT-026",
    "OPEN-EVT-027",
    "OPEN-EVT-028",
    "OPEN-REL-012.B",
    "production_partition_counts",
    "production_retry_backoff_jitter_numerics",
    "production_retention_lag_replay_quarantine_horizons",
    "production_realtime_buffer_session_numerics",
}
EXPECTED_LATER_EXCLUSIONS = {
    "OPEN-EVT-020",
    "OPEN-EVT-021",
    "OPEN-EVT-022",
    "OPEN-EVT-023",
    "OPEN-EVT-024",
    "wave4_monitoring_product_implementation",
    "production_deployment",
}


def load_manifest(root: Path) -> dict:
    return json.loads((root / MANIFEST).read_text(encoding="utf-8"))


def validate_manifest(state: dict) -> list[str]:
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    require(state.get("schema_version") == 1, "schema_version must be 1")
    require(state.get("gate_id") == "D4", "gate_id must be D4")
    require(state.get("gate_name") == "eventing_async_transport_c2", "unexpected D4 gate_name")
    require(state.get("canonical_base") == EXPECTED_BASE, "D4 canonical_base drift")

    predecessor = state.get("predecessor", {})
    require(predecessor.get("gate_id") == "D3", "D4 predecessor must be D3")
    require(predecessor.get("state") == "separately_accepted", "D3 predecessor is not separately accepted")
    require(predecessor.get("canonical_commit") == EXPECTED_BASE, "D3 predecessor commit drift")

    require(state.get("gate_state") == "scoped", "D4 entry PR must remain scoped")
    require(
        state.get("canonical_product_implementation_authority") == "not_granted",
        "D4 entry must not grant canonical Product implementation authority",
    )
    require(
        state.get("wave4_implementation_authority") == "not_granted",
        "D4 entry must not grant Wave 4 implementation authority",
    )
    require(state.get("production_authority") == "none", "D4 entry must not grant production authority")
    require(
        state.get("d4_transport_authority") == "not_selected_not_granted",
        "D4 transport authority must remain unselected/ungranted at entry",
    )
    require(
        state.get("c3_numeric_topology_authority") == "not_selected",
        "D4 entry must not select C3 numeric/topology authority",
    )

    tracks = state.get("tracks")
    require(isinstance(tracks, list), "tracks must be a list")
    if isinstance(tracks, list):
        by_id = {track.get("track_id"): track for track in tracks if isinstance(track, dict)}
        require(set(by_id) == set(EXPECTED_TRACK_SOURCES), "D4 track set drift")
        for track_id, expected_sources in EXPECTED_TRACK_SOURCES.items():
            track = by_id.get(track_id, {})
            require(set(track.get("source_decisions", [])) == expected_sources, f"{track_id} source decision drift")
            require(track.get("state") == EXPECTED_ENTRY_STATES[track_id], f"{track_id} entry state drift")
            required = track.get("required_evidence", [])
            completed = track.get("evidence_completed", [])
            remaining = track.get("evidence_remaining", [])
            require(isinstance(required, list) and len(required) > 0, f"{track_id} must declare required evidence")
            require(len(required) == len(set(required)), f"{track_id} required evidence contains duplicates")
            require(completed == [], f"{track_id} entry gate may not pre-credit evidence")
            require(set(remaining) == set(required), f"{track_id} remaining evidence must equal required evidence at entry")
            require(len(remaining) == len(required), f"{track_id} remaining evidence multiplicity drift")

        d4a = by_id.get("D4-A", {})
        require(d4a.get("candidate") == "kafka", "D4-A leading candidate must remain Kafka at entry")
        require(
            d4a.get("candidate_status") == "leading_candidate_closure_pending",
            "D4-A Kafka candidate must remain closure-pending",
        )
        for track_id in ("D4-B", "D4-C", "D4-D"):
            track = by_id.get(track_id, {})
            require(track.get("candidate") is None, f"{track_id} must not silently select a candidate")
            require(track.get("candidate_status") == "not_selected", f"{track_id} candidate status must remain not_selected")

    require(
        set(state.get("explicit_c3_exclusions", [])) == EXPECTED_C3_EXCLUSIONS,
        "D4 C3 exclusion set drift",
    )
    require(
        set(state.get("explicit_product_or_later_gate_exclusions", [])) == EXPECTED_LATER_EXCLUSIONS,
        "D4 Product/later-gate exclusion set drift",
    )
    require("separate_acceptance" in state.get("acceptance_rule", ""), "D4 acceptance must remain a separate action")
    require(
        "separate_explicit_user_authorization" in state.get("merge_rule", ""),
        "D4 merge rule must require separate explicit user authorization",
    )
    return errors


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    state = load_manifest(root)
    errors = validate_manifest(state)
    if errors:
        for error in errors:
            print(f"D4_STATE_ERROR: {error}", file=sys.stderr)
        return 1
    required = sum(len(track["required_evidence"]) for track in state["tracks"])
    print(
        "d4_eventing_async_state=PASS "
        f"gate_state={state['gate_state']} tracks={len(state['tracks'])} "
        f"evidence_required={required} evidence_credited=0 transport_authority=not_granted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
