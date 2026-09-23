from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from jlmirror_authority.control_plane import (  # noqa: E402
    AuthorizationDecision,
    FinalAdmissionEvidence,
    PlacementEvidence,
    RuntimeLifecycle,
)
from jlmirror_authority.model import (  # noqa: E402
    AdmissionDenied,
    AuthenticationStrengthEvidence,
    EnvironmentClass,
    Principal,
    PrincipalKind,
)
from jlmirror_authority.runtime_profiles import API_AUTH_BOUNDARY  # noqa: E402
from jlmirror_g1.authority import CanonicalTenantAdmission, SHELL_AUTHORIZATION  # noqa: E402


NOW = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)


def principal() -> Principal:
    return Principal("principal-a", PrincipalKind.HUMAN_BROWSER_SESSION, "session-g1")


def strength() -> AuthenticationStrengthEvidence:
    return AuthenticationStrengthEvidence(
        issuer="id.example",
        acr="loa1",
        amr=frozenset({"pwd"}),
        authenticated_at=NOW - timedelta(minutes=1),
        evidence_expires_at=NOW + timedelta(minutes=5),
        policy_version="strength-r1",
        principal_id="principal-a",
        principal_credential_generation="session-g1",
    )


class PrincipalAuthority:
    def __init__(self) -> None:
        self.current = True

    def is_current(self, **kwargs):
        return self.current


class PlacementAuthority:
    def __init__(self) -> None:
        self.evidence = PlacementEvidence(
            tenant_id="tenant-a",
            cell_id="cell-a",
            placement_version="placement-r1",
            runtime_generation="runtime-g1",
            runtime_profile_id=API_AUTH_BOUNDARY.runtime_profile_id,
            runtime_isolation_class=API_AUTH_BOUNDARY.isolation_class,
            configuration_generation="configuration-g1",
            workload_credential_generation="workload-g1",
            network_policy_generation="network-g1",
            environment_class=EnvironmentClass.VALIDATION,
            isolation_class="pooled",
            runtime_lifecycle=RuntimeLifecycle.ACTIVE,
            placement_current=True,
            operation_eligible=True,
            cell_admission_current=True,
            fence_scope_id="tenant-a",
            fence_epoch=1,
        )
        self.current = True

    def resolve_current(self, tenant_id):
        return self.evidence if tenant_id == self.evidence.tenant_id else None

    def context_is_current(self, context):
        return self.current and context.tenant_id == self.evidence.tenant_id


class AuthorizationAuthority:
    def __init__(self) -> None:
        self.granted = True

    def evaluate(self, **kwargs):
        return AuthorizationDecision(
            granted=self.granted,
            current=True,
            policy_revision="membership-r1",
        )


class StrengthPolicy:
    def permits(self, *, policy_id, evidence, now):
        return (
            policy_id == "shell-access-v1"
            and evidence.policy_version == "strength-r1"
            and evidence.is_current(now)
        )


class FinalAdmission:
    def __init__(self) -> None:
        self.calls = 0

    def finalize_current_admission(
        self,
        *,
        principal,
        context,
        declaration,
        expected_runtime_binding,
        authentication_strength_evidence,
        cross_tenant_target,
    ):
        self.calls += 1
        if expected_runtime_binding != API_AUTH_BOUNDARY:
            raise AdmissionDenied("wrong runtime")
        return FinalAdmissionEvidence(
            granted=True,
            current=True,
            admission_revision="final-r1",
            authorization_policy_revision="membership-r1",
            principal_authority_revision="principal-r1",
            principal_id=principal.principal_id,
            principal_kind=principal.kind,
            principal_credential_generation=principal.credential_generation,
            action=declaration.action,
            scope=declaration.scope,
            tenant_requirement=declaration.tenant_requirement,
            resource_scope=declaration.resource_scope,
            cross_tenant_target=cross_tenant_target,
            authentication_strength_policy_id=declaration.authentication_strength_policy_id,
            tenant_id=context.tenant_id,
            cell_id=context.cell_id,
            placement_authority_revision="placement-authority-r1",
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
            authentication_strength_policy_revision=authentication_strength_evidence.policy_version,
            executing_runtime_authority_revision="runtime-authority-r1",
            executing_runtime_profile_id=API_AUTH_BOUNDARY.runtime_profile_id,
            executing_runtime_generation="runtime-execution-g1",
            executing_runtime_environment_class=EnvironmentClass.VALIDATION,
        )


class CanonicalTenantAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.principals = PrincipalAuthority()
        self.placement = PlacementAuthority()
        self.authorization = AuthorizationAuthority()
        self.final = FinalAdmission()
        self.adapter = CanonicalTenantAdmission(
            principal_authority=self.principals,
            placement_authority=self.placement,
            authorization_authority=self.authorization,
            strength_policy=StrengthPolicy(),
            final_admission_authority=self.final,
        )

    def test_shell_declaration_requires_current_membership_and_strength(self):
        self.assertEqual(SHELL_AUTHORIZATION.action, "organization.memberships.read")
        self.assertEqual(SHELL_AUTHORIZATION.authentication_strength_policy_id, "shell-access-v1")
        admission = self.adapter.require_current(
            principal=principal(),
            tenant_id="tenant-a",
            authentication_strength=strength(),
            now=NOW,
        )
        self.assertEqual(admission.tenant_id, "tenant-a")
        self.assertEqual(admission.admission_revision, "final-r1")
        self.assertEqual(self.final.calls, 1)

    def test_client_selected_other_tenant_is_not_authority(self):
        with self.assertRaises(AdmissionDenied):
            self.adapter.require_current(
                principal=principal(),
                tenant_id="tenant-b",
                authentication_strength=strength(),
                now=NOW,
            )

    def test_revoked_principal_fails_before_final_admission(self):
        self.principals.current = False
        with self.assertRaises(AdmissionDenied):
            self.adapter.require_current(
                principal=principal(),
                tenant_id="tenant-a",
                authentication_strength=strength(),
                now=NOW,
            )
        self.assertEqual(self.final.calls, 0)

    def test_revoked_permission_fails_before_final_admission(self):
        self.authorization.granted = False
        with self.assertRaises(AdmissionDenied):
            self.adapter.require_current(
                principal=principal(),
                tenant_id="tenant-a",
                authentication_strength=strength(),
                now=NOW,
            )
        self.assertEqual(self.final.calls, 0)

    def test_stale_authentication_strength_fails_closed(self):
        stale = AuthenticationStrengthEvidence(
            issuer="id.example",
            acr="loa1",
            amr=frozenset({"pwd"}),
            authenticated_at=NOW - timedelta(minutes=10),
            evidence_expires_at=NOW - timedelta(minutes=1),
            policy_version="strength-r1",
            principal_id="principal-a",
            principal_credential_generation="session-g1",
        )
        with self.assertRaises(AdmissionDenied):
            self.adapter.require_current(
                principal=principal(),
                tenant_id="tenant-a",
                authentication_strength=stale,
                now=NOW,
            )
        self.assertEqual(self.final.calls, 0)


if __name__ == "__main__":
    unittest.main()
