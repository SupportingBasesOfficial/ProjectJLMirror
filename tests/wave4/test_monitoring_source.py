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
    def command(self, *, tenant_id: str = "tenant-a") -> CreateMonitoringSourceCommand:
        return CreateMonitoringSourceCommand(
            tenant_id=tenant_id,
            display_name="Primary Zabbix",
            provider_configuration=ZabbixProviderConfiguration("https://zabbix.example.test/zabbix"),
            credential_binding_ref="secret-binding:zabbix-primary",
            configured_provider_scope=ConfiguredProviderScope.from_refs(("group-linux", "group-network")),
        )

    def test_create_plan_keeps_platform_identity_separate_from_provider(self):
        now = datetime(2026, 9, 10, 0, 0, tzinfo=timezone.utc)
        plan = plan_source_creation(
            self.command(),
            source_id_factory=lambda: "mon-src_platform-id",
            generation_factory=lambda: "mon-gen_high-entropy-generation",
            operation_id_factory=lambda: "mon-sync_initial",
            audit_evidence_id_factory=lambda: "mon-audit_create",
            now=lambda: now,
        )
        self.assertEqual(plan.source.monitoring_source_id, "mon-src_platform-id")
        self.assertEqual(plan.source.provider_profile, "zabbix")
        self.assertEqual(plan.source.active_source_instance_generation, "mon-gen_high-entropy-generation")
        self.assertEqual(plan.audit_evidence_id, "mon-audit_create")
        self.assertEqual(plan.source.configuration_revision, 1)
        self.assertEqual(plan.source.scope_revision, 1)
        self.assertEqual(plan.source.operational_evidence_state, OperationalEvidenceState.RECONCILIATION_REQUIRED)
        self.assertEqual(plan.source.last_sync_operation_id, "mon-sync_initial")
        self.assertEqual(plan.sync_operation.state, SyncOperationState.PENDING)
        self.assertEqual(plan.sync_operation.responsibility_kind, "validation_and_initial_sync")
        self.assertEqual(plan.sync_operation.source_instance_generation, plan.source.active_source_instance_generation)
        self.assertEqual(plan.source.created_at, now)
        self.assertIsNone(plan.source.last_successful_sync_at)
        self.assertIsNone(plan.source.last_attempt_at)

    def test_creation_clock_is_normalized_to_utc(self):
        from datetime import timedelta, timezone as tz

        local_time = datetime(2026, 9, 9, 21, 0, tzinfo=tz(timedelta(hours=-3)))
        plan = plan_source_creation(self.command(), now=lambda: local_time)
        self.assertEqual(plan.source.created_at, datetime(2026, 9, 10, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(plan.sync_operation.created_at, plan.source.created_at)

    def test_tenant_is_authority_scope_not_fingerprint_body(self):
        a = self.command(tenant_id="tenant-a")
        b = self.command(tenant_id="tenant-b")
        self.assertEqual(a.canonical_fingerprint(), b.canonical_fingerprint())
        self.assertNotEqual(a.tenant_id, b.tenant_id)

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
        self.assertEqual(
            ZabbixProviderConfiguration("https://zabbix.example.test:8443/zabbix").base_url,
            "https://zabbix.example.test:8443/zabbix",
        )
        self.assertEqual(
            ZabbixProviderConfiguration("https://[2001:db8::1]:8443/zabbix").base_url,
            "https://[2001:db8::1]:8443/zabbix",
        )

    def test_command_text_fields_reject_control_or_alternate_whitespace(self):
        with self.assertRaises(ValueError):
            self.command(tenant_id="tenant-a\nother")
        with self.assertRaises(ValueError):
            CreateMonitoringSourceCommand(
                tenant_id="tenant-a",
                display_name=" Primary Zabbix",
                provider_configuration=ZabbixProviderConfiguration("https://zabbix.example.test"),
                credential_binding_ref="secret-binding:zabbix-primary",
                configured_provider_scope=ConfiguredProviderScope.from_refs(()),
            )

    def test_raw_secret_is_not_part_of_command_shape(self):
        fields = set(CreateMonitoringSourceCommand.__dataclass_fields__)
        self.assertIn("credential_binding_ref", fields)
        self.assertNotIn("token", fields)
        self.assertNotIn("password", fields)
        self.assertNotIn("secret", fields)

    def test_generated_identities_must_be_distinct_and_canonical(self):
        with self.assertRaisesRegex(ValueError, "distinct"):
            plan_source_creation(
                self.command(),
                source_id_factory=lambda: "same",
                generation_factory=lambda: "same",
                operation_id_factory=lambda: "other",
                audit_evidence_id_factory=lambda: "audit",
            )
        with self.assertRaisesRegex(ValueError, "distinct"):
            plan_source_creation(
                self.command(),
                source_id_factory=lambda: "source",
                generation_factory=lambda: "generation",
                operation_id_factory=lambda: "operation",
                audit_evidence_id_factory=lambda: "source",
            )
        with self.assertRaises(ValueError):
            plan_source_creation(self.command(), source_id_factory=lambda: "source\nmalformed")

    def test_creation_clock_must_be_timezone_aware(self):
        with self.assertRaisesRegex(ValueError, "aware timestamp"):
            plan_source_creation(self.command(), now=lambda: datetime(2026, 9, 10))


if __name__ == "__main__":
    unittest.main()
