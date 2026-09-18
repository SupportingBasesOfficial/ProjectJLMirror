from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Protocol, Sequence

RESOURCE_READ_ACTION = "monitoring.resource.read"
PROBLEM_READ_ACTION = "monitoring.problem.read"
HEALTH_READ_ACTION = "monitoring.health.read"
MAX_RESPONSE_BYTES = 1048576


@dataclass(frozen=True)
class CurrentAuthorizationEvidence:
    actor_principal_id: str
    actor_principal_kind: str
    actor_generation_ref: str
    authorization_decision_ref: str


@dataclass(frozen=True)
class ProblemRecord:
    problem_id: str
    monitoring_source_id: str
    source_instance_generation: str
    generation_state: str
    monitoring_resource_id: str
    summary: str
    problem_state: str
    severity_class: str
    opened_at: str
    resolved_at: str | None
    last_confirmed_at: str
    evidence_state: str
    provider_object_kind: str | None = None
    provider_external_ref: str | None = None


@dataclass(frozen=True)
class HealthRecord:
    monitoring_resource_id: str
    monitoring_source_id: str
    source_instance_generation: str
    generation_state: str
    scope_state: str
    scope_evidence_state: str
    presence_state: str
    presence_evidence_state: str
    health_class: str
    evidence_state: str
    projection_revision: int | str
    last_changed_at: str
    last_evidence_at: str
    reason_refs: tuple[str, ...]


class CurrentAuthorizationPort(Protocol):
    @property
    def actor_ref(self) -> str: ...
    def require(self, *, actor_ref: str, tenant_id: str, action: str) -> CurrentAuthorizationEvidence: ...


class ProblemHealthReadPort(Protocol):
    def list_problems(
        self,
        *,
        tenant_id: str,
        monitoring_source_id: str | None,
        monitoring_resource_id: str | None,
        generation_state: str,
        problem_state: str | None,
        severity_class: str | None,
        cursor: str | None,
        limit: int,
    ) -> tuple[Sequence[ProblemRecord], str | None]: ...
    def get_problem(self, *, tenant_id: str, problem_id: str) -> ProblemRecord | None: ...
    def list_health(
        self,
        *,
        tenant_id: str,
        monitoring_source_id: str | None,
        generation_state: str,
        health_class: str | None,
        evidence_state: str | None,
        scope_state: str | None,
        cursor: str | None,
        limit: int,
    ) -> tuple[Sequence[HealthRecord], str | None]: ...
    def get_health(self, *, tenant_id: str, monitoring_resource_id: str) -> HealthRecord | None: ...


def _bounded_text(value: str, *, max_length: int, field: str) -> str:
    if not value or len(value) > max_length:
        raise RuntimeError(f"{field} exceeds accepted bound")
    return value


def _validate_cursor(cursor: str | None) -> None:
    if cursor is not None and (not cursor or len(cursor) > 512):
        raise ValueError("cursor must be a bounded non-empty anchor")


def _validate_limit(limit: int) -> None:
    if limit < 1 or limit > 500:
        raise ValueError("limit is outside accepted G5 bound")


def _bounded_response(value: dict) -> dict:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_RESPONSE_BYTES:
        raise RuntimeError("problem/health response exceeds bounded G5 proof profile")
    return value


def _generation(value: str) -> None:
    if value not in {"active_generation", "historical_generation"}:
        raise RuntimeError("invalid generation state")


def _evidence(value: str) -> None:
    if value not in {"current", "stale", "incomplete", "reconciliation_required", "unavailable"}:
        raise RuntimeError("invalid evidence state")


class ProblemHealthView:
    def __init__(self, *, repository: ProblemHealthReadPort, authorization: CurrentAuthorizationPort) -> None:
        self._repository = repository
        self._authorization = authorization

    def _admit(self, tenant_id: str, action: str) -> CurrentAuthorizationEvidence:
        return self._authorization.require(
            actor_ref=self._authorization.actor_ref,
            tenant_id=tenant_id,
            action=action,
        )

    def list_problems(
        self,
        *,
        tenant_id: str,
        monitoring_source_id: str | None = None,
        monitoring_resource_id: str | None = None,
        generation_state: str = "active_generation",
        problem_state: str | None = None,
        severity_class: str | None = None,
        cursor: str | None = None,
        limit: int = 200,
    ) -> dict:
        _validate_cursor(cursor)
        _validate_limit(limit)
        if monitoring_source_id is not None and (not monitoring_source_id or len(monitoring_source_id) > 512):
            raise ValueError("monitoring_source_id is invalid")
        if monitoring_resource_id is not None and (not monitoring_resource_id or len(monitoring_resource_id) > 512):
            raise ValueError("monitoring_resource_id is invalid")
        if generation_state not in {"active_generation", "historical_generation"}:
            raise ValueError("generation_state is invalid")
        if problem_state is not None and problem_state not in {"active", "resolved"}:
            raise ValueError("problem_state is invalid")
        if severity_class is not None and severity_class not in {"unknown", "informational", "warning", "degraded", "critical"}:
            raise ValueError("severity_class is invalid")

        self._admit(tenant_id, PROBLEM_READ_ACTION)
        if monitoring_resource_id is not None:
            self._admit(tenant_id, RESOURCE_READ_ACTION)
        rows, next_cursor = self._repository.list_problems(
            tenant_id=tenant_id,
            monitoring_source_id=monitoring_source_id,
            monitoring_resource_id=monitoring_resource_id,
            generation_state=generation_state,
            problem_state=problem_state,
            severity_class=severity_class,
            cursor=cursor,
            limit=limit,
        )
        rows = tuple(rows)
        self._admit(tenant_id, PROBLEM_READ_ACTION)
        if monitoring_resource_id is not None:
            self._admit(tenant_id, RESOURCE_READ_ACTION)
        if len(rows) > limit:
            raise RuntimeError("problem repository exceeded requested limit")
        return _bounded_response({
            "items": [self._problem(row, detail=False) for row in rows],
            "next_cursor": next_cursor,
        })

    def get_problem(self, *, tenant_id: str, problem_id: str) -> dict | None:
        if not problem_id or len(problem_id) > 512:
            raise ValueError("problem_id is invalid")
        self._admit(tenant_id, PROBLEM_READ_ACTION)
        row = self._repository.get_problem(tenant_id=tenant_id, problem_id=problem_id)
        if row is None:
            self._admit(tenant_id, PROBLEM_READ_ACTION)
            return None
        self._admit(tenant_id, RESOURCE_READ_ACTION)
        self._admit(tenant_id, PROBLEM_READ_ACTION)
        return _bounded_response(self._problem(row, detail=True))

    def list_health(
        self,
        *,
        tenant_id: str,
        monitoring_source_id: str | None = None,
        generation_state: str = "active_generation",
        health_class: str | None = None,
        evidence_state: str | None = None,
        scope_state: str | None = None,
        cursor: str | None = None,
        limit: int = 200,
    ) -> dict:
        _validate_cursor(cursor)
        _validate_limit(limit)
        if monitoring_source_id is not None and (not monitoring_source_id or len(monitoring_source_id) > 512):
            raise ValueError("monitoring_source_id is invalid")
        if generation_state not in {"active_generation", "historical_generation"}:
            raise ValueError("generation_state is invalid")
        if health_class is not None and health_class not in {"unknown", "healthy", "degraded", "unhealthy"}:
            raise ValueError("health_class is invalid")
        if evidence_state is not None and evidence_state not in {"current", "stale", "incomplete", "reconciliation_required", "unavailable"}:
            raise ValueError("evidence_state is invalid")
        if scope_state is not None and scope_state not in {"in_scope", "out_of_scope"}:
            raise ValueError("scope_state is invalid")

        self._admit(tenant_id, HEALTH_READ_ACTION)
        rows, next_cursor = self._repository.list_health(
            tenant_id=tenant_id,
            monitoring_source_id=monitoring_source_id,
            generation_state=generation_state,
            health_class=health_class,
            evidence_state=evidence_state,
            scope_state=scope_state,
            cursor=cursor,
            limit=limit,
        )
        rows = tuple(rows)
        self._admit(tenant_id, HEALTH_READ_ACTION)
        if len(rows) > limit:
            raise RuntimeError("health repository exceeded requested limit")
        return _bounded_response({
            "items": [self._health(row) for row in rows],
            "next_cursor": next_cursor,
        })

    def get_health(self, *, tenant_id: str, monitoring_resource_id: str) -> dict | None:
        if not monitoring_resource_id or len(monitoring_resource_id) > 512:
            raise ValueError("monitoring_resource_id is invalid")
        self._admit(tenant_id, HEALTH_READ_ACTION)
        self._admit(tenant_id, RESOURCE_READ_ACTION)
        row = self._repository.get_health(
            tenant_id=tenant_id,
            monitoring_resource_id=monitoring_resource_id,
        )
        if row is None:
            self._admit(tenant_id, HEALTH_READ_ACTION)
            self._admit(tenant_id, RESOURCE_READ_ACTION)
            return None
        self._admit(tenant_id, HEALTH_READ_ACTION)
        self._admit(tenant_id, RESOURCE_READ_ACTION)
        return _bounded_response(self._health(row))

    @staticmethod
    def _problem(row: ProblemRecord, *, detail: bool) -> dict:
        _generation(row.generation_state)
        _evidence(row.evidence_state)
        if row.problem_state not in {"active", "resolved"}:
            raise RuntimeError("invalid canonical problem state")
        if row.severity_class not in {"unknown", "informational", "warning", "degraded", "critical"}:
            raise RuntimeError("invalid canonical severity")
        if row.problem_state == "active" and row.resolved_at is not None:
            raise RuntimeError("active problem cannot carry resolved_at")
        if row.problem_state == "resolved" and row.resolved_at is None:
            raise RuntimeError("resolved problem requires resolved_at")

        evidence = row.evidence_state
        if row.generation_state == "historical_generation" and evidence == "current":
            evidence = "stale"

        value = {
            "problem_id": row.problem_id,
            "monitoring_source_id": row.monitoring_source_id,
            "source_instance_generation": row.source_instance_generation,
            "generation_state": row.generation_state,
            "monitoring_resource_ids": [row.monitoring_resource_id],
            "summary": _bounded_text(row.summary, max_length=8192, field="problem summary"),
            "problem_state": row.problem_state,
            "severity_class": row.severity_class,
            "opened_at": row.opened_at,
            "resolved_at": row.resolved_at,
            "last_confirmed_at": row.last_confirmed_at,
            "evidence_state": evidence,
        }
        if detail:
            value["external_references"] = {
                "provider_object_kind": row.provider_object_kind,
                "provider_external_ref": row.provider_external_ref,
            }
        return value

    @staticmethod
    def _health(row: HealthRecord) -> dict:
        _generation(row.generation_state)
        _evidence(row.evidence_state)
        if row.health_class not in {"unknown", "healthy", "degraded", "unhealthy"}:
            raise RuntimeError("invalid canonical health class")
        if row.scope_state not in {"in_scope", "out_of_scope"}:
            raise RuntimeError("invalid scope state")
        if row.scope_evidence_state not in {"current", "reconciliation_required"}:
            raise RuntimeError("invalid scope evidence")
        if row.presence_state not in {"present", "removed"}:
            raise RuntimeError("invalid presence state")
        if row.presence_evidence_state not in {"current", "reconciliation_required"}:
            raise RuntimeError("invalid presence evidence")

        evidence = row.evidence_state
        if row.generation_state == "historical_generation" and evidence == "current":
            evidence = "stale"
        if (
            row.scope_state != "in_scope"
            or row.scope_evidence_state != "current"
            or row.presence_state != "present"
            or row.presence_evidence_state != "current"
        ) and evidence == "current":
            evidence = "reconciliation_required"
        if row.health_class == "healthy" and evidence != "current":
            # Preserve retained canonical class, but never present it as current authority.
            pass

        if len(row.reason_refs) > 64 or any((not ref or len(ref) > 512) for ref in row.reason_refs):
            raise RuntimeError("health reason refs exceed accepted bound")

        return {
            "monitoring_resource_id": row.monitoring_resource_id,
            "monitoring_source_id": row.monitoring_source_id,
            "source_instance_generation": row.source_instance_generation,
            "generation_state": row.generation_state,
            "scope_state": row.scope_state,
            "scope_evidence_state": row.scope_evidence_state,
            "health_class": row.health_class,
            "evidence_state": evidence,
            "projection_revision": row.projection_revision,
            "last_changed_at": row.last_changed_at,
            "last_evidence_at": row.last_evidence_at,
            "problem_refs": list(row.reason_refs),
        }
