#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from validate_d3_identity_security_state import (
    APPROVED_EVIDENCE_PROOFS,
    GATE_DOC,
    MANIFEST,
    validate,
)

REPO = Path(__file__).resolve().parents[2]
BASE_MANIFEST = json.loads((REPO / MANIFEST).read_text(encoding="utf-8"))
BASE_GATE_DOC = (REPO / GATE_DOC).read_text(encoding="utf-8")


def synthetic_proof(track: dict, evidence_id: str, ordinal: int) -> dict:
    artifact_pins = []
    if track["track_id"] == "D3-A":
        artifact_pins = [track["candidate_image_digest"]]
    elif track["track_id"] == "D3-B":
        artifact_pins = list(track["candidate_artifact_digests"].values())
    elif track["track_id"] == "D3-D":
        artifact_pins = [track["candidate_artifact_digest"]]
    return {
        "evidence_id": evidence_id,
        "evidence_sha": f"{ordinal:040x}",
        "workflow_run_id": 90000000000 + ordinal,
        "workflow_run_number": ordinal,
        "workflow_file": ".github/workflows/d3-synthetic-positive-control.yml",
        "job_name": "D3 synthetic positive-control job",
        "probe": "tools/assurance/test_validate_d3_identity_security_state.py",
        "artifact_pins": artifact_pins,
        "result": "pass",
    }


def track_by_id(manifest: dict, track_id: str = "D3-E") -> dict:
    return next(track for track in manifest["tracks"] if track["track_id"] == track_id)


def demote_one_evidence(manifest: dict, track_id: str = "D3-E") -> tuple[dict, str]:
    """Build an explicit synthetic pending state from the now-terminal baseline."""
    track = track_by_id(manifest, track_id)
    evidence_id = track["evidence_completed"].pop()
    track["evidence_remaining"].append(evidence_id)
    track["evidence_proofs"] = [
        proof for proof in track["evidence_proofs"] if proof["evidence_id"] != evidence_id
    ]
    track["state"] = "candidate_selected_conformance_pending"
    manifest["gate_state"] = "candidate_evidence_running"
    return track, evidence_id


def complete_all_evidence(manifest: dict) -> dict:
    registry = {}
    ordinal = 1
    for track in manifest["tracks"]:
        proofs = []
        for evidence_id in track["required_evidence"]:
            proof = synthetic_proof(track, evidence_id, ordinal)
            proofs.append(proof)
            registry[(track["track_id"], evidence_id)] = copy.deepcopy(proof)
            ordinal += 1
        track["evidence_completed"] = list(track["required_evidence"])
        track["evidence_remaining"] = []
        track["evidence_proofs"] = proofs
    return registry


class D3IdentitySecurityStateTests(unittest.TestCase):
    def _root(self, mutate=None) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        manifest = copy.deepcopy(BASE_MANIFEST)
        if mutate is not None:
            mutate(manifest)
        path = root / MANIFEST
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        doc = root / GATE_DOC
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text(BASE_GATE_DOC, encoding="utf-8")
        return root

    def test_current_manifest_passes(self):
        validate(self._root())

    def test_wave4_grant_is_rejected(self):
        with self.assertRaises(AssertionError):
            validate(self._root(lambda m: m.__setitem__("wave4_implementation_authority", "granted")))

    def test_product_code_grant_is_rejected(self):
        with self.assertRaises(AssertionError):
            validate(self._root(lambda m: m.__setitem__("canonical_product_implementation_authority", "granted")))

    def test_production_grant_is_rejected(self):
        with self.assertRaises(AssertionError):
            validate(self._root(lambda m: m.__setitem__("production_authority", "granted")))

    def test_d4_selection_is_rejected(self):
        with self.assertRaises(AssertionError):
            validate(self._root(lambda m: m.__setitem__("d4_transport_authority", "kafka_selected")))

    def test_invalid_gate_state_is_rejected(self):
        with self.assertRaises(AssertionError):
            validate(self._root(lambda m: m.__setitem__("gate_state", "accepted")))

    def test_schema_downgrade_is_rejected(self):
        with self.assertRaises(AssertionError):
            validate(self._root(lambda m: m.__setitem__("schema_version", 2)))

    def test_candidate_identity_drift_is_rejected(self):
        def mutate(m):
            track = track_by_id(m, "D3-A")
            track["candidate"] = "keycloak_26_7_0"
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_candidate_digest_drift_is_rejected(self):
        def mutate(m):
            track = track_by_id(m, "D3-A")
            track["candidate_image_digest"] = "quay.io/keycloak/keycloak@sha256:deadbeef"
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_portability_control_drift_is_rejected(self):
        def mutate(m):
            track = track_by_id(m, "D3-B")
            track["portability_control"] = "redis_only"
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_d3b_candidate_artifact_digest_drift_is_rejected(self):
        def mutate(m):
            track = track_by_id(m, "D3-B")
            track["candidate_artifact_digests"]["redis_compatible_primary"] = (
                "redis@sha256:" + "0" * 64
            )
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_d3d_candidate_artifact_digest_drift_is_rejected(self):
        def mutate(m):
            track = track_by_id(m, "D3-D")
            track["candidate_artifact_digest"] = (
                "spire-1.15.3-linux-amd64-musl.tar.gz@sha256:" + "0" * 64
            )
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_missing_track_is_rejected(self):
        def mutate(m):
            m["tracks"] = [t for t in m["tracks"] if t["track_id"] != "D3-D"]
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_duplicate_track_is_rejected(self):
        def mutate(m):
            m["tracks"].append(copy.deepcopy(m["tracks"][0]))
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_event_transport_open_leak_is_rejected(self):
        def mutate(m):
            m["tracks"][0]["source_decisions"].append("OPEN-EVT-001")
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_evt_011_is_rejected_outside_d3e(self):
        def mutate(m):
            m["tracks"][0]["source_decisions"].append("OPEN-EVT-011")
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_d3e_crypto_only_evt_011_join_is_allowed(self):
        validate(self._root())

    def test_missing_required_source_anchor_is_rejected(self):
        def mutate(m):
            d3b = track_by_id(m, "D3-B")
            d3b["source_decisions"] = ["OPEN-REL-015", "OPEN-REL-008.A:security-session-profile-only"]
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_unrelated_source_anchor_is_rejected(self):
        def mutate(m):
            d3c = track_by_id(m, "D3-C")
            d3c["source_decisions"] = ["OPEN-API-002", "UNRELATED-DECISION"]
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_duplicate_source_anchor_is_rejected(self):
        def mutate(m):
            d3e = track_by_id(m)
            d3e["source_decisions"].append("OPEN-EVT-011:duplicate")
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_missing_required_evidence_is_rejected(self):
        def mutate(m):
            track = track_by_id(m)
            evidence_id = track["required_evidence"][0]
            track["required_evidence"].remove(evidence_id)
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_unknown_completed_evidence_is_rejected(self):
        def mutate(m):
            track = track_by_id(m, "D3-C")
            track["evidence_completed"].append("fabricated_evidence")
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_evidence_cannot_be_completed_and_remaining(self):
        def mutate(m):
            track = track_by_id(m)
            track["evidence_remaining"].append(track["evidence_completed"][0])
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_unaccounted_required_evidence_is_rejected(self):
        def mutate(m):
            track = track_by_id(m)
            evidence_id = track["evidence_completed"].pop()
            track["evidence_proofs"] = [
                proof for proof in track["evidence_proofs"] if proof["evidence_id"] != evidence_id
            ]
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_completed_evidence_without_proof_is_rejected(self):
        def mutate(m):
            track = track_by_id(m, "D3-A")
            track["evidence_proofs"].pop()
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_proof_for_remaining_evidence_is_rejected(self):
        def mutate(m):
            track, evidence_id = demote_one_evidence(m)
            proof = copy.deepcopy(APPROVED_EVIDENCE_PROOFS[("D3-E", evidence_id)])
            track["evidence_proofs"].append(proof)
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_unapproved_structurally_valid_proof_is_rejected(self):
        def mutate(m):
            track = track_by_id(m)
            evidence_id = track["evidence_completed"][0]
            track["evidence_proofs"] = [
                synthetic_proof(track, evidence_id, 701)
                if proof["evidence_id"] == evidence_id else proof
                for proof in track["evidence_proofs"]
            ]
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_d3e_promoted_provenance_drift_is_rejected(self):
        def mutate(m):
            track = track_by_id(m)
            proof = next(
                p for p in track["evidence_proofs"]
                if p["evidence_id"] == "private_key_jwt_replay_atomic_single_winner"
            )
            proof["workflow_run_id"] += 1
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_malformed_evidence_sha_is_rejected(self):
        def mutate(m):
            track = track_by_id(m, "D3-A")
            track["evidence_proofs"][0]["evidence_sha"] = "BAD-SHA"
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_invalid_workflow_run_id_is_rejected(self):
        def mutate(m):
            track = track_by_id(m, "D3-A")
            track["evidence_proofs"][0]["workflow_run_id"] = 0
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_mutable_artifact_pin_is_rejected(self):
        def mutate(m):
            track = track_by_id(m, "D3-A")
            track["evidence_proofs"][0]["artifact_pins"] = ["quay.io/keycloak/keycloak:26.7.2"]
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_approved_proof_digest_drift_is_rejected(self):
        def mutate(m):
            track = track_by_id(m, "D3-A")
            track["evidence_proofs"][0]["artifact_pins"] = [
                "quay.io/keycloak/keycloak@sha256:" + "0" * 64
            ]
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_terminal_track_with_remaining_evidence_is_rejected(self):
        def mutate(m):
            track = track_by_id(m, "D3-D")
            evidence_id = track["evidence_completed"].pop()
            track["evidence_remaining"].append(evidence_id)
            track["evidence_proofs"] = [
                proof for proof in track["evidence_proofs"] if proof["evidence_id"] != evidence_id
            ]
            track["state"] = "per_track_conformed"
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_promoted_terminal_tracks_cannot_coherently_demote(self):
        for track_id in ("D3-A", "D3-B", "D3-C", "D3-D", "D3-E"):
            with self.subTest(track_id=track_id):
                def mutate(m, promoted_track_id=track_id):
                    demote_one_evidence(m, promoted_track_id)

                with self.assertRaises(AssertionError):
                    validate(self._root(mutate))

    def test_missing_c3_boundary_is_rejected(self):
        def mutate(m):
            m["c3_remains_open"].remove("OPEN-REL-031.B")
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_per_track_conformed_gate_rejects_pending_tracks(self):
        def mutate(m):
            demote_one_evidence(m)
            m["gate_state"] = "per_track_conformed"
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_premature_acceptance_with_pending_track_is_rejected(self):
        def mutate(m):
            demote_one_evidence(m)
            m["gate_state"] = "d3_acceptance_eligible"
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_separately_accepted_with_pending_track_is_rejected(self):
        def mutate(m):
            demote_one_evidence(m)
            m["gate_state"] = "separately_accepted"
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_status_only_acceptance_is_rejected_without_evidence_completion(self):
        def mutate(m):
            demote_one_evidence(m)
            m["gate_state"] = "d3_acceptance_eligible"
            for track in m["tracks"]:
                track["state"] = "per_track_conformed"
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_per_track_conformed_gate_requires_exact_track_state(self):
        registry = {}
        def mutate(m):
            m["gate_state"] = "per_track_conformed"
            registry.update(complete_all_evidence(m))
            for track in m["tracks"]:
                track["state"] = "per_track_conformed"
            m["tracks"][0]["state"] = "accepted_candidate"
        root = self._root(mutate)
        with patch.dict(APPROVED_EVIDENCE_PROOFS, registry, clear=True):
            with self.assertRaises(AssertionError):
                validate(root)

    def test_acceptance_eligible_requires_terminal_tracks_completed_evidence_and_approved_proofs(self):
        registry = {}
        def mutate(m):
            m["gate_state"] = "d3_acceptance_eligible"
            registry.update(complete_all_evidence(m))
            for track in m["tracks"]:
                track["state"] = "per_track_conformed"
        root = self._root(mutate)
        with patch.dict(APPROVED_EVIDENCE_PROOFS, registry, clear=True):
            validate(root)

    def test_separate_acceptance_requires_accepted_candidate_track_state(self):
        registry = {}
        def mutate(m):
            m["gate_state"] = "separately_accepted"
            registry.update(complete_all_evidence(m))
            for track in m["tracks"]:
                track["state"] = "per_track_conformed"
        root = self._root(mutate)
        with patch.dict(APPROVED_EVIDENCE_PROOFS, registry, clear=True):
            with self.assertRaises(AssertionError):
                validate(root)

    def test_separately_accepted_requires_terminal_tracks_completed_evidence_and_approved_proofs(self):
        registry = {}
        def mutate(m):
            m["gate_state"] = "separately_accepted"
            registry.update(complete_all_evidence(m))
            for track in m["tracks"]:
                track["state"] = "accepted_candidate"
        root = self._root(mutate)
        with patch.dict(APPROVED_EVIDENCE_PROOFS, registry, clear=True):
            validate(root)

    def test_required_exclusion_cannot_disappear(self):
        def mutate(m):
            m["explicit_exclusions"].remove("OPEN-EVT-001:transport")
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))


if __name__ == "__main__":
    unittest.main(verbosity=2)
