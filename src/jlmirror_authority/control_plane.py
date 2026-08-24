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
from .runtime_profiles import (
    API_AUTH_BOUNDARY,
    CONTROL_PLANE,
    RuntimeBinding,
    WAVE1_RUNTIME_BINDINGS,
)

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$")
_PROFILE_ID_RE = re.compile(r"^[a-z][a-z0-9-]*(?:\.[a-z0-9-]+)+@[1-9][0-9]*$")
_HUMAN_PRINCIPAL_KINDS = frozenset(
    {PrincipalKind.HUMAN_BROWSER_SESSION, PrincipalKind.PLATFORM_ADMIN_PRINCIPAL}
)
_PRIVILEGED_AUDIT_CLASSES = frozenset({AuditClass.PRIVILEGED, AuditClass.SECURITY_CRITICAL})


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


def _profile_id(value: object, field: str, prefix: str) -> str:
    if not isinstance(value, str) or not _PROFILE_ID_RE.fullmatch(value) or not value.startswith(prefix):
        raise ValueError(f"{field} must be a canonical {prefix} profile id")
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
    """Trusted Control-Plane/cell-admission evidence, never caller input.

    `isolation_class` is the tenant placement/isolation class. The distinct
    `runtime_isolation_class` is the Phase 13 process/runtime profile binding.
    """

    tenant_id: str
    cell_id: str
    placement_version: str
    runtime_generation: str
    runtime_profile_id: str
    runtime_isolation_class: str
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
        _profile_id(self.runtime_profile_id, "runtime_profile_id", "runtime.")
        _profile_id(
            self.runtime_isolation_class,
            "runtime_isolation_class",
            "isolation.",
        )
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


@dataclass(frozen=True)
class RuntimeExecutionEvidence:
    """Trusted evidence for the runtime that is actually executing this admission.

    A caller-selected RuntimeBinding is an expected contract only. It does not
    establish where the code is executing. This record is accepted only when it
    is returned by the owning current-runtime authority port.
    """

    runtime_profile_id: str
    principal_class: str
    isolation_class: str
    ingress_profile: str
    runtime_generation: str
    environment_class: EnvironmentClass
    runtime_lifecycle: RuntimeLifecycle
    current: bool

    def __post_init__(self) -> None:
        _profile_id(self.runtime_profile_id, "runtime_profile_id", "runtime.")
        _profile_id(self.principal_class, "principal_class", "principal.")
        _profile_id(self.isolation_class, "isolation_class", "isolation.")
        _profile_id(self.ingress_profile, "ingress_profile", "ingress.")
        _identifier(self.runtime_generation, "runtime_generation")
        if not isinstance(self.environment_class, EnvironmentClass):
            raise ValueError("environment_class must be canonical")
        if not isinstance(self.runtime_lifecycle, RuntimeLifecycle):
            raise ValueError("runtime_lifecycle must be canonical")
        _strict_bool(self.current, "current")


class CurrentPrincipalAuthorityPort(Protocol):
    def is_current(self, *, principal: Principal, now: datetime) -> bool:
        """Prove current session/credential/workload-principal authority.

        A typed Principal or earlier authentication success is not currentness
        evidence. Implementations bind this port to the owning session, credential,
        workload-identity or platform-principal authority and return literal True
        only for the exact principal + credential generation at `now`.
        """


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


class CurrentRuntimeAuthorityPort(Protocol):
    def resolve_current_execution(self, *, now: datetime) -> RuntimeExecutionEvidence | None:
        """Return trusted evidence for the runtime actually executing admission."""


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("time must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _require_current_principal(
    *,
    principal: Principal,
    principal_authority: CurrentPrincipalAuthorityPort,
    now: datetime,
) -> None:
    """Fail closed unless the owning credential/session authority says exact current."""

    if not isinstance(principal, Principal) or principal.active is not True:
        raise AdmissionDenied("current authenticated principal cannot be established")
    if principal_authority is None or not hasattr(principal_authority, "is_current"):
        raise AdmissionDenied("current principal/credential authority is unavailable")
    try:
        current = principal_authority.is_current(principal=principal, now=_utc(now))
    except Exception as exc:
        raise AdmissionDenied("current principal/credential authority failed closed") from exc
    if current is not True:
        raise AdmissionDenied("principal/session/credential generation is not current")


def _placement_is_admissible(evidence: PlacementEvidence) -> bool:
    return (
        evidence.runtime_lifecycle is RuntimeLifecycle.ACTIVE
        and evidence.placement_current is True
        and evidence.operation_eligible is True
        and evidence.cell_admission_current is True
        and type(evidence.fence_epoch) is int
        and evidence.fence_epoch > 0
    )


def _placement_matches_runtime_binding(
    evidence: PlacementEvidence, runtime_binding: RuntimeBinding
) -> bool:
    return (
        evidence.runtime_profile_id == runtime_binding.runtime_profile_id
        and evidence.runtime_isolation_class == runtime_binding.isolation_class
        and evidence.environment_class in runtime_binding.allowed_environment_classes
    )


def _context_matches_runtime_binding(
    context: TenantContext, runtime_binding: RuntimeBinding
) -> bool:
    return (
        context.runtime_profile_id == runtime_binding.runtime_profile_id
        and context.runtime_isolation_class == runtime_binding.isolation_class
        and context.environment_class in runtime_binding.allowed_environment_classes
    )


def _placement_matches_context(evidence: PlacementEvidence, context: TenantContext) -> bool:
    return (
        _placement_is_admissible(evidence)
        and evidence.tenant_id == context.tenant_id
        and evidence.cell_id == context.cell_id
        and evidence.placement_version == context.placement_version
        and evidence.runtime_generation == context.runtime_generation
        and evidence.runtime_profile_id == context.runtime_profile_id
        and evidence.runtime_isolation_class == context.runtime_isolation_class
        and evidence.configuration_generation == context.configuration_generation
        and evidence.workload_credential_generation == context.workload_credential_generation
        and evidence.network_policy_generation == context.network_policy_generation
        and evidence.environment_class is context.environment_class
        and evidence.isolation_class == context.isolation_class
        and evidence.fence_scope_id == context.fence_scope_id
        and evidence.fence_epoch == context.fence_epoch
    )


def _require_wave1_runtime_binding(runtime_binding: RuntimeBinding) -> None:
    if not isinstance(runtime_binding, RuntimeBinding) or runtime_binding not in WAVE1_RUNTIME_BINDINGS:
        raise AdmissionDenied("runtime binding is not an exact accepted Wave 1 profile")


def _require_current_runtime_execution(
    *,
    runtime_binding: RuntimeBinding,
    runtime_authority: CurrentRuntimeAuthorityPort | None,
    now: datetime,
) -> RuntimeExecutionEvidence:
    """Prove actual current execution matches an accepted runtime binding."""

    _require_wave1_runtime_binding(runtime_binding)
    if runtime_authority is None or not hasattr(runtime_authority, "resolve_current_execution"):
        raise AdmissionDenied("trusted current executing-runtime authority is unavailable")
    try:
        evidence = runtime_authority.resolve_current_execution(now=_utc(now))
    except Exception as exc:
        raise AdmissionDenied("current executing-runtime authority failed closed") from exc
    if not isinstance(evidence, RuntimeExecutionEvidence):
        raise AdmissionDenied("executing-runtime authority returned malformed evidence")
    if evidence.current is not True or evidence.runtime_lifecycle is not RuntimeLifecycle.ACTIVE:
        raise AdmissionDenied("executing runtime is not current and active")
    if (
        evidence.runtime_profile_id != runtime_binding.runtime_profile_id
        or evidence.principal_class != runtime_binding.principal_class
        or evidence.isolation_class != runtime_binding.isolation_class
        or evidence.ingress_profile != runtime_binding.ingress_profile
    ):
        raise AdmissionDenied("executing runtime does not match the required authority boundary")
    try:
        runtime_binding.admit_environment(evidence.environment_class)
    except AdmissionDenied:
        raise
    except Exception as exc:
        raise AdmissionDenied("executing runtime environment authority failed closed") from exc
    return evidence


def _require_privileged_human_assurance_declaration(
    principal: Principal, declaration: AuthorizationDeclaration
) -> None:
    if (
        principal.kind in _HUMAN_PRINCIPAL_KINDS
        and declaration.audit_class in _PRIVILEGED_AUDIT_CLASSES
        and declaration.step_up is StepUpClass.NONE
    ):
        raise AdmissionDenied(
            "privileged human operation requires explicit current authentication-strength policy"
        )


def _require_declared_authentication_strength(
    *,
    principal: Principal,
    declaration: AuthorizationDeclaration,
    strength_policy: AuthenticationStrengthPolicyPort | None,
    strength_evidence: AuthenticationStrengthEvidence | None,
    now: datetime,
) -> None:
    if declaration.step_up is StepUpClass.NONE:
        return
    if not declaration.authentication_strength_policy_id or strength_policy is None:
        raise AdmissionDenied("required authentication-strength authority is unavailable")
    require_authentication_strength(
        policy=strength_policy,
        policy_id=declaration.authentication_strength_policy_id,
        evidence=strength_evidence,
        principal=principal,
        now=_utc(now),
    )


def _evaluate_current_authorization(
    *,
    authorization_authority: CurrentAuthorizationPort,
    principal: Principal,
    context: TenantContext | None,
    declaration: AuthorizationDeclaration,
+) -> AuthorizationDecision:
    try:
        decision = authorization_authority.evaluate(
            principal=principal,
            context=context,
            declaration=declaration,
        )
    except Exception as exc:
        raise AdmissionDenied("owning authorization authority failed closed") from exc
    if not isinstance(decision, AuthorizationDecision):
        raise AdmissionDenied("owning authorization returned malformed authority evidence")
    if decision.current is not True:
        raise AdmissionDenied("owning authorization evidence is not current")
    if decision.granted is not True:
        raise AdmissionDenied("owning authorization denied the operation")
    return decision


def construct_tenant_context(
    *,
    principal: Principal,
    principal_authority: CurrentPrincipalAuthorityPort,
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
    """Construct TenantContext only after current authentication + trusted runtime authority."""

    _require_current_principal(
        principal=principal,
        principal_authority=principal_authority,
        now=now,
    )
    _require_wave1_runtime_binding(runtime_binding)
    if not isinstance(required_environment, EnvironmentClass):
        raise AdmissionDenied("destination runtime environment authority is not canonical")

    try:
        tenant_id = _identifier(tenant_id, "tenant_id")
        destination_cell_id = _identifier(destination_cell_id, "destination_cell_id")
        destination_runtime_generation = _identifier(
            destination_runtime_generation, "destination_runtime_generation"
        )
        destination_configuration_generation = _identifier(
            destination_configuration_generation, "destination_configuration_generation"
        )
        destination_workload_credential_generation = _identifier(
            destination_workload_credential_generation,
            "destination_workload_credential_generation",
        )
        destination_network_policy_generation = _identifier(
            destination_network_policy_generation, "destination_network_policy_generation"
        )
    except ValueError as exc:
        raise AdmissionDenied(
            "tenant/destination authority lookup input is not canonical"
        ) from exc

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
    if not _placement_matches_runtime_binding(evidence, runtime_binding):
        raise AdmissionDenied("placement runtime profile/isolation does not match this authority boundary")
    if not _placement_is_admissible(evidence):
        raise AdmissionDenied("placement/runtime/cell admission currentness cannot be proven")

    # Recheck after placement lookup so a session/credential revoked during routing
    # cannot be converted into a newly trusted TenantContext.
    _require_current_principal(
        principal=principal,
        principal_authority=principal_authority,
        now=now,
    )

    try:
        return TenantContext(
            tenant_id=tenant_id,
            principal_id=principal.principal_id,
            principal_kind=principal.kind,
            principal_credential_generation=principal.credential_generation,
            cell_id=evidence.cell_id,
            placement_version=evidence.placement_version,
            runtime_generation=evidence.runtime_generation,
            runtime_profile_id=evidence.runtime_profile_id,
            runtime_isolation_class=evidence.runtime_isolation_class,
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
    principal_authority: CurrentPrincipalAuthorityPort,
    declaration: AuthorizationDeclaration,
    placement_authority: PlacementAuthorityPort,
    authorization_authority: CurrentAuthorizationPort,
    context: TenantContext | None,
    now: datetime,
    strength_policy: AuthenticationStrengthPolicyPort | None = None,
    strength_evidence: AuthenticationStrengthEvidence | None = None,
    runtime_binding: RuntimeBinding = API_AUTH_BOUNDARY,
    runtime_authority: CurrentRuntimeAuthorityPort | None = None,
) -> AuthorizationDecision:
    _require_current_principal(
        principal=principal,
        principal_authority=principal_authority,
        now=now,
    )
    if not isinstance(declaration, AuthorizationDeclaration):
        raise AdmissionDenied("authorization declaration is malformed or unreviewed")
    _require_wave1_runtime_binding(runtime_binding)
    _require_privileged_human_assurance_declaration(principal, declaration)

    requirement = declaration.tenant_requirement
    if requirement is TenantRequirement.REQUIRED and context is None:
        raise AdmissionDenied("protected operation requires trusted TenantContext")
    if requirement is TenantRequirement.EXPLICIT_CROSS_TENANT_PRIVILEGED:
        if runtime_binding != CONTROL_PLANE:
            raise AdmissionDenied(
                "cross-tenant privileged platform authority requires the accepted Control Plane runtime boundary"
            )
        _require_current_runtime_execution(
            runtime_binding=CONTROL_PLANE,
            runtime_authority=runtime_authority,
            now=now,
        )
        if context is not None:
            raise AdmissionDenied("cross-tenant privileged platform operation cannot reuse ordinary TenantContext")
        if principal.kind is not PrincipalKind.PLATFORM_ADMIN_PRINCIPAL:
            raise AdmissionDenied("cross-tenant privileged operation requires platform principal")
        if declaration.audit_class not in {AuditClass.PRIVILEGED, AuditClass.SECURITY_CRITICAL}:
            raise AdmissionDenied("cross-tenant privileged operation lacks privileged audit class")

    if context is not None:
        if not isinstance(context, TenantContext) or not context.matches_principal(principal):
            raise AdmissionDenied("TenantContext principal binding does not match current principal")
        if not _context_matches_runtime_binding(context, runtime_binding):
            raise AdmissionDenied("TenantContext runtime profile/isolation does not match this authority boundary")
        if placement_authority.context_is_current(context) is not True:
            raise AdmissionDenied("TenantContext placement/currentness narrowing gate denied")
        current_placement = placement_authority.resolve_current(context.tenant_id)
        if not isinstance(current_placement, PlacementEvidence) or not _placement_matches_context(
            current_placement, context
        ):
            raise AdmissionDenied("TenantContext no longer matches exact current runtime/placement authority")
        if not _placement_matches_runtime_binding(current_placement, runtime_binding):
            raise AdmissionDenied("current placement no longer matches this runtime authority boundary")
    if declaration.scope in {ScopeClass.TENANT, ScopeClass.RESOURCE} and context is None:
        raise AdmissionDenied("tenant/resource scope requires current TenantContext")

    _require_declared_authentication_strength(
        principal=principal,
        declaration=declaration,
        strength_policy=strength_policy,
        strength_evidence=strength_evidence,
        now=now,
    )

    # Recheck current credential/session after placement and step-up evaluation,
    # immediately before the owning authorization decision.
    _require_current_principal(
        principal=principal,
        principal_authority=principal_authority,
        now=now,
    )
    _evaluate_current_authorization(
        authorization_authority=authorization_authority,
        principal=principal,
        context=context,
        declaration=declaration,
    )

    # Placement/currentness can change while the owning authorization authority
    # evaluates policy (for example during tenant relocation). A decision computed
    # over a context that became stale must never be returned as admitted.
    if context is not None:
        if placement_authority.context_is_current(context) is not True:
            raise AdmissionDenied("TenantContext became stale during authorization")
        final_placement = placement_authority.resolve_current(context.tenant_id)
        if not isinstance(final_placement, PlacementEvidence) or not _placement_matches_context(
            final_placement, context
        ):
            raise AdmissionDenied("placement/runtime authority changed during authorization")
        if not _placement_matches_runtime_binding(final_placement, runtime_binding):
            raise AdmissionDenied("current placement no longer matches this runtime authority boundary")

    # Security-owned authentication-strength policy can harden while the owning
    # authorization decision is being evaluated. Revalidate the same principal-
    # bound assurance immediately before final protected-operation admission.
    _require_declared_authentication_strength(
        principal=principal,
        declaration=declaration,
        strength_policy=strength_policy,
        strength_evidence=strength_evidence,
        now=now,
    )

    # A credential/session revoked while authorization was being evaluated cannot
    # be converted into a successful protected-operation admission.
    _require_current_principal(
        principal=principal,
        principal_authority=principal_authority,
        now=now,
    )

    # The earlier owning-authorization result is only a snapshot. Re-evaluate it
    # last, after every other currentness check, so a membership/permission revoke
    # during placement/assurance/principal validation cannot survive admission.
    # The returned decision is still not durable protected-effect authority; an
    # effect boundary must consume the applicable current/atomic authority model.
    return _evaluate_current_authorization(
        authorization_authority=authorization_authority,
        principal=principal,
        context=context,
        declaration=declaration,
    )
