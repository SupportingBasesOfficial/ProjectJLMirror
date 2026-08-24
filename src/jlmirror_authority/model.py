from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import re
from typing import FrozenSet

_ACTION_RE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){2,}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$")
_VERSIONED_ID_RE = re.compile(r"^[a-z][a-z0-9-]*(?:\.[a-z0-9-]+)+@[1-9][0-9]*$")


class AdmissionDenied(PermissionError):
    """Fail-closed denial at an accepted authority boundary."""


class PrincipalKind(str, Enum):
    HUMAN_BROWSER_SESSION = "human_browser_session"
    MACHINE_API_PRINCIPAL = "machine_api_principal"
    INTERNAL_SERVICE_PRINCIPAL = "internal_service_principal"
    PLATFORM_ADMIN_PRINCIPAL = "platform_admin_principal"
    SCHEDULED_SYSTEM_PROCESS = "scheduled/system_process"


class ScopeClass(str, Enum):
    PLATFORM = "platform"
    TENANT = "tenant"
    RESOURCE = "resource"


class TenantRequirement(str, Enum):
    NONE = "none"
    REQUIRED = "required"
    EXPLICIT_CROSS_TENANT_PRIVILEGED = "explicit_cross_tenant_privileged"


class StepUpClass(str, Enum):
    NONE = "none"
    POLICY_DRIVEN = "policy-driven"
    REQUIRED = "required"


class AuditClass(str, Enum):
    NONE = "none"
    NORMAL = "normal"
    PRIVILEGED = "privileged"
    SECURITY_CRITICAL = "security-critical"


class EnvironmentClass(str, Enum):
    DEVELOPMENT = "environment.development@1"
    VALIDATION = "environment.validation@1"
    PRODUCTION = "environment.production@1"
    RECOVERY = "environment.recovery@1"


def _aware(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _identifier(value: str, field: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise ValueError(f"invalid {field}")
    return value


def _versioned_identifier(value: str, field: str, prefix: str | None = None) -> str:
    if not isinstance(value, str) or not _VERSIONED_ID_RE.fullmatch(value):
        raise ValueError(f"invalid {field}")
    if prefix is not None and not value.startswith(prefix):
        raise ValueError(f"{field} must use {prefix} profile namespace")
    return value


def _optional_identifier(value: str | None, field: str) -> str | None:
    if value is not None:
        _identifier(value, field)
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
class Principal:
    principal_id: str
    kind: PrincipalKind
    credential_generation: str
    active: bool = True

    def __post_init__(self) -> None:
        _identifier(self.principal_id, "principal_id")
        if not isinstance(self.kind, PrincipalKind):
            raise ValueError("kind must be a canonical PrincipalKind")
        _identifier(self.credential_generation, "credential_generation")
        _strict_bool(self.active, "active")


@dataclass(frozen=True)
class AuthenticationStrengthEvidence:
    issuer: str
    acr: str | None
    amr: FrozenSet[str]
    authenticated_at: datetime
    evidence_expires_at: datetime
    policy_version: str
    principal_id: str | None = None
    principal_credential_generation: str | None = None

    def __post_init__(self) -> None:
        _optional_identifier(self.principal_id, "principal_id")
        _optional_identifier(
            self.principal_credential_generation, "principal_credential_generation"
        )
        if (self.principal_id is None) is not (self.principal_credential_generation is None):
            raise ValueError(
                "authentication-strength principal id and credential generation must be bound together"
            )
        _identifier(self.issuer, "issuer")
        if self.acr is not None:
            _identifier(self.acr, "acr")
        if isinstance(self.amr, (str, bytes)):
            raise ValueError("amr must be a collection of canonical entries")
        try:
            amr = frozenset(self.amr)
        except TypeError as exc:
            raise ValueError("amr must be an immutable-compatible collection") from exc
        if any(not isinstance(item, str) or not _ID_RE.fullmatch(item) for item in amr):
            raise ValueError("invalid amr entry")
        object.__setattr__(self, "amr", amr)
        authenticated = _aware(self.authenticated_at, "authenticated_at")
        expires = _aware(self.evidence_expires_at, "evidence_expires_at")
        if expires <= authenticated:
            raise ValueError("authentication-strength evidence must expire after authentication")
        _identifier(self.policy_version, "policy_version")

    def is_current(self, now: datetime) -> bool:
        return _aware(self.authenticated_at, "authenticated_at") <= _aware(now, "now") < _aware(
            self.evidence_expires_at, "evidence_expires_at"
        )


@dataclass(frozen=True)
class AuthorizationDeclaration:
    action: str
    scope: ScopeClass
    tenant_required: bool
    step_up: StepUpClass
    audit_class: AuditClass
    resource_scope: str | None = None
    authentication_strength_policy_id: str | None = None
    tenant_requirement: TenantRequirement | None = None

    def __post_init__(self) -> None:
        if not _ACTION_RE.fullmatch(self.action):
            raise ValueError("action must use canonical <domain>.<resource>.<verb> form")
        if not isinstance(self.scope, ScopeClass):
            raise ValueError("scope must be a canonical ScopeClass")
        if not isinstance(self.step_up, StepUpClass):
            raise ValueError("step_up must be a canonical StepUpClass")
        if not isinstance(self.audit_class, AuditClass):
            raise ValueError("audit_class must be a canonical AuditClass")
        _strict_bool(self.tenant_required, "tenant_required")
        if self.resource_scope is not None:
            _identifier(self.resource_scope, "resource_scope")
        if self.authentication_strength_policy_id is not None:
            _identifier(self.authentication_strength_policy_id, "authentication_strength_policy_id")
        if self.step_up is not StepUpClass.NONE and not self.authentication_strength_policy_id:
            raise ValueError("non-none step-up requires an explicit Security policy identifier")
        if self.step_up is StepUpClass.NONE and self.authentication_strength_policy_id is not None:
            raise ValueError("step_up=none cannot carry an authentication-strength policy")

        if self.tenant_requirement is None:
            canonical_requirement = (
                TenantRequirement.REQUIRED if self.tenant_required else TenantRequirement.NONE
            )
            object.__setattr__(self, "tenant_requirement", canonical_requirement)
        else:
            if not isinstance(self.tenant_requirement, TenantRequirement):
                raise ValueError("tenant_requirement must be a canonical TenantRequirement")
            canonical_requirement = self.tenant_requirement
            expected_legacy_flag = canonical_requirement is TenantRequirement.REQUIRED
            if self.tenant_required is not expected_legacy_flag:
                raise ValueError("tenant_required compatibility flag contradicts tenant_requirement")

        if self.scope in {ScopeClass.TENANT, ScopeClass.RESOURCE} and canonical_requirement is not TenantRequirement.REQUIRED:
            raise ValueError("tenant/resource scope requires tenant_requirement=required")
        if canonical_requirement is TenantRequirement.EXPLICIT_CROSS_TENANT_PRIVILEGED:
            if self.scope is not ScopeClass.PLATFORM:
                raise ValueError("cross-tenant privileged operations are distinct platform operations")
            if self.audit_class not in {AuditClass.PRIVILEGED, AuditClass.SECURITY_CRITICAL}:
                raise ValueError("cross-tenant privileged operations require privileged/security-critical audit")


@dataclass(frozen=True)
class TenantContext:
    """Trusted logical tenant context plus internal runtime-admission bindings.

    `isolation_class` remains the accepted tenant isolation class (for example
    pooled/dedicated). `runtime_isolation_class` is the separate Phase 13 runtime
    isolation profile. Neither may substitute for the other.
    """

    tenant_id: str
    principal_id: str
    principal_kind: PrincipalKind
    principal_credential_generation: str
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
    fence_scope_id: str
    fence_epoch: int
    constructed_at: datetime
    membership_id: str | None = None
    authorization_context: str | None = None
    request_id: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    operation_id: str | None = None

    def __post_init__(self) -> None:
        for field, value in (
            ("tenant_id", self.tenant_id),
            ("principal_id", self.principal_id),
            ("principal_credential_generation", self.principal_credential_generation),
            ("cell_id", self.cell_id),
            ("placement_version", self.placement_version),
            ("runtime_generation", self.runtime_generation),
            ("configuration_generation", self.configuration_generation),
            ("workload_credential_generation", self.workload_credential_generation),
            ("network_policy_generation", self.network_policy_generation),
            ("isolation_class", self.isolation_class),
            ("fence_scope_id", self.fence_scope_id),
        ):
            _identifier(value, field)
        _versioned_identifier(self.runtime_profile_id, "runtime_profile_id", "runtime.")
        _versioned_identifier(
            self.runtime_isolation_class,
            "runtime_isolation_class",
            "isolation.",
        )
        if not isinstance(self.principal_kind, PrincipalKind):
            raise ValueError("principal_kind must be canonical")
        if not isinstance(self.environment_class, EnvironmentClass):
            raise ValueError("environment_class must be canonical")
        _strict_positive_int(self.fence_epoch, "fence_epoch")
        _aware(self.constructed_at, "constructed_at")
        for field in (
            "membership_id",
            "authorization_context",
            "request_id",
            "correlation_id",
            "causation_id",
            "operation_id",
        ):
            _optional_identifier(getattr(self, field), field)

    def matches_principal(self, principal: Principal) -> bool:
        return (
            principal.active is True
            and self.principal_id == principal.principal_id
            and self.principal_kind is principal.kind
            and self.principal_credential_generation == principal.credential_generation
        )


@dataclass(frozen=True)
class SecretReference:
    reference_id: str
    reference_class: str
    generation: str

    def __post_init__(self) -> None:
        _identifier(self.reference_id, "reference_id")
        if not _VERSIONED_ID_RE.fullmatch(self.reference_class):
            raise ValueError("reference_class must be a canonical versioned profile ID")
        if not self.reference_class.startswith("secretref."):
            raise ValueError("reference_class must be a secretref profile")
        _identifier(self.generation, "generation")

    def __repr__(self) -> str:
        return (
            "SecretReference(reference_id=<redacted>, "
            f"reference_class={self.reference_class!r}, generation={self.generation!r})"
        )
