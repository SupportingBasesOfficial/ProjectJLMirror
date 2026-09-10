from datetime import datetime, timezone
import unittest

from jlmirror_monitoring import (
    ConfiguredProviderScope,
    CreateMonitoringSourceCommand,
    OperationalEvidenceState,
    SyncOperationState,
    ZabbixProviderConfiguration,
    plan_source_creation,
)


class MonitoringSourceFoundationTests(unittest.TestCase):
    def command(
        self,
        *,
        tenant_id: str = "tenant-a",
        provider_instance_ref: str = "provider-instance:central-zabbix",
    ) -> CreateMonitoringSourceCommand:
        return CreateMonitoringSourceCommand(
            tenant_id=tenant_id,
            display_name="Primary Zabbix",
            provider_instance_ref=provider_instance_ref,
            provider_configuration=ZabbixProviderConfiguration("https://zabbix.example.test/zabbix"),
            credential_binding_ref="provider-access-binding:zabbix-primary",
            configured_provider_scope=ConfiguredProviderScope.from_refs(("group-linux", "group-network")),
        )

    def test_create_plan_separates_source_binding_generation_and_provider_instance(self):
        now = datetime(2026, 9, 10, 0, 0, tzinfo=timezone.utc)
        plan = plan_source_creation(
            self.command(),
            source_id_factory=lambda: "mon-src_platform-id",
            generation_factory=lambda: "mon-gen_attachment-generation",
            scope_tenant_binding_id_factory=lambda: "mon-bind_tenant-a",
            operation_id_factory=lambda: "mon-sync_initial",
            audit_evidence_id_factory=lambda: "mon-audit_create",
            now=lambda: now,
        )
        self.assertEqual(plan.source.monitoring_source_id, "mon-src_platform-id")
        self.assertEqual(plan.source.provider_scope_tenant_binding_id, "mon-bind_tenant-a")
        self.assertEqual(plan.generation.provider_instance_ref, "provider-instance:central-zabbix")
        self.assertEqual(plan.generation.source_instance_generation, "mon-gen_attachment-generation")
        self.assertEqual(plan.source.active_source_instance_generation, plan.generation.source_instance_generation)
        self.assertEqual(plan.source.operational_evidence_state, OperationalEvidenceState.RECONCILIATION_REQUIRED)
        self.assertEqual(plan.sync_operation.state, SyncOperationState.PENDING)
        self.assertEqual(plan.sync_operation.responsibility_kind, "validation_and_initial_sync")
        self.assertEqual(plan.audit_evidence_id, "mon-audit_create")
        self.assertEqual(plan.source.created_at, now)

    def test_same_provider_instance_can_back_independent_tenant_sources(self):
        a = plan_source_creation(
            self.command(tenant_id="tenant-a"),
            source_id_factory=lambda: "source-a",
            generation_factory=lambda: "generation-a",
            scope_tenant_binding_id_factory=lambda: "binding-a",
            operation_id_factory=lambda: "sync-a",
            audit_evidence_id_factory=lambda: "audit-a",
        )
        b = plan_source_creation(
            self.command(tenant_id="tenant-b"),
            source_id_factory=lambda: "source-b",
            generation_factory=lambda: "generation-b",
            scope_tenant_binding_id_factory=lambda: "binding-b",
            operation_id_factory=lambda: "sync-b",
            audit_evidence_id_factory=lambda: "audit-b",
        )
        self.assertEqual(a.generation.provider_instance_ref, b.generation.provider_instance_ref)
        self.assertNotEqual(a.source.tenant_id, b.source.tenant_id)
        self.assertNotEqual(a.source.monitoring_source_id, b.source.monitoring_source_id)
        self.assertNotEqual(a.source.provider_scope_tenant_binding_id, b.source.provider_scope_tenant_binding_id)
        self.assertNotEqual(a.generation.source_instance_generation, b.generation.source_instance_generation)

    def test_provider_instance_participates_in_create_fingerprint_but_tenant_does_not(self):
        a = self.command(tenant_id="tenant-a")
        b = self.command(tenant_id="tenant-b")
        c = self.command(tenant_id="tenant-a", provider_instance_ref="provider-instance:other")
        self.assertEqual(a.canonical_fingerprint(), b.canonical_fingerprint())
        self.assertNotEqual(a.canonical_fingerprint(), c.canonical_fingerprint())

    def test_scope_is_bounded_duplicate_free_and_control_safe(self):
        with self.assertRaisesRegex(ValueError, "duplicates"):
            ConfiguredProviderScope.from_refs(("same", "same"))
        with self.assertRaisesRegex(ValueError, "bounded cardinality"):
            ConfiguredProviderScope.from_refs(str(i) for i in range(257))
        for invalid in ("", " group", "group\nadmin"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    ConfiguredProviderScope.from_refs((invalid,))

    def test_zabbix_url_is_static_https_only_and_canonical(self):
        for invalid in (
            "http://zabbix.example.test",
            "https://user:pass@zabbix.example.test",
            "https://zabbix.example.test?a=1",
            "https://zabbix.example.test#fragment",
            "https://ZABBIX.example.test",
            "https://zabbix.example.test./zabbix",
            "https://zabbix.example.test/./zabbix",
            "https://zabbix.example.test/a/../zabbix",
            "https://zabbix.example.test\\zabbix",
            "https://zabbix.example.test/\nadmin",
            "https://zábbix.example.test/zabbix",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    ZabbixProviderConfiguration(invalid)

    def test_command_rejects_noncanonical_provider_instance_ref(self):
        with self.assertRaises(ValueError):
            self.command(provider_instance_ref=" provider-instance:central")
        with self.assertRaises(ValueError):
            self.command(provider_instance_ref="provider-instance:\ncentral")

    def test_raw_secret_is_not_part_of_command_shape(self):
        fields = set(CreateMonitoringSourceCommand.__dataclass_fields__)
        self.assertIn("credential_binding_ref", fields)
        self.assertIn("provider_instance_ref", fields)
        self.assertNotIn("token", fields)
        self.assertNotIn("password", fields)
        self.assertNotIn("secret", fields)

    def test_generated_identities_must_be_distinct(self):
        with self.assertRaisesRegex(ValueError, "distinct"):
            plan_source_creation(
                self.command(),
                source_id_factory=lambda: "same",
                generation_factory=lambda: "same",
                scope_tenant_binding_id_factory=lambda: "binding",
                operation_id_factory=lambda: "operation",
                audit_evidence_id_factory=lambda: "audit",
            )

    def test_creation_clock_must_be_timezone_aware(self):
        with self.assertRaisesRegex(ValueError, "aware timestamp"):
            plan_source_creation(self.command(), now=lambda: datetime(2026, 9, 10))


if __name__ == "__main__":
    unittest.main()
