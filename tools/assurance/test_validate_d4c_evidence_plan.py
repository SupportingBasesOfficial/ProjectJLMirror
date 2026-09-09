#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from validate_d4c_evidence_plan import (
    PLAN, STATE, PROMOTION_025, SOURCE_025, CREDIT_025, CREDITS,
    HISTORICAL_PROMOTIONS, validate,
)

ROOT = Path(__file__).resolve().parents[2]

class PromotionFalsificationTests(unittest.TestCase):
    def _root(self) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="d4c-promotion-"))
        rels = [PLAN, STATE, PROMOTION_025, SOURCE_025, *HISTORICAL_PROMOTIONS.keys()]
        for promotion in HISTORICAL_PROMOTIONS:
            record = json.loads((ROOT / promotion).read_text(encoding="utf-8"))
            rels.append(Path(record["source_manifest"]["path"]))
        for rel in dict.fromkeys(rels):
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

    def _reject(self, mutator, fragment: str):
        root = self._root()
        mutator(root)
        errors = validate(root)
        self.assertTrue(any(fragment in e for e in errors), errors)

    def _mutate_json(self, rel: Path, fn):
        def mutate(root):
            data = self._read(root, rel)
            fn(data)
            self._write(root, rel, data)
        return mutate

    def test_baseline_is_valid(self):
        self.assertEqual(validate(ROOT), [])

    def test_source_decision_inventory_drift_is_rejected(self):
        self._reject(
            self._mutate_json(PLAN, lambda p: p["source_decisions"].__setitem__(-1, "OPEN-EVT-024")),
            "source decision inventory drift",
        )

    def test_ninth_credit_regression_is_rejected(self):
        def change(p):
            p["credited_evidence"].remove(CREDIT_025)
            p["remaining_evidence"] = [CREDIT_025]
        self._reject(self._mutate_json(PLAN, change), "credited evidence")

    def test_extra_credit_or_duplicate_is_rejected(self):
        self._reject(
            self._mutate_json(PLAN, lambda p: p["credited_evidence"].append(CREDIT_025)),
            "credited evidence",
        )

    def test_required_credit_order_is_exact(self):
        self._reject(
            self._mutate_json(PLAN, lambda p: p.__setitem__("credited_evidence", list(reversed(p["credited_evidence"])))),
            "credited evidence",
        )

    def test_plan_hidden_field_is_rejected(self):
        self._reject(
            self._mutate_json(PLAN, lambda p: p.__setitem__("hidden_authority", "granted")),
            "exact key schema drift",
        )

    def test_selection_leakage_is_rejected(self):
        self._reject(
            self._mutate_json(PLAN, lambda p: p.__setitem__("selection_state", "selected")),
            "plan scalar drift: selection_state",
        )

    def test_historical_promotion_bytes_are_pinned(self):
        rel = next(iter(HISTORICAL_PROMOTIONS))
        def mutate(root):
            data = self._read(root, rel)
            data["credit_count"] = 2
            self._write(root, rel, data)
        self._reject(mutate, "historical promotion blob drift")

    def test_historical_source_bytes_are_bound(self):
        rel = next(iter(HISTORICAL_PROMOTIONS))
        record = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        source = Path(record["source_manifest"]["path"])
        self._reject(
            self._mutate_json(source, lambda s: s.__setitem__("current_run_auto_credit", True)),
            "historical source manifest bytes drift",
        )

    def test_025_review_id_drift_is_rejected(self):
        self._reject(
            self._mutate_json(PROMOTION_025, lambda p: p["source_review"].__setitem__("review_id", 1)),
            "source review id drift",
        )

    def test_025_artifact_digest_drift_is_rejected(self):
        self._reject(
            self._mutate_json(PROMOTION_025, lambda p: p["source_workflow"].__setitem__("artifact_digest", "sha256:" + "0"*64)),
            "source workflow provenance drift",
        )

    def test_025_source_must_remain_nonpromoting(self):
        self._reject(
            self._mutate_json(SOURCE_025, lambda s: s.__setitem__("current_run_auto_credit", True)),
            "source manifest bytes drift",
        )

    def test_025_promotion_hidden_field_is_rejected(self):
        self._reject(
            self._mutate_json(PROMOTION_025, lambda p: p.__setitem__("hidden_authority", "granted")),
            "promotion exact key schema drift",
        )

    def test_025_credit_count_bool_is_rejected(self):
        self._reject(
            self._mutate_json(PROMOTION_025, lambda p: p.__setitem__("credit_count", True)),
            "promotion scalar drift: credit_count",
        )

    def test_state_ninth_credit_regression_is_rejected(self):
        def change(s):
            d4c = next(t for t in s["tracks"] if t["track_id"] == "D4-C")
            d4c["evidence_completed"].remove(CREDIT_025)
            d4c["evidence_remaining"] = [CREDIT_025]
        self._reject(self._mutate_json(STATE, change), "D4-C state credit drift")

    def test_sibling_credit_regression_is_rejected(self):
        def change(s):
            d4d = next(t for t in s["tracks"] if t["track_id"] == "D4-D")
            fifth = "trace_context_observability_only_validation_and_redaction"
            d4d["evidence_completed"].remove(fifth)
            d4d["evidence_remaining"] = [fifth]
        self._reject(self._mutate_json(STATE, change), "D4-D state/credit leakage")

    def test_duplicate_track_id_is_rejected(self):
        def change(s):
            s["tracks"].append(dict(s["tracks"][2]))
        self._reject(self._mutate_json(STATE, change), "track structure")

    def test_authority_leakage_is_rejected(self):
        self._reject(
            self._mutate_json(STATE, lambda s: s.__setitem__("wave4_implementation_authority", "granted")),
            "global authority drift",
        )

if __name__ == "__main__":
    unittest.main(verbosity=2)
