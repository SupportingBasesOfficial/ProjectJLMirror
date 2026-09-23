from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/g2-monitoring-source-onboarding"))
sys.path.insert(0, str(ROOT / "src"))

from onboarding import CurrentAuthorizationEvidence, MonitoringSourceOnboarding, SourceSnapshot, present  # noqa: E402
from jlmirror_monitoring import (  # noqa: E402
    OperationalEvidenceState,
    SyncOperationState,
)


class Authorization:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self.denied = False
        self.deny_on_call: int | None = None

    def require(self, *, actor_ref: str, tenant_id: str, action: str) -> CurrentAuthorizationEvidence:
        self.calls.append((actor_ref, tenant_id, action))
        if self.denied or self.deny_on_call == len(self.calls):
            raise PermissionError("current authorization denied")
        return CurrentAuthorizationEvidence(
            actor_principal_id=actor_ref,
            actor_principal_kind="human_browser_session",
            actor_generation_ref="principal-generation-a",
            authorization_decision_ref="admission-r1",
        )


class ProviderBinding:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def current_instance_ref(self, *, tenant_id: str, provider_profile: str) -> str:
        self.calls.append((tenant_id, provider_profile))
        return "provider-instance:tenant-current"


class SourcePort:
    def __init__(self) -> None:
        self.create_calls = []
        self.read_calls = []
        self.snapshot: SourceSnapshot | None = None
        self.committed_override: SourceSnapshot | None = None

    def create_initial(
        self,
        *,
        plan,
        idempotency_key: str,
        actor_principal_id: str,
        actor_principal_kind: str,
        actor_generation_ref: str,
        authorization_decision_ref: str,
        request_correlation_id: str,
    ) -> SourceSnapshot:
        self.create_calls.append((
            plan,
            idempotency_key,
            actor_principal_id,
            actor_principal_kind,
            actor_generation_ref,
            authorization_decision_ref,
            request_correlation_id,
        ))
        if getattr(self, "committed_override", None) is not None:
            return self.committed_override
        return SourceSnapshot(
            monitoring_source_id=plan.source.monitoring_source_id,
            monitoring_sync_operation_id=plan.sync_operation.monitoring_sync_operation_id,
            operational_evidence_state=plan.source.operational_evidence_state,
            sync_operation_state=plan.sync_operation.state,
        )

    def read_source(self, *, tenant_id: str, monitoring_source_id: str) -> SourceSnapshot:
        self.read_calls.append((tenant_id, monitoring_source_id))
        if self.snapshot is None:
            raise LookupError("missing fixture")
        return self.snapshot


class ValidationResponsibility:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def make_ready(self, *, tenant_id: str, monitoring_sync_operation_id: str) -> None:
        self.calls.append((tenant_id, monitoring_sync_operation_id))


class G2MonitoringSourceOnboardingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.authorization = Authorization()
        self.binding = ProviderBinding()
        self.source = SourcePort()
        self.validation = ValidationResponsibility()
        self.service = MonitoringSourceOnboarding(
            authorization=self.authorization,
            provider_binding=self.binding,
            source_port=self.source,
            validation_responsibility=self.validation,
        )

    def payload(self):
        return {
            "provider_profile": "zabbix",
            "display_name": "Primary Zabbix",
            "provider_configuration": {"base_url": "https://zabbix.example.test/zabbix"},
            "credential_binding_ref": "provider-access-binding:zabbix-primary",
            "configured_provider_scope": {"host_group_refs": ["group-linux"]},
        }

    def test_create_authorizes_before_resolving_provider_binding(self):
        self.authorization.denied = True
        with self.assertRaises(PermissionError):
            self.service.create(
                actor_ref="principal-a",
                tenant_id="tenant-a",
                idempotency_key="request-1",
                payload=self.payload(),
            )
        self.assertEqual(self.binding.calls, [])
        self.assertEqual(self.source.create_calls, [])
        self.assertEqual(self.validation.calls, [])

    def test_create_uses_server_side_provider_binding_and_commits_before_validation_ready(self):
        view = self.service.create(
            actor_ref="principal-a",
            tenant_id="tenant-a",
            idempotency_key="request-1",
            payload=self.payload(),
        )
        self.assertEqual(self.binding.calls, [("tenant-a", "zabbix")])
        self.assertEqual(
            self.authorization.calls,
            [
                ("principal-a", "tenant-a", "monitoring.source.manage"),
                ("principal-a", "tenant-a", "monitoring.source.manage"),
            ],
        )
        self.assertEqual(len(self.source.create_calls), 1)
        plan, key, actor_id, actor_kind, generation_ref, decision_ref, correlation_id = self.source.create_calls[0]
        self.assertEqual(key, "request-1")
        self.assertEqual(actor_id, "principal-a")
        self.assertEqual(actor_kind, "human_browser_session")
        self.assertEqual(generation_ref, "principal-generation-a")
        self.assertEqual(decision_ref, "admission-r1")
        self.assertTrue(correlation_id.startswith("g2-request:"))
        self.assertEqual(plan.generation.provider_instance_ref, "provider-instance:tenant-current")
        self.assertEqual(plan.source.tenant_id, "tenant-a")
        self.assertEqual(len(self.validation.calls), 1)
        self.assertEqual(
            self.validation.calls[0],
            ("tenant-a", view.monitoring_sync_operation_id),
        )
        self.assertEqual(view.state, "validation_pending")
        self.assertFalse(view.provider_connection_confirmed)

    def test_create_revalidates_authority_immediately_before_commit(self):
        self.authorization.deny_on_call = 2
        with self.assertRaises(PermissionError):
            self.service.create(
                actor_ref="principal-a",
                tenant_id="tenant-a",
                idempotency_key="request-toctou",
                payload=self.payload(),
            )
        self.assertEqual(self.binding.calls, [("tenant-a", "zabbix")])
        self.assertEqual(self.source.create_calls, [])
        self.assertEqual(self.validation.calls, [])

    def test_idempotent_replay_presents_committed_identity_not_fresh_plan_identity(self):
        self.source.committed_override = SourceSnapshot(
            monitoring_source_id="mon-src-existing",
            monitoring_sync_operation_id="mon-sync-existing",
            operational_evidence_state=OperationalEvidenceState.CURRENT,
            sync_operation_state=SyncOperationState.SUCCEEDED,
        )
        view = self.service.create(
            actor_ref="principal-a",
            tenant_id="tenant-a",
            idempotency_key="request-replay",
            payload=self.payload(),
        )
        plan = self.source.create_calls[0][0]
        self.assertNotEqual(plan.source.monitoring_source_id, view.monitoring_source_id)
        self.assertEqual(view.monitoring_source_id, "mon-src-existing")
        self.assertEqual(view.monitoring_sync_operation_id, "mon-sync-existing")
        self.assertEqual(view.state, "current")
        self.assertEqual(self.validation.calls, [])

    def test_request_shape_rejects_unknown_fields(self):
        payload = self.payload()
        payload["unexpected_field"] = "not-allowed"
        with self.assertRaisesRegex(ValueError, "shape"):
            self.service.create(
                actor_ref="principal-a",
                tenant_id="tenant-a",
                idempotency_key="request-1",
                payload=payload,
            )
        self.assertEqual(self.source.create_calls, [])

    def test_request_shape_rejects_noncanonical_provider_configuration(self):
        payload = self.payload()
        payload["provider_configuration"] = {
            "base_url": "https://zabbix.example.test",
            "extra": "not-allowed",
        }
        with self.assertRaisesRegex(ValueError, "provider_configuration shape"):
            self.service.create(
                actor_ref="principal-a",
                tenant_id="tenant-a",
                idempotency_key="request-1",
                payload=payload,
            )

    def test_idempotency_key_is_required_and_canonical(self):
        for value in ("", " key", "key\nother"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "Idempotency-Key"):
                    self.service.create(
                        actor_ref="principal-a",
                        tenant_id="tenant-a",
                        idempotency_key=value,
                        payload=self.payload(),
                    )

    def test_read_rechecks_current_authorization(self):
        self.source.snapshot = SourceSnapshot(
            monitoring_source_id="mon-src-a",
            monitoring_sync_operation_id="mon-sync-a",
            operational_evidence_state=OperationalEvidenceState.CURRENT,
            sync_operation_state=SyncOperationState.SUCCEEDED,
        )
        view = self.service.read(
            actor_ref="principal-a",
            tenant_id="tenant-a",
            monitoring_source_id="mon-src-a",
        )
        self.assertEqual(
            self.authorization.calls,
            [
                ("principal-a", "tenant-a", "monitoring.source.read"),
                ("principal-a", "tenant-a", "monitoring.source.read"),
                ("principal-a", "tenant-a", "monitoring.sync.read"),
            ],
        )
        self.assertTrue(view.provider_connection_confirmed)
        self.assertEqual(view.state, "current")

    def test_read_revalidates_source_authority_before_response(self):
        self.source.snapshot = SourceSnapshot(
            monitoring_source_id="mon-src-a",
            monitoring_sync_operation_id="mon-sync-a",
            operational_evidence_state=OperationalEvidenceState.CURRENT,
            sync_operation_state=SyncOperationState.SUCCEEDED,
        )
        self.authorization.deny_on_call = 2
        with self.assertRaises(PermissionError):
            self.service.read(
                actor_ref="principal-a",
                tenant_id="tenant-a",
                monitoring_source_id="mon-src-a",
            )
        self.assertEqual(
            self.authorization.calls,
            [
                ("principal-a", "tenant-a", "monitoring.source.read"),
                ("principal-a", "tenant-a", "monitoring.source.read"),
            ],
        )

    def test_presentation_never_confirms_connection_before_current_success(self):
        cases = [
            (OperationalEvidenceState.RECONCILIATION_REQUIRED, SyncOperationState.PENDING, "validation_pending"),
            (OperationalEvidenceState.INCOMPLETE, SyncOperationState.RECONCILIATION_REQUIRED, "incomplete"),
            (OperationalEvidenceState.UNAVAILABLE, SyncOperationState.RECONCILIATION_REQUIRED, "unavailable"),
            (OperationalEvidenceState.STALE, SyncOperationState.SUCCEEDED, "reconciliation_required"),
        ]
        for evidence, operation, expected in cases:
            with self.subTest(evidence=evidence, operation=operation):
                view = present(
                    SourceSnapshot(
                        monitoring_source_id="mon-src-a",
                        monitoring_sync_operation_id="mon-sync-a",
                        operational_evidence_state=evidence,
                        sync_operation_state=operation,
                    )
                )
                self.assertEqual(view.state, expected)
                self.assertFalse(view.provider_connection_confirmed)


if __name__ == "__main__":
    unittest.main()
