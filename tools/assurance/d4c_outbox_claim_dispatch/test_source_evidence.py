#!/usr/bin/env python3
from __future__ import annotations

import threading
import time
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
    OutboxFact,
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
        self.assertEqual(sum(len(names) for names in PROOF_CHECKS.values()), 32)

    def test_business_mutation_cannot_commit_without_outbox_fact(self):
        store = DurableStore()
        store.commit_business_and_outbox(
            business_value="v1", message_id="m1", semantic_content="{}", fail_before_commit=True
        )
        self.assertEqual(store.business_revision, 0)
        self.assertEqual(dict(store.outbox), {})

    def test_business_snapshot_isolated_and_mutable_keys_rejected(self):
        store = DurableStore()
        value = {"rev": 1, "nested": {"status": "committed"}}
        store.commit_business_and_outbox(business_value=value, message_id="m1", semantic_content="{}")
        value["rev"] = 2
        value["nested"]["status"] = "mutated"
        self.assertEqual(store.business_value["rev"], 1)
        self.assertEqual(store.business_value["nested"]["status"], "committed")
        with self.assertRaises(TypeError):
            store.business_value["rev"] = 3

        class MutableKey:
            def __init__(self): self.value = "before"
            def __hash__(self): return 7

        key = MutableKey()
        key_store = DurableStore()
        with self.assertRaisesRegex(ContractViolation, "unsupported_mutable_business_key"):
            key_store.commit_business_and_outbox(
                business_value={key: "value"}, message_id="key-msg", semantic_content="{}"
            )
        key.value = "after"
        self.assertEqual(key_store.business_revision, 0)
        self.assertNotIn("key-msg", key_store.outbox)

    def test_broker_acceptance_is_atomic_and_conflict_fails_closed(self):
        broker = BrokerProbe()
        broker.accept_pause_after_lookup = True
        semantic = '{"a":1}'
        fact = OutboxFact("m1", semantic, DurableStore._digest(semantic), 1)
        barrier = threading.Barrier(8)
        failures = []

        def publish():
            try:
                barrier.wait()
                broker.publish(fact, authorize_accept=lambda: None)
            except Exception as exc:
                failures.append(exc)

        threads = [threading.Thread(target=publish) for _ in range(8)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(failures, [])
        self.assertEqual(len(broker.attempts), 8)
        self.assertEqual(broker.accepted, [("m1", DurableStore._digest(semantic))])

        conflict = OutboxFact("m1", '{"a":2}', DurableStore._digest('{"a":2}'), 1)
        with self.assertRaisesRegex(ContractViolation, "broker_message_identity_conflict"):
            broker.publish(conflict, authorize_accept=lambda: None)
        self.assertEqual(len(broker.accepted), 1)

    def test_inflight_worker_is_fenced_before_broker_accept_after_takeover(self):
        store, broker = DurableStore(), BrokerProbe()
        store.commit_business_and_outbox(business_value="v1", message_id="m1", semantic_content="{}")
        token_a = store.claim("m1", "a", now=0, lease=2)
        dispatcher_a = Dispatcher(store, broker, candidate=CANDIDATES[0], owner="a")
        token_b = []

        def takeover(): token_b.append(store.claim("m1", "b", now=2, lease=2))

        with self.assertRaisesRegex(ContractViolation, "stale_claim"):
            dispatcher_a.dispatch(token_a, now=1, accept_now=2, before_accept=takeover)
        self.assertEqual(broker.accepted, [])
        self.assertGreater(token_b[0].fence, token_a.fence)

    def test_post_authorize_takeover_deduplicates_at_atomic_broker_boundary(self):
        store, broker = DurableStore(), BrokerProbe()
        store.commit_business_and_outbox(business_value="v1", message_id="m1", semantic_content="{}")
        token_a = store.claim("m1", "a", now=0, lease=2)
        dispatcher_a = Dispatcher(store, broker, candidate=CANDIDATES[0], owner="a")

        def takeover_and_publish():
            token_b = store.claim("m1", "b", now=2, lease=2)
            Dispatcher(store, broker, candidate=CANDIDATES[0], owner="b").dispatch(token_b, now=2)

        receipt = dispatcher_a.dispatch(token_a, now=1, accept_now=1, after_authorize=takeover_and_publish)
        self.assertEqual(receipt.status, "acked")
        self.assertEqual(len(broker.attempts), 2)
        self.assertEqual(len(broker.accepted), 1)

    def test_terminal_write_serializes_claim_check_and_commit(self):
        store, broker = DurableStore(), BrokerProbe()
        store.commit_business_and_outbox(business_value="v1", message_id="m1", semantic_content="{}")
        token_a = store.claim("m1", "a", now=0, lease=2)
        acked = Dispatcher(store, broker, candidate=CANDIDATES[0], owner="a").dispatch(token_a, now=1)
        store.terminal_pause_after_read = True
        failures = []

        def mark():
            try: store.mark_terminal_delivery(token_a, acked, now=1)
            except Exception as exc: failures.append(exc)

        writer = threading.Thread(target=mark)
        writer.start()
        time.sleep(0.002)
        token_b = store.claim("m1", "b", now=2, lease=2)
        writer.join()
        self.assertEqual(failures, [])
        current = store.outbox["m1"]
        self.assertEqual(current.claim_owner, "b")
        self.assertEqual(current.claim_fence, token_b.fence)
        self.assertTrue(current.terminal_delivery_evidence)

    def test_expired_and_superseded_claims_cannot_mark_terminal(self):
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

    def test_terminal_takeover_before_cas_is_rejected(self):
        store, broker = DurableStore(), BrokerProbe()
        store.commit_business_and_outbox(business_value="v1", message_id="m1", semantic_content="{}")
        token_a = store.claim("m1", "a", now=0, lease=2)
        acked = Dispatcher(store, broker, candidate=CANDIDATES[0], owner="a").dispatch(token_a, now=1)
        token_b = []
        def takeover(): token_b.append(store.claim("m1", "b", now=2, lease=2))
        with self.assertRaisesRegex(ContractViolation, "stale_claim"):
            store.mark_terminal_delivery(token_a, acked, now=1, commit_now=2, before_commit=takeover)
        current = store.outbox["m1"]
        self.assertEqual(current.claim_owner, "b")
        self.assertFalse(current.terminal_delivery_evidence)

    def test_coherent_immutable_fact_rewrite_is_rejected(self):
        store = DurableStore()
        store.commit_business_and_outbox(business_value="v1", message_id="m1", semantic_content='{"a":1}')
        before = store.outbox["m1"]
        rewritten = '{"a":2}'
        coherent = replace(before, semantic_content=rewritten, content_digest=DurableStore._digest(rewritten))
        with self.assertRaisesRegex(ContractViolation, "immutable_fact_rewrite"):
            store._replace_fact("m1", coherent)
        self.assertEqual(store.outbox["m1"].semantic_content, before.semantic_content)

    def test_ack_ambiguity_and_foreign_receipts_cannot_grant_terminal(self):
        store, broker = DurableStore(), BrokerProbe()
        store.commit_business_and_outbox(business_value="v1", message_id="m1", semantic_content='{"a":1}')
        token = store.claim("m1", "a", now=0, lease=5)
        d = Dispatcher(store, broker, candidate=CANDIDATES[1], owner="a")
        broker.accept_then_lose_ack_once = True
        ambiguous = d.dispatch(token, now=1)
        with self.assertRaisesRegex(ContractViolation, "delivery_not_terminal"):
            store.mark_terminal_delivery(token, ambiguous, now=1)
        acked = d.dispatch(token, now=2)
        self.assertEqual(len(broker.accepted), 1)
        with self.assertRaisesRegex(ContractViolation, "delivery_receipt_mismatch"):
            store.mark_terminal_delivery(token, PublishReceipt("acked", "other", acked.content_digest), now=2)
        with self.assertRaisesRegex(ContractViolation, "delivery_receipt_mismatch"):
            store.mark_terminal_delivery(token, PublishReceipt("acked", "m1", DurableStore._digest("different")), now=2)

    def test_unavailable_publish_cannot_grant_terminal_authority(self):
        store, broker = DurableStore(), BrokerProbe()
        store.commit_business_and_outbox(business_value="v1", message_id="m1", semantic_content="{}")
        token = store.claim("m1", "a", now=0, lease=3)
        broker.available = False
        receipt = Dispatcher(store, broker, candidate=CANDIDATES[0], owner="a").dispatch(token, now=1)
        with self.assertRaisesRegex(ContractViolation, "delivery_not_terminal"):
            store.mark_terminal_delivery(token, receipt, now=1)

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
        token = store.claim("m1", "a", now=0, lease=3)
        self.assertEqual(d.notifications, [])
        self.assertEqual(d.dispatch(token, now=1).status, "acked")


if __name__ == "__main__":
    unittest.main(verbosity=2)
