from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jlmirror_authority.control_plane import (  # noqa: E402
    AuthorizationDecision,
    authorize_protected_operation,
)
from jlmirror_authority.model import (  # noqa: E402
    AdmissionDenied,
    AuditClass,
    AuthorizationDeclaration,
    Principal,
    PrincipalKind,
    ScopeClass,
    StepUpClass,
    TenantRequirement,
)

NOW = datetime(2026, 8, 24, 4, 0, tzinfo=timezone.utc)


class UnusedPlacementAuthority:
    def resolve_current(self, tenant_id):
        raise AssertionError("cross-tenant platform operation must not resolve ordinary TenantContext")

    def context_is_current(self, context):
        raise AssertionError("cross-tenant platform operation must not consume ordinary TenantContext")


class Authz:
    def evaluate(self, **kwargs):
        return AuthorizationDecision(granted=True, current=True, policy_revision="platform-authz-r4")


class AuthorizationDeclarationAlignmentTests(unittest.TestCase):
    def test_legacy_tenant_required_normalizes_to_canonical_requirement(self):
        declaration = AuthorizationDeclaration(
            action="organization.memberships.manage",
            scope=ScopeClass.TENANT,
            tenant_required=True,
            step_up=StepUpClass.NONE,
            audit_class=AuditClass.PRIVILEGED,
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
                step_up=StepUpClass.NONE,
                audit_class=AuditClass.PRIVILEGED,
            )
        with self.assertRaises(ValueError):
            AuthorizationDeclaration(
                action="platform.tenants.suspend",
                scope=ScopeClass.PLATFORM,
                tenant_required=False,
                tenant_requirement=TenantRequirement.EXPLICIT_CROSS_TENANT_PRIVILEGED,
                step_up=StepUpClass.NONE,
                audit_class=AuditClass.NORMAL,
            )

    def test_cross_tenant_compatibility_flag_cannot_contradict_requirement(self):
        with self.assertRaises(ValueError):
            AuthorizationDeclaration(
                action="platform.tenants.suspend",
                scope=ScopeClass.PLATFORM,
                tenant_required=True,
                tenant_requirement=TenantRequirement.EXPLICIT_CROSS_TENANT_PRIVILEGED,
                step_up=StepUpClass.NONE,
                audit_class=AuditClass.PRIVILEGED,
            )

    def test_cross_tenant_requires_platform_principal(self):
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
                    "user-1", PrincipalKind.HUMAN_BROWSER_SESSION, "session-g1"
                ),
                declaration=declaration,
                placement_authority=UnusedPlacementAuthority(),
                authorization_authority=Authz(),
                context=None,
                now=NOW,
            )

    def test_cross_tenant_platform_principal_does_not_reuse_ordinary_tenant_context(self):
        declaration = AuthorizationDeclaration(
            action="platform.tenants.suspend",
            scope=ScopeClass.PLATFORM,
            tenant_required=False,
            tenant_requirement=TenantRequirement.EXPLICIT_CROSS_TENANT_PRIVILEGED,
            step_up=StepUpClass.NONE,
            audit_class=AuditClass.PRIVILEGED,
        )
        decision = authorize_protected_operation(
            principal=Principal(
                "platform-admin-1", PrincipalKind.PLATFORM_ADMIN_PRINCIPAL, "session-g7"
            ),
            declaration=declaration,
            placement_authority=UnusedPlacementAuthority(),
            authorization_authority=Authz(),
            context=None,
            now=NOW,
        )
        self.assertTrue(decision.granted)


if __name__ == "__main__":
    unittest.main(verbosity=2)
