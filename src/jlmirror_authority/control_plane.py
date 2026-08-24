from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Protocol

from .browser import AuthenticationStrengthPolicyPort, require_authentication_strength
from .model import (
    AdmissionDenied,
    AuditClass,
    AuthenticationStrengthEvidence,
    AuthorizationDeclaration,
    EnvironmentClass,
    Principal,
    PrincipalKind,
    ScopeClass,
    StepUpClass,
    TenantContext,
    TenantRequirement,
)
from .runtime_profiles import API_AUTH_BOUNDARY, RuntimeBinding, WAVE1_RUNTIME_BINDINGS

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$")


class RuntimeLifecycle(str, Enum):
    PROVISIONING = "provisioning"
    VALIDATING = "validating"
    ADMITTED = "admitted"
    ACTIVE = "active"
    DRAINING = "draining"
    QUARANTINED = "quarantined"
    RETIRED = "retired"
    FAILED = "failed"


def _identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise ValueError(f"{field} must be an explicit canonical identifier")
    return value


def _strict_bool(value: object, field: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{field} must be a boolean")
    return value


def _strict_positive_int(value: object, field: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


@dataclass(frozen=True)
class PlacementEvidence:
    """Trusted Control-Plane/cell-admission evidence, never caller input."""

    tenant_id: str
    cell_id: str
    placement_version: str
    runtime_generation: str
    configuration_generation: str
    workload_credential_generation: str
    network_policy_generation: str
    environment_class: EnvironmentClass
    isolation_class: str
    runtime_lifecycle: RuntimeLifecycle
    placement_current: bool
    operation_eligible: bool
    cell_admission_current: bool
    fence_scope_id: str
    fence_epoch: int

    def __post_init__(self) -> None:
        for field in (
            "tenant_id",
            "cell_id",
            "placement_version",
            "runtime_generation",
            "configuration_generation",
            "workload_credential_generation",
            "network_policy_generation",
            "isolation_class",
            "fence_scope_id",
        ):
            _identifier(getattr(self, field), field)
        if not isinstance(self.environment_class, EnvironmentClass):
            raise ValueError("environment_class must be canonical")
        if not isinstance(self.runtime_lifecycle, RuntimeLifecycle):
            raise ValueError("runtime_lifecycle must be canonical")
        _strict_bool(self.placement_current, "placement_current")
        _strict_bool(self.operation_eligible, "operation_eligible")
        _strict_bool(self.cell_admission_current, "cell_admission_current")
        _strict_positive_int(self.fence_epoch, "fence_epoch")


@dataclass(frozen=True)
class AuthorizationDecision:
    granted: bool
    current: bool
    policy_revision: str

    def __post_init__(self) -> None:
        _strict_bool(self.granted, "granted")
        _strict_bool(self.current, "current")
        _identifier(self.policy_revision, "policy_revision")


class PlacementAuthorityPort(Protocol):
    def resolve_current(self, tenant_id: str) -> PlacementEvidence | None:
        """Resolve trusted current placement from the owning authority."""

    def context_is_current(self, context: TenantContext) -> bool:
        """Optional narrowing/deny signal; only literal True can pass."""


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
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("time must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _placement_is_admissible(evidence: PlacementEvidence) -> bool:
    return (
        evidence.runtime_lifecycle is RuntimeLifecycle.ACTIVE
        and evidence.placement_current is True
        and evidence.operation_eligible is True
        and evidence.cell_admission_current is True
        and type(evidence.fence_epoch) is int
        and evidence.fence_epoch > 0
    )


def _placement_matches_context(evidence: PlacementEvidence, context: TenantContext) -> bool:
    return (
        _placement_is_admissible(evidence)
        and evidence.tenant_id == context.tenant_id
        and evidence.cell_id == context.cell_id
        and evidence.placement_version == context.placement_version
        and evidence.runtime_generation == context.runtime_generation
        and evidence.configuration_generation == context.configuration_generation
        and evidence.workload_credential_generation == context.workload_credential_generation
        and evidence.network_policy_generation == context.network_policy_generation
        and evidence.environment_class is context.environment_class
        and evidence.isolation_class == context.isolation_class
        and evidence.fence_scope_id == context.fence_scope_id
        and evidence.fence_epoch == context.fence_epoch
    )


def construct_tenant_context(
    *,
    principal: Principal,
    placement_authority: PlacementAuthorityPort,
    tenant_id: str,
    destination_cell_id: str,
    destination_runtime_generation: str,
    destination_configuration_generation: str,
    destination_workload_credential_generation: str,
    destination_network_policy_generation: str,
    required_environment: EnvironmentClass,
    now: datetime,
    request_id: str | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    operation_id: str | None = None,
    runtime_binding: RuntimeBinding = API_AUTH_BOUNDARY,
) -> TenantContext:
    """Construct TenantContext only from authenticated principal + trusted current runtime authority."""

    if not isinstance(principal, Principal) or principal.active is not True:
        raise AdmissionDenied("current authenticated principal cannot be established")
    if not isinstance(runtime_binding, RuntimeBinding) or runtime_binding not in WAVE1_RUNTIME_BINDINGS:
        raise AdmissionDenied("TenantContext runtime binding is not an accepted Wave 1 profile")
    if not isinstance(required_environment, EnvironmentClass):
        raise AdmissionDenied("destination runtime environment authority is not canonical")

    evidence = placement_authority.resolve_current(tenant_id)
    if not isinstance(evidence, PlacementEvidence):
        raise AdmissionDenied("trusted tenant placement cannot be established")
    if evidence.tenant_id != tenant_id:
        raise AdmissionDenied("placement authority returned mismatched tenant")
    if evidence.cell_id != destination_cell_id:
        raise AdmissionDenied("request reached a non-authoritative cell")
    if evidence.runtime_generation != destination_runtime_generation:
        raise AdmissionDenied("destination runtime generation is stale")
    if evidence.configuration_generation != destination_configuration_generation:
        raise AdmissionDenied("destination configuration generation is stale")
    if evidence.workload_credential_generation != destination_workload_credential_generation:
        raise AdmissionDenied("destination workload credential generation is stale")
    if evidence.network_policy_generation != destination_network_policy_generation:
        raise AdmissionDenied("destination network-policy generation is stale")
    if evidence.environment_class is not required_environment:
        raise AdmissionDenied("runtime environment class does not match destination authority")
    runtime_binding.admit_environment(evidence.environment_class)
    if not _placement_is_admissible(evidence):
        raise AdmissionDenied("placement/runtime/cell admission currentness cannot be proven")

    try:
        return TenantContext(
            tenant_id=tenant_id,
            principal_id=principal.principal_id,
            principal_kind=principal.kind,
            principal_credential_generation=principal.credential_generation,
            cell_id=evidence.cell_id,
            placement_version=evidence.placement_version,
            runtime_generation=evidence.runtime_generation,
            configuration_generation=evidence.configuration_generation,
            workload_credential_generation=evidence.workload_credential_generation,
            network_policy_generation=evidence.network_policy_generation,
            environment_class=evidence.environment_class,
            isolation_class=evidence.isolation_class,
            fence_scope_id=evidence.fence_scope_id,
            fence_epoch=evidence.fence_epoch,
            constructed_at=_utc(now),
            request_id=request_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            operation_id=operation_id,
        )
    except (TypeError, ValueError) as exc:
        raise AdmissionDenied("trusted TenantContext evidence is not canonical") from exc


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
    if not isinstance(principal, Principal) or principal.active is not True:
        raise AdmissionDenied("principal/credential is retired or malformed")
    if not isinstance(declaration, AuthorizationDeclaration):
        raise AdmissionDenied("authorization declaration is malformed or unreviewed")

    requirement = declaration.tenant_requirement
    if requirement is TenantRequirement.REQUIRED and context is None:
        raise AdmissionDenied("protected operation requires trusted TenantContext")
    if requirement is TenantRequirement.EXPLICIT_CROSS_TENANT_PRIVILEGED:
        if context is not None:
            raise AdmissionDenied("cross-tenant privileged platform operation cannot reuse ordinary TenantContext")
        if principal.kind is not PrincipalKind.PLATFORM_ADMIN_PRINCIPAL:
            raise AdmissionDenied("cross-tenant privileged operation requires platform principal")
        if declaration.audit_class not in {AuditClass.PRIVILEGED, AuditClass.SECURITY_CRITICAL}:
            raise AdmissionDenied("cross-tenant privileged operation lacks privileged audit class")

    if context is not None:
        if not isinstance(context, TenantContext) or not context.matches_principal(principal):
            raise AdmissionDenied("TenantContext principal binding does not match current principal")
        if placement_authority.context_is_current(context) is not True:
            raise AdmissionDenied("TenantContext placement/currentness narrowing gate denied")
        current_placement = placement_authority.resolve_current(context.tenant_id)
        if not isinstance(current_placement, PlacementEvidence) or not _placement_matches_context(
            current_placement, context
        ):
            raise AdmissionDenied("TenantContext no longer matches exact current runtime/placement authority")
    if declaration.scope in {ScopeClass.TENANT, ScopeClass.RESOURCE} and context is None:
        raise AdmissionDenied("tenant/resource scope requires current TenantContext")

    if declaration.step_up is not StepUpClass.NONE:
        if not declaration.authentication_strength_policy_id or strength_policy is None:
            raise AdmissionDenied("required authentication-strength authority is unavailable")
        require_authentication_strength(
            policy=strength_policy,
            policy_id=declaration.authentication_strength_policy_id,
            evidence=strength_evidence,
            principal=principal,
            now=_utc(now),
        )

    decision = authorization_authority.evaluate(
        principal=principal,
        context=context,
        declaration=declaration,
    )
    if not isinstance(decision, AuthorizationDecision):
        raise AdmissionDenied("owning authorization returned malformed authority evidence")
    if decision.current is not True:
        raise AdmissionDenied("owning authorization evidence is not current")
    if decision.granted is not True:
        raise AdmissionDenied("owning authorization denied the operation")
    return decision