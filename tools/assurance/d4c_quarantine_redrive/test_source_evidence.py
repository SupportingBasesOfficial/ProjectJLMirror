#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest
from pathlib import Path

from evaluate_candidates import (
    AuthorizationDenied,
    CANDIDATES,
    ClassificationDenied,
    IntegrityFailure,
    QuarantineAuthority,
    TEST_FINGERPRINT_PROFILE,
    TEST_RETRY_BUDGET,
    Uncertainty,
    evaluate_all,
)

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "implementation/d4-eventing-async/source-evidence/d4-c-quarantine-redrive-source.json"
PLAN = ROOT / "implementation/d4-eventing-async/d4-c-candidate-evaluation-plan.json"
STATE = ROOT / "implementation/d4-eventing-async/state-manifest.json"
CREDIT = "ack_after_durable_responsibility_and_lease_ambiguity"


class SourceEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.identity = ("consumer.orders.v1", "tenant:t1/order:o1", "msg-009")
        self.content = {"envelope": {"event_type": "order.updated", "contract_version": 7}, "payload": {"order_id": "o1", "revision": 9}}

    def _quarantined(self) -> QuarantineAuthority:
        q = QuarantineAuthority()
        state = q.record_failure(
            self.identity,
            self.content,
            classification="confidential",
            retention_policy_class="regulated_event_policy",
            retry_count=TEST_RETRY_BUDGET,
            retry_budget=TEST_RETRY_BUDGET,
            broker_adapter="test_adapter",
            broker_dlq_ref="opaque:test",
        )
        self.assertEqual(state, "quarantined")
        return q

    def test_all_concrete_candidates_are_evidence_eligible(self):
        runtime = evaluate_all()
        self.assertEqual(set(runtime["candidate_results"]), set(CANDIDATES))
        self.assertEqual(set(runtime["candidate_results"].values()), {"eligible_for_evidence_execution"})
        self.assertTrue(all(all(checks.values()) for checks in runtime["checks"].values()))
        self.assertEqual(runtime["selection"], "not_selected")
        self.assertEqual(runtime["ledger_credit"], [])
        self.assertTrue(runtime["test_retry_budget_is_noncanonical_fixture"])
        self.assertEqual(runtime["test_fingerprint_profile"], TEST_FINGERPRINT_PROFILE)
        self.assertEqual(TEST_FINGERPRINT_PROFILE, "sha256_fixture_only_noncanonical")

    def test_retry_updates_preserve_audit_and_effect_truth(self):
        q = QuarantineAuthority()
        self.assertEqual(q.record_failure(self.identity, self.content, classification="confidential", retention_policy_class="regulated_event_policy", retry_count=TEST_RETRY_BUDGET - 1, retry_budget=TEST_RETRY_BUDGET, broker_adapter="a", broker_dlq_ref=None), "retryable")
        q.set_effect_truth(self.identity, committed=True)
        self.assertEqual(q.record_failure(self.identity, self.content, classification="confidential", retention_policy_class="regulated_event_policy", retry_count=TEST_RETRY_BUDGET, retry_budget=TEST_RETRY_BUDGET, broker_adapter="a", broker_dlq_ref=None), "quarantined")
        snapshot = q.snapshot(self.identity)
        self.assertTrue(snapshot["effect_committed"])
        self.assertEqual(len([e for e in snapshot["audit"] if e.get("action") == "failure_recorded"]), 2)
        q.close()

    def test_redrive_requires_current_not_historical_authority_and_audits_denial(self):
        q = self._quarantined()
        q.grant_redrive("operator", {"confidential"})
        q.revoke_redrive("operator")
        with self.assertRaises(AuthorizationDenied):
            q.redrive(self.identity, self.content, actor="operator", reason="revoked actor")
        audit = q.snapshot(self.identity)["audit"]
        self.assertTrue(any(e.get("action") == "redrive_denied" and e.get("actor") == "operator" for e in audit))
        q.close()

    def test_classification_scope_is_current_authority(self):
        q = self._quarantined()
        q.grant_redrive("public-operator", {"public"})
        with self.assertRaises(ClassificationDenied):
            q.read_payload(self.identity, "public-operator")
        with self.assertRaises(ClassificationDenied):
            q.redrive(self.identity, self.content, actor="public-operator", reason="wrong classification")
        q.close()

    def test_redrive_cannot_bypass_dedup_equivalence_or_reconciliation(self):
        q = self._quarantined()
        q.grant_redrive("admin", {"confidential"})
        with self.assertRaises(IntegrityFailure):
            q.redrive(self.identity, {**self.content, "payload": {"order_id": "o1", "revision": 10}}, actor="admin", reason="conflicting replay")
        q.remove_equivalence_authority(self.identity)
        with self.assertRaises(Uncertainty):
            q.redrive(self.identity, self.content, actor="admin", reason="missing equivalence")
        q.close()

        q = self._quarantined()
        q.grant_redrive("admin", {"confidential"})
        q.set_effect_truth(self.identity, committed=False, external_outcome_unknown=True)
        self.assertEqual(q.redrive(self.identity, self.content, actor="admin", reason="reconcile"), "reconciliation_required")
        self.assertEqual(q.snapshot(self.identity)["state"], "quarantined_reconciliation")
        q.close()

    def test_effect_already_committed_becomes_duplicate_noop_and_is_audited(self):
        q = self._quarantined()
        q.grant_redrive("admin", {"confidential"})
        q.set_effect_truth(self.identity, committed=True)
        self.assertEqual(q.redrive(self.identity, self.content, actor="admin", reason="authorized replay"), "duplicate_noop")
        snapshot = q.snapshot(self.identity)
        self.assertEqual(snapshot["state"], "resolved_duplicate")
        self.assertTrue(any(e.get("action") == "redrive_attempt" and e.get("actor") == "admin" for e in snapshot["audit"]))
        q.close()

    def test_broker_replacement_and_authority_survive_restart_without_rewriting_truth(self):
        import tempfile
        with tempfile.TemporaryDirectory(prefix="d4c-quarantine-test-") as td:
            db = Path(td) / "quarantine.sqlite3"
            q = QuarantineAuthority(db)
            q.record_failure(self.identity, self.content, classification="confidential", retention_policy_class="regulated_event_policy", retry_count=TEST_RETRY_BUDGET, retry_budget=TEST_RETRY_BUDGET, broker_adapter="original", broker_dlq_ref="original:opaque")
            q.grant_redrive("admin", {"confidential"})
            before = q.snapshot(self.identity)
            q.replace_broker(self.identity, new_adapter="replacement", new_dlq_ref="replacement:opaque")
            q.close()
            q = QuarantineAuthority(db)
            after = q.snapshot(self.identity)
            self.assertEqual(before["fingerprint"], after["fingerprint"])
            self.assertEqual(before["classification"], after["classification"])
            self.assertEqual(before["retention_policy_class"], after["retention_policy_class"])
            self.assertEqual(after["broker_adapter"], "replacement")
            self.assertEqual(q.read_payload(self.identity, "admin"), self.content)
            q.close()

    def test_source_manifest_matches_runtime_and_accepted_axis(self):
        source = json.loads(SOURCE.read_text(encoding="utf-8"))
        plan = json.loads(PLAN.read_text(encoding="utf-8"))
        axis = plan["axes"]["quarantine_and_redrive"]
        runtime = evaluate_all()
        self.assertEqual(source["source_decision"], axis["decision"])
        self.assertEqual(source["evidence_id"], axis["evidence_id"])
        self.assertEqual(source["required_proofs"], axis["must_prove"])
        self.assertEqual(source["candidate_results"], runtime["candidate_results"])
        self.assertEqual(source["equivalent_reviewed_profile"], runtime["equivalent_reviewed_profile"])
        self.assertFalse(source["current_run_auto_credit"])
        self.assertEqual(source["ledger_credit"], [])

    def test_current_global_state_is_not_modified_by_source_run(self):
        state = json.loads(STATE.read_text(encoding="utf-8"))
        tracks = {t["track_id"]: t for t in state["tracks"]}
        d4c = tracks["D4-C"]
        self.assertEqual(d4c["evidence_completed"], [CREDIT])
        self.assertEqual(len(d4c["evidence_remaining"]), 8)
        self.assertIsNone(d4c["candidate"])
        self.assertEqual(d4c["candidate_status"], "not_selected")
        self.assertEqual(tracks["D4-D"]["evidence_completed"], [])
        self.assertEqual(sum(len(t["evidence_completed"]) for t in state["tracks"]), 13)
        self.assertEqual(state["gate_state"], "scoped")
        self.assertEqual(state["canonical_product_implementation_authority"], "not_granted")
        self.assertEqual(state["wave4_implementation_authority"], "not_granted")
        self.assertEqual(state["production_authority"], "none")
        self.assertEqual(state["c3_numeric_topology_authority"], "not_selected")


if __name__ == "__main__":
    unittest.main(verbosity=2)
