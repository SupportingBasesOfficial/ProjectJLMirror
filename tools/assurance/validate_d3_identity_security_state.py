#!/usr/bin/env python3
"""D3 validator entry point with exact promoted D3-A evidence provenance.

The prior validator body is preserved in the adjacent legacy module so this
promotion changes only the assurance-approved provenance for the corrected
Keycloak conformance evidence. The manifest remains the machine-owned state
surface; this wrapper replaces the six D3-A proof allowlist entries with the
exact successful post-review run before delegating all validation semantics.
"""

from __future__ import annotations

import sys

import validate_d3_identity_security_state_legacy as legacy


D3A_CONFORMANCE_EVIDENCE_SHA = "03aa54561e86970849c96175fee70dc23263ae20"
D3A_CONFORMANCE_WORKFLOW_RUN_ID = 33356682378
D3A_CONFORMANCE_WORKFLOW_RUN_NUMBER = 20
D3A_CONFORMANCE_WORKFLOW_FILE = ".github/workflows/d3-keycloak-conformance.yml"
D3A_CONFORMANCE_JOB = "Keycloak 26.7.2 MFA + authority effects"
D3A_PROBES = {
    "acr_amr_mfa_step_up_context": (
        "implementation/d3-identity-security/harness/keycloak_mfa_single_use_runner.py"
    ),
    "backchannel_logout_authenticity_replay_profile": (
        "implementation/d3-identity-security/harness/keycloak_authority_upgrade_guard_runner.py"
    ),
    "provider_sid_sub_mapping_non_authority": (
        "implementation/d3-identity-security/harness/keycloak_authority_upgrade_guard_runner.py"
    ),
    "principal_wide_logout_generation_fence": (
        "implementation/d3-identity-security/harness/keycloak_authority_upgrade_guard_runner.py"
    ),
    "idp_outage_currentness_join": (
        "implementation/d3-identity-security/harness/keycloak_authority_upgrade_guard_runner.py"
    ),
    "idp_native_roles_groups_organizations_non_authority": (
        "implementation/d3-identity-security/harness/keycloak_authority_upgrade_guard_runner.py"
    ),
}


def _promoted_proof(evidence_id: str, probe: str) -> dict:
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


for _evidence_id, _probe in D3A_PROBES.items():
    _key = ("D3-A", _evidence_id)
    if _key not in legacy.APPROVED_EVIDENCE_PROOFS:
        raise RuntimeError(f"missing governed D3-A proof slot: {_evidence_id}")
    legacy.APPROVED_EVIDENCE_PROOFS[_key] = _promoted_proof(_evidence_id, _probe)

# Re-export the governed validator contract consumed by the falsification and
# terminal-provenance suites. Keeping these aliases explicit prevents this
# provenance wrapper from silently becoming a second validator implementation.
APPROVED_EVIDENCE_PROOFS = legacy.APPROVED_EVIDENCE_PROOFS
REQUIRED_EVIDENCE = legacy.REQUIRED_EVIDENCE
GATE_DOC = legacy.GATE_DOC
MANIFEST = legacy.MANIFEST
validate = legacy.validate


def main(argv: list[str]) -> int:
    return legacy.main(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
