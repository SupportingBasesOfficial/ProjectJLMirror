from pathlib import Path
import unittest

from jlmirror_monitoring import ConfiguredProviderScope

ROOT = Path(__file__).resolve().parents[2]
SQL3 = ROOT / "sql/wave4/003_monitoring_source_tenant_and_canonical_hardening.sql"


class MonitoringSourceHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hardening = SQL3.read_text(encoding="utf-8")

    def test_direct_scope_construction_cannot_bypass_invariants(self):
        with self.assertRaisesRegex(ValueError, "duplicates"):
            ConfiguredProviderScope(("same", "same"))
        with self.assertRaisesRegex(ValueError, "bounded cardinality"):
            ConfiguredProviderScope(tuple(str(i) for i in range(257)))
        with self.assertRaises(ValueError):
            ConfiguredProviderScope(("group\nadmin",))
        with self.assertRaisesRegex(ValueError, "immutable tuple"):
            ConfiguredProviderScope(["group-linux"])  # type: ignore[arg-type]

    def test_every_wave4_tenant_table_is_fail_closed_by_rls(self):
        for table in (
            "monitoring_source",
            "monitoring_source_generation",
            "monitoring_sync_operation",
            "monitoring_source_create_idempotency",
            "monitoring_source_audit_evidence",
        ):
            with self.subTest(table=table):
                self.assertIn(f"ALTER TABLE monitoring.{table} ENABLE ROW LEVEL SECURITY;", self.hardening)
                self.assertIn(f"ALTER TABLE monitoring.{table} FORCE ROW LEVEL SECURITY;", self.hardening)
        self.assertIn("current_setting('jlmirror.tenant_id', true)", self.hardening)

    def test_scope_change_requires_strict_revision_advance(self):
        self.assertIn(
            "NEW.configured_provider_scope IS DISTINCT FROM OLD.configured_provider_scope",
            self.hardening,
        )
        self.assertIn("NEW.scope_revision <= OLD.scope_revision", self.hardening)
        self.assertIn("Monitoring source scope change requires scope revision advance", self.hardening)

    def test_sql_boundary_uses_network_free_canonical_url_validator(self):
        self.assertIn("CREATE FUNCTION monitoring.wave4_is_canonical_zabbix_base_url", self.hardening)
        self.assertIn("monitoring_source_generation_canonical_base_url", self.hardening)
        self.assertIn("octet_length(p_url) <> length(p_url)", self.hardening)
        self.assertIn("path_segment IN ('.', '..')", self.hardening)
        self.assertNotIn("http_get", self.hardening.lower())
        self.assertNotIn("dblink(", self.hardening.lower())


if __name__ == "__main__":
    unittest.main()
