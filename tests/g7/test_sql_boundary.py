from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SQL=(ROOT/"sql/alerting/001_alert_policy_lifecycle.sql").read_text(encoding="utf-8")
LOWER=SQL.lower()
EXPECTED={
    "alerting.alert_policy",
    "alerting.alert_policy_version",
    "alerting.alert_policy_effective_version",
    "alerting.alert",
    "alerting.alert_transition",
    "alerting.alert_decision",
}


class SqlBoundaryTests(unittest.TestCase):
    def test_exact_relation_surface(self):
        found={
            f"{schema.lower()}.{table.lower()}"
            for schema,table in re.findall(
                r"create\s+table\s+([a-z_][\w]*)\.([a-z_][\w]*)",SQL,re.I
            )
            if schema.lower()=="alerting"
        }
        self.assertEqual(found,EXPECTED)

    def test_all_relations_force_tenant_rls(self):
        for relation in EXPECTED:
            self.assertIn(f"alter table {relation} enable row level security",LOWER)
            self.assertIn(f"alter table {relation} force row level security",LOWER)

    def test_application_role_has_no_table_mutation_grant(self):
        self.assertIn("from public, jlmirror_g7_alerting_invoker",LOWER)
        self.assertNotIn("grant insert on alerting.",LOWER.split("to jlmirror_g7_alerting_invoker")[0][-300:])

    def test_effect_rereads_current_monitoring_owner_state(self):
        self.assertIn("from monitoring.monitoring_problem as p",LOWER)
        self.assertIn("from monitoring.health_projection as h",LOWER)
        self.assertIn("active_source_instance_generation",LOWER)
        self.assertIn("operational_evidence_state",LOWER)
        self.assertIn("currentness_unproven",LOWER)

    def test_lifecycle_and_idempotency_guards_exist(self):
        self.assertIn("g7.resolved_alert_terminal",LOWER)
        self.assertIn("g7.decision_equivalence_conflict",LOWER)
        self.assertIn("alert_one_active_occurrence",LOWER)
        self.assertIn("pg_advisory_xact_lock",LOWER)


if __name__=="__main__":
    unittest.main()
