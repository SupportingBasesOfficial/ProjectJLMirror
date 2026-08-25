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
    FinalAdmissionEvidence,
    PlacementEvidence,
    RuntimeLifecycle,
    authorize_protected_operation,
    construct_tenant_context,
)
from jlmirror_authority.model import (  # noqa: E402
    AdmissionDenied,
    AuditClass,
    AuthorizationDeclaration,
    EnvironmentClass,
    Principal,
    PrincipalKind,
    ScopeClass,
    StepUpClass,
)

NOW = datetime(2026, 8, 24, 20, 45, tzinfo=timezone.utc)


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


class FlippingAuthorizationAuthority:
    def __init__(self, *, final_current=True, final_granted=False):
        self.calls = 0
        self.final_current = final_current
        self.final_granted = final_granted

    def evaluate(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return AuthorizationDecision(True, True, "authz-r1")
        return AuthorizationDecision(
            self.final_granted,
            self.final_current,
            "authz-r2",
        )


class AdvancingAuthorizationAuthority:
    def __init__(self):
        self.calls = 0

    def evaluate(self, **kwargs):
        self.calls += 1
        return AuthorizationDecision(True, True, f"authz-r{self.calls}")


class TenantFinalAdmissionAuthority:
    def __init__(self, context):
        self.context = context
        self.calls = 0

    def finalize_current_admission(self, *, principal, context, declaration, **kwargs):
        self.calls += 1
        if context != self.context:
            raise AssertionError("test finalizer received unexpected TenantContext")
        return FinalAdmissionEvidence(
            granted=True,
            current=True,
            admission_revision="admission-r3",
            authorization_policy_revision="authz-final-r3",
            principal_authority_revision="principal-r3",
            principal_id=principal.principal_id,
            principal_credential_generation=principal.credential_generation,
            action=declaration.action,
            tenant_id=context.tenant_id,
            cell_id=context.cell_id,
            placement_authority_revision="placement-r3",
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
            executing_runtime_authority_revision="runtime-authority-r3",
            executing_runtime_profile_id="runtime.api@1",
            executing_runtime_generation="runtime-api-g3",
        )


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


def declaration():
    return AuthorizationDeclaration(
        action="organization.memberships.read",
        scope=ScopeClass.TENANT,
        tenant_required=True,
        step_up=StepUpClass.NONE,
        audit_class=AuditClass.NORMAL,
    )


class FinalAuthorizationCurrentnessTests(unittest.TestCase):
    def setUp(self):
        self.principal = Principal(
            "user-1", PrincipalKind.HUMAN_BROWSER_SESSION, "session-g1"
        )
        self.principal_authority = PrincipalAuthority()
        self.placement_authority = PlacementAuthority(placement())
        current = self.placement_authority.evidence
        self.context = construct_tenant_context(
            principal=self.principal,
            principal_authority=self.principal_authority,
            placement_authority=self.placement_authority,
            tenant_id=current.tenant_id,
            destination_cell_id=current.cell_id,
            destination_runtime_generation=current.runtime_generation,
            destination_configuration_generation=current.configuration_generation,
            destination_workload_credential_generation=current.workload_credential_generation,
            destination_network_policy_generation=current.network_policy_generation,
            required_environment=current.environment_class,
            now=NOW,
        )

    def test_permission_revoked_after_first_evaluation_fails_closed(self):
        authority = FlippingAuthorizationAuthority(final_current=True, final_granted=False)
        with self.assertRaises(AdmissionDenied):
            authorize_protected_operation(
                principal=self.principal,
                principal_authority=self.principal_authority,
                declaration=declaration(),
                placement_authority=self.placement_authority,
                authorization_authority=authority,
                context=self.context,
                now=NOW,
            )
        self.assertEqual(authority.calls, 2)

    def test_authorization_currentness_lost_after_first_evaluation_fails_closed(self):
        authority = FlippingAuthorizationAuthority(final_current=False, final_granted=True)
        with self.assertRaises(AdmissionDenied):
            authorize_protected_operation(
                principal=self.principal,
                principal_authority=self.principal_authority,
                declaration=declaration(),
                placement_authority=self.placement_authority,
                authorization_authority=authority,
                context=self.context,
                now=NOW,
            )
        self.assertEqual(authority.calls, 2)

    def test_revision_bound_final_admission_authorization_revision_is_returned(self):
        authority = AdvancingAuthorizationAuthority()
        finalizer = TenantFinalAdmissionAuthority(self.context)
        decision = authorize_protected_operation(
            principal=self.principal,
            principal_authority=self.principal_authority,
            declaration=declaration(),
            placement_authority=self.placement_authority,
            authorization_authority=authority,
            context=self.context,
            now=NOW,
            final_admission_authority=finalizer,
        )
        self.assertEqual(authority.calls, 2)
        self.assertEqual(finalizer.calls, 1)
        self.assertEqual(decision.policy_revision, "authz-final-r3")


if __name__ == "__main__":
    unittest.main(verbosity=2)
