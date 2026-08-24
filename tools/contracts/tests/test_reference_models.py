from concurrent.futures import ThreadPoolExecutor
import unittest

from tools.contracts.reference_models import (
    FenceReference,
    IdempotencyDecision,
    IdempotencyReference,
    RecoveryReference,
    ambiguous_external_effect_disposition,
    tenant_effect_allowed,
)


class ReferenceModelTests(unittest.TestCase):
    def test_tenant_authority_requires_current_matching_derived_tenant(self):
        self.assertTrue(
            tenant_effect_allowed(
                derived_tenant="t1", requested_tenant="t1", current_authority=True
            )
        )
        self.assertFalse(
            tenant_effect_allowed(
                derived_tenant="t1", requested_tenant="t2", current_authority=True
            )
        )
        self.assertFalse(
            tenant_effect_allowed(
                derived_tenant="t1", requested_tenant="t1", current_authority=False
            )
        )

    def test_idempotency_create_or_observe(self):
        store = IdempotencyReference()
        self.assertEqual(store.begin("tenant:t1", "k1", "fp1"), IdempotencyDecision.EXECUTE)
        self.assertEqual(
            store.begin("tenant:t1", "k1", "fp1"),
            IdempotencyDecision.OBSERVE_IN_PROGRESS,
        )
        self.assertEqual(
            store.begin("tenant:t1", "k1", "different"), IdempotencyDecision.CONFLICT
        )
        store.complete("tenant:t1", "k1", "ok")
        self.assertEqual(
            store.begin("tenant:t1", "k1", "fp1"), IdempotencyDecision.REPLAY_COMPLETED
        )

    def test_idempotency_concurrent_start_has_one_executor(self):
        store = IdempotencyReference()
        with ThreadPoolExecutor(max_workers=16) as pool:
            results = list(
                pool.map(
                    lambda _: store.begin("tenant:t1", "race", "fp"),
                    range(64),
                )
            )
        self.assertEqual(results.count(IdempotencyDecision.EXECUTE), 1)
        self.assertEqual(
            results.count(IdempotencyDecision.OBSERVE_IN_PROGRESS), 63
        )

    def test_idempotency_scope_is_part_of_identity(self):
        store = IdempotencyReference()
        self.assertEqual(store.begin("tenant:t1", "same", "fp"), IdempotencyDecision.EXECUTE)
        self.assertEqual(store.begin("tenant:t2", "same", "fp"), IdempotencyDecision.EXECUTE)

    def test_ambiguity_requires_reconciliation_when_absence_not_proven(self):
        self.assertEqual(
            ambiguous_external_effect_disposition(False, False),
            "reconciliation_required",
        )
        self.assertEqual(
            ambiguous_external_effect_disposition(True, False),
            "safe_new_attempt_subject_to_current_authority",
        )
        self.assertEqual(
            ambiguous_external_effect_disposition(False, True),
            "observe_completed_effect",
        )

    def test_fence_has_single_current_epoch(self):
        fence = FenceReference(current_epoch=7)
        successor = fence.acquire_successor(7)
        self.assertEqual(successor, 8)
        self.assertFalse(fence.effect_allowed(7))
        self.assertTrue(fence.effect_allowed(8))
        with self.assertRaises(ValueError):
            fence.acquire_successor(7)

    def test_fence_concurrent_acquisition_has_one_successor(self):
        fence = FenceReference(current_epoch=7)

        def attempt(_: int) -> int | None:
            try:
                return fence.acquire_successor(7)
            except ValueError:
                return None

        with ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(attempt, range(64)))
        self.assertEqual(results.count(8), 1)
        self.assertEqual(results.count(None), 63)
        self.assertEqual(fence.current_epoch, 8)

    def test_restore_cannot_move_fence_backwards(self):
        fence = FenceReference(current_epoch=9)
        self.assertEqual(fence.restore(4), "quarantine_and_fence_forward")
        self.assertEqual(fence.current_epoch, 9)

    def test_recovery_requires_RF_reconciliation_and_current_authority(self):
        gate = RecoveryReference(
            restore_marker=10, fence_marker=14, unresolved_sequences={11, 14}
        )
        self.assertFalse(gate.admission_allowed())
        gate.reconcile(11)
        gate.reconcile(14)
        self.assertFalse(gate.admission_allowed())
        gate.current_authorities_proven = True
        self.assertTrue(gate.admission_allowed())

    def test_recovery_rejects_obligation_outside_uncertainty_interval(self):
        with self.assertRaises(ValueError):
            RecoveryReference(
                restore_marker=10, fence_marker=14, unresolved_sequences={10, 15}
            )


if __name__ == "__main__":
    unittest.main()
