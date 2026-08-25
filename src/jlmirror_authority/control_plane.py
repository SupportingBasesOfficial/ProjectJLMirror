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


def _optional_identifier(value: object, field: str) -> str | None:
    if value is None:
        return None
    return _identifier(value, field)


def _profile_id(value: object, field: str, prefix: str) -> str:
    if not isinstance(value, str) or not _PROFILE_ID_RE.fullmatch(value) or not value.startswith(prefix):
        raise ValueError(f"{field} must be a canonical {prefix} profile id")
    return value


def _optional_profile_id(value: object, field: str, prefix: str) -> str | None:
    if value is None:
        return None
    return _profile_id(value, field, prefix)


def _strict_bool(value: object, field: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{field} must be a boolean")
    return value


def _strict_positive_int(value: object, field: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("time must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class PlacementEvidence:
    """Trusted Control-Plane/cell-admission evidence, never caller input."""

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
        _profile_id(self.runtime_isolation_class, "runtime_isolation_class", "isolation.")
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
    """Trusted evidence for the runtime actually executing this admission."""

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


@dataclass(frozen=True)
class CrossTenantTargetBinding:
    """Canonical target authority input for a cross-tenant privileged operation.

    Exactly one mode is used: an explicit non-empty tenant-id set or an accepted
    selection-criteria identifier. This object is request/operation input, not
    authority by itself; the final admission authority must authorize and echo the
    exact canonical binding in its revision-bound evidence.
    """

    target_tenant_ids: tuple[str, ...] = ()
    selection_criteria_id: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.target_tenant_ids, (str, bytes)):
            raise ValueError("cross-tenant target ids must be an explicit collection")
        try:
            target_ids = tuple(self.target_tenant_ids)
        except TypeError as exc:
            raise ValueError("cross-tenant target ids must be an explicit collection") from exc
        for tenant_id in target_ids:
            _identifier(tenant_id, "cross_tenant_target_tenant_id")
        if len(set(target_ids)) != len(target_ids):
            raise ValueError("cross-tenant target ids cannot contain duplicates")
        target_ids = tuple(sorted(target_ids))
        object.__setattr__(self, "target_tenant_ids", target_ids)
        _optional_identifier(self.selection_criteria_id, "cross_tenant_selection_criteria_id")
        explicit_mode = bool(target_ids)
        selection_mode = self.selection_criteria_id is not None
        if explicit_mode is selection_mode:
            raise ValueError(
                "cross-tenant target binding requires exactly one of explicit tenant ids or selection criteria"
            )


@dataclass(frozen=True)
class FinalAdmissionEvidence:
    """One revision-bound final admission snapshot from trusted current authorities.

    The implementation behind FinalAdmissionAuthorityPort owns its current clock
    and SHALL re-establish all applicable authority dimensions as one atomic or
    revision-bound logical decision. Earlier serial checks are only narrowing
    evidence and cannot manufacture this record.
    """

    granted: bool
    current: bool
    admission_revision: str
    authorization_policy_revision: str
    principal_authority_revision: str
    principal_id: str
    principal_kind: PrincipalKind
    principal_credential_generation: str
    action: str
    scope: ScopeClass
    tenant_requirement: TenantRequirement
    resource_scope: str | None = None
    cross_tenant_target: CrossTenantTargetBinding | None = None
    authentication_strength_policy_id: str | None = None
    tenant_id: str | None = None
    cell_id: str | None = None
    placement_authority_revision: str | None = None
    placement_version: str | None = None
    runtime_generation: str | None = None
    runtime_profile_id: str | None = None
    runtime_isolation_class: str | None = None
    configuration_generation: str | None = None
    workload_credential_generation: str | None = None
    network_policy_generation: str | None = None
    environment_class: EnvironmentClass | None = None
    isolation_class: str | None = None
    fence_scope_id: str | None = None
    fence_epoch: int | None = None
    authentication_strength_policy_revision: str | None = None
    executing_runtime_authority_revision: str | None = None
    executing_runtime_profile_id: str | None = None
    executing_runtime_generation: str | None = None

    def __post_init__(self) -> None:
        _strict_bool(self.granted, "granted")
        _strict_bool(self.current, "current")
        for field in (
            "admission_revision",
            "authorization_policy_revision",
            "principal_authority_revision",
            "principal_id",
            "principal_credential_generation",
            "action",
        ):
            _identifier(getattr(self, field), field)
        if not isinstance(self.principal_kind, PrincipalKind):
            raise ValueError("principal_kind must be a canonical PrincipalKind")
        if not isinstance(self.scope, ScopeClass):
            raise ValueError("scope must be a canonical ScopeClass")
        if not isinstance(self.tenant_requirement, TenantRequirement):
            raise ValueError("tenant_requirement must be a canonical TenantRequirement")
        _optional_identifier(self.resource_scope, "resource_scope")
        if self.cross_tenant_target is not None and not isinstance(
            self.cross_tenant_target, CrossTenantTargetBinding
        ):
            raise ValueError("cross_tenant_target must be a canonical CrossTenantTargetBinding")
        _optional_identifier(
            self.authentication_strength_policy_id,
            "authentication_strength_policy_id",
        )
        _optional_identifier(
            self.authentication_strength_policy_revision,
            "authentication_strength_policy_revision",
        )

        tenant_values = (
            self.tenant_id,
            self.cell_id,
            self.placement_authority_revision,
            self.placement_version,
            self.runtime_generation,
            self.runtime_profile_id,
            self.runtime_isolation_class,
            self.configuration_generation,
            self.workload_credential_generation,
            self.network_policy_generation,
            self.environment_class,
            self.isolation_class,
            self.fence_scope_id,
            self.fence_epoch,
        )
        if any(value is not None for value in tenant_values):
            if any(value is None for value in tenant_values):
                raise ValueError("tenant final-admission authority bindings must be complete")
            for field in (
                "tenant_id",
                "cell_id",
                "placement_authority_revision",
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
            _strict_positive_int(self.fence_epoch, "fence_epoch")

        runtime_values = (
            self.executing_runtime_authority_revision,
            self.executing_runtime_profile_id,
            self.executing_runtime_generation,
        )
        if any(value is None for value in runtime_values):
            raise ValueError("every final admission must bind current executing-runtime authority")
        _identifier(
            self.executing_runtime_authority_revision,
            "executing_runtime_authority_revision",
        )
        _profile_id(
            self.executing_runtime_profile_id,
            "executing_runtime_profile_id",
            "runtime.",
        )
        _identifier(self.executing_runtime_generation, "executing_runtime_generation")


class CurrentPrincipalAuthorityPort(Protocol):
    def is_current(self, *, principal: Principal, now: datetime) -> bool:
        """Narrowing current session/credential/workload-principal check."""


class PlacementAuthorityPort(Protocol):
    def resolve_current(self, tenant_id: str) -> PlacementEvidence | None:
        """Resolve trusted current placement from the owning authority."""

    def context_is_current(self, context: TenantContext) -> bool:
        """Narrowing/deny signal; only literal True can pass."""


class CurrentAuthorizationPort(Protocol):
    def evaluate(
        self,
        *,
        principal: Principal,
        context: TenantContext | None,
        declaration: AuthorizationDeclaration,
    ) -> AuthorizationDecision:
        """Narrowing owning membership/permission/resource-policy check."""


class CurrentRuntimeAuthorityPort(Protocol):
    def resolve_current_execution(self, *, now: datetime) -> RuntimeExecutionEvidence | None:
        """Narrowing evidence for the runtime actually executing admission."""


class FinalAdmissionAuthorityPort(Protocol):
    def finalize_current_admission(
        self,
        *,
        principal: Principal,
        context: TenantContext | None,
        declaration: AuthorizationDeclaration,
        expected_runtime_binding: RuntimeBinding,
        authentication_strength_evidence: AuthenticationStrengthEvidence | None,
        cross_tenant_target: CrossTenantTargetBinding | None,
    ) -> FinalAdmissionEvidence:
        """Atomically/revision-bind all applicable current authorities.

        This boundary owns its trusted current clock/currentness reads. It MUST
        NOT use caller-supplied request time or earlier booleans as final proof.
        """


def _require_current_principal(
    *,
    principal: Principal,
    principal_authority: CurrentPrincipalAuthorityPort,
    now: datetime,
) -> None:
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
) -> AuthorizationDecision:
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


def _finalize_current_admission(
    *,
    final_admission_authority: FinalAdmissionAuthorityPort | None,
    principal: Principal,
    context: TenantContext | None,
    declaration: AuthorizationDeclaration,
    runtime_binding: RuntimeBinding,
    strength_evidence: AuthenticationStrengthEvidence | None,
    latest_runtime_evidence: RuntimeExecutionEvidence | None,
    cross_tenant_target: CrossTenantTargetBinding | None,
) -> AuthorizationDecision:
    if final_admission_authority is None or not hasattr(
        final_admission_authority, "finalize_current_admission"
    ):
        raise AdmissionDenied("revision-bound final admission authority is unavailable")
    try:
        evidence = final_admission_authority.finalize_current_admission(
            principal=principal,
            context=context,
            declaration=declaration,
            expected_runtime_binding=runtime_binding,
            authentication_strength_evidence=strength_evidence,
            cross_tenant_target=cross_tenant_target,
        )
    except Exception as exc:
        raise AdmissionDenied("revision-bound final admission authority failed closed") from exc
    if not isinstance(evidence, FinalAdmissionEvidence):
        raise AdmissionDenied("final admission authority returned malformed evidence")
    if evidence.current is not True or evidence.granted is not True:
        raise AdmissionDenied("final admission authority did not grant current admission")
    if (
        evidence.principal_id != principal.principal_id
        or evidence.principal_kind is not principal.kind
        or evidence.principal_credential_generation != principal.credential_generation
        or evidence.action != declaration.action
        or evidence.scope is not declaration.scope
        or evidence.tenant_requirement is not declaration.tenant_requirement
        or evidence.resource_scope != declaration.resource_scope
        or evidence.cross_tenant_target != cross_tenant_target
        or evidence.authentication_strength_policy_id
        != declaration.authentication_strength_policy_id
    ):
        raise AdmissionDenied(
            "final admission evidence is bound to another principal identity/kind, action, declaration scope, resource, cross-tenant target, or authentication-strength policy"
        )

    if context is None:
        if evidence.tenant_id is not None:
            raise AdmissionDenied("tenantless final admission cannot carry tenant authority")
    else:
        expected = (
            (evidence.tenant_id, context.tenant_id),
            (evidence.cell_id, context.cell_id),
            (evidence.placement_version, context.placement_version),
            (evidence.runtime_generation, context.runtime_generation),
            (evidence.runtime_profile_id, context.runtime_profile_id),
            (evidence.runtime_isolation_class, context.runtime_isolation_class),
            (evidence.configuration_generation, context.configuration_generation),
            (
                evidence.workload_credential_generation,
                context.workload_credential_generation,
            ),
            (evidence.network_policy_generation, context.network_policy_generation),
            (evidence.environment_class, context.environment_class),
            (evidence.isolation_class, context.isolation_class),
            (evidence.fence_scope_id, context.fence_scope_id),
            (evidence.fence_epoch, context.fence_epoch),
        )
        if any(actual != wanted for actual, wanted in expected):
            raise AdmissionDenied("final admission no longer matches exact TenantContext authority")
        if evidence.placement_authority_revision is None:
            raise AdmissionDenied("final admission lacks placement/currentness revision")

    if declaration.step_up is StepUpClass.NONE:
        if evidence.authentication_strength_policy_revision is not None:
            raise AdmissionDenied("final admission carries unexpected authentication-strength authority")
    else:
        if not isinstance(strength_evidence, AuthenticationStrengthEvidence):
            raise AdmissionDenied("final admission lacks principal-bound authentication-strength evidence")
        if (
            evidence.authentication_strength_policy_revision
            != strength_evidence.policy_version
        ):
            raise AdmissionDenied("final admission authentication-strength revision changed")

    if (
        evidence.executing_runtime_authority_revision is None
        or evidence.executing_runtime_profile_id != runtime_binding.runtime_profile_id
        or evidence.executing_runtime_generation is None
    ):
        raise AdmissionDenied("final admission lacks exact current executing-runtime authority")
    if latest_runtime_evidence is not None and (
        evidence.executing_runtime_profile_id != latest_runtime_evidence.runtime_profile_id
        or evidence.executing_runtime_generation != latest_runtime_evidence.runtime_generation
    ):
        raise AdmissionDenied("final admission executing-runtime authority changed")
    if declaration.tenant_requirement is TenantRequirement.EXPLICIT_CROSS_TENANT_PRIVILEGED and (
        evidence.executing_runtime_profile_id != CONTROL_PLANE.runtime_profile_id
    ):
        raise AdmissionDenied("final cross-tenant admission is not bound to Control Plane runtime")

    return AuthorizationDecision(
        granted=True,
        current=True,
        policy_revision=evidence.authorization_policy_revision,
    )


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
        raise AdmissionDenied("tenant/destination authority lookup input is not canonical") from exc

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
    final_admission_authority: FinalAdmissionAuthorityPort | None = None,
    cross_tenant_target: CrossTenantTargetBinding | None = None,
) -> AuthorizationDecision:
    """Narrow serially, then require one combined final current-admission proof."""

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
    latest_runtime_evidence: RuntimeExecutionEvidence | None = None
    if requirement is TenantRequirement.EXPLICIT_CROSS_TENANT_PRIVILEGED:
        if not isinstance(cross_tenant_target, CrossTenantTargetBinding):
            raise AdmissionDenied("cross-tenant privileged operation requires exact canonical target binding")
    elif cross_tenant_target is not None:
        raise AdmissionDenied("cross-tenant target binding is forbidden for non-cross-tenant operation")

    if declaration.scope in {ScopeClass.TENANT, ScopeClass.RESOURCE} and runtime_binding != API_AUTH_BOUNDARY:
        raise AdmissionDenied("tenant/resource protected operations require the accepted API runtime boundary")
    if requirement is TenantRequirement.REQUIRED and context is None:
        raise AdmissionDenied("protected operation requires trusted TenantContext")
    if requirement is TenantRequirement.EXPLICIT_CROSS_TENANT_PRIVILEGED:
        if runtime_binding != CONTROL_PLANE:
            raise AdmissionDenied(
                "cross-tenant privileged platform authority requires the accepted Control Plane runtime boundary"
            )
        latest_runtime_evidence = _require_current_runtime_execution(
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

    _require_declared_authentication_strength(
        principal=principal,
        declaration=declaration,
        strength_policy=strength_policy,
        strength_evidence=strength_evidence,
        now=now,
    )
    _require_current_principal(
        principal=principal,
        principal_authority=principal_authority,
        now=now,
    )

    if requirement is TenantRequirement.EXPLICIT_CROSS_TENANT_PRIVILEGED:
        latest_runtime_evidence = _require_current_runtime_execution(
            runtime_binding=CONTROL_PLANE,
            runtime_authority=runtime_authority,
            now=now,
        )

    # Historical/serial authorization remains a narrowing gate only. Its result
    # is deliberately not returned as final protected-operation authority.
    _evaluate_current_authorization(
        authorization_authority=authorization_authority,
        principal=principal,
        context=context,
        declaration=declaration,
    )

    return _finalize_current_admission(
        final_admission_authority=final_admission_authority,
        principal=principal,
        context=context,
        declaration=declaration,
        runtime_binding=runtime_binding,
        strength_evidence=strength_evidence,
        latest_runtime_evidence=latest_runtime_evidence,
        cross_tenant_target=cross_tenant_target,
    )
