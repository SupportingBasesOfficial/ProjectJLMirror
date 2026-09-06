#!/usr/bin/env python3
from __future__ import annotations

import unittest
from dataclasses import replace

from evaluate_candidates import CANDIDATES, PROOFS, PROOF_CHECKS, ContractViolation, DurableStore, BrokerProbe, Dispatcher, evaluate_all


class SourceEvidenceTests(unittest.TestCase):
    def test_all_candidates_prove_all_contract_obligations(self):
        result = evaluate_all()
        self.assertEqual(set(result["candidate_results"]), set(CANDIDATES))
        for candidate in CANDIDATES:
            self.assertEqual(result["candidate_results"][candidate], "eligible_for_evidence_execution")
            self.assertEqual(set(result["proof_results"][candidate]), set(PROOFS))
            self.assertTrue(all(result["proof_results"][candidate].values()))

    def test_proof_map_is_total_and_nonempty(self):
        self.assertEqual(set(PROOF_CHECKS), set(PROOFS))
        self.assertTrue(all(PROOF_CHECKS[p] for p in PROOFS))

    def test_business_mutation_cannot_commit_without_outbox_fact(self):
        store = DurableStore()
        store.commit_business_and_outbox(business_value="v1", message_id="m1", semantic_content="{}", fail_before_commit=True)
        self.assertEqual(store.business_revision, 0)
        self.assertEqual(dict(store.outbox), {})

    def test_stale_claim_cannot_dispatch_after_noncooperative_expiry_takeover(self):
        store, broker = DurableStore(), BrokerProbe()
        store.commit_business_and_outbox(business_value="v1", message_id="m1", semantic_content="{}")
        a = store.claim("m1", "a", now=0, lease=2)
        with self.assertRaisesRegex(ContractViolation, "claim_already_owned"):
            store.claim("m1", "b", now=1, lease=2)
        b = store.claim("m1", "b", now=2, lease=2)
        self.assertGreater(b.fence, a.fence)
        with self.assertRaisesRegex(ContractViolation, "stale_claim"):
            Dispatcher(store, broker, candidate=CANDIDATES[0], owner="a").dispatch(a)

    def test_immutable_fact_rewrite_is_rejected(self):
        store = DurableStore()
        store.commit_business_and_outbox(business_value="v1", message_id="m1", semantic_content='{"a":1}')
        before = store.outbox["m1"]
        with self.assertRaisesRegex(ContractViolation, "immutable_fact_rewrite"):
            store._replace_fact("m1", replace(before, semantic_content='{"a":2}'))
        self.assertEqual(store.outbox["m1"].semantic_content, before.semantic_content)
        self.assertEqual(store.outbox["m1"].content_digest, before.content_digest)

    def test_ack_ambiguity_does_not_change_identity_or_grant_terminal_authority(self):
        store, broker = DurableStore(), BrokerProbe()
        store.commit_business_and_outbox(business_value="v1", message_id="m1", semantic_content='{"a":1}')
        token = store.claim("m1", "a", now=0, lease=2)
        d = Dispatcher(store, broker, candidate=CANDIDATES[1], owner="a")
        broker.accept_then_lose_ack_once = True
        ambiguous = d.dispatch(token)
        self.assertEqual(ambiguous.status, "ambiguous_ack_lost")
        with self.assertRaisesRegex(ContractViolation, "delivery_not_terminal"):
            store.mark_terminal_delivery(token, ambiguous)
        acked = d.dispatch(token)
        self.assertEqual(acked.status, "acked")
        self.assertEqual(broker.attempts[-2], broker.attempts[-1])
        store.mark_terminal_delivery(token, acked)
        self.assertTrue(store.outbox["m1"].terminal_delivery_evidence)

    def test_unavailable_publish_cannot_grant_terminal_authority(self):
        store, broker = DurableStore(), BrokerProbe()
        store.commit_business_and_outbox(business_value="v1", message_id="m1", semantic_content="{}")
        token = store.claim("m1", "a", now=0, lease=2)
        broker.available = False
        receipt = Dispatcher(store, broker, candidate=CANDIDATES[0], owner="a").dispatch(token)
        self.assertEqual(receipt.status, "unavailable")
        with self.assertRaisesRegex(ContractViolation, "delivery_not_terminal"):
            store.mark_terminal_delivery(token, receipt)
        self.assertFalse(store.outbox["m1"].terminal_delivery_evidence)

    def test_cleanup_requires_terminal_evidence_and_safe_horizon(self):
        store, broker = DurableStore(), BrokerProbe()
        store.commit_business_and_outbox(business_value="v1", message_id="m1", semantic_content="{}")
        token = store.claim("m1", "a", now=0, lease=2)
        with self.assertRaisesRegex(ContractViolation, "delivery_uncertain"):
            store.cleanup("m1")
        acked = Dispatcher(store, broker, candidate=CANDIDATES[0], owner="a").dispatch(token)
        store.mark_terminal_delivery(token, acked)
        with self.assertRaisesRegex(ContractViolation, "safe_horizon_not_reached"):
            store.cleanup("m1")
        store.set_safe_horizon("m1")
        store.cleanup("m1")
        self.assertNotIn("m1", store.outbox)

    def test_notification_is_not_recovery_authority(self):
        store, broker = DurableStore(), BrokerProbe()
        store.commit_business_and_outbox(business_value="v1", message_id="m1", semantic_content="{}")
        d = Dispatcher(store, broker, candidate="notification_assisted_polling_claim_profile", owner="a")
        self.assertEqual(d.notifications, [])
        token = store.claim("m1", "a", now=0, lease=2)
        self.assertEqual(d.dispatch(token).status, "acked")


if __name__ == "__main__":
    unittest.main(verbosity=2)
