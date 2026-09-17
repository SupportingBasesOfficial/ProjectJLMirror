from __future__ import annotations

from datetime import datetime

from jlmirror_authority.control_plane import (
    FinalAdmissionEvidence,
    PlacementEvidence,
    authorize_protected_operation,
    construct_tenant_context,
)
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


class Wave1TenantAdmission:
    """G1 adapter over the accepted Wave 1 current-authority boundary.

    The requested tenant id is lookup scope only. Placement, membership/permission,
    authentication-strength and final admission remain owned by the injected
    canonical authorities.
    """

    def __init__(
        self,
        *,
        principal_authority,
        placement_authority,
        authorization_authority,
        final_admission_authority,
        strength_policy,
        action: str = "organization.memberships.read",
        strength_policy_id: str = "g1-shell-strength-v1",
    ) -> None:
        self._principal_authority = principal_authority
        self._placement_authority = placement_authority
        self._authorization_authority = authorization_authority
        self._final_admission_authority = final_admission_authority
        self._strength_policy = strength_policy
        self._declaration = AuthorizationDeclaration(
            action=action,
            scope=ScopeClass.TENANT,
            tenant_required=True,
            step_up=StepUpClass.POLICY_DRIVEN,
            audit_class=AuditClass.NORMAL,
            authentication_strength_policy_id=strength_policy_id,
        )

    def require_current(
        self,
        *,
        principal: Principal,
        tenant_id: str,
        now: datetime,
        authentication_strength: AuthenticationStrengthEvidence | None,
    ) -> TenantShellAdmission:
        placement = self._placement_authority.resolve_current(tenant_id)
        if not isinstance(placement, PlacementEvidence) or placement.tenant_id != tenant_id:
            raise AdmissionDenied("trusted current tenant placement is unavailable")

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
        class _CapturingFinalAdmission:
            def __init__(self, owner) -> None:
                self._owner = owner
                self.evidence: FinalAdmissionEvidence | None = None

            def finalize_current_admission(self, **kwargs):
                evidence = self._owner.finalize_current_admission(**kwargs)
                self.evidence = evidence
                return evidence

        final_admission = _CapturingFinalAdmission(self._final_admission_authority)
        authorize_protected_operation(
            principal=principal,
            principal_authority=self._principal_authority,
            declaration=self._declaration,
            placement_authority=self._placement_authority,
            authorization_authority=self._authorization_authority,
            context=context,
            now=now,
            strength_policy=self._strength_policy,
            strength_evidence=authentication_strength,
            runtime_binding=API_AUTH_BOUNDARY,
            final_admission_authority=final_admission,
        )
        evidence = final_admission.evidence
        if not isinstance(evidence, FinalAdmissionEvidence):
            raise AdmissionDenied("final admission evidence is unavailable after canonical admission")
        return TenantShellAdmission(
            tenant_id=context.tenant_id,
            admission_revision=evidence.admission_revision,
        )
