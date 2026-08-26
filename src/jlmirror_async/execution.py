from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from jlmirror_authority import EnvironmentClass, TenantContext

from .model import ScopedMessageIdentity, aware, contract_name, identifier, optional_identifier

_ALLOWED_RUNTIME_PROFILES = frozenset({"runtime.api@1", "runtime.worker@1"})


@dataclass(frozen=True)
class AsyncExecutionRequest:
    """Exact protected-execution scope that must be re-authorized now.

    The request is built by the correctness substrate from trusted receipt/operation
    state. It is not a message payload capability. Exactly one stable effect identity
    is present: either a consumer scoped-message identity or a cross-authority
    operation id.
    """

    authority_contract: str
    runtime_profile_id: str
    tenant_id: str | None = None
    message_identity: ScopedMessageIdentity | None = None
    operation_id: str | None = None

    def __post_init__(self) -> None:
        contract_name(self.authority_contract, "authority_contract")
        identifier(self.runtime_profile_id, "runtime_profile_id")
        if self.runtime_profile_id not in _ALLOWED_RUNTIME_PROFILES:
            raise ValueError("Wave 2 execution requires an accepted API/worker runtime profile")
        optional_identifier(self.tenant_id, "tenant_id")
        optional_identifier(self.operation_id, "operation_id")
        if self.message_identity is not None and not isinstance(
            self.message_identity, ScopedMessageIdentity
        ):
            raise ValueError("message_identity must be canonical when present")
        message_mode = self.message_identity is not None
        operation_mode = self.operation_id is not None
        if message_mode is operation_mode:
            raise ValueError("execution request requires exactly one message identity or operation_id")
        if self.message_identity is not None:
            if self.authority_contract != self.message_identity.consumer_contract:
                raise ValueError("message execution authority must match consumer_contract")
            if self.tenant_id != self.message_identity.tenant_id:
                raise ValueError("message execution tenant binding must match trusted scoped identity")


@dataclass(frozen=True)
class AsyncExecutionAdmission:
    """Revision-bound current execution evidence produced by a trusted authority.

    The concrete adapter may use the accepted Wave 1 placement/final-admission
    authorities, but Wave 2 does not select that backend. The adapter owns its
    current clock. This record is evidence only for the exact request below and is
    not reusable as a bearer capability for another message/operation.
    """

    request: AsyncExecutionRequest
    principal_id: str
    principal_credential_generation: str
    authorization_revision: str
    admission_revision: str
    runtime_generation: str
    environment_class: EnvironmentClass
    observed_at: datetime
    current: bool
    tenant_context: TenantContext | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.request, AsyncExecutionRequest):
            raise ValueError("execution admission requires canonical request binding")
        for field in (
            "principal_id",
            "principal_credential_generation",
            "authorization_revision",
            "admission_revision",
            "runtime_generation",
        ):
            identifier(getattr(self, field), field)
        if not isinstance(self.environment_class, EnvironmentClass):
            raise ValueError("environment_class must be canonical")
        aware(self.observed_at, "observed_at")
        if type(self.current) is not bool:
            raise ValueError("current must be an explicit boolean")

        if self.request.tenant_id is None:
            if self.tenant_context is not None:
                raise ValueError("global execution admission cannot carry TenantContext")
            return

        if not isinstance(self.tenant_context, TenantContext):
            raise ValueError("tenant execution admission requires trusted TenantContext")
        context = self.tenant_context
        if (
            context.tenant_id != self.request.tenant_id
            or context.principal_id != self.principal_id
            or context.principal_credential_generation != self.principal_credential_generation
            or context.runtime_profile_id != self.request.runtime_profile_id
            or context.runtime_generation != self.runtime_generation
            or context.environment_class is not self.environment_class
        ):
            raise ValueError("execution admission does not match exact TenantContext authority")


class CurrentAsyncExecutionAuthorityPort(Protocol):
    def finalize_current_execution(
        self,
        *,
        request: AsyncExecutionRequest,
    ) -> AsyncExecutionAdmission:
        """Return one current revision-bound decision for this exact effect scope.

        Implementations must re-establish principal/service authority, tenant
        placement/admission/fence and owning authorization/policy as applicable.
        The implementation owns its trusted current clock; callers do not provide
        a timestamp that can manufacture freshness.
        """


def require_current_execution(
    authority: CurrentAsyncExecutionAuthorityPort,
    request: AsyncExecutionRequest,
) -> AsyncExecutionAdmission:
    """Fail closed unless the authority proves this exact execution request now."""

    if authority is None or not hasattr(authority, "finalize_current_execution"):
        raise ValueError("current async execution authority is unavailable")
    try:
        admission = authority.finalize_current_execution(request=request)
    except Exception as exc:
        raise ValueError("current async execution authority failed closed") from exc
    if not isinstance(admission, AsyncExecutionAdmission):
        raise ValueError("current async execution authority returned malformed evidence")
    if admission.request != request:
        raise ValueError("execution admission is bound to another message/operation scope")
    if admission.current is not True:
        raise ValueError("execution admission is not current")
    if admission.request.runtime_profile_id != request.runtime_profile_id:
        raise ValueError("execution admission runtime profile changed")
    return admission
