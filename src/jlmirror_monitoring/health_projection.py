from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable, Sequence


MAX_HEALTH_REASON_REFS = 64
MAX_HEALTH_PAGE_ROWS = 500
MAX_HEALTH_SERIALIZED_BYTES = 1_048_576


class HealthClass(StrEnum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class EvidenceState(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    INCOMPLETE = "incomplete"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    UNAVAILABLE = "unavailable"


class SeverityClass(StrEnum):
    UNKNOWN = "unknown"
    INFORMATIONAL = "informational"
    WARNING = "warning"
    DEGRADED = "degraded"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class HealthInput:
    tenant_id: str
    monitoring_source_id: str
    source_instance_generation: str
    monitoring_resource_id: str
    source_is_current: bool
    resource_present: bool
    scope_is_current_and_in_scope: bool
    problem_completeness_is_current: bool
    evidence_state: EvidenceState
    active_problem_severities: Sequence[SeverityClass]
    reason_refs: Sequence[str] = ()


@dataclass(frozen=True, slots=True)
class HealthDecision:
    health_class: HealthClass
    evidence_state: EvidenceState
    reason_refs: tuple[str, ...]


def _bounded_reason_refs(reason_refs: Iterable[str]) -> tuple[str, ...]:
    refs = tuple(reason_refs)
    if len(refs) > MAX_HEALTH_REASON_REFS:
        raise ValueError("monitoring.health_reason_refs_overflow")
    if any(not ref or len(ref) > 512 for ref in refs):
        raise ValueError("monitoring.health_reason_ref_invalid")
    return refs


def derive_health(value: HealthInput) -> HealthDecision:
    reasons = _bounded_reason_refs(value.reason_refs)

    current_authority = (
        value.source_is_current
        and value.resource_present
        and value.scope_is_current_and_in_scope
        and value.problem_completeness_is_current
        and value.evidence_state is EvidenceState.CURRENT
    )

    severities = set(value.active_problem_severities)

    if SeverityClass.CRITICAL in severities:
        return HealthDecision(
            HealthClass.UNHEALTHY,
            EvidenceState.CURRENT if current_authority else value.evidence_state,
            reasons,
        )

    if SeverityClass.WARNING in severities or SeverityClass.DEGRADED in severities:
        return HealthDecision(
            HealthClass.DEGRADED,
            EvidenceState.CURRENT if current_authority else value.evidence_state,
            reasons,
        )

    if SeverityClass.UNKNOWN in severities:
        return HealthDecision(
            HealthClass.UNKNOWN,
            EvidenceState.CURRENT if current_authority else value.evidence_state,
            reasons,
        )

    # Positive healthy authority is intentionally the strictest branch.
    if current_authority:
        return HealthDecision(HealthClass.HEALTHY, EvidenceState.CURRENT, reasons)

    return HealthDecision(HealthClass.UNKNOWN, value.evidence_state, reasons)


def semantic_health_change(previous: HealthDecision | None, current: HealthDecision) -> bool:
    return previous is None or previous.health_class is not current.health_class
