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
    PlacementEvidence,
    RuntimeLifecycle,
    authorize_protected_operation,
    construct_tenant_context,
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
)

NOW = datetime(2026, 8, 24, 20, 15, tzinfo=timezone.utc)


class PrincipalAuthority:
    def is_current(self, **kwargs):
        return True


class PlacementAuthority:
    def __init__(self, evidence):
        self.evidence = evidence

    def resolve_current(self, tenant_id):
        return self.evidence if tenant_id == self.evidence.tenant_id else None

    def context_is_current(self, context):
        return True


class AuthorizationAuthority:
    def evaluate(self, **kwargs):
        return AuthorizationDecision(True, True, "authz-r1")


class FlippingStrengthPolicy:
    def __init__(self):
        self.calls = 0

    def permits(self, **kwargs):
        self.calls += 1
        return self.calls == 1


def placement():
    return PlacementEvidence(
        tenant_id="tenant-acme",
        cell_id="cell-a",
        placement_version="pv-1",
        runtime_generation="runtime-g1",
        runtime_profile_id="runtime.api@1",
        runtime_isolation_class="isolation.application-serving@1",
        configuration_generation="cfg-g1",
        workload_credential_generation="wc-g1",
        network_policy_generation="np-g1",
        environment_class=EnvironmentClass.PRODUCTION,
        isolation_class="pooled",
        runtime_lifecycle=RuntimeLifecycle.ACTIVE,
        placement_current=True,
        operation_eligible=True,
        cell_admission_current=True,
        fence_scope_id="tenant:acme",
        fence_epoch=1,
    )


class PostAuthorizationStrengthCurrentnessTests(unittest.TestCase):
    def test_policy_hardening_during_authorization_fails_closed(self):
        principal = Principal(
            "user-1",
            PrincipalKind.HUMAN_BROWSER_SESSION,
            "session-g1",
        )
        principal_authority = PrincipalAuthority()
        placement_authority = PlacementAuthority(placement())
        current = placement_authority.evidence
        context = construct_tenant_context(
            principal=principal,
            principal_authority=principal_authority,
            placement_authority=placement_authority,
            tenant_id=current.tenant_id,
            destination_cell_id=current.cell_id,
            destination_runtime_generation=current.runtime_generation,
            destination_configuration_generation=current.configuration_generation,
            destination_workload_credential_generation=current.workload_credential_generation,
            destination_network_policy_generation=current.network_policy_generation,
            required_environment=current.environment_class,
            now=NOW,
        )
        declaration = AuthorizationDeclaration(
            action="organization.memberships.manage",
            scope=ScopeClass.TENANT,
            tenant_required=True,
            step_up=StepUpClass.REQUIRED,
            audit_class=AuditClass.PRIVILEGED,
            authentication_strength_policy_id="privileged-v1",
        )
        evidence = AuthenticationStrengthEvidence(
            issuer="id.example",
            acr="loa2",
            amr=frozenset({"pwd", "otp"}),
            authenticated_at=NOW - timedelta(minutes=1),
            evidence_expires_at=NOW + timedelta(minutes=5),
            policy_version="security-policy-v7",
            principal_id=principal.principal_id,
            principal_credential_generation=principal.credential_generation,
        )
        policy = FlippingStrengthPolicy()

        with self.assertRaises(AdmissionDenied):
            authorize_protected_operation(
                principal=principal,
                principal_authority=principal_authority,
                declaration=declaration,
                placement_authority=placement_authority,
                authorization_authority=AuthorizationAuthority(),
                context=context,
                now=NOW,
                strength_policy=policy,
                strength_evidence=evidence,
            )
        self.assertEqual(policy.calls, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
