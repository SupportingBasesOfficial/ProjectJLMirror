#!/usr/bin/env python3
from __future__ import annotations

import unittest
from dataclasses import replace

from evaluate_candidates import (
    CANDIDATES,
    PROOFS,
    PROOF_CHECKS,
    ContractViolation,
    DurableStore,
    BrokerProbe,
    Dispatcher,
    PublishReceipt,
    evaluate_all,
)


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
        store.commit_business_and_outbox(
            business_value="v1", message_id="m1", semantic_content="{}", fail_before_commit=True
        )
        self.assertEqual(store.business_revision, 0)
        self.assertEqual(dict(store.outbox), {})

    def test_inflight_worker_is_fenced_before_broker_accept_after_takeover(self):
        store, broker = DurableStore(), BrokerProbe()
        store.commit_business_and_outbox(business_value="v1", message_id="m1", semantic_content="{}")
        token_a = store.claim("m1", "a", now=0, lease=2)
        dispatcher_a = Dispatcher(store, broker, candidate=CANDIDATES[0], owner="a")
        token_b: list = []
        def takeover() -> None:
            token_b.append(store.claim("m1", "b", now=2, lease=2))
        with self.assertRaisesRegex(ContractViolation, "stale_claim"):
            dispatcher_a.dispatch(token_a, now=1, accept_now=2, before_accept=takeover)
        self.assertEqual(broker.accepted, [])
        self.assertEqual(len(token_b), 1)
        self.assertGreater(token_b[0].fence, token_a.fence)

    def test_expired_claim_cannot_dispatch_before_takeover(self):
        store, broker = DurableStore(), BrokerProbe()
        store.commit_business_and_outbox(business_value="v1", message_id="m1", semantic_content="{}")
        token = store.claim("m1", "a", now=0, lease=2)
        with self.assertRaisesRegex(ContractViolation, "claim_expired"):
            Dispatcher(store, broker, candidate=CANDIDATES[0], owner="a").dispatch(token, now=2)

    def test_acked_receipt_cannot_mark_terminal_after_expiry_or_takeover(self):
        store, broker = DurableStore(), BrokerProbe()
        store.commit_business_and_outbox(business_value="v1", message_id="m1", semantic_content="{}")
        token_a = store.claim("m1", "a", now=0, lease=2)
        acked = Dispatcher(store, broker, candidate=CANDIDATES[0], owner="a").dispatch(token_a, now=1)
        with self.assertRaisesRegex(ContractViolation, "claim_expired"):
            store.mark_terminal_delivery(token_a, acked, now=2)
        token_b = store.claim("m1", "b", now=2, lease=2)
        self.assertGreater(token_b.fence, token_a.fence)
        with self.assertRaisesRegex(ContractViolation, "stale_claim"):
            store.mark_terminal_delivery(token_a, acked, now=2)
        self.assertFalse(store.outbox["m1"].terminal_delivery_evidence)

    def test_coherent_immutable_fact_rewrite_is_rejected(self):
        store = DurableStore()
        store.commit_business_and_outbox(business_value="v1", message_id="m1", semantic_content='{"a":1}')
        before = store.outbox["m1"]
        rewritten = '{"a":2}'
        coherent = replace(before, semantic_content=rewritten, content_digest=DurableStore._digest(rewritten))
        with self.assertRaisesRegex(ContractViolation, "immutable_fact_rewrite"):
            store._replace_fact("m1", coherent)
        self.assertEqual(store.outbox["m1"].semantic_content, before.semantic_content)
        self.assertEqual(store.outbox["m1"].content_digest, before.content_digest)

    def test_ack_ambiguity_does_not_change_identity_or_grant_terminal_authority(self):
        store, broker = DurableStore(), BrokerProbe()
        store.commit_business_and_outbox(business_value="v1", message_id="m1", semantic_content='{"a":1}')
        token = store.claim("m1", "a", now=0, lease=5)
        d = Dispatcher(store, broker, candidate=CANDIDATES[1], owner="a")
        broker.accept_then_lose_ack_once = True
        ambiguous = d.dispatch(token, now=1)
        self.assertEqual(ambiguous.status, "ambiguous_ack_lost")
        with self.assertRaisesRegex(ContractViolation, "delivery_not_terminal"):
            store.mark_terminal_delivery(token, ambiguous, now=1)
        acked = d.dispatch(token, now=2)
        self.assertEqual(acked.status, "acked")
        self.assertEqual(broker.attempts[-2], broker.attempts[-1])

    def test_foreign_acked_receipts_cannot_grant_terminal_authority(self):
        store, broker = DurableStore(), BrokerProbe()
        store.commit_business_and_outbox(business_value="v1", message_id="m1", semantic_content='{"a":1}')
        token = store.claim("m1", "a", now=0, lease=5)
        acked = Dispatcher(store, broker, candidate=CANDIDATES[0], owner="a").dispatch(token, now=1)
        with self.assertRaisesRegex(ContractViolation, "delivery_receipt_mismatch"):
            store.mark_terminal_delivery(token, PublishReceipt("acked", "other", acked.content_digest), now=1)
        with self.assertRaisesRegex(ContractViolation, "delivery_receipt_mismatch"):
            store.mark_terminal_delivery(token, PublishReceipt("acked", "m1", DurableStore._digest("different")), now=1)
        self.assertFalse(store.outbox["m1"].terminal_delivery_evidence)

    def test_unavailable_publish_cannot_grant_terminal_authority(self):
        store, broker = DurableStore(), BrokerProbe()
        store.commit_business_and_outbox(business_value="v1", message_id="m1", semantic_content="{}")
        token = store.claim("m1", "a", now=0, lease=3)
        broker.available = False
        receipt = Dispatcher(store, broker, candidate=CANDIDATES[0], owner="a").dispatch(token, now=1)
        self.assertEqual(receipt.status, "unavailable")
        with self.assertRaisesRegex(ContractViolation, "delivery_not_terminal"):
            store.mark_terminal_delivery(token, receipt, now=1)
        self.assertFalse(store.outbox["m1"].terminal_delivery_evidence)

    def test_cleanup_requires_terminal_evidence_and_safe_horizon(self):
        store, broker = DurableStore(), BrokerProbe()
        store.commit_business_and_outbox(business_value="v1", message_id="m1", semantic_content="{}")
        token = store.claim("m1", "a", now=0, lease=3)
        with self.assertRaisesRegex(ContractViolation, "delivery_uncertain"):
            store.cleanup("m1")
        acked = Dispatcher(store, broker, candidate=CANDIDATES[0], owner="a").dispatch(token, now=1)
        store.mark_terminal_delivery(token, acked, now=1)
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
        token = store.claim("m1", "a", now=0, lease=3)
        self.assertEqual(d.dispatch(token, now=1).status, "acked")


if __name__ == "__main__":
    unittest.main(verbosity=2)
