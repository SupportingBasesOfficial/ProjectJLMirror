#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))

from evaluate_candidates import (  # noqa: E402
    CANDIDATES,
    DurableConsumerAuthority,
    FenceViolation,
    Identity,
    IntegrityFailure,
    PrematureProgress,
    Uncertainty,
    evaluate_all,
    run_profile,
)
from validate_source_evidence import (  # noqa: E402
    PLAN_PATH,
    SOURCE_PATH,
    STATE_PATH,
    validate,
)


class RuntimeSemanticsTests(unittest.TestCase):
    def test_every_concrete_candidate_satisfies_all_reference_semantics(self):
        for candidate in CANDIDATES:
            with self.subTest(candidate=candidate):
                checks = run_profile(candidate)
                self.assertTrue(all(checks.values()), checks)
                self.assertEqual(evaluate_all()[candidate], "eligible_for_evidence_execution")

    def test_same_identity_changed_content_fails_closed(self):
        store = DurableConsumerAuthority()
        identity: Identity = ("consumer.a", "tenant:t1/resource:r1", "m1")
        store.claim(identity, {"value": 1}, "w1", 1)
        with self.assertRaises(IntegrityFailure):
            store.claim(identity, {"value": 2}, "w2", 2)

    def test_missing_equivalence_authority_is_uncertainty_not_duplicate(self):
        store = DurableConsumerAuthority()
        identity: Identity = ("consumer.a", "tenant:t1/resource:r1", "m1")
        payload = {"value": 1}
        store.claim(identity, payload, "w1", 1)
        store.remove_equivalence_authority(identity)
        with self.assertRaises(Uncertainty):
            store.claim(identity, payload, "w2", 2)

    def test_takeover_requires_strictly_new_epoch_and_fences_stale_owner(self):
        store = DurableConsumerAuthority()
        identity: Identity = ("consumer.a", "tenant:t1/resource:r1", "m1")
        payload = {"value": 1}
        store.claim(identity, payload, "w1", 1)
        store.expire_lease(identity, "w1", 1)
        with self.assertRaises(FenceViolation):
            store.claim(identity, payload, "w2", 1)
        store.claim(identity, payload, "w2", 2)
        with self.assertRaises(FenceViolation):
            store.complete_effect(identity, "w1", 1)

    def test_higher_epoch_cannot_steal_unexpired_claim(self):
        store = DurableConsumerAuthority()
        identity: Identity = ("consumer.a", "tenant:t1/resource:r1", "m1")
        payload = {"value": 1}
        store.claim(identity, payload, "w1", 1)
        with self.assertRaises(FenceViolation):
            store.claim(identity, payload, "w2", 2)

    def test_progress_before_responsibility_is_rejected(self):
        store = DurableConsumerAuthority()
        identity: Identity = ("consumer.a", "tenant:t1/resource:r1", "m1")
        with self.assertRaises(PrematureProgress):
            store.ack(identity, "w1", 1)
        with self.assertRaises(PrematureProgress):
            store.checkpoint(identity, "w1", 1)

    def test_durable_receipt_and_effect_survive_close_reopen(self):
        identity: Identity = ("consumer.a", "tenant:t1/resource:r1", "m1")
        payload = {"value": 1}
        with tempfile.TemporaryDirectory(prefix="d4c-restart-") as td:
            db = Path(td) / "authority.sqlite3"
            first = DurableConsumerAuthority(db)
            first.claim(identity, payload, "w1", 1)
            first.complete_effect(identity, "w1", 1)
            first.close()

            restarted = DurableConsumerAuthority(db)
            self.assertTrue(restarted.business_effect_truth(identity))
            self.assertEqual(restarted.effect_count(identity), 1)
            restarted.expire_lease(identity, "w1", 1)
            restarted.claim(identity, payload, "w2", 2)
            self.assertEqual(restarted.complete_effect(identity, "w2", 2), "duplicate_noop")
            self.assertEqual(restarted.effect_count(identity), 1)
            restarted.close()

    def test_equivalence_uncertainty_survives_close_reopen(self):
        identity: Identity = ("consumer.a", "tenant:t1/resource:r1", "m1")
        payload = {"value": 1}
        with tempfile.TemporaryDirectory(prefix="d4c-equivalence-restart-") as td:
            db = Path(td) / "authority.sqlite3"
            first = DurableConsumerAuthority(db)
            first.claim(identity, payload, "w1", 1)
            first.remove_equivalence_authority(identity)
            first.close()
            restarted = DurableConsumerAuthority(db)
            with self.assertRaises(Uncertainty):
                restarted.claim(identity, payload, "w1", 1)
            restarted.close()


class ValidatorFalsificationTests(unittest.TestCase):
    def _temp_root(self) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="d4c-ack-lease-"))
        for rel in (SOURCE_PATH, PLAN_PATH, STATE_PATH):
            destination = tmp / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, destination)
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        return tmp

    @staticmethod
    def _read(root: Path, rel: Path):
        return json.loads((root / rel).read_text(encoding="utf-8"))

    @staticmethod
    def _write(root: Path, rel: Path, data) -> None:
        (root / rel).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def _assert_rejected(self, mutate, expected_fragment: str):
        root = self._temp_root()
        mutate(root)
        errors = validate(root)
        self.assertTrue(any(expected_fragment in error for error in errors), errors)

    def test_missing_proof_is_rejected(self):
        def mutate(root):
            source = self._read(root, SOURCE_PATH)
            source["required_proofs"].pop()
            self._write(root, SOURCE_PATH, source)
        self._assert_rejected(mutate, "exact required proof inventory drift")

    def test_same_count_proof_substitution_is_rejected(self):
        def mutate(root):
            source = self._read(root, SOURCE_PATH)
            source["required_proofs"][0] = "weakened_placeholder"
            self._write(root, SOURCE_PATH, source)
        self._assert_rejected(mutate, "exact required proof inventory drift")

    def test_missing_source_assertion_is_rejected(self):
        def mutate(root):
            source = self._read(root, SOURCE_PATH)
            source["source_assertions"].pop()
            self._write(root, SOURCE_PATH, source)
        self._assert_rejected(mutate, "exact source assertion inventory drift")

    def test_same_count_source_assertion_substitution_is_rejected(self):
        def mutate(root):
            source = self._read(root, SOURCE_PATH)
            source["source_assertions"][0] = "weakened_placeholder"
            self._write(root, SOURCE_PATH, source)
        self._assert_rejected(mutate, "exact source assertion inventory drift")

    def test_hidden_selection_is_rejected(self):
        def mutate(root):
            source = self._read(root, SOURCE_PATH)
            source["selection_state"] = "selected"
            self._write(root, SOURCE_PATH, source)
        self._assert_rejected(mutate, "source scalar drift: selection_state")

    def test_auto_credit_is_rejected(self):
        def mutate(root):
            source = self._read(root, SOURCE_PATH)
            source["current_run_auto_credit"] = True
            self._write(root, SOURCE_PATH, source)
        self._assert_rejected(mutate, "source scalar drift: current_run_auto_credit")

    def test_ledger_credit_is_rejected(self):
        def mutate(root):
            source = self._read(root, SOURCE_PATH)
            source["ledger_credit"] = ["ack_after_durable_responsibility_and_lease_ambiguity"]
            self._write(root, SOURCE_PATH, source)
        self._assert_rejected(mutate, "source ledger credit must remain empty")

    def test_candidate_result_escalation_is_rejected(self):
        def mutate(root):
            source = self._read(root, SOURCE_PATH)
            source["candidate_results"][CANDIDATES[0]] = "selected"
            self._write(root, SOURCE_PATH, source)
        self._assert_rejected(mutate, "candidate results drift from executable source harness")

    def test_plan_proof_drift_is_rejected(self):
        def mutate(root):
            plan = self._read(root, PLAN_PATH)
            plan["axes"]["ack_visibility_lease_and_checkpoint"]["must_prove"].pop()
            self._write(root, PLAN_PATH, plan)
        self._assert_rejected(mutate, "source proof inventory no longer matches accepted candidate plan")

    def test_d4c_credit_leakage_is_rejected(self):
        def mutate(root):
            state = self._read(root, STATE_PATH)
            track = next(t for t in state["tracks"] if t["track_id"] == "D4-C")
            evidence = track["evidence_remaining"].pop(0)
            track["evidence_completed"].append(evidence)
            self._write(root, STATE_PATH, state)
        self._assert_rejected(mutate, "D4-C ledger credit leakage")

    def test_duplicate_json_member_is_rejected(self):
        root = self._temp_root()
        path = root / SOURCE_PATH
        raw = path.read_text(encoding="utf-8")
        raw = raw.replace('"schema_version": 1,', '"schema_version": 1,\n  "schema_version": 1,', 1)
        path.write_text(raw, encoding="utf-8")
        errors = validate(root)
        self.assertTrue(any("duplicate JSON member: schema_version" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main(verbosity=2)
