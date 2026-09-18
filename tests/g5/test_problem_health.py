from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"apps/g5-problem-health"))

from problem_health import (  # noqa: E402
    HEALTH_READ_ACTION,
    PROBLEM_READ_ACTION,
    RESOURCE_READ_ACTION,
    HealthRecord,
    ProblemHealthView,
    ProblemRecord,
)


class Authorization:
    def __init__(self) -> None:
        self.actor_ref="principal-a"
        self.calls=[]

    def require(self, *, actor_ref: str, tenant_id: str, action: str):
        self.calls.append((actor_ref,tenant_id,action))
        return object()


def problem(*, state="active", generation="active_generation", evidence="current") -> ProblemRecord:
    return ProblemRecord(
        problem_id="problem-1",
        monitoring_source_id="source-a",
        source_instance_generation="generation-a",
        generation_state=generation,
        monitoring_resource_id="resource-101",
        summary="CPU threshold exceeded",
        problem_state=state,
        severity_class="warning",
        opened_at="2026-09-18T05:00:00Z",
        resolved_at=None if state=="active" else "2026-09-18T05:30:00Z",
        last_confirmed_at="2026-09-18T05:30:00Z",
        evidence_state=evidence,
        provider_object_kind="zabbix_event",
        provider_external_ref="9001",
    )


def health(*, cls="degraded", generation="active_generation", evidence="current") -> HealthRecord:
    return HealthRecord(
        monitoring_resource_id="resource-101",
        monitoring_source_id="source-a",
        source_instance_generation="generation-a",
        generation_state=generation,
        scope_state="in_scope",
        scope_evidence_state="current",
        presence_state="present",
        presence_evidence_state="current",
        health_class=cls,
        evidence_state=evidence,
        projection_revision=3,
        last_changed_at="2026-09-18T05:00:01Z",
        last_evidence_at="2026-09-18T05:10:01Z",
        reason_refs=("problem-1",),
    )


class Repository:
    def __init__(self) -> None:
        self.problem=problem()
        self.health=health()
        self.problem_next=None
        self.health_next=None

    def list_problems(self, **kwargs):
        if kwargs["cursor"]=="invalid":
            raise ValueError("cursor_invalid")
        return (self.problem,), self.problem_next

    def get_problem(self, *, tenant_id: str, problem_id: str):
        return self.problem if tenant_id=="tenant-a" and problem_id=="problem-1" else None

    def list_health(self, **kwargs):
        if kwargs["cursor"]=="invalid":
            raise ValueError("cursor_invalid")
        return (self.health,), self.health_next

    def get_health(self, *, tenant_id: str, monitoring_resource_id: str):
        return self.health if tenant_id=="tenant-a" and monitoring_resource_id=="resource-101" else None


class ProblemHealthTests(unittest.TestCase):
    def test_problem_list_reauthorizes_problem_and_resource_scope(self):
        auth=Authorization()
        view=ProblemHealthView(repository=Repository(),authorization=auth).list_problems(
            tenant_id="tenant-a",
            monitoring_resource_id="resource-101",
        )
        self.assertEqual(view["items"][0]["problem_state"],"active")
        self.assertEqual(auth.calls,[
            ("principal-a","tenant-a",PROBLEM_READ_ACTION),
            ("principal-a","tenant-a",RESOURCE_READ_ACTION),
            ("principal-a","tenant-a",PROBLEM_READ_ACTION),
            ("principal-a","tenant-a",RESOURCE_READ_ACTION),
        ])

    def test_problem_detail_exposes_only_bounded_external_reference(self):
        value=ProblemHealthView(repository=Repository(),authorization=Authorization()).get_problem(
            tenant_id="tenant-a",
            problem_id="problem-1",
        )
        self.assertEqual(value["external_references"]["provider_external_ref"],"9001")
        self.assertNotIn("provider_metadata",value)

    def test_historical_active_problem_never_presents_current_evidence(self):
        repo=Repository()
        repo.problem=problem(generation="historical_generation",evidence="current")
        item=ProblemHealthView(repository=repo,authorization=Authorization()).list_problems(
            tenant_id="tenant-a",
            generation_state="historical_generation",
        )["items"][0]
        self.assertEqual(item["problem_state"],"active")
        self.assertEqual(item["generation_state"],"historical_generation")
        self.assertEqual(item["evidence_state"],"stale")

    def test_resolved_problem_requires_explicit_resolved_timestamp(self):
        repo=Repository()
        repo.problem=replace(problem(state="resolved"),resolved_at=None)
        with self.assertRaises(RuntimeError):
            ProblemHealthView(repository=repo,authorization=Authorization()).get_problem(
                tenant_id="tenant-a",
                problem_id="problem-1",
            )

    def test_health_preserves_class_but_downgrades_historical_authority(self):
        repo=Repository()
        repo.health=health(cls="healthy",generation="historical_generation",evidence="current")
        item=ProblemHealthView(repository=repo,authorization=Authorization()).list_health(
            tenant_id="tenant-a",
            generation_state="historical_generation",
        )["items"][0]
        self.assertEqual(item["health_class"],"healthy")
        self.assertEqual(item["generation_state"],"historical_generation")
        self.assertEqual(item["evidence_state"],"stale")

    def test_out_of_scope_current_health_is_not_current_authority(self):
        repo=Repository()
        repo.health=replace(health(cls="healthy"),scope_state="out_of_scope")
        item=ProblemHealthView(repository=repo,authorization=Authorization()).get_health(
            tenant_id="tenant-a",
            monitoring_resource_id="resource-101",
        )
        self.assertEqual(item["health_class"],"healthy")
        self.assertEqual(item["evidence_state"],"reconciliation_required")

    def test_removed_resource_current_health_is_not_current_authority(self):
        repo=Repository()
        repo.health=replace(health(cls="healthy"),presence_state="removed")
        item=ProblemHealthView(repository=repo,authorization=Authorization()).get_health(
            tenant_id="tenant-a",
            monitoring_resource_id="resource-101",
        )
        self.assertEqual(item["evidence_state"],"reconciliation_required")

    def test_continuation_anchors_are_preserved(self):
        repo=Repository()
        repo.problem_next="problem-next"
        repo.health_next="resource-next"
        service=ProblemHealthView(repository=repo,authorization=Authorization())
        self.assertEqual(service.list_problems(tenant_id="tenant-a")["next_cursor"],"problem-next")
        self.assertEqual(service.list_health(tenant_id="tenant-a")["next_cursor"],"resource-next")

    def test_invalid_anchor_fails_closed(self):
        service=ProblemHealthView(repository=Repository(),authorization=Authorization())
        with self.assertRaises(ValueError):
            service.list_problems(tenant_id="tenant-a",cursor="invalid")
        with self.assertRaises(ValueError):
            service.list_health(tenant_id="tenant-a",cursor="invalid")


if __name__=="__main__":
    unittest.main()
