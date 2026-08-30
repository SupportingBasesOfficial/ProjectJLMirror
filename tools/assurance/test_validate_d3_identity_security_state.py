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

    def test_missing_c3_boundary_is_rejected(self):
        def mutate(m):
            m["c3_remains_open"].remove("OPEN-REL-031.B")
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_premature_acceptance_with_pending_track_is_rejected(self):
        def mutate(m):
            m["gate_state"] = "d3_acceptance_eligible"
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))

    def test_acceptance_eligible_requires_all_tracks_terminal(self):
        def mutate(m):
            m["gate_state"] = "d3_acceptance_eligible"
            for track in m["tracks"]:
                track["state"] = "per_track_conformed"
        validate(self._root(mutate))

    def test_required_exclusion_cannot_disappear(self):
        def mutate(m):
            m["explicit_exclusions"].remove("OPEN-EVT-001:transport")
        with self.assertRaises(AssertionError):
            validate(self._root(mutate))


if __name__ == "__main__":
    unittest.main(verbosity=2)
