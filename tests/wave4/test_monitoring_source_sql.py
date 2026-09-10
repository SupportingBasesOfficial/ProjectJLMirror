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

    def test_schema_separates_logical_source_from_provider_generation(self):
        self.assertIn("CREATE TABLE monitoring.monitoring_source (", self.foundation)
        self.assertIn("CREATE TABLE monitoring.monitoring_source_generation (", self.foundation)
        self.assertIn("PRIMARY KEY (tenant_id, monitoring_source_id, source_instance_generation)", self.foundation)
        self.assertIn("Monitoring source generation records are immutable", self.foundation)

    def test_mutable_credential_and_scope_live_on_logical_source(self):
        source_start = self.foundation.index("CREATE TABLE monitoring.monitoring_source (")
        generation_start = self.foundation.index("CREATE TABLE monitoring.monitoring_source_generation (")
        sync_start = self.foundation.index("CREATE TABLE monitoring.monitoring_sync_operation (")
        source_block = self.foundation[source_start:generation_start]
        generation_block = self.foundation[generation_start:sync_start]
        self.assertIn("credential_binding_ref TEXT NOT NULL", source_block)
        self.assertIn("configured_provider_scope JSONB NOT NULL", source_block)
        self.assertNotIn("credential_binding_ref", generation_block)
        self.assertNotIn("configured_provider_scope", generation_block)
        self.assertIn("provider_base_url TEXT NOT NULL", generation_block)

    def test_sync_operation_binds_exact_generation(self):
        self.assertIn("CREATE TABLE monitoring.monitoring_sync_operation (", self.foundation)
        self.assertIn("REFERENCES monitoring.monitoring_source_generation(", self.foundation)
        self.assertIn("tenant_id, monitoring_source_id, source_instance_generation", self.foundation)
        self.assertIn("'validation_and_initial_sync'", self.foundation)

    def test_idempotency_is_tenant_scoped_fingerprint_and_audit_bound(self):
        self.assertIn("CREATE TABLE monitoring.monitoring_source_create_idempotency (", self.foundation)
        self.assertIn("PRIMARY KEY (tenant_id, idempotency_key)", self.foundation)
        self.assertIn("request_fingerprint ~ '^[0-9a-f]{64}$'", self.foundation)
        self.assertIn("ADD COLUMN audit_evidence_id TEXT NOT NULL", self.audit)
        self.assertIn("monitoring_source_create_audit_evidence_fk", self.audit)
        self.assertIn("ON CONFLICT (tenant_id, idempotency_key) DO NOTHING", self.audit)
        self.assertIn("RAISE EXCEPTION 'idempotency.key_reused'", self.audit)

    def test_final_create_signature_replaces_non_audited_signature(self):
        self.assertIn("DROP FUNCTION monitoring.create_zabbix_source(", self.audit)
        self.assertIn("p_audit_evidence_id TEXT", self.audit)
        self.assertIn("p_actor_principal_id TEXT", self.audit)
        self.assertIn("p_actor_credential_generation TEXT", self.audit)
        self.assertIn("p_authorization_decision_ref TEXT", self.audit)
        self.assertIn("p_request_correlation_id TEXT", self.audit)

    def test_atomic_create_commits_source_generation_sync_and_audit(self):
        self.assertIn("INSERT INTO monitoring.monitoring_source(", self.audit)
        self.assertIn("INSERT INTO monitoring.monitoring_source_generation(", self.audit)
        self.assertIn("INSERT INTO monitoring.monitoring_sync_operation(", self.audit)
        self.assertIn("INSERT INTO monitoring.monitoring_source_audit_evidence(", self.audit)
        self.assertIn("'monitoring.source.manage', 'privileged'", self.audit)
        self.assertIn("'local_creation_committed'", self.audit)
        self.assertIn("SET state = 'completed', completed_at = transaction_timestamp()", self.audit)
        self.assertIn("RETURN QUERY SELECT existing_source_id, existing_operation_id, existing_state, TRUE", self.audit)
        self.assertIn("RETURN QUERY SELECT p_monitoring_source_id, p_monitoring_sync_operation_id, 'completed'::TEXT, FALSE", self.audit)

    def test_audit_evidence_is_append_only_and_secret_minimized(self):
        self.assertIn("CREATE TABLE monitoring.monitoring_source_audit_evidence (", self.audit)
        self.assertIn("Monitoring source audit evidence is immutable", self.audit)
        self.assertIn("safe_summary = '{\"mutation\":\"create\",\"provider_profile\":\"zabbix\"}'::jsonb", self.audit)
        audit_table = self.audit[
            self.audit.index("CREATE TABLE monitoring.monitoring_source_audit_evidence ("):
            self.audit.index("COMMENT ON TABLE monitoring.monitoring_source_audit_evidence")
        ]
        self.assertNotIn("credential_binding_ref", audit_table)
        self.assertNotIn("provider_base_url", audit_table)
        self.assertNotIn("configured_provider_scope", audit_table)

    def test_initial_persistence_does_not_call_provider_network(self):
        lowered = self.text.lower()
        for forbidden in ("http_get", "curl ", "wget ", "dblink(", "foreign data wrapper"):
            self.assertNotIn(forbidden, lowered)
        self.assertIn("Network-dependent Zabbix validation is deliberately absent", self.foundation)
        self.assertIn("it performs no provider network call", lowered)

    def test_source_identity_and_revisions_fail_closed(self):
        self.assertIn("Monitoring source tenant/logical identity/provider profile is immutable", self.foundation)
        self.assertIn("Monitoring source revisions cannot regress", self.foundation)
        self.assertIn("active_source_instance_generation TEXT NOT NULL", self.foundation)


if __name__ == "__main__":
    unittest.main()
