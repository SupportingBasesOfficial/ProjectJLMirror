from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
import unittest

from jlmirror_authority import EnvironmentClass, PrincipalKind, TenantContext
from jlmirror_async import (
    BrokerPublicationReceipt,
    ComparisonEvidence,
    EffectResultLink,
    InboxAdmission,
    InboxState,
    InMemoryCrossAuthorityOperationLedger,
    InMemoryInboxLedger,
    InMemoryOutboxLedger,
    InvalidTransition,
    LogicalMessage,
    MessageClass,
    MessageScope,
    OperationState,
    ReconciliationBlocked,
    ReconciliationResolution,
    ScopedMessageIdentity,
    tenant_message_from_context,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def tenant_context(tenant_id: str = "tenant-a") -> TenantContext:
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
        fence_scope_id="tenant-a-worker",
        fence_epoch=9,
        constructed_at=NOW,
        correlation_id="corr-1",
    )


def evidence(value: bytes = b"same", *, profile: str = "cmp.message-v1", verifier: str | None = None) -> ComparisonEvidence:
    return ComparisonEvidence(
        comparison_profile_id=profile,
        comparison_profile_version="v1",
        evidence_form="opaque-protected",
        verifier_generation=verifier,
        evidence=value,
    )


def tenant_event(*, message_id: str = "msg-1", payload: bytes = b"payload", ev: ComparisonEvidence | None = None) -> LogicalMessage:
    return tenant_message_from_context(
        tenant_context(),
        message_id=message_id,
        producer_message_scope="producer-scope-a",
        message_class=MessageClass.DOMAIN_EVENT,
        contract_name="platform.test.changed",
        contract_version="v1",
        producer="PlatformManagement",
        producer_generation="runtime-4",
        occurred_at=NOW,
        correlation_id="corr-1",
        data_classification="internal",
        serialization_profile_id="serialization.adapter-v1",
        encoded_payload=payload,
        comparison_evidence=ev or evidence(),
    )


def tenant_job(*, operation_id: str = "op-job-1", message_id: str = "job-1") -> LogicalMessage:
    return tenant_message_from_context(
        tenant_context(),
        message_id=message_id,
        producer_message_scope="job-producer-scope-a",
        message_class=MessageClass.JOB_COMMAND,
        contract_name="platform.test.execute",
        contract_version="v1",
        producer="PlatformManagement",
        created_at=NOW,
        operation_id=operation_id,
        not_before=NOW + timedelta(seconds=1),
        deadline=NOW + timedelta(minutes=5),
        correlation_id="corr-job-1",
        data_classification="internal",
        serialization_profile_id="serialization.adapter-v1",
        encoded_payload=b"job-payload",
        comparison_evidence=evidence(b"job-evidence"),
    )


class MessageBoundaryTests(unittest.TestCase):
    def test_tenant_scope_is_derived_from_trusted_context(self) -> None:
        message = tenant_event()
        self.assertEqual(message.tenant_id, "tenant-a")
        self.assertEqual(message.scope, MessageScope.TENANT)

    def test_explicit_global_message_cannot_smuggle_tenant(self) -> None:
        with self.assertRaises(ValueError):
            LogicalMessage(
                message_id="m-global",
                producer_message_scope="global-scope",
                message_class=MessageClass.DOMAIN_EVENT,
                contract_name="platform.global.changed",
                contract_version="v1",
                producer="PlatformManagement",
                scope=MessageScope.GLOBAL,
                tenant_id="tenant-a",
                occurred_at=NOW,
                correlation_id="corr-1",
                data_classification="internal",
                serialization_profile_id="serialization.adapter-v1",
                encoded_payload=b"x",
                comparison_evidence=evidence(),
            )

    def test_message_semantics_are_frozen(self) -> None:
        message = tenant_event()
        with self.assertRaises(FrozenInstanceError):
            message.message_id = "changed"  # type: ignore[misc]

    def test_equivalence_profile_drift_is_unknown_not_success(self) -> None:
        self.assertEqual(
            evidence(profile="cmp.message-v1").relation_to(evidence(profile="cmp.message-v2")).value,
            "unknown",
        )

    def test_event_requires_occurred_at_and_forbids_created_at(self) -> None:
        with self.assertRaises(ValueError):
            tenant_message_from_context(
                tenant_context(),
                message_id="event-bad-time",
                producer_message_scope="producer-scope-a",
                message_class=MessageClass.INTEGRATION_EVENT,
                contract_name="platform.test.changed",
                contract_version="v1",
                producer="PlatformManagement",
                created_at=NOW,
                correlation_id="corr-1",
                data_classification="internal",
                serialization_profile_id="serialization.adapter-v1",
                encoded_payload=b"x",
                comparison_evidence=evidence(),
            )

    def test_job_requires_created_at_and_stable_operation_id(self) -> None:
        job = tenant_job()
        self.assertEqual(job.created_at, NOW)
        self.assertIsNone(job.occurred_at)
        self.assertEqual(job.operation_id, "op-job-1")
        with self.assertRaises(ValueError):
            tenant_message_from_context(
                tenant_context(),
                message_id="job-missing-op",
                producer_message_scope="job-producer-scope-a",
                message_class=MessageClass.JOB_COMMAND,
                contract_name="platform.test.execute",
                contract_version="v1",
                producer="PlatformManagement",
                created_at=NOW,
                correlation_id="corr-job-1",
                data_classification="internal",
                serialization_profile_id="serialization.adapter-v1",
                encoded_payload=b"job-payload",
                comparison_evidence=evidence(b"job-evidence"),
            )

    def test_job_time_window_cannot_precede_creation(self) -> None:
        with self.assertRaises(ValueError):
            tenant_message_from_context(
                tenant_context(),
                message_id="job-bad-window",
                producer_message_scope="job-producer-scope-a",
                message_class=MessageClass.JOB_COMMAND,
                contract_name="platform.test.execute",
                contract_version="v1",
                producer="PlatformManagement",
                created_at=NOW,
                operation_id="op-job-bad-window",
                not_before=NOW - timedelta(seconds=1),
                correlation_id="corr-job-1",
                data_classification="internal",
                serialization_profile_id="serialization.adapter-v1",
                encoded_payload=b"job-payload",
                comparison_evidence=evidence(b"job-evidence"),
            )


class OutboxTests(unittest.TestCase):
    def test_identity_reuse_with_changed_meaning_fails(self) -> None:
        ledger = InMemoryOutboxLedger()
        ledger.append_committed(tenant_event(ev=evidence(b"A")))
        with self.assertRaises(InvalidTransition):
            ledger.append_committed(tenant_event(payload=b"different", ev=evidence(b"B")))

    def test_concurrent_claim_has_one_current_owner(self) -> None:
        ledger = InMemoryOutboxLedger()
        record_id = ledger.append_committed(tenant_event())
        with ThreadPoolExecutor(max_workers=32) as pool:
            claims = list(pool.map(lambda i: ledger.claim_next(f"dispatcher-{i}"), range(64)))
        winners = [claim for claim in claims if claim is not None]
        self.assertEqual(len(winners), 1)
        self.assertEqual(winners[0].record_id, record_id)

    def test_ambiguous_publication_retries_same_logical_message(self) -> None:
        ledger = InMemoryOutboxLedger()
        record_id = ledger.append_committed(tenant_event(message_id="msg-stable"))
        first = ledger.claim_next("dispatcher-a")
        assert first is not None
        ledger.mark_publication_ambiguous(first)
        second = ledger.claim_next("dispatcher-b")
        assert second is not None
        self.assertEqual(second.message.message_id, "msg-stable")
        self.assertEqual(second.record_id, record_id)
        self.assertEqual(ledger.attempt_count(record_id), 2)

    def test_stale_claim_cannot_ack_publication(self) -> None:
        ledger = InMemoryOutboxLedger()
        ledger.append_committed(tenant_event())
        first = ledger.claim_next("dispatcher-a")
        assert first is not None
        ledger.mark_publication_ambiguous(first)
        second = ledger.claim_next("dispatcher-b")
        assert second is not None
        with self.assertRaises(InvalidTransition):
            ledger.mark_published(
                first,
                BrokerPublicationReceipt("receipt-old", NOW + timedelta(seconds=1)),
            )
        ledger.mark_published(
            second,
            BrokerPublicationReceipt("receipt-new", NOW + timedelta(seconds=2)),
        )


class InboxTests(unittest.TestCase):
    def identity(self, scope: str = "scope-a") -> ScopedMessageIdentity:
        return ScopedMessageIdentity(
            consumer_contract="monitoring.observation.consume",
            message_identity_scope=scope,
            message_id="message-1",
            tenant_id="tenant-a",
        )

    def test_atomic_admission_allows_one_executor(self) -> None:
        ledger = InMemoryInboxLedger()
        identity = self.identity()
        self.assertEqual(ledger.admit(identity, evidence()), InboxAdmission.NEW)

        def claim(i: int) -> bool:
            try:
                ledger.claim_effect(identity, f"worker-{i}")
                return True
            except InvalidTransition:
                return False

        with ThreadPoolExecutor(max_workers=32) as pool:
            results = list(pool.map(claim, range(64)))
        self.assertEqual(sum(results), 1)

    def test_completed_duplicate_does_not_reexecute(self) -> None:
        ledger = InMemoryInboxLedger()
        identity = self.identity()
        ledger.admit(identity, evidence())
        claim = ledger.claim_effect(identity, "worker-a")
        ledger.complete_local_effect(claim, EffectResultLink("revision-7", "resource_revision"))
        self.assertEqual(ledger.admit(identity, evidence()), InboxAdmission.DUPLICATE_COMPLETED)
        with self.assertRaises(InvalidTransition):
            ledger.claim_effect(identity, "worker-b")

    def test_same_scoped_id_conflicting_content_quarantines(self) -> None:
        ledger = InMemoryInboxLedger()
        identity = self.identity()
        ledger.admit(identity, evidence(b"A"))
        self.assertEqual(ledger.admit(identity, evidence(b"B")), InboxAdmission.INTEGRITY_CONFLICT)
        self.assertEqual(ledger.state(identity), InboxState.QUARANTINED)

    def test_unknown_historical_comparison_authority_blocks(self) -> None:
        ledger = InMemoryInboxLedger()
        identity = self.identity()
        ledger.admit(identity, evidence(b"same", verifier="key-generation-a"))
        result = ledger.admit(identity, evidence(b"same", verifier="key-generation-b"))
        self.assertEqual(result, InboxAdmission.RECONCILIATION_BLOCKED)
        self.assertEqual(ledger.state(identity), InboxState.RECONCILIATION_REQUIRED)
        with self.assertRaises(ReconciliationBlocked):
            ledger.claim_effect(identity, "worker-a")

    def test_same_raw_id_in_different_trusted_scope_is_independent(self) -> None:
        ledger = InMemoryInboxLedger()
        a = self.identity("tenant-a-source")
        b = self.identity("tenant-b-source")
        self.assertEqual(ledger.admit(a, evidence()), InboxAdmission.NEW)
        self.assertEqual(ledger.admit(b, evidence()), InboxAdmission.NEW)
        ledger.claim_effect(a, "worker-a")
        ledger.claim_effect(b, "worker-b")


class CrossAuthorityOperationTests(unittest.TestCase):
    def test_ambiguous_effect_blocks_blind_retry_until_proven_absent(self) -> None:
        ledger = InMemoryCrossAuthorityOperationLedger()
        ledger.prepare("op-1", "integrations.provider-effect", tenant_id="tenant-a")
        attempt = ledger.begin_attempt("op-1", "worker-a")
        ledger.mark_ambiguous(attempt, "timeout_after_request_write")
        with self.assertRaises(ReconciliationBlocked):
            ledger.begin_attempt("op-1", "worker-b")
        ledger.reconcile("op-1", ReconciliationResolution.STILL_UNKNOWN)
        self.assertEqual(ledger.state("op-1"), OperationState.RECONCILIATION_REQUIRED)
        ledger.reconcile("op-1", ReconciliationResolution.EFFECT_PROVEN_ABSENT)
        retry = ledger.begin_attempt("op-1", "worker-b")
        self.assertEqual(retry.operation_id, "op-1")
        self.assertEqual(retry.attempt_generation, 2)

    def test_reconciliation_can_confirm_existing_effect(self) -> None:
        ledger = InMemoryCrossAuthorityOperationLedger()
        ledger.prepare("op-2", "integrations.provider-effect", tenant_id="tenant-a")
        attempt = ledger.begin_attempt("op-2", "worker-a")
        ledger.mark_ambiguous(attempt, "connection_lost")
        outcome = EffectResultLink("provider-result-9", "provider_outcome")
        ledger.reconcile(
            "op-2",
            ReconciliationResolution.EFFECT_CONFIRMED,
            confirmed_outcome=outcome,
        )
        self.assertEqual(ledger.state("op-2"), OperationState.COMPLETED)
        self.assertEqual(ledger.outcome("op-2"), outcome)
        with self.assertRaises(InvalidTransition):
            ledger.begin_attempt("op-2", "worker-c")


if __name__ == "__main__":
    unittest.main()
