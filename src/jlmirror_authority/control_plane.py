from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol

from .browser import AuthenticationStrengthPolicyPort, require_authentication_strength
from .model import (
    AdmissionDenied,
    AuthenticationStrengthEvidence,
    AuthorizationDeclaration,
    EnvironmentClass,
    Principal,
    ScopeClass,
    StepUpClass,
    TenantContext,
)


class RuntimeLifecycle(str, Enum):
    PROVISIONING = "provisioning"
    VALIDATING = "validating"
    ADMITTED = "admitted"
    ACTIVE = "active"
    DRAINING = "draining"
    QUARANTINED = "quarantined"
    RETIRED = "retired"
    FAILED = "failed"


@dataclass(frozen=True)
class PlacementEvidence:
    """Trusted Control-Plane/cell-admission evidence, never caller input."""

    tenant_id: str
    cell_id: str
    placement_version: str
    runtime_generation: str
    environment_class: EnvironmentClass
    runtime_lifecycle: RuntimeLifecycle
    placement_current: bool
    operation_eligible: bool
    cell_admission_current: bool
    fence_scope_id: str
    fence_epoch: int


@dataclass(frozen=True)
class AuthorizationDecision:
    granted: bool
    current: bool
    policy_revision: str


class PlacementAuthorityPort(Protocol):
    def resolve_current(self, tenant_id: str) -> PlacementEvidence | None:
        """Resolve trusted current placement from the owning authority."""

    def context_is_current(self, context: TenantContext) -> bool:
        """Re-establish current placement/admission for a previously built context."""


class CurrentAuthorizationPort(Protocol):
    def evaluate(
        self,
        *,
        principal: Principal,
        context: TenantContext | None,
        declaration: AuthorizationDeclaration,
    ) -> AuthorizationDecision:
        """Evaluate owning membership/permission/resource policy at current authority."""


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("time must be timezone-aware")
    return value.astimezone(timezone.utc)


def construct_tenant_context(
    *,
    placement_authority: PlacementAuthorityPort,
    tenant_id: str,
    destination_cell_id: str,
    destination_runtime_generation: str,
    required_environment: EnvironmentClass,
    now: datetime,
) -> TenantContext:
    """Construct TenantContext only from trusted placement/admission evidence."""

    evidence = placement_authority.resolve_current(tenant_id)
    if evidence is None:
        raise AdmissionDenied("trusted tenant placement cannot be established")
    if evidence.tenant_id != tenant_id:
        raise AdmissionDenied("placement authority returned mismatched tenant")
    if evidence.cell_id != destination_cell_id:
        raise AdmissionDenied("request reached a non-authoritative cell")
    if evidence.runtime_generation != destination_runtime_generation:
        raise AdmissionDenied("destination runtime generation is stale")
    if evidence.environment_class is not required_environment:
        raise AdmissionDenied("runtime environment class is not eligible for this workload")
    if evidence.runtime_lifecycle is not RuntimeLifecycle.ACTIVE:
        raise AdmissionDenied("runtime lifecycle does not allow normal protected serving")
    if not (evidence.placement_current and evidence.operation_eligible and evidence.cell_admission_current):
        raise AdmissionDenied("placement/admission currentness cannot be proven")
    if evidence.fence_epoch <= 0:
        raise AdmissionDenied("placement fence epoch is invalid")

    return TenantContext(
        tenant_id=tenant_id,
        cell_id=evidence.cell_id,
        placement_version=evidence.placement_version,
        runtime_generation=evidence.runtime_generation,
        environment_class=evidence.environment_class,
        fence_scope_id=evidence.fence_scope_id,
        fence_epoch=evidence.fence_epoch,
        constructed_at=_utc(now),
    )


def authorize_protected_operation(
    *,
    principal: Principal,
    declaration: AuthorizationDeclaration,
    placement_authority: PlacementAuthorityPort,
    authorization_authority: CurrentAuthorizationPort,
    context: TenantContext | None,
    now: datetime,
    strength_policy: AuthenticationStrengthPolicyPort | None = None,
    strength_evidence: AuthenticationStrengthEvidence | None = None,
) -> AuthorizationDecision:
    if not principal.active:
        raise AdmissionDenied("principal/credential is retired")
    if declaration.tenant_required and context is None:
        raise AdmissionDenied("protected operation requires trusted TenantContext")
    if context is not None and not placement_authority.context_is_current(context):
        raise AdmissionDenied("TenantContext placement/currentness is stale")
    if declaration.scope in {ScopeClass.TENANT, ScopeClass.RESOURCE} and context is None:
        raise AdmissionDenied("tenant/resource scope requires current TenantContext")
    if declaration.step_up is not StepUpClass.NONE:
        if not declaration.authentication_strength_policy_id or strength_policy is None:
            raise AdmissionDenied("required authentication-strength authority is unavailable")
        require_authentication_strength(
            policy=strength_policy,
            policy_id=declaration.authentication_strength_policy_id,
            evidence=strength_evidence,
            now=_utc(now),
        )

    decision = authorization_authority.evaluate(
        principal=principal,
        context=context,
        declaration=declaration,
    )
    if not decision.current:
        raise AdmissionDenied("owning authorization evidence is not current")
    if not decision.granted:
        raise AdmissionDenied("owning authorization denied the operation")
    return decision
