#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from validate_d3_identity_security_state import GATE_DOC, MANIFEST, validate

REPO = Path(__file__).resolve().parents[2]
BASE_MANIFEST = json.loads((REPO / MANIFEST).read_text(encoding="utf-8"))
BASE_GATE_DOC = (REPO / GATE_DOC).read_text(encoding="utf-8")


def complete_all_evidence(manifest: dict) -> None:
    for track in manifest["tracks"]:
        track["evidence_completed"] = list(track["required_evidence"])
        track["evidence_remaining"] = []


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
            validate(self._root(lambda m: m.__setitem__("schema_version", 1)))

    def test_candidate_identity_drift_is_rejected(self):
        def mutate(m):
            track = next(t for t in m["tracks"] if t["track_id"] == "D3-A")
            track["candidate"] = "keycloak_26_7_0"
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_candidate_digest_drift_is_rejected(self):
        def mutate(m):
            track = next(t for t in m["tracks"] if t["track_id"] == "D3-A")
            track["candidate_image_digest"] = "quay.io/keycloak/keycloak@sha256:deadbeef"
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_portability_control_drift_is_rejected(self):
        def mutate(m):
            track = next(t for t in m["tracks"] if t["track_id"] == "D3-B")
            track["portability_control"] = "redis_only"
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
            d3b = next(t for t in m["tracks"] if t["track_id"] == "D3-B")
            d3b["source_decisions"] = ["OPEN-REL-015", "OPEN-REL-008.A:security-session-profile-only"]
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_unrelated_source_anchor_is_rejected(self):
        def mutate(m):
            d3c = next(t for t in m["tracks"] if t["track_id"] == "D3-C")
            d3c["source_decisions"] = ["OPEN-API-002", "UNRELATED-DECISION"]
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_duplicate_source_anchor_is_rejected(self):
        def mutate(m):
            d3e = next(t for t in m["tracks"] if t["track_id"] == "D3-E")
            d3e["source_decisions"].append("OPEN-EVT-011:duplicate")
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_missing_required_evidence_is_rejected(self):
        def mutate(m):
            track = next(t for t in m["tracks"] if t["track_id"] == "D3-A")
            missing = track["required_evidence"].pop()
            track["evidence_remaining"].remove(missing)
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_unknown_completed_evidence_is_rejected(self):
        def mutate(m):
            track = next(t for t in m["tracks"] if t["track_id"] == "D3-C")
            track["evidence_completed"].append("fabricated_evidence")
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_evidence_cannot_be_completed_and_remaining(self):
        def mutate(m):
            track = next(t for t in m["tracks"] if t["track_id"] == "D3-E")
            track["evidence_completed"].append(track["evidence_remaining"][0])
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_unaccounted_required_evidence_is_rejected(self):
        def mutate(m):
            track = next(t for t in m["tracks"] if t["track_id"] == "D3-B")
            track["evidence_remaining"].pop()
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_terminal_track_with_remaining_evidence_is_rejected(self):
        def mutate(m):
            track = next(t for t in m["tracks"] if t["track_id"] == "D3-D")
            track["state"] = "per_track_conformed"
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_missing_c3_boundary_is_rejected(self):
        def mutate(m):
            m["c3_remains_open"].remove("OPEN-REL-031.B")
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_per_track_conformed_gate_rejects_pending_tracks(self):
        def mutate(m):
            m["gate_state"] = "per_track_conformed"
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_premature_acceptance_with_pending_track_is_rejected(self):
        def mutate(m):
            m["gate_state"] = "d3_acceptance_eligible"
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_separately_accepted_with_pending_track_is_rejected(self):
        def mutate(m):
            m["gate_state"] = "separately_accepted"
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_status_only_acceptance_is_rejected_without_evidence_completion(self):
        def mutate(m):
            m["gate_state"] = "d3_acceptance_eligible"
            for track in m["tracks"]:
                track["state"] = "per_track_conformed"
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_per_track_conformed_gate_requires_exact_track_state(self):
        def mutate(m):
            m["gate_state"] = "per_track_conformed"
            complete_all_evidence(m)
            for track in m["tracks"]:
                track["state"] = "per_track_conformed"
            m["tracks"][0]["state"] = "accepted_candidate"
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_acceptance_eligible_requires_terminal_tracks_and_completed_evidence(self):
        def mutate(m):
            m["gate_state"] = "d3_acceptance_eligible"
            complete_all_evidence(m)
            for track in m["tracks"]:
                track["state"] = "per_track_conformed"
        validate(self._root(mutate))

    def test_separate_acceptance_requires_accepted_candidate_track_state(self):
        def mutate(m):
            m["gate_state"] = "separately_accepted"
            complete_all_evidence(m)
            for track in m["tracks"]:
                track["state"] = "per_track_conformed"
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_separately_accepted_requires_terminal_tracks_and_completed_evidence(self):
        def mutate(m):
            m["gate_state"] = "separately_accepted"
            complete_all_evidence(m)
            for track in m["tracks"]:
                track["state"] = "accepted_candidate"
        validate(self._root(mutate))

    def test_required_exclusion_cannot_disappear(self):
        def mutate(m):
            m["explicit_exclusions"].remove("OPEN-EVT-001:transport")
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))


if __name__ == "__main__":
    unittest.main(verbosity=2)
