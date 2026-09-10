from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SQL1 = ROOT / "sql/wave4/001_monitoring_source_foundation.sql"
SQL2 = ROOT / "sql/wave4/002_monitoring_source_audit_evidence.sql"


class MonitoringSourceSqlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.foundation = SQL1.read_text(encoding="utf-8")
        cls.audit = SQL2.read_text(encoding="utf-8")
        cls.text = cls.foundation + "\n" + cls.audit

    def test_source_has_explicit_provider_scope_tenant_binding(self):
        self.assertIn("provider_scope_tenant_binding_id TEXT NOT NULL", self.foundation)
        self.assertIn("UNIQUE (tenant_id, provider_scope_tenant_binding_id)", self.foundation)
        self.assertIn("tenant/logical/binding identity/provider profile is immutable", self.foundation)

    def test_generation_references_shared_provider_instance(self):
        self.assertIn("provider_instance_ref TEXT NOT NULL", self.foundation)
        self.assertIn("may be shared by independent tenant-scoped Monitoring sources", self.foundation)
        self.assertIn("source_instance_generation remains tenant/source historical fencing authority", self.foundation)

    def test_provider_instance_is_not_part_of_tenant_primary_key(self):
        self.assertIn("PRIMARY KEY (tenant_id, monitoring_source_id)", self.foundation)
        self.assertIn("PRIMARY KEY (tenant_id, monitoring_source_id, source_instance_generation)", self.foundation)
        self.assertNotIn("PRIMARY KEY (provider_instance_ref", self.foundation)

    def test_final_create_signature_carries_provider_and_binding_lineage(self):
        self.assertIn("p_provider_scope_tenant_binding_id TEXT", self.audit)
        self.assertIn("p_provider_instance_ref TEXT", self.audit)
        self.assertIn("p_credential_binding_ref TEXT", self.audit)
        self.assertIn("p_configured_provider_scope JSONB", self.audit)

    def test_atomic_create_commits_source_generation_sync_and_audit(self):
        self.assertIn("INSERT INTO monitoring.monitoring_source(", self.audit)
        self.assertIn("INSERT INTO monitoring.monitoring_source_generation(", self.audit)
        self.assertIn("INSERT INTO monitoring.monitoring_sync_operation(", self.audit)
        self.assertIn("INSERT INTO monitoring.monitoring_source_audit_evidence(", self.audit)
        self.assertIn("ON CONFLICT (tenant_id, idempotency_key) DO NOTHING", self.audit)
        self.assertIn("RAISE EXCEPTION 'idempotency.key_reused'", self.audit)

    def test_generation_and_audit_are_immutable(self):
        self.assertIn("Monitoring source generation records are immutable", self.foundation)
        self.assertIn("Monitoring source audit evidence is immutable", self.audit)

    def test_audit_excludes_provider_sensitive_configuration(self):
        audit_table = self.audit[
            self.audit.index("CREATE TABLE monitoring.monitoring_source_audit_evidence ("):
            self.audit.index("COMMENT ON TABLE monitoring.monitoring_source_audit_evidence")
        ]
        for forbidden in (
            "credential_binding_ref",
            "provider_base_url",
            "configured_provider_scope",
            "provider_instance_ref",
        ):
            self.assertNotIn(forbidden, audit_table)

    def test_no_provider_network_side_effect_in_local_transaction(self):
        lowered = self.text.lower()
        for forbidden in ("http_get", "curl ", "wget ", "dblink(", "foreign data wrapper"):
            self.assertNotIn(forbidden, lowered)
        self.assertIn("No provider network call occurs", self.text)


if __name__ == "__main__":
    unittest.main()
