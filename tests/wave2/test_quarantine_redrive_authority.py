from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import unittest

from jlmirror_authority import EnvironmentClass, PrincipalKind, TenantContext
from jlmirror_async import (
    ComparisonEvidence,
    LogicalMessage,
    MessageClass,
    MessageScope,
    QuarantineSource,
    QuarantineSubject,
    RedriveAdmission,
    ReconciliationBlocked,
    ScopedMessageIdentity,
    inbox_redrive_request,
    outbox_redrive_request,
    require_current_redrive,
    tenant_message_from_context,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


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


def evidence() -> ComparisonEvidence:
    return ComparisonEvidence(
        comparison_profile_id="cmp.message-v1",
        comparison_profile_version="v1",
        evidence_form="opaque-protected",
        evidence=b"same",
    )


def tenant_job() -> LogicalMessage:
    return tenant_message_from_context(
        context(),
        message_id="job-1",
        producer_message_scope="producer-scope-a",
        message_class=MessageClass.JOB_COMMAND,
        contract_name="platform.test.execute",
        contract_version="v1",
        producer="PlatformManagement",
        created_at=NOW,
        operation_id="op-1",
        correlation_id="corr-1",
        data_classification="internal",
        serialization_profile_id="serialization.adapter-v1",
        encoded_payload=b"payload",
        comparison_evidence=evidence(),
    )


class RedriveAuthority:
    def __init__(self, *, current: bool = True, eligible: bool = True) -> None:
        self.current = current
        self.eligible = eligible
        self.override_request = None

    def authorize_redrive(self, *, request):
        bound_request = self.override_request or request
        return RedriveAdmission(
            request=bound_request,
            quarantine_state_revision="quarantine-state-12",
            authorizing_principal_id="ops-principal-1",
            privileged_authority_revision="priv-authz-7",
            compatibility_revision="compat-3",
            effect_safety_revision="effect-safety-9",
            capacity_admission_revision="capacity-4",
            audit_revision="audit-8",
            observed_at=NOW,
            current=self.current,
            eligible=self.eligible,
            placement_version="placement-11" if request.subject.tenant_id else None,
            reconciliation_revision="recon-5" if request.subject.operation_id else None,
        )


class QuarantineRedriveAuthorityTests(unittest.TestCase):
    def test_outbox_request_derives_stable_scope_from_immutable_message(self) -> None:
        request = outbox_redrive_request(
            tenant_job(),
            claim_generation=4,
            quarantine_reason_class="poison_or_unknown",
            redrive_operation_id="redrive-1",
        )
        self.assertEqual(request.subject.source, QuarantineSource.OUTBOX_PUBLICATION)
        self.assertEqual(request.subject.owner_contract, "platform.test.execute")
        self.assertEqual(request.subject.identity_scope, "producer-scope-a")
        self.assertEqual(request.subject.message_id, "job-1")
        self.assertEqual(request.subject.tenant_id, "tenant-a")
        self.assertEqual(request.subject.operation_id, "op-1")
        self.assertEqual(request.subject.quarantine_generation, 4)
        self.assertEqual(request.subject.reliability_profile_id, "rel.outbox-publication@1")

    def test_inbox_request_derives_consumer_and_tenant_from_trusted_identity(self) -> None:
        identity = ScopedMessageIdentity(
            consumer_contract="monitoring.observation.consume",
            message_identity_scope="trusted-source-a",
            message_id="message-1",
            tenant_id="tenant-a",
        )
        request = inbox_redrive_request(
            identity,
            execution_generation=3,
            quarantine_reason_class="poison_or_unknown",
            correlation_id="corr-2",
            redrive_operation_id="redrive-2",
            operation_id="op-2",
        )
        self.assertEqual(request.subject.source, QuarantineSource.CONSUMER_INBOX)
        self.assertEqual(request.subject.owner_contract, identity.consumer_contract)
        self.assertEqual(request.subject.identity_scope, identity.message_identity_scope)
        self.assertEqual(request.subject.tenant_id, identity.tenant_id)
        self.assertEqual(request.subject.reliability_profile_id, "rel.consumer-inbox-effect@1")

    def test_quarantine_source_cannot_select_wrong_reliability_profile(self) -> None:
        with self.assertRaises(ValueError):
            QuarantineSubject(
                source=QuarantineSource.OUTBOX_PUBLICATION,
                owner_contract="platform.test.execute",
                identity_scope="scope-a",
                message_id="message-1",
                quarantine_generation=1,
                quarantine_reason_class="poison_or_unknown",
                correlation_id="corr-1",
                reliability_profile_id="rel.consumer-inbox-effect@1",
            )

    def test_redrive_requires_current_privileged_authority(self) -> None:
        request = outbox_redrive_request(
            tenant_job(),
            claim_generation=4,
            quarantine_reason_class="poison_or_unknown",
            redrive_operation_id="redrive-1",
        )
        with self.assertRaises(ReconciliationBlocked):
            require_current_redrive(RedriveAuthority(current=False), request)

    def test_redrive_requires_owning_contract_eligibility(self) -> None:
        request = outbox_redrive_request(
            tenant_job(),
            claim_generation=4,
            quarantine_reason_class="poison_or_unknown",
            redrive_operation_id="redrive-1",
        )
        with self.assertRaises(ReconciliationBlocked):
            require_current_redrive(RedriveAuthority(eligible=False), request)

    def test_redrive_admission_is_exact_quarantine_generation_bound(self) -> None:
        current = outbox_redrive_request(
            tenant_job(),
            claim_generation=5,
            quarantine_reason_class="poison_or_unknown",
            redrive_operation_id="redrive-2",
        )
        stale = replace(
            current,
            subject=replace(current.subject, quarantine_generation=4),
        )
        authority = RedriveAuthority()
        authority.override_request = stale
        with self.assertRaises(ReconciliationBlocked):
            require_current_redrive(authority, current)

    def test_redrive_admission_requires_durable_quarantine_state_revision(self) -> None:
        request = outbox_redrive_request(
            tenant_job(),
            claim_generation=1,
            quarantine_reason_class="poison_or_unknown",
            redrive_operation_id="redrive-1",
        )
        with self.assertRaises(ValueError):
            RedriveAdmission(
                request=request,
                quarantine_state_revision="",
                authorizing_principal_id="ops-principal-1",
                privileged_authority_revision="priv-authz-7",
                compatibility_revision="compat-3",
                effect_safety_revision="effect-safety-9",
                capacity_admission_revision="capacity-4",
                audit_revision="audit-8",
                observed_at=NOW,
                current=True,
                eligible=True,
                placement_version="placement-11",
            )

    def test_tenant_redrive_admission_requires_current_placement_evidence(self) -> None:
        request = outbox_redrive_request(
            tenant_job(),
            claim_generation=1,
            quarantine_reason_class="poison_or_unknown",
            redrive_operation_id="redrive-1",
        )
        with self.assertRaises(ValueError):
            RedriveAdmission(
                request=request,
                quarantine_state_revision="quarantine-state-12",
                authorizing_principal_id="ops-principal-1",
                privileged_authority_revision="priv-authz-7",
                compatibility_revision="compat-3",
                effect_safety_revision="effect-safety-9",
                capacity_admission_revision="capacity-4",
                audit_revision="audit-8",
                observed_at=NOW,
                current=True,
                eligible=True,
                placement_version=None,
            )

    def test_global_redrive_must_not_manufacture_tenant_placement(self) -> None:
        message = LogicalMessage(
            message_id="global-1",
            producer_message_scope="global-source",
            message_class=MessageClass.DOMAIN_EVENT,
            contract_name="platform.global.changed",
            contract_version="v1",
            producer="PlatformManagement",
            scope=MessageScope.GLOBAL,
            occurred_at=NOW,
            correlation_id="corr-global",
            data_classification="internal",
            serialization_profile_id="serialization.adapter-v1",
            encoded_payload=b"payload",
            comparison_evidence=evidence(),
        )
        request = outbox_redrive_request(
            message,
            claim_generation=1,
            quarantine_reason_class="poison_or_unknown",
            redrive_operation_id="redrive-global",
        )
        with self.assertRaises(ValueError):
            RedriveAdmission(
                request=request,
                quarantine_state_revision="quarantine-state-global-1",
                authorizing_principal_id="ops-principal-1",
                privileged_authority_revision="priv-authz-7",
                compatibility_revision="compat-3",
                effect_safety_revision="effect-safety-9",
                capacity_admission_revision="capacity-4",
                audit_revision="audit-8",
                observed_at=NOW,
                current=True,
                eligible=True,
                placement_version="placement-should-not-exist",
            )


if __name__ == "__main__":
    unittest.main()
