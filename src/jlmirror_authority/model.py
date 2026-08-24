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
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _identifier(value: str, field: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise ValueError(f"invalid {field}")
    return value


@dataclass(frozen=True)
class Principal:
    principal_id: str
    kind: PrincipalKind
    credential_generation: str
    active: bool = True

    def __post_init__(self) -> None:
        _identifier(self.principal_id, "principal_id")
        _identifier(self.credential_generation, "credential_generation")


@dataclass(frozen=True)
class AuthenticationStrengthEvidence:
    issuer: str
    acr: str | None
    amr: FrozenSet[str]
    authenticated_at: datetime
    evidence_expires_at: datetime
    policy_version: str

    def __post_init__(self) -> None:
        _identifier(self.issuer, "issuer")
        if self.acr is not None:
            _identifier(self.acr, "acr")
        if any(not _ID_RE.fullmatch(item) for item in self.amr):
            raise ValueError("invalid amr entry")
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

    def __post_init__(self) -> None:
        if not _ACTION_RE.fullmatch(self.action):
            raise ValueError("action must use canonical <domain>.<resource>.<verb> form")
        if self.resource_scope is not None:
            _identifier(self.resource_scope, "resource_scope")
        if self.authentication_strength_policy_id is not None:
            _identifier(self.authentication_strength_policy_id, "authentication_strength_policy_id")
        if self.step_up is StepUpClass.REQUIRED and not self.authentication_strength_policy_id:
            raise ValueError("required step-up needs an explicit Security policy identifier")
        if self.scope in {ScopeClass.TENANT, ScopeClass.RESOURCE} and not self.tenant_required:
            raise ValueError("tenant/resource scope requires tenant context")


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    cell_id: str
    placement_version: str
    runtime_generation: str
    environment_class: EnvironmentClass
    fence_scope_id: str
    fence_epoch: int
    constructed_at: datetime

    def __post_init__(self) -> None:
        for field, value in (
            ("tenant_id", self.tenant_id),
            ("cell_id", self.cell_id),
            ("placement_version", self.placement_version),
            ("runtime_generation", self.runtime_generation),
            ("fence_scope_id", self.fence_scope_id),
        ):
            _identifier(value, field)
        if not isinstance(self.fence_epoch, int) or self.fence_epoch <= 0:
            raise ValueError("fence_epoch must be a positive integer")
        _aware(self.constructed_at, "constructed_at")


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
