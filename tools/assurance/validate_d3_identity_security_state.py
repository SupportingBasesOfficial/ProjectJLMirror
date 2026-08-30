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
EXPECTED_CANDIDATE_FIELDS = {
    "D3-A": {
        "candidate": "keycloak_26_7_2",
        "candidate_image_digest": "quay.io/keycloak/keycloak@sha256:831330513f55695572286e521f94fcd3c7e285250ed5b848090265a33192f669",
    },
    "D3-B": {
        "candidate": "postgresql_18_6_session_sor_plus_redis_compatible_security_cache",
        "portability_control": "valkey_9_1",
    },
    "D3-C": {"candidate": "hmac_sha256_double_submit_versioned_keyring"},
    "D3-D": {"candidate": "spire_1_15_2"},
    "D3-E": {"candidate": "openbao_2_6_2_transit_behind_provider_neutral_key_authority_port"},
}
REQUIRED_SOURCE_ANCHORS = {
    "D3-A": {"IR-D-001-keycloak-idp", "IR-D-001"},
    "D3-B": {"OPEN-REL-031.A", "OPEN-REL-015", "OPEN-REL-008.A"},
    "D3-C": {"OPEN-API-002"},
    "D3-D": {"OPEN-PRT-008.B", "IR-D-002"},
    "D3-E": {"OPEN-REL-016.A", "IR-D-001", "OPEN-EVT-011"},
}
REQUIRED_EVIDENCE = {
    "D3-A": {
        "oidc_authorization_code_pkce_bff_binding",
        "token_signature_issuer_audience_client_time_jwks_algorithm_validation",
        "acr_amr_mfa_step_up_context",
        "backchannel_logout_authenticity_replay_profile",
        "provider_sid_sub_mapping_non_authority",
        "principal_wide_logout_generation_fence",
        "idp_outage_currentness_join",
        "idp_native_roles_groups_organizations_non_authority",
    },
    "D3-B": {
        "session_authority_owner_boundaries",
        "cache_generation_bound_derived_only",
        "healthy_single_roundtrip_zero_pg_generation_queries",
        "mixed_generation_read_rejected",
        "independent_cache_admission_epoch",
        "revocation_partial_write_safety",
        "prepare_fence_commit_finalize_single_winner",
        "fleet_wide_cache_exclusion_barrier",
        "restore_failover_positive_authority_nonresurrection",
        "broad_revocation_bounded_constant",
        "degraded_owner_read_bulkhead_fail_closed",
    },
    "D3-C": {
        "token_session_lineage_binding",
        "current_previous_key_only",
        "rotation_overlap_safety_lifetime",
        "no_historical_key_search",
        "previous_key_observability_stale_detection",
        "duplicate_conflicting_cookie_header_ingress_rejection",
        "routine_session_renewal_preserves_csrf",
        "privilege_boundary_reissue",
        "uncertain_key_generation_fail_closed",
    },
    "D3-D": {
        "runtime_attestation_not_caller_identity",
        "trust_domain_environment_runtime_binding",
        "short_lived_rotation_retired_bundle_rejection",
        "cross_environment_rejection",
        "workload_identity_non_tenant_authority",
        "private_key_non_exportability_profile",
        "issuer_restore_retired_authority_nonresurrection",
        "vendor_credential_adapter_least_privilege",
    },
    "D3-E": {
        "tenant_scope_domain_separation",
        "erasure_granularity_key_alignment",
        "historical_verifier_relocation_recovery_continuity",
        "retired_erased_key_nonresurrection",
        "private_key_jwt_replay_atomic_single_winner",
        "replay_partition_fail_closed",
        "replay_consumed_identity_survives_restore_loss",
        "key_generation_rotation_retirement",
        "provider_neutral_key_authority_port",
    },
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
EVIDENCE_COMPLETE_GATE_STATES = {
    "per_track_conformed",
    "d3_acceptance_eligible",
    "separately_accepted",
}
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


def _string_set(track_id: str, track: dict, key: str) -> set[str]:
    value = track.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise AssertionError(f"{track_id}: {key} must be a string list")
    if len(set(value)) != len(value):
        raise AssertionError(f"{track_id}: {key} contains duplicate entries")
    return set(value)


def validate(root: Path) -> None:
    data = _load(root)
    gate_doc = root / GATE_DOC
    if not gate_doc.is_file():
        raise AssertionError(f"missing D3 gate document: {GATE_DOC}")

    _require_equal(data, "schema_version", 2)
    _require_equal(data, "gate_id", "D3")
    _require_equal(data, "gate_name", "identity_security_authority_c2")
    _require_equal(data, "canonical_base", EXPECTED_BASE)
    _require_equal(data, "canonical_product_implementation_authority", "not_granted")
    _require_equal(data, "wave4_implementation_authority", "not_granted")
    _require_equal(data, "production_authority", "none")
    _require_equal(data, "d4_transport_authority", "not_selected_not_granted")
    _require_equal(
        data,
        "acceptance_rule",
        "all_tracks_conformed_all_required_evidence_completed_and_exact_head_assurance_clean_then_separate_acceptance",
    )
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

        for field, expected in EXPECTED_CANDIDATE_FIELDS[track_id].items():
            if track.get(field) != expected:
                raise AssertionError(
                    f"{track_id}: candidate field {field} drifted; expected={expected!r} actual={track.get(field)!r}"
                )

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

        evt_sources = sorted(anchor for anchor in anchors if anchor.startswith("OPEN-EVT-"))
        if evt_sources:
            if track_id != "D3-E" or evt_sources != ["OPEN-EVT-011"]:
                raise AssertionError(
                    f"{track_id}: event OPEN ownership exceeds D3 crypto-only join: {evt_sources}"
                )

        expected_evidence = REQUIRED_EVIDENCE[track_id]
        declared_required = _string_set(track_id, track, "required_evidence")
        completed = _string_set(track_id, track, "evidence_completed")
        remaining = _string_set(track_id, track, "evidence_remaining")

        if declared_required != expected_evidence:
            missing = sorted(expected_evidence - declared_required)
            unexpected = sorted(declared_required - expected_evidence)
            raise AssertionError(
                f"{track_id}: required_evidence mismatch; missing={missing} unexpected={unexpected}"
            )
        if completed - expected_evidence:
            raise AssertionError(
                f"{track_id}: evidence_completed contains unknown evidence: {sorted(completed - expected_evidence)}"
            )
        if remaining - expected_evidence:
            raise AssertionError(
                f"{track_id}: evidence_remaining contains unknown evidence: {sorted(remaining - expected_evidence)}"
            )
        overlap = completed & remaining
        if overlap:
            raise AssertionError(f"{track_id}: evidence cannot be both completed and remaining: {sorted(overlap)}")
        accounted = completed | remaining
        if accounted != expected_evidence:
            missing = sorted(expected_evidence - accounted)
            raise AssertionError(f"{track_id}: required evidence is unaccounted: {missing}")
        if state in TERMINAL_TRACK_STATES and remaining:
            raise AssertionError(
                f"{track_id}: terminal state {state!r} still has remaining evidence: {sorted(remaining)}"
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

    if gate_state in EVIDENCE_COMPLETE_GATE_STATES:
        nonterminal = [
            track["track_id"]
            for track in tracks
            if track.get("state") not in TERMINAL_TRACK_STATES
        ]
        if nonterminal:
            raise AssertionError(
                f"D3 gate cannot enter {gate_state!r} with nonterminal tracks: {nonterminal}"
            )
        incomplete = [
            track["track_id"]
            for track in tracks
            if track.get("evidence_remaining")
        ]
        if incomplete:
            raise AssertionError(
                f"D3 gate cannot enter {gate_state!r} with incomplete evidence: {incomplete}"
            )

    if gate_state in {"per_track_conformed", "d3_acceptance_eligible"}:
        wrong_state = [
            track["track_id"]
            for track in tracks
            if track.get("state") != "per_track_conformed"
        ]
        if wrong_state:
            raise AssertionError(
                f"D3 gate {gate_state!r} requires every track state 'per_track_conformed': {wrong_state}"
            )

    if gate_state == "separately_accepted":
        not_accepted = [
            track["track_id"]
            for track in tracks
            if track.get("state") != "accepted_candidate"
        ]
        if not_accepted:
            raise AssertionError(
                f"D3 separate acceptance requires every track state 'accepted_candidate': {not_accepted}"
            )


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    try:
        validate(root)
    except AssertionError as exc:
        print(f"d3_identity_security_state=FAIL reason={exc}", file=sys.stderr)
        return 1
    print(
        "d3_identity_security_state=PASS tracks=5 evidence_ledger=complete_accounting "
        "candidate_pins=locked gate_state_coherence=locked "
        "wave4=not_granted production=none d4=not_selected_not_granted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
