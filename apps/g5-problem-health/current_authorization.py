from __future__ import annotations

from datetime import datetime

from jlmirror_authority.control_plane import (
    FinalAdmissionAuthorityPort,
    PlacementAuthorityPort,
    CurrentAuthorizationPort as PlatformAuthorizationPort,
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

from metrics import (
    CurrentAuthorizationEvidence,
    METRIC_READ_ACTION,
    RESOURCE_READ_ACTION,
)


class BoundProblemHealthAuthorization:
    def __init__(
        self,
        *,
        principal: Principal,
        authentication_strength: AuthenticationStrengthEvidence | None,
        principal_authority: CurrentPrincipalAuthorityPort,
        placement_authority: PlacementAuthorityPort,
        authorization_authority: PlatformAuthorizationPort,
        strength_policy: AuthenticationStrengthPolicyPort,
        final_admission_authority: FinalAdmissionAuthorityPort,
        now: datetime,
    ) -> None:
        self._principal = principal
        self._authentication_strength = authentication_strength
        self._principal_authority = principal_authority
        self._placement_authority = placement_authority
        self._authorization_authority = authorization_authority
        self._strength_policy = strength_policy
        self._final_admission_authority = final_admission_authority
        self._now = now

    @property
    def actor_ref(self) -> str:
        return self._principal.principal_id

    def require(
        self,
        *,
        actor_ref: str,
        tenant_id: str,
        action: str,
    ) -> CurrentAuthorizationEvidence:
        if actor_ref != self._principal.principal_id:
            raise AdmissionDenied("actor reference does not match the current browser principal")
        if action not in {RESOURCE_READ_ACTION, PROBLEM_READ_ACTION, HEALTH_READ_ACTION}:
            raise AdmissionDenied("action is outside the bounded G5 authorization surface")

        placement = self._placement_authority.resolve_current(tenant_id)
        if placement is None:
            raise AdmissionDenied("trusted tenant placement cannot be established")

        context = construct_tenant_context(
            principal=self._principal,
            principal_authority=self._principal_authority,
            placement_authority=self._placement_authority,
            tenant_id=tenant_id,
            destination_cell_id=placement.cell_id,
            destination_runtime_generation=placement.runtime_generation,
            destination_configuration_generation=placement.configuration_generation,
            destination_workload_credential_generation=placement.workload_credential_generation,
            destination_network_policy_generation=placement.network_policy_generation,
            required_environment=placement.environment_class,
            now=self._now,
            runtime_binding=API_AUTH_BOUNDARY,
        )

        declaration = AuthorizationDeclaration(
            action=action,
            scope=ScopeClass.TENANT,
            tenant_required=True,
            step_up=StepUpClass.POLICY_DRIVEN,
            audit_class=AuditClass.NORMAL,
            authentication_strength_policy_id="shell-access-v1",
        )
        captured: list[FinalAdmissionEvidence] = []
        downstream = self._final_admission_authority

        class Capture:
            def finalize_current_admission(self, **kwargs) -> FinalAdmissionEvidence:
                evidence = downstream.finalize_current_admission(**kwargs)
                if isinstance(evidence, FinalAdmissionEvidence):
                    captured.append(evidence)
                return evidence

        authorize_protected_operation(
            principal=self._principal,
            principal_authority=self._principal_authority,
            declaration=declaration,
            placement_authority=self._placement_authority,
            authorization_authority=self._authorization_authority,
            context=context,
            now=self._now,
            strength_policy=self._strength_policy,
            strength_evidence=self._authentication_strength,
            runtime_binding=API_AUTH_BOUNDARY,
            final_admission_authority=Capture(),
        )
        if len(captured) != 1:
            raise AdmissionDenied("final problem/health admission evidence is unavailable")
        evidence = captured[0]
        if evidence.tenant_id != tenant_id or evidence.action != action:
            raise AdmissionDenied("final problem/health admission evidence does not match the requested operation")
        return CurrentAuthorizationEvidence(
            actor_principal_id=evidence.principal_id,
            actor_principal_kind=evidence.principal_kind.value,
            actor_generation_ref=evidence.principal_credential_generation,
            authorization_decision_ref=evidence.admission_revision,
        )
