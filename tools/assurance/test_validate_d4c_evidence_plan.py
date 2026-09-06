#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from validate_d4c_evidence_plan import (
    PLAN, STATE,
    PROMOTION_008, PROMOTION_009, PROMOTION_010, PROMOTION_011,
    PROMOTION_012, PROMOTION_013, PROMOTION_014, PROMOTION_015,
    SOURCE_008, SOURCE_009, SOURCE_010, SOURCE_011,
    SOURCE_012, SOURCE_013, SOURCE_014, SOURCE_015,
    CREDIT_008, CREDIT_009, CREDIT_010, CREDIT_011,
    CREDIT_012, CREDIT_013, CREDIT_014, CREDIT_015,
    validate,
)

ROOT = Path(__file__).resolve().parents[2]
PROMOTIONS = (
    PROMOTION_008, PROMOTION_009, PROMOTION_010, PROMOTION_011,
    PROMOTION_012, PROMOTION_013, PROMOTION_014, PROMOTION_015,
)
SOURCES = (
    SOURCE_008, SOURCE_009, SOURCE_010, SOURCE_011,
    SOURCE_012, SOURCE_013, SOURCE_014, SOURCE_015,
)
CREDITS = (
    CREDIT_008, CREDIT_009, CREDIT_010, CREDIT_011,
    CREDIT_012, CREDIT_013, CREDIT_014, CREDIT_015,
)

class PromotionFalsificationTests(unittest.TestCase):
    def _root(self) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="d4c-promotion-"))
        for rel in (PLAN, *PROMOTIONS, *SOURCES, STATE):
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

    def test_baseline_is_valid(self):
        self.assertEqual(validate(ROOT), [])

    def test_plan_hidden_field_is_rejected(self):
        self._reject(
            self._mutate(PLAN, lambda p: p.__setitem__("hidden_authority", "granted")),
            "evidence-plan exact key schema drift",
        )

    def test_eighth_credit_removal_is_rejected(self):
        self._reject(self._mutate(PLAN, lambda p: p["credited_evidence"].pop()), "credited evidence")

    def test_ninth_credit_is_rejected(self):
        def change(p):
            p["credited_evidence"].append(p["remaining_evidence"].pop(0))
        self._reject(self._mutate(PLAN, change), "credited evidence")

    def test_selection_leakage_is_rejected(self):
        self._reject(
            self._mutate(PLAN, lambda p: p.__setitem__("selection_state", "selected")),
            "plan scalar drift: selection_state",
        )

    def test_all_promotion_record_heads_are_bound(self):
        decisions = range(8, 16)
        for rel, decision in zip(PROMOTIONS, decisions):
            with self.subTest(decision=decision):
                self._reject(
                    self._mutate(rel, lambda p: p.__setitem__("source_reviewed_head", "0" * 40)),
                    f"OPEN-EVT-{decision:03d}: promotion scalar drift",
                )

    def test_015_review_id_drift_is_rejected(self):
        self._reject(
            self._mutate(PROMOTION_015, lambda p: p["source_review"].__setitem__("review_id", 1)),
            "OPEN-EVT-015: source review id drift",
        )

    def test_015_artifact_digest_drift_is_rejected(self):
        self._reject(
            self._mutate(
                PROMOTION_015,
                lambda p: p["source_workflow"].__setitem__("artifact_digest", "sha256:" + "0" * 64),
            ),
            "OPEN-EVT-015: source workflow provenance drift",
        )

    def test_all_source_packages_remain_non_promoting(self):
        decisions = range(8, 16)
        for rel, decision in zip(SOURCES, decisions):
            with self.subTest(decision=decision):
                self._reject(
                    self._mutate(rel, lambda s: s.__setitem__("current_run_auto_credit", True)),
                    f"OPEN-EVT-{decision:03d}: source package must remain non-promoting",
                )

    def test_state_eighth_credit_regression_is_rejected(self):
        def change(s):
            d4c = next(t for t in s["tracks"] if t["track_id"] == "D4-C")
            d4c["evidence_completed"].remove(CREDIT_015)
            d4c["evidence_remaining"].insert(0, CREDIT_015)
        self._reject(self._mutate(STATE, change), "D4-C state credit drift")

    def test_state_extra_ninth_credit_is_rejected(self):
        def change(s):
            d4c = next(t for t in s["tracks"] if t["track_id"] == "D4-C")
            d4c["evidence_completed"].append(d4c["evidence_remaining"].pop(0))
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

    def test_promotion_hidden_field_is_rejected(self):
        self._reject(
            self._mutate(PROMOTION_015, lambda p: p.__setitem__("hidden_authority", "granted")),
            "OPEN-EVT-015: promotion exact key schema drift",
        )

    def test_nested_review_hidden_field_is_rejected(self):
        self._reject(
            self._mutate(PROMOTION_015, lambda p: p["source_review"].__setitem__("hidden", True)),
            "OPEN-EVT-015: source review exact key schema drift",
        )

    def test_credit_count_bool_is_rejected(self):
        self._reject(
            self._mutate(PROMOTION_015, lambda p: p.__setitem__("credit_count", True)),
            "OPEN-EVT-015: promotion credit drift",
        )

    def test_separate_selection_guard_is_rejected(self):
        self._reject(
            self._mutate(PROMOTION_015, lambda p: p.__setitem__("separate_selection_required", False)),
            "OPEN-EVT-015: separate-selection guard drift",
        )

    def test_separate_acceptance_guard_is_rejected(self):
        self._reject(
            self._mutate(PROMOTION_015, lambda p: p.__setitem__("separate_d4_acceptance_required", False)),
            "OPEN-EVT-015: separate-acceptance guard drift",
        )

    def test_duplicate_json_member_is_rejected(self):
        root = self._root()
        path = root / PROMOTION_015
        raw = path.read_text(encoding="utf-8")
        path.write_text(
            raw.replace('"schema_version": 1,', '"schema_version": 1,\n  "schema_version": 1,', 1),
            encoding="utf-8",
        )
        errors = validate(root)
        self.assertTrue(any("duplicate JSON member: schema_version" in e for e in errors), errors)

    def test_required_credit_order_is_exact(self):
        def change(p):
            p["credited_evidence"] = [
                CREDIT_009, CREDIT_008, CREDIT_010, CREDIT_011,
                CREDIT_012, CREDIT_013, CREDIT_014, CREDIT_015,
            ]
        self._reject(self._mutate(PLAN, change), "credited evidence")

if __name__ == "__main__":
    unittest.main(verbosity=2)
