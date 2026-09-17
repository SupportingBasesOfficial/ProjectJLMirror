from __future__ import annotations

from datetime import datetime
from typing import Protocol

from jlmirror_authority.control_plane import (
    FinalAdmissionAuthorityPort,
    PlacementAuthorityPort,
    CurrentAuthorizationPort,
    CurrentPrincipalAuthorityPort,
    FinalAdmissionEvidence,
    authorize_protected_operation,
    construct_tenant_context,
)
from jlmirror_authority.browser import AuthenticationStrengthPolicyPort
from jlmirror_authority.model import (
    AdmissionDenied,
    AuditClass,
    AuthenticationStrengthEvidence,
    AuthorizationDeclaration,
    Principal,
    ScopeClass,
    StepUpClass,
)
from jlmirror_authority.runtime_profiles import API_AUTH_BOUNDARY

from .shell import TenantShellAdmission


SHELL_AUTHORIZATION = AuthorizationDeclaration(
    action="organization.memberships.read",
    scope=ScopeClass.TENANT,
    tenant_required=True,
    step_up=StepUpClass.POLICY_DRIVEN,
    audit_class=AuditClass.NORMAL,
    authentication_strength_policy_id="shell-access-v1",
)


class CanonicalTenantAdmission:
    """G1 adapter over the accepted Wave 1 current-authority owner.

    The requested tenant id is only lookup scope. Placement, membership/permission,
    authentication-strength and final admission are all re-established by accepted
    server-side authorities before a shell view is returned.
    """

    def __init__(
        self,
        *,
        principal_authority: CurrentPrincipalAuthorityPort,
        placement_authority: PlacementAuthorityPort,
        authorization_authority: CurrentAuthorizationPort,
        strength_policy: AuthenticationStrengthPolicyPort,
        final_admission_authority: FinalAdmissionAuthorityPort,
    ) -> None:
        self._principal_authority = principal_authority
        self._placement_authority = placement_authority
        self._authorization_authority = authorization_authority
        self._strength_policy = strength_policy
        self._final_admission_authority = final_admission_authority

    def require_current(
        self,
        *,
        principal: Principal,
        tenant_id: str,
        authentication_strength: AuthenticationStrengthEvidence | None,
        now: datetime,
    ) -> TenantShellAdmission:
        placement = self._placement_authority.resolve_current(tenant_id)
        if placement is None:
            raise AdmissionDenied("trusted tenant placement cannot be established")

        context = construct_tenant_context(
            principal=principal,
            principal_authority=self._principal_authority,
            placement_authority=self._placement_authority,
            tenant_id=tenant_id,
            destination_cell_id=placement.cell_id,
            destination_runtime_generation=placement.runtime_generation,
            destination_configuration_generation=placement.configuration_generation,
            destination_workload_credential_generation=placement.workload_credential_generation,
            destination_network_policy_generation=placement.network_policy_generation,
            required_environment=placement.environment_class,
            now=now,
            runtime_binding=API_AUTH_BOUNDARY,
        )

        captured: list[FinalAdmissionEvidence] = []
        downstream = self._final_admission_authority

        class CaptureFinalAdmission:
            def finalize_current_admission(self, **kwargs) -> FinalAdmissionEvidence:
                evidence = downstream.finalize_current_admission(**kwargs)
                if isinstance(evidence, FinalAdmissionEvidence):
                    captured.append(evidence)
                return evidence

        authorize_protected_operation(
            principal=principal,
            principal_authority=self._principal_authority,
            declaration=SHELL_AUTHORIZATION,
            placement_authority=self._placement_authority,
            authorization_authority=self._authorization_authority,
            context=context,
            now=now,
            strength_policy=self._strength_policy,
            strength_evidence=authentication_strength,
            runtime_binding=API_AUTH_BOUNDARY,
            final_admission_authority=CaptureFinalAdmission(),
        )
        if len(captured) != 1:
            raise AdmissionDenied("final shell admission evidence is unavailable")
        evidence = captured[0]
        if evidence.tenant_id != tenant_id:
            raise AdmissionDenied("final shell admission evidence belongs to another tenant")
        return TenantShellAdmission(
            tenant_id=tenant_id,
            admission_revision=evidence.admission_revision,
        )
