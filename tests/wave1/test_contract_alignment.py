from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jlmirror_authority.control_plane import (  # noqa: E402
    AuthorizationDecision,
    RuntimeExecutionEvidence,
    RuntimeLifecycle,
    authorize_protected_operation,
)
from jlmirror_authority.model import (  # noqa: E402
    AdmissionDenied,
    AuditClass,
    AuthenticationStrengthEvidence,
    AuthorizationDeclaration,
    EnvironmentClass,
    Principal,
    PrincipalKind,
    ScopeClass,
    StepUpClass,
    TenantRequirement,
)
from jlmirror_authority.runtime_profiles import (  # noqa: E402
    API_AUTH_BOUNDARY,
    CONTROL_PLANE,
)

NOW = datetime(2026, 8, 24, 4, 0, tzinfo=timezone.utc)


class PrincipalAuthority:
    def is_current(self, **kwargs):
        return True


PRINCIPAL_AUTHORITY = PrincipalAuthority()


class UnusedPlacementAuthority:
    def resolve_current(self, tenant_id):
        raise AssertionError("cross-tenant platform operation must not resolve ordinary TenantContext")

    def context_is_current(self, context):
        raise AssertionError("cross-tenant platform operation must not consume ordinary TenantContext")


class Authz:
    def evaluate(self, **kwargs):
        return AuthorizationDecision(granted=True, current=True, policy_revision="platform-authz-r4")


class StrengthPolicy:
    def permits(self, **kwargs):
        return kwargs["policy_id"] == "platform-privileged-v1"


class RuntimeAuthority:
    def __init__(self, *, control_plane: bool = True, current: bool = True):
        if control_plane:
            self.evidence = RuntimeExecutionEvidence(
                runtime_profile_id="runtime.control-plane@1",
                principal_class="principal.control-plane@1",
                isolation_class="isolation.control-plane@1",
                ingress_profile="ingress.privileged-platform@1",
                runtime_generation="runtime-control-g7",
                environment_class=EnvironmentClass.PRODUCTION,
                runtime_lifecycle=RuntimeLifecycle.ACTIVE,
                current=current,
            )
        else:
            self.evidence = RuntimeExecutionEvidence(
                runtime_profile_id="runtime.api@1",
                principal_class="principal.application-serving@1",
                isolation_class="isolation.application-serving@1",
                ingress_profile="ingress.authenticated-api@1",
                runtime_generation="runtime-api-g9",
                environment_class=EnvironmentClass.PRODUCTION,
                runtime_lifecycle=RuntimeLifecycle.ACTIVE,
                current=current,
            )

    def resolve_current_execution(self, **kwargs):
        return self.evidence


def admin_strength() -> AuthenticationStrengthEvidence:
    return AuthenticationStrengthEvidence(
        issuer="id.example",
        acr="loa2",
        amr=frozenset({"pwd", "otp"}),
        authenticated_at=NOW - timedelta(minutes=1),
        evidence_expires_at=NOW + timedelta(minutes=5),
        policy_version="security-policy-r7",
        principal_id="platform-admin-1",
        principal_credential_generation="session-g7",
    )


class AuthorizationDeclarationAlignmentTests(unittest.TestCase):
    def test_legacy_tenant_required_normalizes_to_canonical_requirement(self):
        declaration = AuthorizationDeclaration(
            action="organization.memberships.read",
            scope=ScopeClass.TENANT,
            tenant_required=True,
            step_up=StepUpClass.NONE,
            audit_class=AuditClass.NORMAL,
        )
        self.assertEqual(declaration.tenant_requirement, TenantRequirement.REQUIRED)

    def test_cross_tenant_is_not_a_scope_class(self):
        self.assertNotIn(
            "explicit_cross_tenant_privileged",
            {item.value for item in ScopeClass},
        )
        self.assertIn(
            "explicit_cross_tenant_privileged",
            {item.value for item in TenantRequirement},
        )

    def test_cross_tenant_must_be_platform_and_privileged_audit(self):
        with self.assertRaises(ValueError):
            AuthorizationDeclaration(
                action="platform.tenants.suspend",
                scope=ScopeClass.TENANT,
                tenant_required=False,
                tenant_requirement=TenantRequirement.EXPLICIT_CROSS_TENANT_PRIVILEGED,
                step_up=StepUpClass.REQUIRED,
                authentication_strength_policy_id="platform-privileged-v1",
                audit_class=AuditClass.PRIVILEGED,
            )
        with self.assertRaises(ValueError):
            AuthorizationDeclaration(
                action="platform.tenants.suspend",
                scope=ScopeClass.PLATFORM,
                tenant_required=False,
                tenant_requirement=TenantRequirement.EXPLICIT_CROSS_TENANT_PRIVILEGED,
                step_up=StepUpClass.REQUIRED,
                authentication_strength_policy_id="platform-privileged-v1",
                audit_class=AuditClass.NORMAL,
            )

    def test_cross_tenant_compatibility_flag_cannot_contradict_requirement(self):
        with self.assertRaises(ValueError):
            AuthorizationDeclaration(
                action="platform.tenants.suspend",
                scope=ScopeClass.PLATFORM,
                tenant_required=True,
                tenant_requirement=TenantRequirement.EXPLICIT_CROSS_TENANT_PRIVILEGED,
                step_up=StepUpClass.REQUIRED,
                authentication_strength_policy_id="platform-privileged-v1",
                audit_class=AuditClass.PRIVILEGED,
            )

    def test_privileged_human_operation_cannot_declare_step_up_none(self):
        declaration = AuthorizationDeclaration(
            action="platform.tenants.suspend",
            scope=ScopeClass.PLATFORM,
            tenant_required=False,
            tenant_requirement=TenantRequirement.EXPLICIT_CROSS_TENANT_PRIVILEGED,
            step_up=StepUpClass.NONE,
            audit_class=AuditClass.PRIVILEGED,
        )
        with self.assertRaises(AdmissionDenied):
            authorize_protected_operation(
                principal=Principal(
                    "platform-admin-1", PrincipalKind.PLATFORM_ADMIN_PRINCIPAL, "session-g7"
                ),
                principal_authority=PRINCIPAL_AUTHORITY,
                declaration=declaration,
                placement_authority=UnusedPlacementAuthority(),
                authorization_authority=Authz(),
                context=None,
                now=NOW,
                runtime_binding=CONTROL_PLANE,
                runtime_authority=RuntimeAuthority(),
            )

    def test_cross_tenant_requires_platform_principal(self):
        declaration = AuthorizationDeclaration(
            action="platform.tenants.suspend",
            scope=ScopeClass.PLATFORM,
            tenant_required=False,
            tenant_requirement=TenantRequirement.EXPLICIT_CROSS_TENANT_PRIVILEGED,
            step_up=StepUpClass.REQUIRED,
            authentication_strength_policy_id="platform-privileged-v1",
            audit_class=AuditClass.PRIVILEGED,
        )
        with self.assertRaises(AdmissionDenied):
            authorize_protected_operation(
                principal=Principal(
                    "user-1", PrincipalKind.HUMAN_BROWSER_SESSION, "session-g1"
                ),
                principal_authority=PRINCIPAL_AUTHORITY,
                declaration=declaration,
                placement_authority=UnusedPlacementAuthority(),
                authorization_authority=Authz(),
                context=None,
                now=NOW,
                strength_policy=StrengthPolicy(),
                strength_evidence=None,
                runtime_binding=CONTROL_PLANE,
                runtime_authority=RuntimeAuthority(),
            )

    def test_cross_tenant_platform_principal_requires_control_plane_and_current_strength(self):
        declaration = AuthorizationDeclaration(
            action="platform.tenants.suspend",
            scope=ScopeClass.PLATFORM,
            tenant_required=False,
            tenant_requirement=TenantRequirement.EXPLICIT_CROSS_TENANT_PRIVILEGED,
            step_up=StepUpClass.REQUIRED,
            authentication_strength_policy_id="platform-privileged-v1",
            audit_class=AuditClass.PRIVILEGED,
        )
        principal = Principal(
            "platform-admin-1", PrincipalKind.PLATFORM_ADMIN_PRINCIPAL, "session-g7"
        )
        with self.assertRaises(AdmissionDenied):
            authorize_protected_operation(
                principal=principal,
                principal_authority=PRINCIPAL_AUTHORITY,
                declaration=declaration,
                placement_authority=UnusedPlacementAuthority(),
                authorization_authority=Authz(),
                context=None,
                now=NOW,
                strength_policy=StrengthPolicy(),
                strength_evidence=None,
                runtime_binding=CONTROL_PLANE,
                runtime_authority=RuntimeAuthority(),
            )
        with self.assertRaises(AdmissionDenied):
            authorize_protected_operation(
                principal=principal,
                principal_authority=PRINCIPAL_AUTHORITY,
                declaration=declaration,
                placement_authority=UnusedPlacementAuthority(),
                authorization_authority=Authz(),
                context=None,
                now=NOW,
                strength_policy=StrengthPolicy(),
                strength_evidence=admin_strength(),
                runtime_binding=API_AUTH_BOUNDARY,
            )

        # Merely passing the CONTROL_PLANE binding is not executing-runtime proof.
        with self.assertRaises(AdmissionDenied):
            authorize_protected_operation(
                principal=principal,
                principal_authority=PRINCIPAL_AUTHORITY,
                declaration=declaration,
                placement_authority=UnusedPlacementAuthority(),
                authorization_authority=Authz(),
                context=None,
                now=NOW,
                strength_policy=StrengthPolicy(),
                strength_evidence=admin_strength(),
                runtime_binding=CONTROL_PLANE,
            )

        # Trusted runtime evidence for the ordinary API boundary cannot be laundered
        # by a caller-selected CONTROL_PLANE binding.
        with self.assertRaises(AdmissionDenied):
            authorize_protected_operation(
                principal=principal,
                principal_authority=PRINCIPAL_AUTHORITY,
                declaration=declaration,
                placement_authority=UnusedPlacementAuthority(),
                authorization_authority=Authz(),
                context=None,
                now=NOW,
                strength_policy=StrengthPolicy(),
                strength_evidence=admin_strength(),
                runtime_binding=CONTROL_PLANE,
                runtime_authority=RuntimeAuthority(control_plane=False),
            )

        decision = authorize_protected_operation(
            principal=principal,
            principal_authority=PRINCIPAL_AUTHORITY,
            declaration=declaration,
            placement_authority=UnusedPlacementAuthority(),
            authorization_authority=Authz(),
            context=None,
            now=NOW,
            strength_policy=StrengthPolicy(),
            strength_evidence=admin_strength(),
            runtime_binding=CONTROL_PLANE,
            runtime_authority=RuntimeAuthority(),
        )
        self.assertTrue(decision.granted)


if __name__ == "__main__":
    unittest.main(verbosity=2)
