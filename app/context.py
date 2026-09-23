"""Tenant context middleware.

Resolves a trusted ``TenantContext`` (ADR-005) for each request using the
configured authority adapters. In development mode, the principal and tenant
are resolved from request headers for convenience. In production, this
middleware resolves identity from the BFF session / OIDC token and placement
from the control-plane service.
"""

from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from jlmirror_authority.control_plane import construct_tenant_context
from jlmirror_authority.model import Principal, PrincipalKind

from app.auth import (
    DevAuthorizationAuthority,
    DevFinalAdmissionAuthority,
    DevPlacementAuthority,
    DevPrincipalAuthority,
    DevRuntimeAuthority,
    is_dev_mode,
)

# Context variables for the current request's principal and tenant context.
_current_principal: ContextVar[Principal | None] = ContextVar(
    "current_principal", default=None
)
_current_tenant_id: ContextVar[str | None] = ContextVar(
    "current_tenant_id", default=None
)


def get_current_principal() -> Principal | None:
    return _current_principal.get()


def get_current_tenant_id() -> str | None:
    return _current_tenant_id.get()


def set_request_principal(
    *,
    principal_id: str,
    kind: PrincipalKind = PrincipalKind.HUMAN_BROWSER_SESSION,
    credential_generation: str = "credential-gen-dev-1",
) -> Principal:
    principal = Principal(
        principal_id=principal_id,
        kind=kind,
        credential_generation=credential_generation,
        active=True,
    )
    _current_principal.set(principal)
    return principal


def set_request_tenant_id(tenant_id: str | None) -> None:
    _current_tenant_id.set(tenant_id)


def resolve_dev_principal(
    x_principal_id: Annotated[str | None, Header()] = None,
    x_tenant_id: Annotated[str | None, Header()] = None,
) -> Principal:
    """Dev-mode principal resolution from headers."""
    if not is_dev_mode():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dev-mode principal resolution is disabled outside development environment.",
        )
    principal_id = x_principal_id or "dev-user-1"
    return set_request_principal(principal_id=principal_id)


def resolve_dev_tenant_id(
    x_tenant_id: Annotated[str | None, Header()] = None,
) -> str | None:
    """Dev-mode tenant resolution from headers."""
    if not is_dev_mode():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dev-mode tenant resolution is disabled outside development environment.",
        )
    tenant_id = x_tenant_id or "tenant:dev"
    set_request_tenant_id(tenant_id)
    return tenant_id


def build_tenant_context(
    principal: Annotated[Principal, Depends(resolve_dev_principal)],
    tenant_id: Annotated[str | None, Depends(resolve_dev_tenant_id)],
):
    """Construct a TenantContext using the dev authorities.

    Returns the ``TenantContext`` or ``None`` for platform-scoped operations.
    Raises HTTP 403 if the placement authority cannot resolve the tenant.
    """
    if tenant_id is None:
        return None

    placement_authority = DevPlacementAuthority(tenant_id=tenant_id)
    placement = placement_authority.resolve_current(tenant_id)
    if placement is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Placement authority could not resolve tenant: {tenant_id}",
        )

    try:
        context = construct_tenant_context(
            principal=principal,
            principal_authority=DevPrincipalAuthority(),
            placement_authority=placement_authority,
            tenant_id=tenant_id,
            destination_cell_id=placement.cell_id,
            destination_runtime_generation=placement.runtime_generation,
            destination_configuration_generation=placement.configuration_generation,
            destination_workload_credential_generation=placement.workload_credential_generation,
            destination_network_policy_generation=placement.network_policy_generation,
            required_environment=placement.environment_class,
            now=datetime.now(timezone.utc),
            request_id="dev-request",
            correlation_id="dev-correlation",
            operation_id="dev-operation",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tenant context construction failed: {exc}",
        ) from exc

    return context


# Authority singletons for dependency injection.
principal_authority = DevPrincipalAuthority()
placement_authority_factory = DevPlacementAuthority
authorization_authority = DevAuthorizationAuthority()
runtime_authority = DevRuntimeAuthority()
final_admission_authority = DevFinalAdmissionAuthority()
