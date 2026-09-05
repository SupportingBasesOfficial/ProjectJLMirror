#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from validate_d4c_evidence_plan import PLAN, PROMOTION, SOURCE, STATE, validate

ROOT = Path(__file__).resolve().parents[2]


class PromotionFalsificationTests(unittest.TestCase):
    def _root(self) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="d4c-promotion-"))
        for rel in (PLAN, PROMOTION, SOURCE, STATE):
            dst = tmp / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, dst)
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        return tmp

    @staticmethod
    def _read(root: Path, rel: Path):
        return json.loads((root / rel).read_text(encoding="utf-8"))

    @staticmethod
    def _write(root: Path, rel: Path, data) -> None:
        (root / rel).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def _reject(self, mutate, fragment: str):
        root = self._root()
        mutate(root)
        errors = validate(root)
        self.assertTrue(any(fragment in error for error in errors), errors)

    def test_credit_removal_is_rejected(self):
        self._reject(lambda r: self._mutate_list(r, PLAN, "credited_evidence", []), "credited evidence")

    def test_extra_credit_is_rejected(self):
        def mutate(root):
            p = self._read(root, PLAN)
            p["credited_evidence"].append(p["remaining_evidence"][0])
            self._write(root, PLAN, p)
        self._reject(mutate, "credited evidence")

    def test_selection_leakage_is_rejected(self):
        def mutate(root):
            p = self._read(root, PLAN)
            p["selection_state"] = "selected"
            self._write(root, PLAN, p)
        self._reject(mutate, "plan scalar drift: selection_state")

    def test_source_head_drift_is_rejected(self):
        def mutate(root):
            p = self._read(root, PROMOTION)
            p["source_reviewed_head"] = "0" * 40
            self._write(root, PROMOTION, p)
        self._reject(mutate, "source reviewed HEAD drift")

    def test_artifact_digest_drift_is_rejected(self):
        def mutate(root):
            p = self._read(root, PROMOTION)
            p["source_workflow"]["artifact_digest"] = "sha256:" + "0" * 64
            self._write(root, PROMOTION, p)
        self._reject(mutate, "source workflow provenance drift")

    def test_source_auto_credit_is_rejected(self):
        def mutate(root):
            s = self._read(root, SOURCE)
            s["current_run_auto_credit"] = True
            self._write(root, SOURCE, s)
        self._reject(mutate, "source package must remain non-promoting")

    def test_state_credit_regression_is_rejected(self):
        def mutate(root):
            s = self._read(root, STATE)
            d4c = next(t for t in s["tracks"] if t["track_id"] == "D4-C")
            d4c["evidence_completed"] = []
            d4c["evidence_remaining"].insert(0, "ack_after_durable_responsibility_and_lease_ambiguity")
            self._write(root, STATE, s)
        self._reject(mutate, "D4-C state credit drift")

    def test_sibling_credit_leakage_is_rejected(self):
        def mutate(root):
            s = self._read(root, STATE)
            d4d = next(t for t in s["tracks"] if t["track_id"] == "D4-D")
            d4d["evidence_completed"] = [d4d["evidence_remaining"].pop(0)]
            self._write(root, STATE, s)
        self._reject(mutate, "D4-wide credited evidence must be exactly 13/26")

    def test_duplicate_json_member_is_rejected(self):
        root = self._root()
        path = root / PROMOTION
        raw = path.read_text(encoding="utf-8")
        path.write_text(raw.replace('"schema_version": 1,', '"schema_version": 1,\n  "schema_version": 1,', 1), encoding="utf-8")
        errors = validate(root)
        self.assertTrue(any("duplicate JSON member: schema_version" in e for e in errors), errors)

    def _mutate_list(self, root, rel, key, value):
        data = self._read(root, rel)
        data[key] = value
        self._write(root, rel, data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
