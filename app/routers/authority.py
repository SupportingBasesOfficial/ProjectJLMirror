"""Authority domain router — identity, authorization, fencing.

Exposes operations from ``jlmirror_authority``: browser session lifecycle,
authorization checks, and fence management. See ADR-005 (identity) and
ADR-007 (API/BFF boundary).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from jlmirror_authority.control_plane import authorize_protected_operation
from jlmirror_authority.fencing import acquire_next_fence
from jlmirror_authority.model import (
    AuditClass,
    AuthorizationDeclaration,
    Principal,
    ScopeClass,
    StepUpClass,
)
from jlmirror_authority.runtime_profiles import API_AUTH_BOUNDARY
from jlmirror_authority.session import (
    BrowserSessionHandle,
    issue_browser_session,
    resolve_browser_session,
    retire_browser_session,
)

from app.auth import fence_authority, session_authority
from app.context import (
    authorization_authority,
    build_tenant_context,
    final_admission_authority,
    principal_authority,
    resolve_dev_principal,
    runtime_authority,
)

router = APIRouter()


class SessionIssueRequest(BaseModel):
    principal_id: str
    credential_generation: str = "credential-gen-dev-1"


class SessionIssueResponse(BaseModel):
    session_handle: str
    principal_id: str
    issued_at: str
    expires_at: str


@router.post("/auth/session/issue", response_model=SessionIssueResponse)
async def issue_session(
    body: SessionIssueRequest,
    principal: Annotated[Principal, Depends(resolve_dev_principal)],
) -> SessionIssueResponse:
    """Issue a BFF-managed browser session (ADR-005/007).

    In production this is called by the BFF after OIDC callback. In dev mode
    it issues a session directly for the given principal.
    """
    now = datetime.now(timezone.utc)
    handle = issue_browser_session(
        authority=session_authority,
        principal=principal,
        now=now,
        lifetime=timedelta(hours=1),
    )
    record = resolve_browser_session(authority=session_authority, handle=handle, now=now)
    return SessionIssueResponse(
        session_handle=handle.value,
        principal_id=record.principal.principal_id,
        issued_at=record.created_at.isoformat(),
        expires_at=record.expires_at.isoformat(),
    )


class SessionRetireRequest(BaseModel):
    session_handle: str


@router.post("/auth/session/retire", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def retire_session(body: SessionRetireRequest) -> None:
    """Retire a browser session."""
    now = datetime.now(timezone.utc)
    handle = BrowserSessionHandle(value=body.session_handle)
    retire_browser_session(authority=session_authority, handle=handle, now=now)


class AuthorizeRequest(BaseModel):
    action: str
    scope: str = "tenant"
    tenant_required: bool = True


class AuthorizeResponse(BaseModel):
    granted: bool
    current: bool
    policy_revision: str


@router.post("/auth/authorize", response_model=AuthorizeResponse)
async def authorize(
    body: AuthorizeRequest,
    principal: Annotated[Principal, Depends(resolve_dev_principal)],
    context: Annotated[Any, Depends(build_tenant_context)],
) -> AuthorizeResponse:
    """Check authorization for a declared action (ADR-005).

    Uses ``authorize_protected_operation`` from the domain layer with the
    configured authority adapters.
    """
    try:
        scope = ScopeClass(body.scope)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scope: {exc}",
        ) from exc

    declaration = AuthorizationDeclaration(
        action=body.action,
        scope=scope,
        tenant_required=body.tenant_required,
        step_up=StepUpClass.NONE,
        audit_class=AuditClass.NORMAL,
    )

    # For tenant-scoped ops, use the dev placement authority from context.
    from app.context import placement_authority_factory

    placement_auth = placement_authority_factory(tenant_id=context.tenant_id) if context else None

    try:
        decision = authorize_protected_operation(
            principal=principal,
            principal_authority=principal_authority,
            declaration=declaration,
            placement_authority=placement_auth,
            authorization_authority=authorization_authority,
            context=context,
            now=datetime.now(timezone.utc),
            runtime_binding=API_AUTH_BOUNDARY,
            runtime_authority=runtime_authority,
            final_admission_authority=final_admission_authority,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Authorization denied: {exc}",
        ) from exc

    return AuthorizeResponse(
        granted=decision.granted,
        current=decision.current,
        policy_revision=decision.policy_revision,
    )


class FenceBootstrapRequest(BaseModel):
    fence_scope_id: str
    generation_id: str = "gen-1"


class FenceAcquireRequest(BaseModel):
    fence_scope_id: str
    expected_predecessor_epoch: int
    expected_predecessor_generation_id: str | None = None
    successor_generation_id: str
    successor_state: str = "active"


class FenceResponse(BaseModel):
    fence_scope_id: str
    current_fence_epoch: int
    current_generation_id: str
    authority_state: str


@router.post("/fence/bootstrap", response_model=FenceResponse)
async def bootstrap_fence(
    body: FenceBootstrapRequest,
    principal: Annotated[Principal, Depends(resolve_dev_principal)],
) -> FenceResponse:
    """Bootstrap a fence with epoch 1 (dev mode only)."""
    record = fence_authority.bootstrap(body.fence_scope_id, body.generation_id)
    return FenceResponse(
        fence_scope_id=record.fence_scope_id,
        current_fence_epoch=record.current_fence_epoch,
        current_generation_id=record.current_generation_id,
        authority_state=record.authority_state,
    )


@router.post("/fence/acquire", response_model=FenceResponse)
async def acquire_fence_endpoint(
    body: FenceAcquireRequest,
    principal: Annotated[Principal, Depends(resolve_dev_principal)],
) -> FenceResponse:
    """Acquire the next fence epoch (ADR-008 — transactions and outbox).

    Uses the in-memory fence authority from the domain layer. In production
    this is backed by the ``platform.authority_fences`` table.
    """
    try:
        record = acquire_next_fence(
            authority=fence_authority,
            fence_scope_id=body.fence_scope_id,
            expected_predecessor_epoch=body.expected_predecessor_epoch,
            expected_predecessor_generation_id=body.expected_predecessor_generation_id,
            successor_generation_id=body.successor_generation_id,
            successor_state=body.successor_state,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Fence acquisition failed: {exc}",
        ) from exc

    return FenceResponse(
        fence_scope_id=record.fence_scope_id,
        current_fence_epoch=record.current_fence_epoch,
        current_generation_id=record.current_generation_id,
        authority_state=record.authority_state,
    )
