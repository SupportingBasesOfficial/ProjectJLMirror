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

    def _mutate(self, rel: Path, fn):
        def mutate(root):
            data = self._read(root, rel)
            fn(data)
            self._write(root, rel, data)
        return mutate

    def test_plan_hidden_field_is_rejected(self):
        self._reject(self._mutate(PLAN, lambda p: p.__setitem__("hidden_authority", "granted")), "evidence-plan exact key schema drift")

    def test_promotion_hidden_field_is_rejected(self):
        self._reject(self._mutate(PROMOTION, lambda p: p.__setitem__("hidden_authority", "granted")), "promotion exact key schema drift")

    def test_nested_review_hidden_field_is_rejected(self):
        self._reject(self._mutate(PROMOTION, lambda p: p["source_review"].__setitem__("hidden", True)), "source review exact key schema drift")

    def test_nested_workflow_hidden_field_is_rejected(self):
        self._reject(self._mutate(PROMOTION, lambda p: p["source_workflow"].__setitem__("hidden", True)), "source workflow exact key schema drift")

    def test_nested_manifest_hidden_field_is_rejected(self):
        self._reject(self._mutate(PROMOTION, lambda p: p["source_manifest"].__setitem__("hidden", True)), "source manifest exact key schema drift")

    def test_promotion_bool_schema_version_is_rejected(self):
        self._reject(self._mutate(PROMOTION, lambda p: p.__setitem__("schema_version", True)), "schema_version must be integer 1")

    def test_credit_count_bool_is_rejected(self):
        self._reject(self._mutate(PROMOTION, lambda p: p.__setitem__("credit_count", True)), "promotion credit drift")

    def test_credit_removal_is_rejected(self):
        self._reject(self._mutate(PLAN, lambda p: p.__setitem__("credited_evidence", [])), "credited evidence")

    def test_extra_credit_is_rejected(self):
        def change(p):
            p["credited_evidence"].append(p["remaining_evidence"][0])
        self._reject(self._mutate(PLAN, change), "credited evidence")

    def test_selection_leakage_is_rejected(self):
        self._reject(self._mutate(PLAN, lambda p: p.__setitem__("selection_state", "selected")), "plan scalar drift: selection_state")

    def test_source_head_drift_is_rejected(self):
        self._reject(self._mutate(PROMOTION, lambda p: p.__setitem__("source_reviewed_head", "0" * 40)), "source reviewed HEAD drift")

    def test_source_merge_commit_drift_is_rejected(self):
        self._reject(self._mutate(PROMOTION, lambda p: p.__setitem__("source_merge_commit", "0" * 40)), "source merge commit drift")

    def test_source_review_mode_drift_is_rejected(self):
        self._reject(self._mutate(PROMOTION, lambda p: p["source_review"].__setitem__("review_mode", "older_review_reused")), "source review mode drift")

    def test_source_review_id_drift_is_rejected(self):
        self._reject(self._mutate(PROMOTION, lambda p: p["source_review"].__setitem__("review_id", 1)), "source review id drift")

    def test_artifact_digest_drift_is_rejected(self):
        self._reject(self._mutate(PROMOTION, lambda p: p["source_workflow"].__setitem__("artifact_digest", "sha256:" + "0" * 64)), "source workflow provenance drift")

    def test_run_attempt_bool_is_rejected(self):
        self._reject(self._mutate(PROMOTION, lambda p: p["source_workflow"].__setitem__("run_attempt", True)), "source workflow provenance drift")

    def test_separate_selection_guard_is_rejected(self):
        self._reject(self._mutate(PROMOTION, lambda p: p.__setitem__("separate_selection_required", False)), "separate-selection guard drift")

    def test_separate_acceptance_guard_is_rejected(self):
        self._reject(self._mutate(PROMOTION, lambda p: p.__setitem__("separate_d4_acceptance_required", False)), "separate-acceptance guard drift")

    def test_source_auto_credit_is_rejected(self):
        self._reject(self._mutate(SOURCE, lambda s: s.__setitem__("current_run_auto_credit", True)), "source package must remain non-promoting")

    def test_state_credit_regression_is_rejected(self):
        def change(s):
            d4c = next(t for t in s["tracks"] if t["track_id"] == "D4-C")
            d4c["evidence_completed"] = []
            d4c["evidence_remaining"].insert(0, "ack_after_durable_responsibility_and_lease_ambiguity")
        self._reject(self._mutate(STATE, change), "D4-C state credit drift")

    def test_sibling_credit_leakage_is_rejected(self):
        def change(s):
            d4d = next(t for t in s["tracks"] if t["track_id"] == "D4-D")
            d4d["evidence_completed"] = [d4d["evidence_remaining"].pop(0)]
        self._reject(self._mutate(STATE, change), "D4-D state/credit leakage")

    def test_duplicate_track_id_is_rejected(self):
        def change(s):
            s["tracks"].append(dict(s["tracks"][2]))
        self._reject(self._mutate(STATE, change), "D4 track structure drift")

    def test_duplicate_json_member_is_rejected(self):
        root = self._root()
        path = root / PROMOTION
        raw = path.read_text(encoding="utf-8")
        path.write_text(raw.replace('"schema_version": 1,', '"schema_version": 1,\n  "schema_version": 1,', 1), encoding="utf-8")
        errors = validate(root)
        self.assertTrue(any("duplicate JSON member: schema_version" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main(verbosity=2)
