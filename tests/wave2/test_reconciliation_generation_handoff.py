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


class ReconciliationGenerationHandoffTests(unittest.TestCase):
    def test_absence_evidence_remains_history_but_not_successor_attempt_state(self) -> None:
        identity = ScopedMessageIdentity(
            consumer_contract="monitoring.observation.consume",
            message_identity_scope="producer-scope-a",
            message_id="message-1",
            tenant_id="tenant-a",
        )
        evidence = ComparisonEvidence(
            comparison_profile_id="cmp.message-v1",
            comparison_profile_version="v1",
            evidence_form="opaque-protected",
            evidence=b"same",
        )
        result = EffectResultLink("revision-2", "resource_revision")
        authority = CurrentExecutionAuthority()
        inbox = InMemoryInboxLedger()
        operations = InMemoryCrossAuthorityOperationLedger()

        operations.prepare("op-1", identity.consumer_contract, tenant_id="tenant-a")
        inbox.admit(identity, evidence)
        first_claim = inbox.claim_effect(
            identity,
            "worker-a",
            execution_authority=authority,
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
            "effect-executor-a",
            execution_authority=authority,
            attempt_expires_at=LEASE_END,
        )
        operations.mark_ambiguous(
            first_attempt,
            "provider_response_lost",
            observed_at=NOW + timedelta(seconds=2),
        )
        inbox.require_reconciliation(
            first_claim,
            "provider_response_lost",
            observed_at=NOW + timedelta(seconds=2),
        )
        operations.reconcile(
            "op-1",
            ReconciliationResolution.EFFECT_PROVEN_ABSENT,
            reconciliation_revision="absent-attempt-1",
        )
        inbox.reconcile_retry_eligible(identity, operations)

        historical = operations.reconciliation_evidence("op-1", "absent-attempt-1")
        self.assertIsNotNone(historical)
        self.assertEqual(
            operations.reconciliation_resolution("op-1"),
            ReconciliationResolution.EFFECT_PROVEN_ABSENT,
        )

        second_claim = inbox.claim_effect(
            identity,
            "worker-b",
            execution_authority=authority,
            claim_expires_at=LEASE_END,
        )
        second_attempt = operations.begin_attempt(
            "op-1",
            "effect-executor-b",
            execution_authority=authority,
            attempt_expires_at=LEASE_END,
        )

        self.assertIsNone(operations.reconciliation_revision("op-1"))
        self.assertIsNone(operations.reconciliation_resolution("op-1"))
        self.assertEqual(
            operations.reconciliation_evidence("op-1", "absent-attempt-1"),
            historical,
        )
        self.assertEqual(second_attempt.attempt_generation, 2)

        operations.complete(
            second_attempt,
            result,
            observed_at=NOW + timedelta(seconds=3),
        )
        inbox.complete_cross_authority_effect(
            second_claim,
            result,
            operation_authority=operations,
            observed_at=NOW + timedelta(seconds=4),
        )

        self.assertEqual(inbox.state(identity), InboxState.COMPLETED)
        self.assertEqual(inbox.result_link(identity), result)


if __name__ == "__main__":
    unittest.main()
