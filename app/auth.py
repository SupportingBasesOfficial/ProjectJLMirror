"""Development-mode stub authorities.

These implement the authority Ports defined by ``jlmirror_authority.control_plane``
so the API can run locally without a real identity provider, placement service,
or authorization policy engine. They return permissive-but-valid evidence for
the ``environment.development@1`` class only.

In production, replace these with real adapters:
- ``PlacementAuthority`` -> control-plane placement service
- ``AuthorizationAuthority`` -> policy engine (e.g. OPA, Cedar, or DB-backed)
- ``RuntimeAuthority`` -> platform runtime registry
- ``FinalAdmissionAuthority`` -> revision-bound atomic admission authority

See ADR-005 (identity/authorization) and ADR-007 (API/BFF boundary).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from jlmirror_authority.control_plane import (
    AuthorizationDecision,
    FinalAdmissionEvidence,
    PlacementEvidence,
    RuntimeExecutionEvidence,
    RuntimeLifecycle,
)
from jlmirror_authority.model import (
    AuthorizationDeclaration,
    EnvironmentClass,
    Principal,
    TenantContext,
    TenantRequirement,
)
from jlmirror_authority.runtime_profiles import API_AUTH_BOUNDARY, RuntimeBinding

from app.config import settings

_NOW = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
_DEV_ENV = EnvironmentClass.DEVELOPMENT


class DevPrincipalAuthority:
    """Always-current principal authority for development."""

    def is_current(self, *, principal: Principal, now: datetime) -> bool:
        return principal.active is True


class DevPlacementAuthority:
    """Returns a fixed valid placement for any tenant in development."""

    def __init__(self, tenant_id: str = "tenant:dev", cell_id: str = "cell:dev-a"):
        self._tenant_id = tenant_id
        self._cell_id = cell_id

    def resolve_current(self, tenant_id: str) -> PlacementEvidence | None:
        if tenant_id != self._tenant_id:
            return None
        return PlacementEvidence(
            tenant_id=self._tenant_id,
            cell_id=self._cell_id,
            placement_version="pv-dev-1",
            runtime_generation="runtime-gen-dev-1",
            runtime_profile_id=API_AUTH_BOUNDARY.runtime_profile_id,
            runtime_isolation_class=API_AUTH_BOUNDARY.isolation_class,
            configuration_generation="cfg-gen-dev-1",
            workload_credential_generation="wc-gen-dev-1",
            network_policy_generation="np-gen-dev-1",
            environment_class=_DEV_ENV,
            isolation_class="pooled",
            runtime_lifecycle=RuntimeLifecycle.ACTIVE,
            placement_current=True,
            operation_eligible=True,
            cell_admission_current=True,
            fence_scope_id=f"tenant:{self._tenant_id}",
            fence_epoch=1,
        )

    def context_is_current(self, context: TenantContext) -> bool:
        return True


class DevAuthorizationAuthority:
    """Permissive authorization for development — grants all declared operations."""

    def evaluate(
        self,
        *,
        principal: Principal,
        context: TenantContext | None,
        declaration: AuthorizationDeclaration,
    ) -> AuthorizationDecision:
        return AuthorizationDecision(
            granted=True,
            current=True,
            policy_revision="dev-policy-r1",
        )


class DevRuntimeAuthority:
    """Returns valid runtime execution evidence for the API auth boundary."""

    def resolve_current_execution(self, *, now: datetime) -> RuntimeExecutionEvidence | None:
        return RuntimeExecutionEvidence(
            runtime_profile_id=API_AUTH_BOUNDARY.runtime_profile_id,
            principal_class=API_AUTH_BOUNDARY.principal_class,
            isolation_class=API_AUTH_BOUNDARY.isolation_class,
            ingress_profile=API_AUTH_BOUNDARY.ingress_profile,
            runtime_generation="runtime-gen-dev-1",
            environment_class=_DEV_ENV,
            runtime_lifecycle=RuntimeLifecycle.ACTIVE,
            current=True,
        )


class DevFinalAdmissionAuthority:
    """Revision-bound final admission that mirrors the inputs for development."""

    def finalize_current_admission(
        self,
        *,
        principal: Principal,
        context: TenantContext | None,
        declaration: AuthorizationDeclaration,
        expected_runtime_binding: RuntimeBinding,
        authentication_strength_evidence: object | None,
        cross_tenant_target: object | None,
    ) -> FinalAdmissionEvidence:
        common = dict(
            granted=True,
            current=True,
            admission_revision="admission-rev-dev-1",
            authorization_policy_revision="dev-policy-r1",
            principal_authority_revision="principal-rev-dev-1",
            principal_id=principal.principal_id,
            principal_kind=principal.kind,
            principal_credential_generation=principal.credential_generation,
            action=declaration.action,
            scope=declaration.scope,
            tenant_requirement=declaration.tenant_requirement,
            resource_scope=declaration.resource_scope,
            authentication_strength_policy_id=declaration.authentication_strength_policy_id,
            executing_runtime_authority_revision="runtime-rev-dev-1",
            executing_runtime_profile_id=expected_runtime_binding.runtime_profile_id,
            executing_runtime_generation="runtime-gen-dev-1",
            executing_runtime_environment_class=_DEV_ENV,
        )
        if context is not None:
            return FinalAdmissionEvidence(
                **common,
                tenant_id=context.tenant_id,
                cell_id=context.cell_id,
                placement_authority_revision="placement-rev-dev-1",
                placement_version=context.placement_version,
                runtime_generation=context.runtime_generation,
                runtime_profile_id=context.runtime_profile_id,
                runtime_isolation_class=context.runtime_isolation_class,
                configuration_generation=context.configuration_generation,
                workload_credential_generation=context.workload_credential_generation,
                network_policy_generation=context.network_policy_generation,
                environment_class=context.environment_class,
                isolation_class=context.isolation_class,
                fence_scope_id=context.fence_scope_id,
                fence_epoch=context.fence_epoch,
            )
        return FinalAdmissionEvidence(**common)


def is_dev_mode() -> bool:
    return settings.is_development


# ---------------------------------------------------------------------------
# In-memory authority port implementations for development mode.
# ---------------------------------------------------------------------------

from datetime import timedelta  # noqa: E402

from jlmirror_authority.fencing import FenceRecord, FenceAuthorityPort  # noqa: E402
from jlmirror_authority.session import (  # noqa: E402
    BrowserSessionRecord,
    SessionAuthorityPort,
)


class InMemorySessionAuthority(SessionAuthorityPort):
    """In-memory session store for development. Not durable."""

    def __init__(self) -> None:
        self._sessions: dict[str, BrowserSessionRecord] = {}

    def create(self, record: BrowserSessionRecord) -> bool:
        if record.handle_digest in self._sessions:
            return False
        self._sessions[record.handle_digest] = record
        return True

    def resolve(self, handle_digest: str) -> BrowserSessionRecord | None:
        return self._sessions.get(handle_digest)

    def rotate(
        self,
        *,
        predecessor_handle_digest: str,
        expected_predecessor_generation: str,
        successor: BrowserSessionRecord,
    ) -> bool:
        current = self._sessions.get(predecessor_handle_digest)
        if current is None or current.session_generation != expected_predecessor_generation:
            return False
        self._sessions.pop(predecessor_handle_digest, None)
        self._sessions[successor.handle_digest] = successor
        return True

    def retire(self, *, handle_digest: str, expected_generation: str) -> bool:
        current = self._sessions.get(handle_digest)
        if current is None or current.session_generation != expected_generation:
            return False
        self._sessions[handle_digest] = type(current)(
            handle_digest=current.handle_digest,
            principal=current.principal,
            session_generation=current.session_generation,
            created_at=current.created_at,
            expires_at=current.expires_at,
            retired=True,
            authentication_strength=current.authentication_strength,
        )
        return True


class InMemoryFenceAuthority(FenceAuthorityPort):
    """In-memory fence authority for development. Not durable."""

    def __init__(self) -> None:
        self._fences: dict[str, FenceRecord] = {}

    def current(self, fence_scope_id: str) -> FenceRecord | None:
        return self._fences.get(fence_scope_id)

    def acquire_successor(
        self,
        *,
        fence_scope_id: str,
        expected_predecessor_epoch: int,
        expected_predecessor_generation_id: str,
        successor_generation_id: str,
        successor_state: str,
    ) -> FenceRecord | None:
        current = self._fences.get(fence_scope_id)
        if current is None:
            return None
        if (
            current.current_fence_epoch != expected_predecessor_epoch
            or current.current_generation_id != expected_predecessor_generation_id
        ):
            return None
        successor = FenceRecord(
            fence_scope_id=fence_scope_id,
            current_fence_epoch=current.current_fence_epoch + 1,
            current_generation_id=successor_generation_id,
            authority_state=successor_state,
        )
        self._fences[fence_scope_id] = successor
        return successor

    def bootstrap(self, fence_scope_id: str, generation_id: str = "gen-1") -> FenceRecord:
        """Initialize a fence with epoch 1 for development."""
        record = FenceRecord(
            fence_scope_id=fence_scope_id,
            current_fence_epoch=1,
            current_generation_id=generation_id,
            authority_state="active",
        )
        self._fences[fence_scope_id] = record
        return record


# Singleton instances for development mode.
session_authority = InMemorySessionAuthority()
fence_authority = InMemoryFenceAuthority()
