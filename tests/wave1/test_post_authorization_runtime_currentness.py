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
from jlmirror_authority.runtime_profiles import CONTROL_PLANE  # noqa: E402

NOW = datetime(2026, 8, 24, 20, 55, tzinfo=timezone.utc)


class PrincipalAuthority:
    def is_current(self, **kwargs):
        return True


class UnusedPlacement:
    def resolve_current(self, tenant_id):
        raise AssertionError("cross-tenant admission must not use TenantContext placement")

    def context_is_current(self, context):
        raise AssertionError("cross-tenant admission must not use TenantContext placement")


class Authz:
    def evaluate(self, **kwargs):
        return AuthorizationDecision(True, True, "platform-authz-r9")


class StrengthPolicy:
    def permits(self, **kwargs):
        return True


class FlippingRuntimeAuthority:
    def __init__(self):
        self.calls = 0

    def resolve_current_execution(self, **kwargs):
        self.calls += 1
        return RuntimeExecutionEvidence(
            runtime_profile_id="runtime.control-plane@1",
            principal_class="principal.control-plane@1",
            isolation_class="isolation.control-plane@1",
            ingress_profile="ingress.privileged-platform@1",
            runtime_generation="runtime-control-g7",
            environment_class=EnvironmentClass.PRODUCTION,
            runtime_lifecycle=RuntimeLifecycle.ACTIVE,
            current=self.calls == 1,
        )


def strength():
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


class PostAuthorizationRuntimeCurrentnessTests(unittest.TestCase):
    def test_cross_tenant_runtime_retired_during_admission_fails_closed(self):
        runtime = FlippingRuntimeAuthority()
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
                    "platform-admin-1",
                    PrincipalKind.PLATFORM_ADMIN_PRINCIPAL,
                    "session-g7",
                ),
                principal_authority=PrincipalAuthority(),
                declaration=declaration,
                placement_authority=UnusedPlacement(),
                authorization_authority=Authz(),
                context=None,
                now=NOW,
                strength_policy=StrengthPolicy(),
                strength_evidence=strength(),
                runtime_binding=CONTROL_PLANE,
                runtime_authority=runtime,
            )
        self.assertEqual(runtime.calls, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
