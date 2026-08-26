from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from jlmirror_authority import EnvironmentClass, PrincipalKind, TenantContext
from jlmirror_async import (
    AsyncExecutionAdmission,
    AsyncExecutionRequest,
    ComparisonEvidence,
    InMemoryCrossAuthorityOperationLedger,
    InMemoryInboxLedger,
    InvalidTransition,
    ReconciliationResolution,
    ScopedMessageIdentity,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
LEASE_END = NOW + timedelta(seconds=30)


def context() -> TenantContext:
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
    def __init__(self) -> None:
        self.count = 0

    def finalize_current_execution(self, *, request: AsyncExecutionRequest) -> AsyncExecutionAdmission:
        self.count += 1
        return AsyncExecutionAdmission(
            request=request,
            principal_id="service-worker-a",
            principal_credential_generation="cred-7",
            authorization_revision=f"authz-{self.count}",
            admission_revision=f"admission-{self.count}",
            runtime_generation="runtime-4",
            environment_class=EnvironmentClass.PRODUCTION,
            observed_at=NOW,
            current=True,
            tenant_context=context() if request.tenant_id else None,
        )


class ReconciliationAttemptBindingTests(unittest.TestCase):
    def test_prior_attempt_absence_revision_cannot_reauthorize_later_ambiguity(self) -> None:
        identity = ScopedMessageIdentity(
            consumer_contract="monitoring.observation.consume",
            message_identity_scope="producer-scope-a",
            message_id="message-1",
            tenant_id="tenant-a",
        )
        comparison = ComparisonEvidence(
            comparison_profile_id="cmp.message-v1",
            comparison_profile_version="v1",
            evidence_form="opaque-protected",
            evidence=b"same",
        )
        execution = CurrentExecutionAuthority()
        operations = InMemoryCrossAuthorityOperationLedger()
        inbox = InMemoryInboxLedger()

        operations.prepare("op-1", identity.consumer_contract, tenant_id="tenant-a")
        inbox.admit(identity, comparison)

        first_claim = inbox.claim_effect(
            identity,
            "worker-a",
            execution_authority=execution,
            claim_expires_at=LEASE_END,
        )
        inbox.bind_cross_authority_operation(
            first_claim,
            "op-1",
            operation_authority=operations,
            observed_at=NOW + timedelta(seconds=1),
        )
        first_attempt = operations.begin_attempt(
            "op-1",
            "effect-a",
            execution_authority=execution,
            attempt_expires_at=LEASE_END,
        )
        operations.mark_ambiguous(
            first_attempt,
            "response_lost_attempt_1",
            observed_at=NOW + timedelta(seconds=2),
        )
        inbox.require_reconciliation(
            first_claim,
            "response_lost_attempt_1",
            observed_at=NOW + timedelta(seconds=2),
        )
        operations.reconcile(
            "op-1",
            ReconciliationResolution.EFFECT_PROVEN_ABSENT,
            reconciliation_revision="absence-proof-1",
        )
        first_evidence = operations.reconciliation_evidence("op-1", "absence-proof-1")
        self.assertIsNotNone(first_evidence)
        self.assertEqual(first_evidence.attempt_generation, 1)
        inbox.reconcile_retry_eligible(identity, operations)

        second_claim = inbox.claim_effect(
            identity,
            "worker-b",
            execution_authority=execution,
            claim_expires_at=LEASE_END,
        )
        second_attempt = operations.begin_attempt(
            "op-1",
            "effect-b",
            execution_authority=execution,
            attempt_expires_at=LEASE_END,
        )
        self.assertEqual(second_attempt.attempt_generation, 2)
        operations.mark_ambiguous(
            second_attempt,
            "response_lost_attempt_2",
            observed_at=NOW + timedelta(seconds=3),
        )
        inbox.require_reconciliation(
            second_claim,
            "response_lost_attempt_2",
            observed_at=NOW + timedelta(seconds=3),
        )

        with self.assertRaises(InvalidTransition):
            operations.reconcile(
                "op-1",
                ReconciliationResolution.EFFECT_PROVEN_ABSENT,
                reconciliation_revision="absence-proof-1",
            )

        historical = operations.reconciliation_evidence("op-1", "absence-proof-1")
        self.assertEqual(historical, first_evidence)
        self.assertEqual(historical.attempt_generation, 1)

    def test_each_ambiguous_attempt_can_have_its_own_absence_revision(self) -> None:
        execution = CurrentExecutionAuthority()
        operations = InMemoryCrossAuthorityOperationLedger()
        operations.prepare("op-2", "monitoring.observation.consume", tenant_id="tenant-a")

        first = operations.begin_attempt(
            "op-2",
            "effect-a",
            execution_authority=execution,
            attempt_expires_at=LEASE_END,
        )
        operations.mark_ambiguous(
            first,
            "lost-1",
            observed_at=NOW + timedelta(seconds=1),
        )
        operations.reconcile(
            "op-2",
            ReconciliationResolution.EFFECT_PROVEN_ABSENT,
            reconciliation_revision="proof-1",
        )

        second = operations.begin_attempt(
            "op-2",
            "effect-b",
            execution_authority=execution,
            attempt_expires_at=LEASE_END,
        )
        operations.mark_ambiguous(
            second,
            "lost-2",
            observed_at=NOW + timedelta(seconds=2),
        )
        operations.reconcile(
            "op-2",
            ReconciliationResolution.EFFECT_PROVEN_ABSENT,
            reconciliation_revision="proof-2",
        )

        self.assertEqual(
            operations.reconciliation_evidence("op-2", "proof-1").attempt_generation,
            1,
        )
        self.assertEqual(
            operations.reconciliation_evidence("op-2", "proof-2").attempt_generation,
            2,
        )


if __name__ == "__main__":
    unittest.main()
