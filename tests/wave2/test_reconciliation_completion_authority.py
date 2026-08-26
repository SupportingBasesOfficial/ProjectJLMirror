from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from jlmirror_authority import EnvironmentClass, PrincipalKind, TenantContext
from jlmirror_async import (
    AsyncExecutionAdmission,
    AsyncExecutionRequest,
    ComparisonEvidence,
    EffectResultLink,
    InboxState,
    InMemoryCrossAuthorityOperationLedger,
    InMemoryInboxLedger,
    InvalidTransition,
    ReconciliationBlocked,
    ReconciliationResolution,
    ScopedMessageIdentity,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
LEASE_END = NOW + timedelta(seconds=30)


def identity() -> ScopedMessageIdentity:
    return ScopedMessageIdentity(
        consumer_contract="monitoring.observation.consume",
        message_identity_scope="producer-scope-a",
        message_id="message-1",
        tenant_id="tenant-a",
    )


def evidence() -> ComparisonEvidence:
    return ComparisonEvidence(
        comparison_profile_id="cmp.message-v1",
        comparison_profile_version="v1",
        evidence_form="opaque-protected",
        evidence=b"same",
    )


def tenant_context() -> TenantContext:
    return TenantContext(
        tenant_id="tenant-a",
        principal_id="service-worker-a",
        principal_kind=PrincipalKind.INTERNAL_SERVICE_PRINCIPAL,
        principal_credential_generation="cred-7",
        cell_id="cell-a",
        placement_version="placement-11",
        runtime_generation="runtime-4",
        runtime_profile_id="runtime.worker@1",
        runtime_isolation_class="isolation.workload-bulkhead@1",
        configuration_generation="config-8",
        workload_credential_generation="workload-cred-7",
        network_policy_generation="network-5",
        environment_class=EnvironmentClass.PRODUCTION,
        isolation_class="pooled",
        fence_scope_id="tenant-a-worker",
        fence_epoch=9,
        constructed_at=NOW,
        correlation_id="corr-1",
    )


class CurrentExecutionAuthority:
    def finalize_current_execution(self, *, request: AsyncExecutionRequest) -> AsyncExecutionAdmission:
        return AsyncExecutionAdmission(
            request=request,
            principal_id="service-worker-a",
            principal_credential_generation="cred-7",
            authorization_revision="authz-19",
            admission_revision="admission-20",
            runtime_generation="runtime-4",
            environment_class=EnvironmentClass.PRODUCTION,
            observed_at=NOW,
            current=True,
            tenant_context=tenant_context() if request.tenant_id else None,
        )


class ReconciliationCompletionAuthorityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.identity = identity()
        self.result = EffectResultLink("revision-7", "resource_revision")
        self.execution_authority = CurrentExecutionAuthority()

    def blocked_local_receipt(self) -> InMemoryInboxLedger:
        ledger = InMemoryInboxLedger()
        ledger.admit(self.identity, evidence())
        claim = ledger.claim_effect(
            self.identity,
            "worker-a",
            execution_authority=self.execution_authority,
            claim_expires_at=LEASE_END,
        )
        ledger.require_reconciliation(
            claim,
            "local_effect_outcome_uncertain",
            observed_at=NOW + timedelta(seconds=1),
        )
        return ledger

    def operation_bound_receipt(self):
        ledger = InMemoryInboxLedger()
        operations = InMemoryCrossAuthorityOperationLedger()
        operations.prepare("op-1", self.identity.consumer_contract, tenant_id="tenant-a")
        ledger.admit(self.identity, evidence())
        claim = ledger.claim_effect(
            self.identity,
            "worker-a",
            execution_authority=self.execution_authority,
            claim_expires_at=LEASE_END,
        )
        ledger.bind_cross_authority_operation(
            claim,
            "op-1",
            observed_at=NOW + timedelta(seconds=1),
        )
        return ledger, operations, claim

    def test_operation_bound_receipt_cannot_use_local_completion(self) -> None:
        ledger, _operations, claim = self.operation_bound_receipt()

        with self.assertRaises(InvalidTransition):
            ledger.complete_local_effect(
                claim,
                self.result,
                observed_at=NOW + timedelta(seconds=2),
            )

        self.assertEqual(ledger.state(self.identity), InboxState.PROCESSING)
        self.assertIsNone(ledger.result_link(self.identity))

    def test_direct_cross_authority_completion_requires_exact_durable_outcome(self) -> None:
        ledger, operations, claim = self.operation_bound_receipt()
        attempt = operations.begin_attempt(
            "op-1",
            "effect-executor-a",
            execution_authority=self.execution_authority,
            attempt_expires_at=LEASE_END,
        )
        operations.complete(
            attempt,
            self.result,
            observed_at=NOW + timedelta(seconds=2),
        )

        ledger.complete_cross_authority_effect(
            claim,
            self.result,
            operation_authority=operations,
            observed_at=NOW + timedelta(seconds=3),
        )

        self.assertEqual(ledger.state(self.identity), InboxState.COMPLETED)
        self.assertEqual(ledger.result_link(self.identity), self.result)

    def test_direct_cross_authority_completion_rejects_mismatched_outcome(self) -> None:
        ledger, operations, claim = self.operation_bound_receipt()
        attempt = operations.begin_attempt(
            "op-1",
            "effect-executor-a",
            execution_authority=self.execution_authority,
            attempt_expires_at=LEASE_END,
        )
        operations.complete(
            attempt,
            self.result,
            observed_at=NOW + timedelta(seconds=2),
        )

        with self.assertRaises(ReconciliationBlocked):
            ledger.complete_cross_authority_effect(
                claim,
                EffectResultLink("revision-8", "resource_revision"),
                operation_authority=operations,
                observed_at=NOW + timedelta(seconds=3),
            )

        self.assertEqual(ledger.state(self.identity), InboxState.PROCESSING)

    def test_reconciled_operation_cannot_use_direct_processing_completion_path(self) -> None:
        ledger, operations, claim = self.operation_bound_receipt()
        attempt = operations.begin_attempt(
            "op-1",
            "effect-executor-a",
            execution_authority=self.execution_authority,
            attempt_expires_at=LEASE_END,
        )
        operations.mark_ambiguous(
            attempt,
            "provider_response_lost",
            observed_at=NOW + timedelta(seconds=2),
        )
        operations.reconcile(
            "op-1",
            ReconciliationResolution.EFFECT_CONFIRMED,
            reconciliation_revision="reconcile-1",
            confirmed_outcome=self.result,
        )

        with self.assertRaises(ReconciliationBlocked):
            ledger.complete_cross_authority_effect(
                claim,
                self.result,
                operation_authority=operations,
                observed_at=NOW + timedelta(seconds=3),
            )

        self.assertEqual(ledger.state(self.identity), InboxState.PROCESSING)

    def test_caller_result_link_cannot_complete_unbound_reconciliation(self) -> None:
        ledger = self.blocked_local_receipt()

        with self.assertRaises(ReconciliationBlocked):
            ledger.reconcile_completed(self.identity, self.result)

        self.assertEqual(ledger.state(self.identity), InboxState.RECONCILIATION_REQUIRED)
        self.assertIsNone(ledger.result_link(self.identity))

    def test_bound_operation_without_operation_authority_remains_blocked(self) -> None:
        ledger, _operations, claim = self.operation_bound_receipt()
        ledger.require_reconciliation(
            claim,
            "external_effect_outcome_uncertain",
            observed_at=NOW + timedelta(seconds=2),
        )

        with self.assertRaises(ReconciliationBlocked):
            ledger.reconcile_completed(self.identity, self.result)

        self.assertEqual(ledger.state(self.identity), InboxState.RECONCILIATION_REQUIRED)

    def test_append_only_confirmed_operation_evidence_allows_exact_completion(self) -> None:
        ledger, operations, claim = self.operation_bound_receipt()
        attempt = operations.begin_attempt(
            "op-1",
            "effect-executor-a",
            execution_authority=self.execution_authority,
            attempt_expires_at=LEASE_END,
        )
        operations.mark_ambiguous(
            attempt,
            "provider_response_lost",
            observed_at=NOW + timedelta(seconds=2),
        )
        ledger.require_reconciliation(
            claim,
            "provider_response_lost",
            observed_at=NOW + timedelta(seconds=2),
        )
        operations.reconcile(
            "op-1",
            ReconciliationResolution.EFFECT_CONFIRMED,
            reconciliation_revision="reconcile-1",
            confirmed_outcome=self.result,
        )

        ledger.reconcile_completed(
            self.identity,
            self.result,
            operation_authority=operations,
        )

        self.assertEqual(ledger.state(self.identity), InboxState.COMPLETED)
        self.assertEqual(ledger.result_link(self.identity), self.result)

    def test_confirmed_operation_with_mismatched_result_remains_blocked(self) -> None:
        ledger, operations, claim = self.operation_bound_receipt()
        attempt = operations.begin_attempt(
            "op-1",
            "effect-executor-a",
            execution_authority=self.execution_authority,
            attempt_expires_at=LEASE_END,
        )
        operations.mark_ambiguous(
            attempt,
            "provider_response_lost",
            observed_at=NOW + timedelta(seconds=2),
        )
        ledger.require_reconciliation(
            claim,
            "provider_response_lost",
            observed_at=NOW + timedelta(seconds=2),
        )
        operations.reconcile(
            "op-1",
            ReconciliationResolution.EFFECT_CONFIRMED,
            reconciliation_revision="reconcile-1",
            confirmed_outcome=self.result,
        )

        with self.assertRaises(ReconciliationBlocked):
            ledger.reconcile_completed(
                self.identity,
                EffectResultLink("revision-8", "resource_revision"),
                operation_authority=operations,
            )

        self.assertEqual(ledger.state(self.identity), InboxState.RECONCILIATION_REQUIRED)


if __name__ == "__main__":
    unittest.main()
