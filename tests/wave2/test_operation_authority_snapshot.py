from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from jlmirror_authority import EnvironmentClass, PrincipalKind, TenantContext
from jlmirror_async import (
    AsyncExecutionAdmission,
    AsyncExecutionRequest,
    ComparisonEvidence,
    CrossAuthorityOperationSnapshot,
    EffectResultLink,
    InboxState,
    InMemoryInboxLedger,
    OperationState,
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
    def finalize_current_execution(self, *, request: AsyncExecutionRequest) -> AsyncExecutionAdmission:
        return AsyncExecutionAdmission(
            request=request,
            principal_id="service-worker-a",
            principal_credential_generation="cred-7",
            authorization_revision="authz-1",
            admission_revision="admission-1",
            runtime_generation="runtime-4",
            environment_class=EnvironmentClass.PRODUCTION,
            observed_at=NOW,
            current=True,
            tenant_context=context() if request.tenant_id else None,
        )


class SnapshotOnlyAuthority:
    def __init__(self, snapshot: CrossAuthorityOperationSnapshot) -> None:
        self.value = snapshot
        self.calls = 0

    def snapshot(self, operation_id: str) -> CrossAuthorityOperationSnapshot:
        self.calls += 1
        if operation_id != self.value.operation_id:
            raise AssertionError("wrong operation requested")
        return self.value

    def state(self, _operation_id: str):  # pragma: no cover - must never be called
        raise AssertionError("split state read is prohibited")

    def outcome(self, _operation_id: str):  # pragma: no cover - must never be called
        raise AssertionError("split outcome read is prohibited")

    def reconciliation_resolution(self, _operation_id: str):  # pragma: no cover
        raise AssertionError("split reconciliation read is prohibited")

    def reconciliation_revision(self, _operation_id: str):  # pragma: no cover
        raise AssertionError("split revision read is prohibited")


class OperationAuthoritySnapshotTests(unittest.TestCase):
    def test_snapshot_rejects_impossible_mixed_authority_tuple(self) -> None:
        with self.assertRaises(ValueError):
            CrossAuthorityOperationSnapshot(
                operation_id="op-1",
                state=OperationState.PREPARED,
                attempt_generation=1,
                reconciliation_resolution=ReconciliationResolution.EFFECT_CONFIRMED,
                reconciliation_revision="rev-1",
                reconciliation_attempt_generation=1,
                outcome=EffectResultLink("result-1", "provider_outcome"),
            )

    def test_snapshot_rejects_reconciliation_evidence_from_another_attempt(self) -> None:
        with self.assertRaises(ValueError):
            CrossAuthorityOperationSnapshot(
                operation_id="op-1",
                state=OperationState.PREPARED,
                attempt_generation=2,
                reconciliation_resolution=ReconciliationResolution.EFFECT_PROVEN_ABSENT,
                reconciliation_revision="rev-attempt-1",
                reconciliation_attempt_generation=1,
            )

    def test_snapshot_requires_generation_with_reconciliation_revision(self) -> None:
        with self.assertRaises(ValueError):
            CrossAuthorityOperationSnapshot(
                operation_id="op-1",
                state=OperationState.PREPARED,
                attempt_generation=1,
                reconciliation_resolution=ReconciliationResolution.EFFECT_PROVEN_ABSENT,
                reconciliation_revision="rev-1",
            )

    def test_direct_completion_consumes_scoped_snapshots_and_no_split_reads(self) -> None:
        identity = ScopedMessageIdentity(
            consumer_contract="monitoring.observation.consume",
            message_identity_scope="producer-scope-a",
            message_id="message-1",
            tenant_id="tenant-a",
        )
        ledger = InMemoryInboxLedger()
        ledger.admit(
            identity,
            ComparisonEvidence(
                comparison_profile_id="cmp.message-v1",
                comparison_profile_version="v1",
                evidence_form="opaque-protected",
                evidence=b"same",
            ),
        )
        claim = ledger.claim_effect(
            identity,
            "worker-a",
            execution_authority=CurrentExecutionAuthority(),
            claim_expires_at=LEASE_END,
        )
        binding_authority = SnapshotOnlyAuthority(
            CrossAuthorityOperationSnapshot(
                operation_id="op-1",
                state=OperationState.PREPARED,
                attempt_generation=0,
                owner_contract=identity.consumer_contract,
                tenant_id=identity.tenant_id,
            )
        )
        ledger.bind_cross_authority_operation(
            claim,
            "op-1",
            operation_authority=binding_authority,
            observed_at=NOW + timedelta(seconds=1),
        )
        result = EffectResultLink("result-1", "provider_outcome")
        authority = SnapshotOnlyAuthority(
            CrossAuthorityOperationSnapshot(
                operation_id="op-1",
                state=OperationState.COMPLETED,
                attempt_generation=1,
                owner_contract=identity.consumer_contract,
                tenant_id=identity.tenant_id,
                outcome=result,
            )
        )

        ledger.complete_cross_authority_effect(
            claim,
            result,
            operation_authority=authority,
            observed_at=NOW + timedelta(seconds=2),
        )

        self.assertEqual(binding_authority.calls, 1)
        self.assertEqual(authority.calls, 1)
        self.assertEqual(ledger.state(identity), InboxState.COMPLETED)


if __name__ == "__main__":
    unittest.main()
