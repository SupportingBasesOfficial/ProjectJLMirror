from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SQL = ROOT / "sql/integration/001_monitoring_alerting_publication.sql"
MANIFEST = ROOT / "implementation/wave-4-monitoring-alerting-publication-runtime/IMPLEMENTATION_MANIFEST.json"


class MonitoringAlertingPublicationRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = SQL.read_text(encoding="utf-8")
        cls.lower = cls.sql.lower()
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_exact_contracts_and_base(self) -> None:
        self.assertEqual(self.manifest["canonical_base"], "fb7d2e6309df432b133105aa081dc1ef37784820")
        self.assertEqual(
            self.manifest["contracts"],
            ["monitoring.problem-state.changed", "monitoring.health-projection.changed"],
        )

    def test_reuses_existing_wave2_outbox(self) -> None:
        self.assertTrue(self.manifest["reuses_wave2_outbox"])
        self.assertFalse(self.manifest["creates_new_outbox_substrate"])
        self.assertIn("system.async_outbox_message", self.sql)
        self.assertIn("system.async_outbox_dispatch", self.sql)
        self.assertNotIn("CREATE TABLE system.async_outbox_message", self.sql)
        self.assertNotIn("CREATE TABLE system.async_outbox_dispatch", self.sql)

    def test_transition_insert_is_atomic_publication_hook(self) -> None:
        self.assertIn("AFTER INSERT ON monitoring.monitoring_problem_transition", self.sql)
        self.assertIn("AFTER INSERT ON monitoring.health_projection_transition", self.sql)
        self.assertTrue(self.manifest["same_transaction_publication"])
        self.assertTrue(self.manifest["rollback_removes_publication_obligation"])

    def test_problem_payload_is_invalidation_only(self) -> None:
        problem = self.sql[
            self.sql.index("CREATE OR REPLACE FUNCTION monitoring.wave4_publish_problem_transition") :
            self.sql.index("CREATE OR REPLACE FUNCTION monitoring.wave4_publish_health_transition")
        ]
        for required in (
            "'problem_id',NEW.problem_id",
            "'monitoring_source_id',NEW.monitoring_source_id",
            "'source_instance_generation',NEW.source_instance_generation",
            "'monitoring_resource_id',NEW.monitoring_resource_id",
            "'projection_revision',NEW.projection_revision",
            "'problem_transition_id',NEW.problem_transition_id",
        ):
            self.assertIn(required, problem)
        for forbidden in ("'problem_state'", "'severity_class'", "'summary'", "'provider_acknowledged'"):
            self.assertNotIn(forbidden, problem)

    def test_health_payload_is_invalidation_only(self) -> None:
        health = self.sql[
            self.sql.index("CREATE OR REPLACE FUNCTION monitoring.wave4_publish_health_transition") :
            self.sql.index("CREATE TRIGGER monitoring_problem_transition_outbox")
        ]
        for required in (
            "'monitoring_source_id',NEW.monitoring_source_id",
            "'source_instance_generation',NEW.source_instance_generation",
            "'monitoring_resource_id',NEW.monitoring_resource_id",
            "'projection_revision',NEW.projection_revision",
            "'health_transition_id',NEW.health_transition_id",
        ):
            self.assertIn(required, health)
        for forbidden in ("'health_class'", "'health_evidence_state'", "'reason_refs'", "'provider_acknowledged'"):
            self.assertNotIn(forbidden, health)

    def test_phase10_envelope_identities_are_distinct(self) -> None:
        self.assertTrue(self.manifest["message_id_not_correlation_id"])
        self.assertTrue(self.manifest["causation_bound_to_owning_transition"])
        self.assertIn("v_correlation_id := 'monitoring-correlation:'", self.sql)
        self.assertIn("v_causation_id := 'monitoring-transition:'", self.sql)
        self.assertIn("v_correlation_id,v_causation_id", self.sql)
        self.assertIn("monitoring.publication_envelope_identity_collision", self.sql)
        self.assertNotIn("p_occurred_at,NULL,NULL,NULL,NULL,v_message_id,NULL", self.sql)

    def test_same_identity_conflict_fails_closed(self) -> None:
        self.assertTrue(self.manifest["non_equivalent_identity_collision_fails_closed"])
        self.assertIn("monitoring.publication_identity_conflict", self.sql)
        self.assertIn("comparison_evidence IS DISTINCT FROM v_equivalence_bytes", self.sql)
        self.assertIn("encoded_payload IS DISTINCT FROM v_payload_bytes", self.sql)
        self.assertIn("correlation_id IS DISTINCT FROM v_correlation_id", self.sql)
        self.assertIn("causation_id IS DISTINCT FROM v_causation_id", self.sql)

    def test_recovery_reuses_exact_transition(self) -> None:
        self.assertTrue(self.manifest["recovery_reuses_transition_identity"])
        self.assertIn("recover_problem_state_publication", self.sql)
        self.assertIn("problem_transition_id=p_problem_transition_id", self.sql)
        self.assertIn("recover_health_projection_publication", self.sql)
        self.assertIn("health_transition_id=p_health_transition_id", self.sql)
        self.assertIn("ON CONFLICT (outbox_record_id) DO NOTHING", self.sql)

    def test_alerting_mutation_remains_blocked(self) -> None:
        self.assertFalse(self.manifest["alerting_business_mutation_authorized"])
        self.assertNotIn("INSERT INTO alerting.", self.sql)
        self.assertNotIn("UPDATE alerting.", self.sql)
        self.assertNotIn("DELETE FROM alerting.", self.sql)

    def test_dedicated_executor_is_nonlogin_and_nonbypass(self) -> None:
        self.assertIn(
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS",
            self.sql,
        )
        self.assertIn("OWNER TO jlmirror_wave4_monitoring_publication_executor", self.sql)


if __name__ == "__main__":
    unittest.main()
