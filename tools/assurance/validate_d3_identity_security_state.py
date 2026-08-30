#!/usr/bin/env python3
"""Validate the machine-owned D3 Identity/Security C2 gate state.

The JSON manifest is the authority surface. Markdown is explanatory only and is
not interpreted to grant or revoke implementation/production authority.

Completed evidence is valid only when it is backed by an exact proof record
allowlisted by this assurance module. A syntactically plausible SHA/run is not
sufficient to advance D3 authority.
"""

from __future__ import annotations

import json
import re
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
POSTGRES_18_6_DIGEST = "postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280"
REDIS_8_10_DIGEST = "redis@sha256:344e3945a0b431c8ff1eecd58c5573538126bd756f02fc7e218ddf1fc2546366"
VALKEY_9_1_DIGEST = "valkey/valkey@sha256:8e8d64b405ce18f41b8e5ee20aa4687a8ed0022d1298f2ce31cdcf3a76e09411"
SPIRE_1_15_3_ARTIFACT = (
    "spire-1.15.3-linux-amd64-musl.tar.gz@sha256:"
    "ca1a4d1155317bdd2afc7f36663828a10410c7c840e54725b90b4064b0a301c7"
)
EXPECTED_CANDIDATE_FIELDS = {
    "D3-A": {
        "candidate": "keycloak_26_7_2",
        "candidate_image_digest": "quay.io/keycloak/keycloak@sha256:831330513f55695572286e521f94fcd3c7e285250ed5b848090265a33192f669",
    },
    "D3-B": {
        "candidate": "postgresql_18_6_session_sor_plus_redis_compatible_security_cache",
        "portability_control": "valkey_9_1",
        "candidate_artifact_digests": {
            "postgresql": POSTGRES_18_6_DIGEST,
            "redis_compatible_primary": REDIS_8_10_DIGEST,
            "portability_control": VALKEY_9_1_DIGEST,
        },
    },
    "D3-C": {"candidate": "hmac_sha256_double_submit_versioned_keyring"},
    "D3-D": {
        "candidate": "spire_1_15_3",
        "candidate_artifact_digest": SPIRE_1_15_3_ARTIFACT,
    },
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
PROOF_FIELDS = {
    "evidence_id",
    "evidence_sha",
    "workflow_run_id",
    "workflow_run_number",
    "workflow_file",
    "job_name",
    "probe",
    "artifact_pins",
    "result",
}
KEYCLOAK_26_7_2_DIGEST = (
    "quay.io/keycloak/keycloak@sha256:"
    "831330513f55695572286e521f94fcd3c7e285250ed5b848090265a33192f669"
)
_D3A_BROWSER_PROOF_COMMON = {
    "evidence_sha": "91861314002d9f5721456c7416d208e414ec4c58",
    "workflow_run_id": 33314472945,
    "workflow_run_number": 21,
    "workflow_file": ".github/workflows/d3-keycloak-exploratory.yml",
    "job_name": "Keycloak 26.7.2 pinned browser + back-channel contracts",
    "probe": "implementation/d3-identity-security/harness/keycloak_browser_probe.py",
    "artifact_pins": [KEYCLOAK_26_7_2_DIGEST],
    "result": "pass",
}
_D3B_PINNED_PROOF_COMMON = {
    "evidence_sha": "a437bb46eb8695e8e48d26b8db5569ff8f12ea7b",
    "workflow_run_id": 33314980744,
    "workflow_run_number": 19,
    "workflow_file": ".github/workflows/d3-cache-exploratory.yml",
    "job_name": "PostgreSQL 18.6 + Redis 8.10 / Valkey 9.1 pinned",
    "probe": "implementation/d3-identity-security/harness/cache_admission_probe.sh",
    "artifact_pins": [POSTGRES_18_6_DIGEST, REDIS_8_10_DIGEST, VALKEY_9_1_DIGEST],
    "result": "pass",
}
_D3_REFERENCE_PROOF_COMMON = {
    "evidence_sha": "796ada5529103d30fb6b711699fe863751ed0f42",
    "workflow_run_id": 33315407695,
    "workflow_run_number": 32,
    "workflow_file": ".github/workflows/d3-identity-security-evidence.yml",
    "job_name": "D3 reference security contracts",
    "probe": "implementation/d3-identity-security/harness/test_crypto_reference.py",
    "artifact_pins": [],
    "result": "pass",
}
_D3C_COMPLETION_PROOF_COMMON = {
    "evidence_sha": "f9bf130677d627adf54af4529abde1b1212c1594",
    "workflow_run_id": 33315948185,
    "workflow_run_number": 36,
    "workflow_file": ".github/workflows/d3-identity-security-evidence.yml",
    "job_name": "D3 reference security contracts",
    "probe": "implementation/d3-identity-security/harness/test_crypto_reference.py",
    "artifact_pins": [],
    "result": "pass",
}
_D3D_SPIRE_PROOF_COMMON = {
    "evidence_sha": "3eb0615af62ad7fdec236620d248165ceff62a65",
    "workflow_run_id": 33317304870,
    "workflow_run_number": 7,
    "workflow_file": ".github/workflows/d3-spire-candidate-evaluation.yml",
    "job_name": "SPIRE 1.15.3 bounded workload-identity evaluation",
    "probe": "implementation/d3-identity-security/harness/spire_candidate_probe.sh",
    "artifact_pins": [SPIRE_1_15_3_ARTIFACT],
    "result": "pass",
}
APPROVED_EVIDENCE_PROOFS = {
    ("D3-A", "oidc_authorization_code_pkce_bff_binding"): {
        "evidence_id": "oidc_authorization_code_pkce_bff_binding",
        **_D3A_BROWSER_PROOF_COMMON,
    },
    ("D3-A", "token_signature_issuer_audience_client_time_jwks_algorithm_validation"): {
        "evidence_id": "token_signature_issuer_audience_client_time_jwks_algorithm_validation",
        **_D3A_BROWSER_PROOF_COMMON,
    },
    ("D3-B", "cache_generation_bound_derived_only"): {
        "evidence_id": "cache_generation_bound_derived_only",
        **_D3B_PINNED_PROOF_COMMON,
    },
    ("D3-B", "healthy_single_roundtrip_zero_pg_generation_queries"): {
        "evidence_id": "healthy_single_roundtrip_zero_pg_generation_queries",
        **_D3B_PINNED_PROOF_COMMON,
    },
    ("D3-B", "mixed_generation_read_rejected"): {
        "evidence_id": "mixed_generation_read_rejected",
        **_D3B_PINNED_PROOF_COMMON,
    },
    ("D3-B", "independent_cache_admission_epoch"): {
        "evidence_id": "independent_cache_admission_epoch",
        **_D3B_PINNED_PROOF_COMMON,
    },
    ("D3-B", "broad_revocation_bounded_constant"): {
        "evidence_id": "broad_revocation_bounded_constant",
        **_D3B_PINNED_PROOF_COMMON,
    },
    ("D3-C", "token_session_lineage_binding"): {
        "evidence_id": "token_session_lineage_binding",
        **_D3_REFERENCE_PROOF_COMMON,
    },
    ("D3-C", "current_previous_key_only"): {
        "evidence_id": "current_previous_key_only",
        **_D3_REFERENCE_PROOF_COMMON,
    },
    ("D3-C", "rotation_overlap_safety_lifetime"): {
        "evidence_id": "rotation_overlap_safety_lifetime",
        **_D3C_COMPLETION_PROOF_COMMON,
    },
    ("D3-C", "no_historical_key_search"): {
        "evidence_id": "no_historical_key_search",
        **_D3_REFERENCE_PROOF_COMMON,
    },
    ("D3-C", "previous_key_observability_stale_detection"): {
        "evidence_id": "previous_key_observability_stale_detection",
        **_D3C_COMPLETION_PROOF_COMMON,
    },
    ("D3-C", "duplicate_conflicting_cookie_header_ingress_rejection"): {
        "evidence_id": "duplicate_conflicting_cookie_header_ingress_rejection",
        **_D3C_COMPLETION_PROOF_COMMON,
    },
    ("D3-C", "routine_session_renewal_preserves_csrf"): {
        "evidence_id": "routine_session_renewal_preserves_csrf",
        **_D3_REFERENCE_PROOF_COMMON,
    },
    ("D3-C", "privilege_boundary_reissue"): {
        "evidence_id": "privilege_boundary_reissue",
        **_D3_REFERENCE_PROOF_COMMON,
    },
    ("D3-C", "uncertain_key_generation_fail_closed"): {
        "evidence_id": "uncertain_key_generation_fail_closed",
        **_D3_REFERENCE_PROOF_COMMON,
    },
    ("D3-D", "runtime_attestation_not_caller_identity"): {
        "evidence_id": "runtime_attestation_not_caller_identity",
        **_D3D_SPIRE_PROOF_COMMON,
    },
    ("D3-D", "trust_domain_environment_runtime_binding"): {
        "evidence_id": "trust_domain_environment_runtime_binding",
        **_D3D_SPIRE_PROOF_COMMON,
    },
    ("D3-D", "cross_environment_rejection"): {
        "evidence_id": "cross_environment_rejection",
        **_D3D_SPIRE_PROOF_COMMON,
    },
    ("D3-E", "tenant_scope_domain_separation"): {
        "evidence_id": "tenant_scope_domain_separation",
        **_D3_REFERENCE_PROOF_COMMON,
    },
    ("D3-E", "erasure_granularity_key_alignment"): {
        "evidence_id": "erasure_granularity_key_alignment",
        **_D3_REFERENCE_PROOF_COMMON,
    },
    ("D3-E", "provider_neutral_key_authority_port"): {
        "evidence_id": "provider_neutral_key_authority_port",
        **_D3_REFERENCE_PROOF_COMMON,
    },
}


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


def _validate_proofs(track_id: str, track: dict, completed: set[str]) -> None:
    proofs = track.get("evidence_proofs")
    if not isinstance(proofs, list):
        raise AssertionError(f"{track_id}: evidence_proofs must be a list")

    proof_ids: set[str] = set()
    for proof in proofs:
        if not isinstance(proof, dict):
            raise AssertionError(f"{track_id}: every evidence proof must be an object")
        if set(proof) != PROOF_FIELDS:
            missing = sorted(PROOF_FIELDS - set(proof))
            unexpected = sorted(set(proof) - PROOF_FIELDS)
            raise AssertionError(
                f"{track_id}: evidence proof field mismatch; missing={missing} unexpected={unexpected}"
            )

        evidence_id = proof.get("evidence_id")
        if not isinstance(evidence_id, str) or not evidence_id:
            raise AssertionError(f"{track_id}: proof evidence_id must be a non-empty string")
        if evidence_id in proof_ids:
            raise AssertionError(f"{track_id}: duplicate evidence proof for {evidence_id!r}")
        proof_ids.add(evidence_id)

        evidence_sha = proof.get("evidence_sha")
        if not isinstance(evidence_sha, str) or re.fullmatch(r"[0-9a-f]{40}", evidence_sha) is None:
            raise AssertionError(f"{track_id}/{evidence_id}: evidence_sha must be exact lowercase 40-hex")

        for key in ("workflow_run_id", "workflow_run_number"):
            value = proof.get(key)
            if type(value) is not int or value <= 0:
                raise AssertionError(f"{track_id}/{evidence_id}: {key} must be a positive integer")

        workflow_file = proof.get("workflow_file")
        if (
            not isinstance(workflow_file, str)
            or not workflow_file.startswith(".github/workflows/")
            or not workflow_file.endswith((".yml", ".yaml"))
        ):
            raise AssertionError(f"{track_id}/{evidence_id}: workflow_file is outside governed workflow scope")

        for key in ("job_name", "probe"):
            value = proof.get(key)
            if not isinstance(value, str) or not value or value != value.strip():
                raise AssertionError(f"{track_id}/{evidence_id}: {key} must be a canonical non-empty string")

        pins = proof.get("artifact_pins")
        if not isinstance(pins, list) or not all(isinstance(pin, str) and pin for pin in pins):
            raise AssertionError(f"{track_id}/{evidence_id}: artifact_pins must be a string list")
        if len(set(pins)) != len(pins):
            raise AssertionError(f"{track_id}/{evidence_id}: artifact_pins contains duplicates")
        for pin in pins:
            if "@sha256:" not in pin:
                raise AssertionError(f"{track_id}/{evidence_id}: mutable/non-digest artifact pin is forbidden")
            digest = pin.rsplit("@sha256:", 1)[1]
            if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
                raise AssertionError(f"{track_id}/{evidence_id}: artifact digest must be lowercase sha256")

        if track_id == "D3-A" and track.get("candidate_image_digest") not in pins:
            raise AssertionError(
                f"{track_id}/{evidence_id}: proof does not bind the exact Keycloak candidate digest"
            )
        if track_id == "D3-B":
            expected_pins = set(track.get("candidate_artifact_digests", {}).values())
            if set(pins) != expected_pins:
                raise AssertionError(
                    f"{track_id}/{evidence_id}: proof does not bind the exact D3-B candidate artifact set"
                )
        if track_id == "D3-D":
            expected_pin = track.get("candidate_artifact_digest")
            if pins != [expected_pin]:
                raise AssertionError(
                    f"{track_id}/{evidence_id}: proof does not bind the exact SPIRE candidate artifact"
                )

        if proof.get("result") != "pass":
            raise AssertionError(f"{track_id}/{evidence_id}: only passing proof may complete evidence")

        approved = APPROVED_EVIDENCE_PROOFS.get((track_id, evidence_id))
        if approved is None:
            raise AssertionError(
                f"{track_id}/{evidence_id}: no assurance-approved proof exists for this evidence"
            )
        if proof != approved:
            raise AssertionError(
                f"{track_id}/{evidence_id}: evidence proof drifted from the assurance-approved provenance"
            )

    if proof_ids != completed:
        missing = sorted(completed - proof_ids)
        unexpected = sorted(proof_ids - completed)
        raise AssertionError(
            f"{track_id}: completed evidence/proof mismatch; missing_proofs={missing} unexpected_proofs={unexpected}"
        )


def validate(root: Path) -> None:
    data = _load(root)
    gate_doc = root / GATE_DOC
    if not gate_doc.is_file():
        raise AssertionError(f"missing D3 gate document: {GATE_DOC}")

    _require_equal(data, "schema_version", 3)
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

        _validate_proofs(track_id, track, completed)

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
    completed_total = sum(
        len(track.get("evidence_completed", []))
        for track in _load(root).get("tracks", [])
    )
    print(
        "d3_identity_security_state=PASS tracks=5 evidence_ledger=complete_accounting "
        f"approved_provenance={completed_total} candidate_pins=locked gate_state_coherence=locked "
        "wave4=not_granted production=none d4=not_selected_not_granted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
