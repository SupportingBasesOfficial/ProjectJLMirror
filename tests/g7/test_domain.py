from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"apps/g7-alert-policy-lifecycle"))

from domain import ActiveAlert, PolicyVersion, SourceState, evaluate


def problem_policy() -> PolicyVersion:
    return PolicyVersion(
        tenant_id="tenant-a",policy_id="policy-a",policy_version=1,
        source_kind="monitoring_problem",content_hash="hash-v1",
        problem_min_severity="warning",
    )


def problem_state(*, revision=7, state="active", severity="warning", current=True) -> SourceState:
    return SourceState(
        tenant_id="tenant-a",source_kind="monitoring_problem",source_subject_id="problem-1",
        monitoring_source_id="source-a",monitoring_resource_id="resource-1",
        source_instance_generation="generation-a",
        active_source_instance_generation="generation-a" if current else "generation-b",
        source_evidence_state="current",projection_evidence_state="current",
        projection_revision=revision,problem_state=state,severity_class=severity,
    )


class DomainTests(unittest.TestCase):
    def test_current_problem_match_creates_once_per_decision(self):
        first=evaluate(problem_policy(),problem_state(),None,policy_is_effective=True)
        second=evaluate(problem_policy(),problem_state(),None,policy_is_effective=True)
        self.assertEqual(first.action,"create")
        self.assertEqual(first,second)
        self.assertIsNotNone(first.alert_id)

    def test_noncurrent_source_fails_closed(self):
        decision=evaluate(problem_policy(),problem_state(current=False),None,policy_is_effective=True)
        self.assertEqual(decision.action,"none")

    def test_non_effective_version_cannot_create(self):
        decision=evaluate(problem_policy(),problem_state(),None,policy_is_effective=False)
        self.assertEqual(decision.action,"none")

    def test_pinned_version_can_only_resolve_existing_occurrence_after_recovery(self):
        active=ActiveAlert(
            alert_id="alert-1",tenant_id="tenant-a",policy_id="policy-a",policy_version=1,
            source_kind="monitoring_problem",source_subject_id="problem-1",source_occurrence_revision=7,
        )
        recovered=problem_state(revision=8,state="resolved")
        decision=evaluate(problem_policy(),recovered,active,policy_is_effective=False)
        self.assertEqual(decision.action,"resolve")
        self.assertEqual(decision.alert_id,"alert-1")

    def test_resolved_identity_is_not_an_input_for_reopen(self):
        later=problem_state(revision=9,state="active")
        decision=evaluate(problem_policy(),later,None,policy_is_effective=True)
        self.assertEqual(decision.action,"create")
        self.assertNotEqual(decision.alert_id,"alert-1")

    def test_health_family_is_bounded(self):
        policy=PolicyVersion(
            tenant_id="tenant-a",policy_id="health-a",policy_version=1,
            source_kind="monitoring_health_projection",content_hash="health-v1",
            health_classes=("degraded","unhealthy"),
        )
        state=SourceState(
            tenant_id="tenant-a",source_kind="monitoring_health_projection",
            source_subject_id="resource-1",monitoring_source_id="source-a",
            monitoring_resource_id="resource-1",source_instance_generation="generation-a",
            active_source_instance_generation="generation-a",source_evidence_state="current",
            projection_evidence_state="current",projection_revision=11,health_class="degraded",
        )
        self.assertEqual(evaluate(policy,state,None,policy_is_effective=True).action,"create")


if __name__=="__main__":
    unittest.main()
