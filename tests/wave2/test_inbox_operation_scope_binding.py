from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from jlmirror_authority import EnvironmentClass, PrincipalKind, TenantContext
from jlmirror_async import (
    AsyncExecutionAdmission,
    AsyncExecutionRequest,
    ComparisonEvidence,
    CrossAuthorityOperationSnapshot,
    EffectResultLink,
    InboxState,
    InMemoryCrossAuthorityOperationLedger,
    InMemoryInboxLedger,
    IntegrityConflict,
    OperationState,
    ReconciliationBlocked,
    ScopedMessageIdentity,
)

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
LEASE_END = NOW + timedelta(seconds=30)


def identity(*, tenant_id: str = "tenant-a", consumer_contract: str = "monitoring.observation.consume") -> ScopedMessageIdentity:
    return ScopedMessageIdentity(
        consumer_contract=consumer_contract,
        message_identity_scope="shared-source",
        message_id="message-1",
        tenant_id=tenant_id,
    )


def evidence() -> ComparisonEvidence:
    return ComparisonEvidence(
        comparison_profile_id="cmp.message-v1",
        comparison_profile_version="v1",
        evidence_form="opaque-protected",
        evidence=b"same",
    )


def context(tenant_id: str) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
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
        fence_scope_id=f"{tenant_id}-worker",
        fence_epoch=9,
        constructed_at=NOW,
        correlation_id="corr-1",
    )


class CurrentExecutionAuthority:
    def __init__(self) -> None:
        self.requests: list[AsyncExecutionRequest] = []

    def finalize_current_execution(self, *, request: AsyncExecutionRequest) -> AsyncExecutionAdmission:
        self.requests.append(request)
        return AsyncExecutionAdmission(
            request=request,
            principal_id="service-worker-a",
            principal_credential_generation="cred-7",
            authorization_revision="authz-1",
            admission_revision=f"admission-{len(self.requests)}",
            runtime_generation="runtime-4",
            environment_class=EnvironmentClass.PRODUCTION,
            observed_at=NOW,
            current=True,
            tenant_context=context(request.tenant_id) if request.tenant_id else None,
        )


class SnapshotAuthority:
    def __init__(self, snapshot: CrossAuthorityOperationSnapshot) -> None:
        self.snapshot_value = snapshot

    def snapshot(self, operation_id: str) -> CrossAuthorityOperationSnapshot:
        if operation_id != self.snapshot_value.operation_id:
            raise AssertionError("wrong operation requested")
        return self.snapshot_value


class InboxOperationScopeBindingTests(unittest.TestCase):
    def claim(self, ledger: InMemoryInboxLedger, trusted_identity: ScopedMessageIdentity):
        authority = CurrentExecutionAuthority()
        claim = ledger.claim_effect(
            trusted_identity,
            "worker-a",
            execution_authority=authority,
            claim_expires_at=LEASE_END,
        )
        return claim, authority

    def test_same_lookup_key_with_different_tenant_cannot_claim_before_authority_call(self) -> None:
        ledger = InMemoryInboxLedger()
        trusted = identity(tenant_id="tenant-a")
        forged = identity(tenant_id="tenant-b")
        self.assertEqual(trusted.key, forged.key)
        ledger.admit(trusted, evidence())
        authority = CurrentExecutionAuthority()

        with self.assertRaises(IntegrityConflict):
            ledger.claim_effect(
                forged,
                "worker-b",
                execution_authority=authority,
                claim_expires_at=LEASE_END,
            )

        self.assertEqual(authority.requests, [])
        self.assertEqual(ledger.state(trusted), InboxState.ADMITTED)

    def test_bind_rejects_operation_from_another_tenant(self) -> None:
        ledger = InMemoryInboxLedger()
        trusted = identity()
        ledger.admit(trusted, evidence())
        claim, _ = self.claim(ledger, trusted)
        operations = InMemoryCrossAuthorityOperationLedger()
        operations.prepare("op-cross-tenant", trusted.consumer_contract, tenant_id="tenant-b")

        with self.assertRaises(ReconciliationBlocked):
            ledger.bind_cross_authority_operation(
                claim,
                "op-cross-tenant",
                operation_authority=operations,
                observed_at=NOW + timedelta(seconds=1),
            )

        self.assertIsNone(ledger.operation_id(trusted))

    def test_bind_rejects_operation_from_another_owner_contract(self) -> None:
        ledger = InMemoryInboxLedger()
        trusted = identity()
        ledger.admit(trusted, evidence())
        claim, _ = self.claim(ledger, trusted)
        operations = InMemoryCrossAuthorityOperationLedger()
        operations.prepare("op-cross-owner", "integrations.provider-effect", tenant_id="tenant-a")

        with self.assertRaises(ReconciliationBlocked):
            ledger.bind_cross_authority_operation(
                claim,
                "op-cross-owner",
                operation_authority=operations,
                observed_at=NOW + timedelta(seconds=1),
            )

        self.assertIsNone(ledger.operation_id(trusted))

    def test_valid_exact_scope_binding_is_retained(self) -> None:
        ledger = InMemoryInboxLedger()
        trusted = identity()
        ledger.admit(trusted, evidence())
        claim, _ = self.claim(ledger, trusted)
        operations = InMemoryCrossAuthorityOperationLedger()
        operations.prepare("op-valid", trusted.consumer_contract, tenant_id=trusted.tenant_id)

        ledger.bind_cross_authority_operation(
            claim,
            "op-valid",
            operation_authority=operations,
            observed_at=NOW + timedelta(seconds=1),
        )

        self.assertEqual(ledger.operation_id(trusted), "op-valid")

    def test_completion_rechecks_scope_in_atomic_snapshot(self) -> None:
        ledger = InMemoryInboxLedger()
        trusted = identity()
        ledger.admit(trusted, evidence())
        claim, _ = self.claim(ledger, trusted)
        valid_binding = SnapshotAuthority(
            CrossAuthorityOperationSnapshot(
                operation_id="op-valid",
                state=OperationState.PREPARED,
                attempt_generation=0,
                owner_contract=trusted.consumer_contract,
                tenant_id=trusted.tenant_id,
            )
        )
        ledger.bind_cross_authority_operation(
            claim,
            "op-valid",
            operation_authority=valid_binding,
            observed_at=NOW + timedelta(seconds=1),
        )
        result = EffectResultLink("result-1", "provider_outcome")
        forged_completion = SnapshotAuthority(
            CrossAuthorityOperationSnapshot(
                operation_id="op-valid",
                state=OperationState.COMPLETED,
                attempt_generation=1,
                owner_contract=trusted.consumer_contract,
                tenant_id="tenant-b",
                outcome=result,
            )
        )

        with self.assertRaises(ReconciliationBlocked):
            ledger.complete_cross_authority_effect(
                claim,
                result,
                operation_authority=forged_completion,
                observed_at=NOW + timedelta(seconds=2),
            )

        self.assertEqual(ledger.state(trusted), InboxState.PROCESSING)

    def test_sql_guard_checks_scope_on_insert_and_update(self) -> None:
        sql = (ROOT / "sql/wave2/006_operation_scope_binding_hardening.sql").read_text(
            encoding="utf-8"
        ).lower()
        self.assertIn("before insert or update on system.async_consumer_inbox", sql)
        self.assertIn("op_tenant_id is distinct from new.tenant_id", sql)
        self.assertIn("op_owner_contract is distinct from new.consumer_contract", sql)
        self.assertIn("for share", sql)
        self.assertIn("security invoker", sql)
        self.assertNotIn("security definer", sql)
        executable_grants = [
            line.strip()
            for line in sql.splitlines()
            if line.strip().startswith("grant ")
        ]
        self.assertEqual(executable_grants, [])


if __name__ == "__main__":
    unittest.main()
