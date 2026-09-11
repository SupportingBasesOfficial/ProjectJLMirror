from __future__ import annotations

import unittest
from pathlib import Path

from jlmirror_monitoring.health_projection import (
    EvidenceState,
    HealthClass,
    HealthInput,
    MAX_HEALTH_PAGE_ROWS,
    MAX_HEALTH_REASON_REFS,
    MAX_HEALTH_SERIALIZED_BYTES,
    SeverityClass,
    derive_health,
    semantic_health_change,
)

ROOT = Path(__file__).resolve().parents[2]
SQL = (ROOT / "sql/wave4/047_health_projection.sql").read_text(encoding="utf-8")
AUTH = (ROOT / "implementation/wave-4-health-projection-authorization/AUTHORIZATION.md").read_text(encoding="utf-8")


class HealthProjectionDomainTests(unittest.TestCase):
    def _base(self, **overrides: object) -> HealthInput:
        values: dict[str, object] = {
            "tenant_id": "tenant-1",
            "monitoring_source_id": "source-1",
            "source_instance_generation": "generation-1",
            "monitoring_resource_id": "resource-1",
            "source_is_current": True,
            "resource_present": True,
            "scope_is_current_and_in_scope": True,
            "problem_completeness_is_current": True,
            "evidence_state": EvidenceState.CURRENT,
            "active_problem_severities": (),
            "reason_refs": (),
        }
        values.update(overrides)
        return HealthInput(**values)  # type: ignore[arg-type]

    def test_complete_current_no_problem_is_healthy(self) -> None:
        decision = derive_health(self._base())
        self.assertIs(decision.health_class, HealthClass.HEALTHY)
        self.assertIs(decision.evidence_state, EvidenceState.CURRENT)

    def test_critical_is_unhealthy(self) -> None:
        decision = derive_health(self._base(active_problem_severities=(SeverityClass.CRITICAL,)))
        self.assertIs(decision.health_class, HealthClass.UNHEALTHY)

    def test_warning_or_degraded_is_degraded(self) -> None:
        for severity in (SeverityClass.WARNING, SeverityClass.DEGRADED):
            with self.subTest(severity=severity):
                decision = derive_health(self._base(active_problem_severities=(severity,)))
                self.assertIs(decision.health_class, HealthClass.DEGRADED)

    def test_unknown_problem_prevents_healthy(self) -> None:
        decision = derive_health(self._base(active_problem_severities=(SeverityClass.UNKNOWN,)))
        self.assertIs(decision.health_class, HealthClass.UNKNOWN)

    def test_informational_only_does_not_degrade(self) -> None:
        decision = derive_health(self._base(active_problem_severities=(SeverityClass.INFORMATIONAL,)))
        self.assertIs(decision.health_class, HealthClass.HEALTHY)

    def test_missing_problem_completeness_fails_closed(self) -> None:
        decision = derive_health(self._base(problem_completeness_is_current=False))
        self.assertIs(decision.health_class, HealthClass.UNKNOWN)
        self.assertIs(decision.evidence_state, EvidenceState.RECONCILIATION_REQUIRED)

    def test_removed_or_out_of_scope_cannot_be_current_health(self) -> None:
        for overrides in (
            {"resource_present": False},
            {"scope_is_current_and_in_scope": False},
            {"source_is_current": False},
        ):
            with self.subTest(overrides=overrides):
                decision = derive_health(self._base(**overrides))
                self.assertIsNot(decision.health_class, HealthClass.HEALTHY)
                self.assertIsNot(decision.evidence_state, EvidenceState.CURRENT)

    def test_reason_refs_are_bounded(self) -> None:
        self.assertGreater(MAX_HEALTH_REASON_REFS, 0)
        self.assertGreater(MAX_HEALTH_PAGE_ROWS, 0)
        self.assertGreater(MAX_HEALTH_SERIALIZED_BYTES, 0)
        with self.assertRaises(ValueError):
            derive_health(self._base(reason_refs=tuple(f"p-{i}" for i in range(MAX_HEALTH_REASON_REFS + 1))))

    def test_semantic_change_tracks_health_class_not_refresh_only(self) -> None:
        old = derive_health(self._base())
        refreshed = derive_health(self._base())
        degraded = derive_health(self._base(active_problem_severities=(SeverityClass.WARNING,)))
        self.assertFalse(semantic_health_change(old, refreshed))
        self.assertTrue(semantic_health_change(old, degraded))


class HealthProjectionPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.lower = SQL.lower()

    def test_authority_is_exact_and_provider_neutral(self) -> None:
        self.assertIn("wave4.monitoring-health-projection@1", SQL)
        self.assertIn("introduces no provider polling authority", self.lower)
        self.assertNotIn("problem.get", self.lower)
        self.assertNotIn("event.get", self.lower)
        self.assertNotIn("trigger.get", self.lower)

    def test_projection_and_transition_are_tenant_rls_forced(self) -> None:
        for table in (
            "monitoring.health_projection",
            "monitoring.health_projection_transition",
        ):
            self.assertIn(f"alter table {table} enable row level security", self.lower)
            self.assertIn(f"alter table {table} force row level security", self.lower)

    def test_current_health_requires_complete_problem_evidence_and_current_resource(self) -> None:
        for marker in (
            "snapshot_complete",
            "operation_state='succeeded'",
            "operational_evidence_state='current'",
            "active_source_instance_generation=new.source_instance_generation",
            "configuration_revision=e.configuration_revision",
            "scope_revision=e.scope_revision",
            "presence_state='present'",
            "presence_evidence_state='current'",
            "scope_state='in_scope'",
            "scope_evidence_state='current'",
            "scope_projection_revision=e.scope_revision",
        ):
            self.assertIn(marker, self.lower)

    def test_healthy_rejects_active_health_affecting_problem(self) -> None:
        self.assertIn("healthy cannot coexist with an active health-affecting canonical problem", self.lower)
        self.assertIn("severity_class in ('unknown','warning','degraded','critical')", self.lower)

    def test_projection_identity_and_revision_are_guarded(self) -> None:
        self.assertIn("health projection ownership and canonical identity are immutable", self.lower)
        self.assertIn("health projection revision must advance exactly once", self.lower)
        self.assertIn("health projection transition evidence is immutable", self.lower)

    def test_downstream_authority_is_still_blocked(self) -> None:
        for forbidden in (
            "insert into alert",
            "update alert",
            "insert into itsm",
            "update itsm",
            "health.changed",
        ):
            self.assertNotIn(forbidden, self.lower)
        self.assertIn("HEALTH PROJECTION != ALERTING STATE", AUTH)
        self.assertIn("HEALTH PROJECTION != ITSM STATE", AUTH)


if __name__ == "__main__":
    unittest.main()
