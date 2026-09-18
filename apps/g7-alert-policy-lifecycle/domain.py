from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

SourceKind = Literal["monitoring_problem", "monitoring_health_projection"]
Lifecycle = Literal["active", "resolved"]
Action = Literal["create", "resolve", "none"]

SEVERITY_ORDER = {
    "unknown": 0,
    "informational": 1,
    "warning": 2,
    "degraded": 3,
    "critical": 4,
}
HEALTH_CLASSES = {"unknown", "healthy", "degraded", "unhealthy"}


@dataclass(frozen=True)
class PolicyVersion:
    tenant_id: str
    policy_id: str
    policy_version: int
    source_kind: SourceKind
    content_hash: str
    problem_min_severity: str | None = None
    health_classes: tuple[str, ...] = ()
    monitoring_source_id: str | None = None
    monitoring_resource_id: str | None = None

    def validate(self) -> None:
        if not self.tenant_id or not self.policy_id or self.policy_version < 1:
            raise ValueError("invalid policy identity")
        if self.source_kind == "monitoring_problem":
            if self.problem_min_severity not in SEVERITY_ORDER or self.health_classes:
                raise ValueError("invalid problem policy")
        elif self.source_kind == "monitoring_health_projection":
            if self.problem_min_severity is not None:
                raise ValueError("invalid health policy")
            if not self.health_classes or not set(self.health_classes) <= HEALTH_CLASSES:
                raise ValueError("invalid health policy")
            if len(set(self.health_classes)) != len(self.health_classes):
                raise ValueError("duplicate health class")
        else:
            raise ValueError("unsupported source kind")


@dataclass(frozen=True)
class SourceState:
    tenant_id: str
    source_kind: SourceKind
    source_subject_id: str
    monitoring_source_id: str
    monitoring_resource_id: str
    source_instance_generation: str
    active_source_instance_generation: str
    source_evidence_state: str
    projection_evidence_state: str
    projection_revision: int
    problem_state: str | None = None
    severity_class: str | None = None
    health_class: str | None = None

    @property
    def current(self) -> bool:
        return (
            self.source_instance_generation == self.active_source_instance_generation
            and self.source_evidence_state == "current"
            and self.projection_evidence_state == "current"
            and self.projection_revision > 0
        )


@dataclass(frozen=True)
class ActiveAlert:
    alert_id: str
    tenant_id: str
    policy_id: str
    policy_version: int
    source_kind: SourceKind
    source_subject_id: str
    source_occurrence_revision: int
    lifecycle_state: Lifecycle = "active"


@dataclass(frozen=True)
class Decision:
    decision_id: str
    decision_hash: str
    action: Action
    policy_id: str
    policy_version: int
    source_kind: SourceKind
    source_subject_id: str
    source_revision: int
    alert_id: str | None


def _matches(policy: PolicyVersion, state: SourceState) -> bool:
    policy.validate()
    if state.tenant_id != policy.tenant_id or state.source_kind != policy.source_kind:
        return False
    if not state.current:
        return False
    if policy.monitoring_source_id and state.monitoring_source_id != policy.monitoring_source_id:
        return False
    if policy.monitoring_resource_id and state.monitoring_resource_id != policy.monitoring_resource_id:
        return False
    if policy.source_kind == "monitoring_problem":
        if state.problem_state != "active" or state.severity_class not in SEVERITY_ORDER:
            return False
        return SEVERITY_ORDER[state.severity_class] >= SEVERITY_ORDER[policy.problem_min_severity or "critical"]
    return state.health_class in set(policy.health_classes)


def evaluate(
    policy: PolicyVersion,
    state: SourceState,
    active: ActiveAlert | None,
    *,
    policy_is_effective: bool,
) -> Decision:
    policy.validate()
    if state.tenant_id != policy.tenant_id:
        raise ValueError("tenant mismatch")
    if state.source_kind != policy.source_kind:
        raise ValueError("source family mismatch")
    if active is not None:
        if (
            active.tenant_id != policy.tenant_id
            or active.policy_id != policy.policy_id
            or active.policy_version != policy.policy_version
            or active.source_kind != policy.source_kind
            or active.source_subject_id != state.source_subject_id
            or active.lifecycle_state != "active"
        ):
            raise ValueError("active alert binding mismatch")

    match = _matches(policy, state)
    if not state.current:
        action: Action = "none"
    elif active is not None and not match:
        action = "resolve"
    elif active is None and match and policy_is_effective:
        action = "create"
    else:
        action = "none"

    material = "\x1f".join(
        (
            policy.tenant_id,
            policy.policy_id,
            str(policy.policy_version),
            policy.content_hash,
            policy.source_kind,
            state.source_subject_id,
            str(state.projection_revision),
            action,
            active.alert_id if active else "",
        )
    )
    decision_hash = sha256(material.encode()).hexdigest()
    decision_id = "g7-decision:" + sha256(
        "\x1f".join(
            (
                policy.tenant_id,
                policy.policy_id,
                str(policy.policy_version),
                policy.source_kind,
                state.source_subject_id,
                str(state.projection_revision),
            )
        ).encode()
    ).hexdigest()
    alert_id = active.alert_id if active else None
    if action == "create":
        alert_id = "g7-alert:" + sha256((decision_id + "\x1f" + policy.content_hash).encode()).hexdigest()

    return Decision(
        decision_id=decision_id,
        decision_hash=decision_hash,
        action=action,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        source_kind=policy.source_kind,
        source_subject_id=state.source_subject_id,
        source_revision=state.projection_revision,
        alert_id=alert_id,
    )
