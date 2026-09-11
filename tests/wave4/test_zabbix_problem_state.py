from __future__ import annotations

import unittest
from pathlib import Path

from jlmirror_monitoring.problem_state import (
    CanonicalProblemState,
    MAX_PROBLEMS_PER_POLL,
    ProblemAssociationTarget,
    ProblemSeverityClass,
    ProviderTag,
    ZabbixProblemEvidence,
    ZabbixRecoveryEvidence,
    normalize_zabbix_severity,
)

ROOT = Path(__file__).resolve().parents[2]
SQL = ROOT / "sql/wave4/042_zabbix_problem_state.sql"
AUTH = ROOT / "implementation/wave-4-problem-state-authorization/AUTHORIZATION.md"


class ProblemStateDomainTests(unittest.TestCase):
    def test_severity_mapping_is_provider_neutral(self) -> None:
        self.assertIs(normalize_zabbix_severity(0), ProblemSeverityClass.UNKNOWN)
        self.assertIs(normalize_zabbix_severity(1), ProblemSeverityClass.INFORMATIONAL)
        self.assertIs(normalize_zabbix_severity(2), ProblemSeverityClass.WARNING)
        self.assertIs(normalize_zabbix_severity(3), ProblemSeverityClass.DEGRADED)
        self.assertIs(normalize_zabbix_severity(4), ProblemSeverityClass.CRITICAL)
        self.assertIs(normalize_zabbix_severity(5), ProblemSeverityClass.CRITICAL)
        with self.assertRaises(ValueError):
            normalize_zabbix_severity(6)

    def test_provider_acknowledgement_remains_metadata(self) -> None:
        row = ZabbixProblemEvidence(
            eventid="100",
            objectid="200",
            clock=1_700_000_000,
            name="CPU high",
            severity=4,
            acknowledged=True,
            tags=(ProviderTag("service", "api"),),
        )
        self.assertTrue(row.acknowledged)
        self.assertEqual(CanonicalProblemState.ACTIVE.value, "active")

    def test_problem_inputs_are_bounded(self) -> None:
        self.assertGreater(MAX_PROBLEMS_PER_POLL, 0)
        with self.assertRaises(ValueError):
            ZabbixProblemEvidence("", "2", 1, "x", 1, False)
        with self.assertRaises(ValueError):
            ProviderTag("", "x")
        with self.assertRaises(ValueError):
            ZabbixRecoveryEvidence("1", "2", 0)
        with self.assertRaises(ValueError):
            ProblemAssociationTarget("", "resource-1")


class ProblemStatePersistenceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = SQL.read_text(encoding="utf-8")
        cls.lower = cls.sql.lower()
        cls.auth = AUTH.read_text(encoding="utf-8")

    def test_authorized_boundary_is_exact(self) -> None:
        self.assertIn("wave4.monitoring-problem-state@1", self.sql)
        self.assertIn("problem.get", self.sql)
        self.assertIn("event.get", self.sql)
        self.assertIn("trigger association", self.lower)

    def test_problem_identity_is_separate_from_provider_identity(self) -> None:
        self.assertIn("create table monitoring.monitoring_problem_provider_binding", self.lower)
        self.assertIn("provider_external_ref text not null", self.lower)
        self.assertIn("problem_id text not null", self.lower)
        self.assertIn("provider eventid is scoped external evidence", self.lower)

    def test_problem_poll_authority_is_independent(self) -> None:
        for marker in (
            "problem_poll_epoch bigint",
            "problem_poll_generation bigint",
            "monitoring_problem_state_runtime_admission",
        ):
            self.assertIn(marker, self.lower)
        self.assertIn("independent from host inventory, metric definitions, current state and metric history", self.lower)

    def test_rls_is_forced_on_problem_state(self) -> None:
        for table in (
            "monitoring.monitoring_problem_state_runtime_admission",
            "monitoring.monitoring_problem_provider_binding",
            "monitoring.monitoring_problem",
            "monitoring.monitoring_problem_transition",
        ):
            self.assertIn(f"alter table {table} enable row level security", self.lower)
            self.assertIn(f"alter table {table} force row level security", self.lower)

    def test_downstream_authorities_do_not_leak_into_slice(self) -> None:
        self.assertNotIn("insert into alert", self.lower)
        self.assertNotIn("update alert", self.lower)
        self.assertNotIn("insert into itsm", self.lower)
        self.assertNotIn("update itsm", self.lower)
        self.assertNotIn("health_projection", self.lower)
        self.assertIn("health, alerting, itsm, provider write-back, frontend", self.lower)

    def test_resolved_identity_does_not_reopen(self) -> None:
        self.assertIn("resolved problem cannot be reopened under the same canonical provider event identity", self.lower)


if __name__ == "__main__":
    unittest.main()
