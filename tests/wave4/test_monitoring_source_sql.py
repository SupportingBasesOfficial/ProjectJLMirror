from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SQL = ROOT / "sql/wave4/001_monitoring_source_foundation.sql"


class MonitoringSourceSqlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SQL.read_text(encoding="utf-8")

    def test_schema_separates_logical_source_from_provider_generation(self):
        self.assertIn("CREATE TABLE monitoring.monitoring_source (", self.text)
        self.assertIn("CREATE TABLE monitoring.monitoring_source_generation (", self.text)
        self.assertIn("PRIMARY KEY (tenant_id, monitoring_source_id, source_instance_generation)", self.text)
        self.assertIn("Monitoring source generation records are immutable", self.text)

    def test_mutable_credential_and_scope_live_on_logical_source(self):
        source_start = self.text.index("CREATE TABLE monitoring.monitoring_source (")
        generation_start = self.text.index("CREATE TABLE monitoring.monitoring_source_generation (")
        sync_start = self.text.index("CREATE TABLE monitoring.monitoring_sync_operation (")
        source_block = self.text[source_start:generation_start]
        generation_block = self.text[generation_start:sync_start]
        self.assertIn("credential_binding_ref TEXT NOT NULL", source_block)
        self.assertIn("configured_provider_scope JSONB NOT NULL", source_block)
        self.assertNotIn("credential_binding_ref", generation_block)
        self.assertNotIn("configured_provider_scope", generation_block)
        self.assertIn("provider_base_url TEXT NOT NULL", generation_block)

    def test_sync_operation_binds_exact_generation(self):
        self.assertIn("CREATE TABLE monitoring.monitoring_sync_operation (", self.text)
        self.assertIn("REFERENCES monitoring.monitoring_source_generation(", self.text)
        self.assertIn("tenant_id, monitoring_source_id, source_instance_generation", self.text)
        self.assertIn("'validation_and_initial_sync'", self.text)

    def test_idempotency_is_tenant_scoped_and_fingerprint_bound(self):
        self.assertIn("CREATE TABLE monitoring.monitoring_source_create_idempotency (", self.text)
        self.assertIn("PRIMARY KEY (tenant_id, idempotency_key)", self.text)
        self.assertIn("request_fingerprint ~ '^[0-9a-f]{64}$'", self.text)
        self.assertIn("ON CONFLICT (tenant_id, idempotency_key) DO NOTHING", self.text)
        self.assertIn("RAISE EXCEPTION 'idempotency.key_reused'", self.text)

    def test_atomic_create_commits_source_generation_and_sync_responsibility(self):
        self.assertIn("CREATE FUNCTION monitoring.create_zabbix_source(", self.text)
        self.assertIn("INSERT INTO monitoring.monitoring_source(", self.text)
        self.assertIn("INSERT INTO monitoring.monitoring_source_generation(", self.text)
        self.assertIn("INSERT INTO monitoring.monitoring_sync_operation(", self.text)
        self.assertIn("SET state = 'completed', completed_at = transaction_timestamp()", self.text)
        self.assertIn("RETURN QUERY SELECT existing_source_id, existing_operation_id, existing_state, TRUE", self.text)
        self.assertIn("RETURN QUERY SELECT p_monitoring_source_id, p_monitoring_sync_operation_id, 'completed'::TEXT, FALSE", self.text)

    def test_initial_persistence_does_not_call_provider_network(self):
        lowered = self.text.lower()
        for forbidden in ("http_get", "curl ", "wget ", "dblink(", "foreign data wrapper"):
            self.assertNotIn(forbidden, lowered)
        self.assertIn("Network-dependent Zabbix validation is deliberately absent", self.text)
        self.assertIn("it performs no provider network call", lowered)

    def test_source_identity_and_revisions_fail_closed(self):
        self.assertIn("Monitoring source tenant/logical identity/provider profile is immutable", self.text)
        self.assertIn("Monitoring source revisions cannot regress", self.text)
        self.assertIn("active_source_instance_generation TEXT NOT NULL", self.text)


if __name__ == "__main__":
    unittest.main()
