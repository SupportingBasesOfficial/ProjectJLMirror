from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Protocol, Sequence

RESOURCE_READ_ACTION = "monitoring.resource.read"
METRIC_READ_ACTION = "monitoring.metric.read"
MAX_HISTORY_WINDOW_SECONDS = 86400
MAX_CANONICAL_VALUE_BYTES = 131072


@dataclass(frozen=True)
class CurrentAuthorizationEvidence:
    actor_principal_id: str
    actor_principal_kind: str
    actor_generation_ref: str
    authorization_decision_ref: str


@dataclass(frozen=True)
class MetricDefinitionRecord:
    metric_definition_id: str
    monitoring_resource_id: str
    monitoring_source_id: str
    source_instance_generation: str
    generation_state: str
    name: str
    value_kind: str
    unit: str
    scope_state: str
    scope_projection_revision: int
    scope_evidence_state: str
    definition_state: str
    provider_object_kind: str | None = None
    provider_external_ref: str | None = None


@dataclass(frozen=True)
class MetricCurrentRecord:
    metric_definition_id: str
    monitoring_resource_id: str
    monitoring_source_id: str
    source_instance_generation: str
    generation_state: str
    scope_state: str
    scope_evidence_state: str
    current_observation_id: str | None
    observed_at: str | None
    accepted_at: str | None
    value_kind: str
    value: object | None
    evidence_state: str
    projection_revision: int | str
    last_changed_at: str | None


@dataclass(frozen=True)
class MetricObservationRecord:
    observation_id: str
    metric_definition_id: str
    monitoring_resource_id: str
    monitoring_source_id: str
    source_instance_generation: str
    observed_at: str
    accepted_at: str
    value_kind: str
    value: object


@dataclass(frozen=True)
class HistoryCoverage:
    state: str
    covered_through: str | None
    gap_refs: tuple[str, ...]


@dataclass(frozen=True)
class HistoryRead:
    definition: MetricDefinitionRecord
    coverage: HistoryCoverage
    observations: tuple[MetricObservationRecord, ...]


class CurrentAuthorizationPort(Protocol):
    @property
    def actor_ref(self) -> str: ...

    def require(
        self,
        *,
        actor_ref: str,
        tenant_id: str,
        action: str,
    ) -> CurrentAuthorizationEvidence: ...


class MetricsReadPort(Protocol):
    def list_definitions(self, *, tenant_id: str, monitoring_resource_id: str) -> Sequence[MetricDefinitionRecord]: ...
    def get_definition(self, *, tenant_id: str, metric_definition_id: str) -> MetricDefinitionRecord | None: ...
    def list_current(self, *, tenant_id: str, monitoring_resource_id: str) -> Sequence[MetricCurrentRecord]: ...
    def get_current(self, *, tenant_id: str, metric_definition_id: str) -> MetricCurrentRecord | None: ...
    def history(
        self,
        *,
        tenant_id: str,
        metric_definition_id: str,
        from_ts: str,
        to_ts: str,
        limit: int,
    ) -> HistoryRead | None: ...


def _parse_utc(value: str) -> datetime:
    if not value or len(value) > 64:
        raise ValueError("timestamp must be bounded UTC ISO-8601 text")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include an offset")
    return parsed.astimezone(timezone.utc)


def _bounded_value(value: object | None) -> object | None:
    if value is None:
        return None
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_CANONICAL_VALUE_BYTES:
        raise RuntimeError("metric value exceeds accepted canonical bound")
    return value


def _require_kind(value_kind: str) -> None:
    if value_kind not in {"number", "integer", "boolean", "string", "text", "log"}:
        raise RuntimeError("unsupported canonical metric value kind")


def _generation(value: str) -> None:
    if value not in {"active_generation", "historical_generation"}:
        raise RuntimeError("invalid generation state")


class MetricsView:
    def __init__(self, *, repository: MetricsReadPort, authorization: CurrentAuthorizationPort) -> None:
        self._repository = repository
        self._authorization = authorization

    def _admit(self, tenant_id: str, action: str) -> CurrentAuthorizationEvidence:
        return self._authorization.require(
            actor_ref=self._authorization.actor_ref,
            tenant_id=tenant_id,
            action=action,
        )

    def _admit_resource_and_metric(self, tenant_id: str) -> None:
        self._admit(tenant_id, RESOURCE_READ_ACTION)
        self._admit(tenant_id, METRIC_READ_ACTION)

    def list_definitions(self, *, tenant_id: str, monitoring_resource_id: str) -> dict:
        if not monitoring_resource_id or len(monitoring_resource_id) > 512:
            raise ValueError("monitoring_resource_id must be bounded non-empty text")
        self._admit_resource_and_metric(tenant_id)
        rows = tuple(self._repository.list_definitions(
            tenant_id=tenant_id,
            monitoring_resource_id=monitoring_resource_id,
        ))
        self._admit_resource_and_metric(tenant_id)
        if len(rows) > 500:
            raise RuntimeError("metric definition list exceeds G4 response bound")
        return {"items": [self._definition(row, detail=False) for row in rows], "next_cursor": None}

    def get_definition(self, *, tenant_id: str, metric_definition_id: str) -> dict | None:
        if not metric_definition_id or len(metric_definition_id) > 512:
            raise ValueError("metric_definition_id must be bounded non-empty text")
        self._admit(tenant_id, METRIC_READ_ACTION)
        row = self._repository.get_definition(
            tenant_id=tenant_id,
            metric_definition_id=metric_definition_id,
        )
        if row is None:
            self._admit(tenant_id, METRIC_READ_ACTION)
            return None
        self._admit_resource_and_metric(tenant_id)
        return self._definition(row, detail=True)

    def list_current(self, *, tenant_id: str, monitoring_resource_id: str) -> dict:
        if not monitoring_resource_id or len(monitoring_resource_id) > 512:
            raise ValueError("monitoring_resource_id must be bounded non-empty text")
        self._admit_resource_and_metric(tenant_id)
        rows = tuple(self._repository.list_current(
            tenant_id=tenant_id,
            monitoring_resource_id=monitoring_resource_id,
        ))
        self._admit_resource_and_metric(tenant_id)
        if len(rows) > 500:
            raise RuntimeError("metric current-state list exceeds G4 response bound")
        return {"items": [self._current(row) for row in rows], "next_cursor": None}

    def get_current(self, *, tenant_id: str, metric_definition_id: str) -> dict | None:
        if not metric_definition_id or len(metric_definition_id) > 512:
            raise ValueError("metric_definition_id must be bounded non-empty text")
        self._admit(tenant_id, METRIC_READ_ACTION)
        row = self._repository.get_current(
            tenant_id=tenant_id,
            metric_definition_id=metric_definition_id,
        )
        if row is None:
            self._admit(tenant_id, METRIC_READ_ACTION)
            return None
        self._admit_resource_and_metric(tenant_id)
        return self._current(row)

    def history(
        self,
        *,
        tenant_id: str,
        metric_definition_id: str,
        from_ts: str,
        to_ts: str,
        limit: int = 200,
    ) -> dict | None:
        if not metric_definition_id or len(metric_definition_id) > 512:
            raise ValueError("metric_definition_id must be bounded non-empty text")
        if limit < 1 or limit > 500:
            raise ValueError("history limit is outside accepted G4 bound")
        start = _parse_utc(from_ts)
        end = _parse_utc(to_ts)
        if start >= end:
            raise ValueError("history window requires from < to")
        if (end - start).total_seconds() > MAX_HISTORY_WINDOW_SECONDS:
            raise ValueError("history window exceeds bounded G4 proof profile")

        self._admit(tenant_id, METRIC_READ_ACTION)
        result = self._repository.history(
            tenant_id=tenant_id,
            metric_definition_id=metric_definition_id,
            from_ts=from_ts,
            to_ts=to_ts,
            limit=limit,
        )
        if result is None:
            self._admit(tenant_id, METRIC_READ_ACTION)
            return None
        self._admit_resource_and_metric(tenant_id)
        _generation(result.definition.generation_state)
        if len(result.observations) > limit:
            raise RuntimeError("history repository exceeded requested limit")
        for row in result.observations:
            if row.metric_definition_id != metric_definition_id:
                raise RuntimeError("cross-metric history union is forbidden")
            if row.source_instance_generation != result.definition.source_instance_generation:
                raise RuntimeError("cross-generation history union is forbidden")

        return {
            "metric_definition_id": metric_definition_id,
            "source_instance_generation": result.definition.source_instance_generation,
            "generation_state": result.definition.generation_state,
            "window": {"from": from_ts, "to": to_ts},
            "completeness": {
                "state": result.coverage.state,
                "covered_through": result.coverage.covered_through,
                "gap_refs": list(result.coverage.gap_refs),
            },
            "items": [self._observation(row) for row in result.observations],
            "next_cursor": None,
        }

    @staticmethod
    def _definition(row: MetricDefinitionRecord, *, detail: bool) -> dict:
        _generation(row.generation_state)
        _require_kind(row.value_kind)
        if row.scope_state not in {"in_scope", "out_of_scope"}:
            raise RuntimeError("invalid metric scope state")
        if row.scope_evidence_state not in {"current", "reconciliation_required"}:
            raise RuntimeError("invalid metric scope evidence")
        if row.definition_state not in {"active", "retired"}:
            raise RuntimeError("invalid metric definition state")
        value = {
            "metric_definition_id": row.metric_definition_id,
            "monitoring_resource_id": row.monitoring_resource_id,
            "monitoring_source_id": row.monitoring_source_id,
            "source_instance_generation": row.source_instance_generation,
            "generation_state": row.generation_state,
            "name": row.name,
            "value_kind": row.value_kind,
            "unit": row.unit or None,
            "scope_state": row.scope_state,
            "scope_projection_revision": row.scope_projection_revision,
            "scope_evidence_state": row.scope_evidence_state,
            "definition_state": row.definition_state,
        }
        if detail:
            value["external_references"] = {
                "provider_object_kind": row.provider_object_kind,
                "provider_external_ref": row.provider_external_ref,
            }
        return value

    @staticmethod
    def _current(row: MetricCurrentRecord) -> dict:
        _generation(row.generation_state)
        _require_kind(row.value_kind)
        evidence = row.evidence_state
        if evidence not in {"current", "stale", "incomplete", "reconciliation_required", "unavailable"}:
            raise RuntimeError("invalid metric current evidence")
        if row.generation_state == "historical_generation" and evidence == "current":
            evidence = "stale"
        if row.scope_state != "in_scope" or row.scope_evidence_state != "current":
            if evidence == "current":
                evidence = "reconciliation_required"
        return {
            "metric_definition_id": row.metric_definition_id,
            "monitoring_resource_id": row.monitoring_resource_id,
            "monitoring_source_id": row.monitoring_source_id,
            "source_instance_generation": row.source_instance_generation,
            "generation_state": row.generation_state,
            "scope_state": row.scope_state,
            "scope_evidence_state": row.scope_evidence_state,
            "current_observation_id": row.current_observation_id,
            "observed_at": row.observed_at,
            "accepted_at": row.accepted_at,
            "value_kind": row.value_kind,
            "value": _bounded_value(row.value),
            "evidence_state": evidence,
            "projection_revision": row.projection_revision,
            "last_changed_at": row.last_changed_at,
        }

    @staticmethod
    def _observation(row: MetricObservationRecord) -> dict:
        _require_kind(row.value_kind)
        return {
            "observation_id": row.observation_id,
            "metric_definition_id": row.metric_definition_id,
            "monitoring_resource_id": row.monitoring_resource_id,
            "monitoring_source_id": row.monitoring_source_id,
            "source_instance_generation": row.source_instance_generation,
            "observed_at": row.observed_at,
            "accepted_at": row.accepted_at,
            "value_kind": row.value_kind,
            "value": _bounded_value(row.value),
        }
