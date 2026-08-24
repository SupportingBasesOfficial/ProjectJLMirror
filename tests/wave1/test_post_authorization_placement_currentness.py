from __future__ import annotations

from dataclasses import replace
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

NOW = datetime(2026, 8, 24, 19, 30, tzinfo=timezone.utc)


class PrincipalAuthority:
    def is_current(self, **kwargs):
        return True


class MutablePlacementAuthority:
    def __init__(self, evidence: PlacementEvidence):
        self.evidence = evidence

    def resolve_current(self, tenant_id):
        return self.evidence if tenant_id == self.evidence.tenant_id else None

    def context_is_current(self, context):
        return True


class RelocatingAuthorizationAuthority:
    def __init__(self, placement_authority: MutablePlacementAuthority):
        self.placement_authority = placement_authority

    def evaluate(self, **kwargs):
        current = self.placement_authority.evidence
        self.placement_authority.evidence = replace(
            current,
            placement_version="pv-2",
            runtime_generation="runtime-g2",
            fence_epoch=current.fence_epoch + 1,
        )
        return AuthorizationDecision(True, True, "policy-rev-2")


def placement() -> PlacementEvidence:
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


class PostAuthorizationPlacementCurrentnessTests(unittest.TestCase):
    def test_relocation_during_owning_authorization_fails_closed(self):
        principal = Principal(
            "user-1",
            PrincipalKind.HUMAN_BROWSER_SESSION,
            "session-g1",
        )
        principal_authority = PrincipalAuthority()
        placement_authority = MutablePlacementAuthority(placement())
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
            action="organization.memberships.read",
            scope=ScopeClass.TENANT,
            tenant_required=True,
            step_up=StepUpClass.NONE,
            audit_class=AuditClass.NORMAL,
        )

        with self.assertRaises(AdmissionDenied):
            authorize_protected_operation(
                principal=principal,
                principal_authority=principal_authority,
                declaration=declaration,
                placement_authority=placement_authority,
                authorization_authority=RelocatingAuthorizationAuthority(
                    placement_authority
                ),
                context=context,
                now=NOW,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
