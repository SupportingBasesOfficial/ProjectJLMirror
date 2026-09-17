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
from jlmirror_g1.csrf import CsrfKeyRing  # noqa: E402
from jlmirror_g1.wave1_admission import Wave1TenantAdmission  # noqa: E402


NOW = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)


class PrincipalAuthority:
    def is_current(self, **kwargs):
        return True


class PlacementAuthority:
    def __init__(self):
        self.current = True
        self.evidence = PlacementEvidence(
            tenant_id="tenant-a",
            cell_id="cell-a",
            placement_version="pv-1",
            runtime_generation="runtime-g1",
            runtime_profile_id="runtime.api@1",
            runtime_isolation_class="isolation.application-serving@1",
            configuration_generation="cfg-g1",
            workload_credential_generation="wc-g1",
            network_policy_generation="np-g1",
            environment_class=EnvironmentClass.VALIDATION,
            isolation_class="pooled",
            runtime_lifecycle=RuntimeLifecycle.ACTIVE,
            placement_current=True,
            operation_eligible=True,
            cell_admission_current=True,
            fence_scope_id="tenant:a",
            fence_epoch=1,
        )

    def resolve_current(self, tenant_id):
        return self.evidence if tenant_id == self.evidence.tenant_id else None

    def context_is_current(self, context):
        return self.current


class AuthorizationAuthority:
    def evaluate(self, **kwargs):
        return AuthorizationDecision(
            granted=True,
            current=True,
            policy_revision="serial-authz-r1",
        )


class StrengthPolicy:
    def __init__(self):
        self.allowed = True

    def permits(self, **kwargs):
        return self.allowed


class FinalAdmissionAuthority:
    def __init__(self):
        self.override_tenant = None

    def finalize_current_admission(self, **kwargs):
        principal = kwargs["principal"]
        context = kwargs["context"]
        declaration = kwargs["declaration"]
        strength = kwargs["authentication_strength_evidence"]
        return FinalAdmissionEvidence(
            granted=True,
            current=True,
            admission_revision="admission-r1",
            authorization_policy_revision="final-authz-r1",
            principal_authority_revision="principal-r1",
            principal_id=principal.principal_id,
            principal_kind=principal.kind,
            principal_credential_generation=principal.credential_generation,
            action=declaration.action,
            scope=declaration.scope,
            tenant_requirement=declaration.tenant_requirement,
            authentication_strength_policy_id=declaration.authentication_strength_policy_id,
            tenant_id=self.override_tenant or context.tenant_id,
            cell_id=context.cell_id,
            placement_authority_revision="placement-r1",
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
            authentication_strength_policy_revision=strength.policy_version,
            executing_runtime_authority_revision="runtime-authority-r1",
            executing_runtime_profile_id="runtime.api@1",
            executing_runtime_generation="runtime-api-g1",
            executing_runtime_environment_class=EnvironmentClass.VALIDATION,
        )


def principal():
    return Principal(
        principal_id="principal-a",
        kind=PrincipalKind.HUMAN_BROWSER_SESSION,
        credential_generation="session-g1",
    )


def strength():
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


class Wave1TenantAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.placement = PlacementAuthority()
        self.strength_policy = StrengthPolicy()
        self.finalizer = FinalAdmissionAuthority()
        self.adapter = Wave1TenantAdmission(
            principal_authority=PrincipalAuthority(),
            placement_authority=self.placement,
            authorization_authority=AuthorizationAuthority(),
            final_admission_authority=self.finalizer,
            strength_policy=self.strength_policy,
        )

    def test_current_wave1_authority_admits_shell(self):
        admission = self.adapter.require_current(
            principal=principal(),
            tenant_id="tenant-a",
            now=NOW,
            authentication_strength=strength(),
        )
        self.assertEqual(admission.tenant_id, "tenant-a")
        self.assertEqual(admission.admission_revision, "admission-r1")
        self.assertNotEqual(admission.admission_revision, "final-authz-r1")

    def test_unknown_cross_tenant_request_fails_before_authorization(self):
        with self.assertRaises(AdmissionDenied):
            self.adapter.require_current(
                principal=principal(),
                tenant_id="tenant-b",
                now=NOW,
                authentication_strength=strength(),
            )

    def test_stale_placement_fails_closed(self):
        self.placement.current = False
        with self.assertRaises(AdmissionDenied):
            self.adapter.require_current(
                principal=principal(),
                tenant_id="tenant-a",
                now=NOW,
                authentication_strength=strength(),
            )

    def test_authentication_strength_policy_denial_fails_closed(self):
        self.strength_policy.allowed = False
        with self.assertRaises(AdmissionDenied):
            self.adapter.require_current(
                principal=principal(),
                tenant_id="tenant-a",
                now=NOW,
                authentication_strength=strength(),
            )

    def test_final_evidence_for_another_tenant_is_rejected(self):
        self.finalizer.override_tenant = "tenant-b"
        with self.assertRaises(AdmissionDenied):
            self.adapter.require_current(
                principal=principal(),
                tenant_id="tenant-a",
                now=NOW,
                authentication_strength=strength(),
            )


class CsrfKeyRingTests(unittest.TestCase):
    def setUp(self):
        self.ring = CsrfKeyRing(
            current_version="v2",
            previous_version="v1",
            keys={"v2": b"2" * 32, "v1": b"1" * 32},
        )

    def test_current_token_is_bound_to_session_lineage(self):
        token = self.ring.issue(session_lineage_id="lineage_0123456789abcdef")
        self.assertTrue(
            self.ring.validate(
                token=token,
                session_lineage_id="lineage_0123456789abcdef",
            )
        )
        self.assertFalse(
            self.ring.validate(
                token=token,
                session_lineage_id="lineage_fedcba9876543210",
            )
        )

    def test_previous_active_key_remains_valid_during_overlap(self):
        old = CsrfKeyRing(
            current_version="v1",
            previous_version="v0",
            keys={"v1": b"1" * 32, "v0": b"0" * 32},
        ).issue(session_lineage_id="lineage_0123456789abcdef")
        self.assertTrue(
            self.ring.validate(
                token=old,
                session_lineage_id="lineage_0123456789abcdef",
            )
        )

    def test_unknown_key_version_is_rejected(self):
        self.assertFalse(
            self.ring.validate(
                token="v0.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                session_lineage_id="lineage_0123456789abcdef",
            )
        )

    def test_exactly_two_active_key_versions_are_required(self):
        with self.assertRaises(ValueError):
            CsrfKeyRing(
                current_version="v2",
                previous_version="v1",
                keys={"v2": b"2" * 32},
            )


if __name__ == "__main__":
    unittest.main()
