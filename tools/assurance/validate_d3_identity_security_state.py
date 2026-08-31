#!/usr/bin/env python3
"""D3 validator entry point with promoted provenance and monotonic track state.

The prior validator body is preserved in the adjacent legacy module. This
wrapper owns assurance-approved provenance for promoted D3 tracks and the
monotonicity boundary for tracks whose conformance has already been credited.
The machine-owned manifest remains the state authority; a credited track may
advance to accepted_candidate later, but it may not silently regress to a
nonterminal state while validator-only assurance continues to pass.
"""

from __future__ import annotations

import sys
from pathlib import Path

import validate_d3_identity_security_state_legacy as legacy


D3A_CONFORMANCE_EVIDENCE_SHA = "f7b0faa2b5745b1261c6b43523c7ae8ad3750d36"
D3A_CONFORMANCE_WORKFLOW_RUN_ID = 33389775478
D3A_CONFORMANCE_WORKFLOW_RUN_NUMBER = 31
D3A_CONFORMANCE_WORKFLOW_FILE = ".github/workflows/d3-keycloak-conformance.yml"
D3A_CONFORMANCE_JOB = "Keycloak 26.7.2 MFA + authority effects"
D3A_PROBES = {
    "acr_amr_mfa_step_up_context": (
        "implementation/d3-identity-security/harness/keycloak_mfa_single_use_runner.py"
    ),
    "backchannel_logout_authenticity_replay_profile": (
        "implementation/d3-identity-security/harness/keycloak_callback_currentness_drain_runner.py"
    ),
    "provider_sid_sub_mapping_non_authority": (
        "implementation/d3-identity-security/harness/keycloak_callback_currentness_drain_runner.py"
    ),
    "principal_wide_logout_generation_fence": (
        "implementation/d3-identity-security/harness/keycloak_callback_currentness_drain_runner.py"
    ),
    "idp_outage_currentness_join": (
        "implementation/d3-identity-security/harness/keycloak_callback_currentness_drain_runner.py"
    ),
    "idp_native_roles_groups_organizations_non_authority": (
        "implementation/d3-identity-security/harness/keycloak_callback_currentness_drain_runner.py"
    ),
}

D3B_CONFORMANCE_EVIDENCE_SHA = "adff4d75c6439eb74d817fb35e7297a13e27f42b"
D3B_CONFORMANCE_WORKFLOW_RUN_ID = 33417936325
D3B_CONFORMANCE_WORKFLOW_RUN_NUMBER = 27
D3B_CONFORMANCE_WORKFLOW_FILE = ".github/workflows/d3-cache-conformance.yml"
D3B_CONFORMANCE_JOB = "PostgreSQL 18.6 + Redis/Valkey authority continuity"
D3B_CONFORMANCE_PROBE = (
    "implementation/d3-identity-security/harness/"
    "cache_authority_conformance_integrity_entrypoint.py"
)
D3B_PROBES = {
    "session_authority_owner_boundaries": D3B_CONFORMANCE_PROBE,
    "revocation_partial_write_safety": D3B_CONFORMANCE_PROBE,
    "prepare_fence_commit_finalize_single_winner": D3B_CONFORMANCE_PROBE,
    "fleet_wide_cache_exclusion_barrier": D3B_CONFORMANCE_PROBE,
    "restore_failover_positive_authority_nonresurrection": D3B_CONFORMANCE_PROBE,
    "degraded_owner_read_bulkhead_fail_closed": D3B_CONFORMANCE_PROBE,
}

# D3-A/C/D were already conformed on the canonical base before this D3-B
# promotion; D3-B becomes conformed in this promotion. D3-E is intentionally
# excluded because its evidence is still legitimately incomplete. A later D3
# acceptance may advance these tracks from per_track_conformed to
# accepted_candidate, hence the invariant is terminal monotonicity rather than
# an exact-state freeze.
PROMOTED_TERMINAL_TRACKS = frozenset({"D3-A", "D3-B", "D3-C", "D3-D"})


def _promoted_d3a_proof(evidence_id: str, probe: str) -> dict:
    return {
        "evidence_id": evidence_id,
        "evidence_sha": D3A_CONFORMANCE_EVIDENCE_SHA,
        "workflow_run_id": D3A_CONFORMANCE_WORKFLOW_RUN_ID,
        "workflow_run_number": D3A_CONFORMANCE_WORKFLOW_RUN_NUMBER,
        "workflow_file": D3A_CONFORMANCE_WORKFLOW_FILE,
        "job_name": D3A_CONFORMANCE_JOB,
        "probe": probe,
        "artifact_pins": [legacy.KEYCLOAK_26_7_2_DIGEST],
        "result": "pass",
    }


def _promoted_d3b_proof(evidence_id: str, probe: str) -> dict:
    return {
        "evidence_id": evidence_id,
        "evidence_sha": D3B_CONFORMANCE_EVIDENCE_SHA,
        "workflow_run_id": D3B_CONFORMANCE_WORKFLOW_RUN_ID,
        "workflow_run_number": D3B_CONFORMANCE_WORKFLOW_RUN_NUMBER,
        "workflow_file": D3B_CONFORMANCE_WORKFLOW_FILE,
        "job_name": D3B_CONFORMANCE_JOB,
        "probe": probe,
        "artifact_pins": [
            legacy.POSTGRES_18_6_DIGEST,
            legacy.REDIS_8_10_DIGEST,
            legacy.VALKEY_9_1_DIGEST,
        ],
        "result": "pass",
    }


for _evidence_id, _probe in D3A_PROBES.items():
    _key = ("D3-A", _evidence_id)
    if _key not in legacy.APPROVED_EVIDENCE_PROOFS:
        raise RuntimeError(f"missing governed D3-A proof slot: {_evidence_id}")
    legacy.APPROVED_EVIDENCE_PROOFS[_key] = _promoted_d3a_proof(_evidence_id, _probe)

for _evidence_id, _probe in D3B_PROBES.items():
    _key = ("D3-B", _evidence_id)
    if _evidence_id not in legacy.REQUIRED_EVIDENCE["D3-B"]:
        raise RuntimeError(f"unknown governed D3-B proof slot: {_evidence_id}")
    legacy.APPROVED_EVIDENCE_PROOFS[_key] = _promoted_d3b_proof(_evidence_id, _probe)


# Re-export the governed validator contract consumed by falsification and
# terminal-provenance suites.
APPROVED_EVIDENCE_PROOFS = legacy.APPROVED_EVIDENCE_PROOFS
REQUIRED_EVIDENCE = legacy.REQUIRED_EVIDENCE
GATE_DOC = legacy.GATE_DOC
MANIFEST = legacy.MANIFEST


def _validate_promoted_terminal_monotonicity(root: Path) -> None:
    """Reject coherent demotion of any track whose evidence was already credited."""
    data = legacy._load(root)
    tracks = {track["track_id"]: track for track in data["tracks"]}

    for track_id in sorted(PROMOTED_TERMINAL_TRACKS):
        track = tracks[track_id]
        state = track["state"]
        if state not in legacy.TERMINAL_TRACK_STATES:
            raise AssertionError(
                f"{track_id}: promoted conformance is monotonic; nonterminal regression to {state!r} is forbidden"
            )

        required = legacy.REQUIRED_EVIDENCE[track_id]
        completed = set(track["evidence_completed"])
        remaining = set(track["evidence_remaining"])
        proof_ids = {proof["evidence_id"] for proof in track["evidence_proofs"]}
        if completed != required or remaining or proof_ids != required:
            raise AssertionError(
                f"{track_id}: promoted terminal evidence/proof accounting must remain complete"
            )


def validate(root: Path) -> None:
    # First execute every structural, candidate, authority, proof and gate-state
    # invariant from the legacy validator. Only a structurally valid manifest is
    # then eligible for the additional monotonic promotion boundary.
    legacy.validate(root)
    _validate_promoted_terminal_monotonicity(root)


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path.cwd()
    try:
        validate(root)
    except AssertionError as exc:
        print(f"d3_identity_security_state=FAIL reason={exc}", file=sys.stderr)
        return 1
    completed_total = sum(
        len(track.get("evidence_completed", []))
        for track in legacy._load(root).get("tracks", [])
    )
    print(
        "d3_identity_security_state=PASS tracks=5 evidence_ledger=complete_accounting "
        f"approved_provenance={completed_total} candidate_pins=locked gate_state_coherence=locked "
        "promoted_tracks=monotonic_terminal wave4=not_granted production=none "
        "d4=not_selected_not_granted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
