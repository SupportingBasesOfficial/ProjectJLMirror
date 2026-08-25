from __future__ import annotations

from dataclasses import replace
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
    FinalAdmissionEvidence,
    PlacementEvidence,
    RuntimeExecutionEvidence,
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
    TenantRequirement,
)
from jlmirror_authority.runtime_profiles import CONTROL_PLANE, WEB_BFF  # noqa: E402

NOW = datetime(2026, 8, 25, 0, 35, tzinfo=timezone.utc)


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
    def __init__(self):
        self.calls = 0

    def evaluate(self, **kwargs):
        self.calls += 1
        return AuthorizationDecision(True, True, f"serial-authz-r{self.calls}")


class StrengthPolicy:
    def permits(self, **kwargs):
        return True


class RuntimeAuthority:
    def resolve_current_execution(self, **kwargs):
        return RuntimeExecutionEvidence(
            runtime_profile_id="runtime.control-plane@1",
            principal_class="principal.control-plane@1",
            isolation_class="isolation.control-plane@1",
            ingress_profile="ingress.privileged-platform@1",
            runtime_generation="runtime-control-g7",
            environment_class=EnvironmentClass.PRODUCTION,
            runtime_lifecycle=RuntimeLifecycle.ACTIVE,
            current=True,
        )


class Finalizer:
    def __init__(self, evidence):
        self.evidence = evidence
        self.calls = 0
        self.kwargs = None

    def finalize_current_admission(self, **kwargs):
        self.calls += 1
        self.kwargs = kwargs
        if isinstance(self.evidence, BaseException):
            raise self.evidence
        return self.evidence


def principal():
    return Principal("user-1", PrincipalKind.HUMAN_BROWSER_SESSION, "session-g1")


def placement():
    return PlacementEvidence(
        tenant_id="tenant-acme",
        cell_id="cell-a",
        placement_version="pv-9",
        runtime_generation="runtime-g12",
        runtime_profile_id="runtime.api@1",
        runtime_isolation_class="isolation.application-serving@1",
        configuration_generation="cfg-g4",
        workload_credential_generation="wc-g9",
        network_policy_generation="np-g6",
        environment_class=EnvironmentClass.PRODUCTION,
        isolation_class="pooled",
        runtime_lifecycle=RuntimeLifecycle.ACTIVE,
        placement_current=True,
        operation_eligible=True,
        cell_admission_current=True,
        fence_scope_id="tenant:acme",
        fence_epoch=7,
    )


def tenant_declaration():
    return AuthorizationDeclaration(
        action="organization.memberships.read",
        scope=ScopeClass.TENANT,
        tenant_required=True,
        step_up=StepUpClass.NONE,
        audit_class=AuditClass.NORMAL,
    )


def resource_declaration(resource_scope: str):
    return AuthorizationDeclaration(
        action="organization.memberships.read",
        scope=ScopeClass.RESOURCE,
        tenant_required=True,
        step_up=StepUpClass.NONE,
        audit_class=AuditClass.NORMAL,
        resource_scope=resource_scope,
    )


def construct_context(authority):
    evidence = authority.evidence
    return construct_tenant_context(
        principal=principal(),
        principal_authority=PrincipalAuthority(),
        placement_authority=authority,
        tenant_id=evidence.tenant_id,
        destination_cell_id=evidence.cell_id,
        destination_runtime_generation=evidence.runtime_generation,
        destination_configuration_generation=evidence.configuration_generation,
        destination_workload_credential_generation=evidence.workload_credential_generation,
        destination_network_policy_generation=evidence.network_policy_generation,
        required_environment=evidence.environment_class,
        now=NOW,
    )


def tenant_final_evidence(context, **overrides):
    values = dict(
        granted=True,
        current=True,
        admission_revision="admission-r9",
        authorization_policy_revision="authz-final-r9",
        principal_authority_revision="principal-r9",
        principal_id=context.principal_id,
        principal_credential_generation=context.principal_credential_generation,
        action="organization.memberships.read",
        scope=ScopeClass.TENANT,
        tenant_requirement=TenantRequirement.REQUIRED,
        resource_scope=None,
        authentication_strength_policy_id=None,
        tenant_id=context.tenant_id,
        cell_id=context.cell_id,
        placement_authority_revision="placement-r9",
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
        executing_runtime_authority_revision="runtime-authority-r9",
        executing_runtime_profile_id="runtime.api@1",
        executing_runtime_generation="runtime-api-g9",
    )
    values.update(overrides)
    return FinalAdmissionEvidence(**values)


def admin_strength():
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


def cross_declaration():
    return AuthorizationDeclaration(
        action="platform.tenants.suspend",
        scope=ScopeClass.PLATFORM,
        tenant_required=False,
        tenant_requirement=TenantRequirement.EXPLICIT_CROSS_TENANT_PRIVILEGED,
        step_up=StepUpClass.REQUIRED,
        authentication_strength_policy_id="platform-privileged-v1",
        audit_class=AuditClass.PRIVILEGED,
    )


def cross_final_evidence(**overrides):
    values = dict(
        granted=True,
        current=True,
        admission_revision="admission-r10",
        authorization_policy_revision="platform-authz-r10",
        principal_authority_revision="principal-r10",
        principal_id="platform-admin-1",
        principal_credential_generation="session-g7",
        action="platform.tenants.suspend",
        scope=ScopeClass.PLATFORM,
        tenant_requirement=TenantRequirement.EXPLICIT_CROSS_TENANT_PRIVILEGED,
        resource_scope=None,
        authentication_strength_policy_id="platform-privileged-v1",
        authentication_strength_policy_revision="security-policy-r7",
        executing_runtime_authority_revision="runtime-authority-r10",
        executing_runtime_profile_id="runtime.control-plane@1",
        executing_runtime_generation="runtime-control-g7",
    )
    values.update(overrides)
    return FinalAdmissionEvidence(**values)


class AtomicFinalAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.principal = principal()
        self.principal_authority = PrincipalAuthority()
        self.placement_authority = PlacementAuthority(placement())
        self.context = construct_context(self.placement_authority)
        self.authorization_authority = AuthorizationAuthority()

    def tenant_call(self, finalizer=None):
        return authorize_protected_operation(
            principal=self.principal,
            principal_authority=self.principal_authority,
            declaration=tenant_declaration(),
            placement_authority=self.placement_authority,
            authorization_authority=self.authorization_authority,
            context=self.context,
            now=NOW,
            final_admission_authority=finalizer,
        )

    def test_serial_green_without_final_admission_authority_fails_closed(self):
        with self.assertRaises(AdmissionDenied):
            self.tenant_call()
        self.assertEqual(self.authorization_authority.calls, 2)

    def test_malformed_or_noncurrent_final_admission_fails_closed(self):
        for evidence in (
            {"granted": True, "current": True},
            tenant_final_evidence(self.context, current=False),
            tenant_final_evidence(self.context, granted=False),
            RuntimeError("final authority unavailable"),
        ):
            with self.subTest(evidence=type(evidence).__name__), self.assertRaises(AdmissionDenied):
                self.authorization_authority.calls = 0
                self.tenant_call(Finalizer(evidence))

    def test_final_principal_or_action_binding_mismatch_fails_closed(self):
        for evidence in (
            tenant_final_evidence(self.context, principal_id="user-2"),
            tenant_final_evidence(self.context, principal_credential_generation="session-g2"),
            tenant_final_evidence(self.context, action="organization.memberships.manage"),
        ):
            with self.subTest(evidence=evidence), self.assertRaises(AdmissionDenied):
                self.authorization_authority.calls = 0
                self.tenant_call(Finalizer(evidence))

    def test_final_declaration_scope_or_tenant_requirement_mismatch_fails_closed(self):
        for evidence in (
            tenant_final_evidence(self.context, scope=ScopeClass.RESOURCE),
            tenant_final_evidence(
                self.context,
                tenant_requirement=TenantRequirement.EXPLICIT_CROSS_TENANT_PRIVILEGED,
            ),
        ):
            with self.subTest(evidence=evidence), self.assertRaises(AdmissionDenied):
                self.authorization_authority.calls = 0
                self.tenant_call(Finalizer(evidence))

    def test_resource_declaration_requires_explicit_scope(self):
        with self.assertRaises(ValueError):
            AuthorizationDeclaration(
                action="organization.memberships.read",
                scope=ScopeClass.RESOURCE,
                tenant_required=True,
                step_up=StepUpClass.NONE,
                audit_class=AuditClass.NORMAL,
            )

    def test_non_resource_declaration_rejects_resource_scope(self):
        with self.assertRaises(ValueError):
            AuthorizationDeclaration(
                action="organization.memberships.read",
                scope=ScopeClass.TENANT,
                tenant_required=True,
                step_up=StepUpClass.NONE,
                audit_class=AuditClass.NORMAL,
                resource_scope="resource:alpha",
            )

    def test_same_action_different_resource_scope_cannot_reuse_final_evidence(self):
        evidence = tenant_final_evidence(
            self.context,
            scope=ScopeClass.RESOURCE,
            resource_scope="resource:alpha",
        )
        with self.assertRaises(AdmissionDenied):
            authorize_protected_operation(
                principal=self.principal,
                principal_authority=self.principal_authority,
                declaration=resource_declaration("resource:beta"),
                placement_authority=self.placement_authority,
                authorization_authority=self.authorization_authority,
                context=self.context,
                now=NOW,
                final_admission_authority=Finalizer(evidence),
            )

        decision = authorize_protected_operation(
            principal=self.principal,
            principal_authority=self.principal_authority,
            declaration=resource_declaration("resource:alpha"),
            placement_authority=self.placement_authority,
            authorization_authority=self.authorization_authority,
            context=self.context,
            now=NOW,
            final_admission_authority=Finalizer(evidence),
        )
        self.assertTrue(decision.granted)

    def test_tenant_or_resource_admission_rejects_non_api_runtime_binding(self):
        for declaration in (tenant_declaration(), resource_declaration("resource:alpha")):
            for runtime_binding in (WEB_BFF, CONTROL_PLANE):
                with self.subTest(
                    scope=declaration.scope,
                    runtime=runtime_binding.runtime_profile_id,
                ), self.assertRaises(AdmissionDenied):
                    authorize_protected_operation(
                        principal=self.principal,
                        principal_authority=self.principal_authority,
                        declaration=declaration,
                        placement_authority=self.placement_authority,
                        authorization_authority=self.authorization_authority,
                        context=self.context,
                        now=NOW,
                        runtime_binding=runtime_binding,
                        final_admission_authority=Finalizer(tenant_final_evidence(self.context)),
                    )

    def test_tenant_final_admission_requires_executing_runtime_binding(self):
        for field in (
            "executing_runtime_authority_revision",
            "executing_runtime_profile_id",
            "executing_runtime_generation",
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                tenant_final_evidence(self.context, **{field: None})

    def test_tenant_final_admission_rejects_wrong_executing_runtime_profile(self):
        evidence = tenant_final_evidence(
            self.context,
            executing_runtime_profile_id="runtime.control-plane@1",
        )
        with self.assertRaises(AdmissionDenied):
            self.tenant_call(Finalizer(evidence))

    def test_any_tenant_placement_generation_or_fence_drift_fails_closed(self):
        mutations = {
            "tenant_id": "tenant-other",
            "cell_id": "cell-b",
            "placement_version": "pv-10",
            "runtime_generation": "runtime-g13",
            "runtime_profile_id": "runtime.control-plane@1",
            "runtime_isolation_class": "isolation.control-plane@1",
            "configuration_generation": "cfg-g5",
            "workload_credential_generation": "wc-g10",
            "network_policy_generation": "np-g7",
            "environment_class": EnvironmentClass.VALIDATION,
            "isolation_class": "dedicated",
            "fence_scope_id": "tenant:other",
            "fence_epoch": 8,
        }
        baseline = tenant_final_evidence(self.context)
        for field, value in mutations.items():
            with self.subTest(field=field), self.assertRaises(AdmissionDenied):
                self.authorization_authority.calls = 0
                self.tenant_call(Finalizer(replace(baseline, **{field: value})))

    def test_valid_final_snapshot_is_only_returned_authorization_revision(self):
        finalizer = Finalizer(tenant_final_evidence(self.context))
        decision = self.tenant_call(finalizer)
        self.assertEqual(self.authorization_authority.calls, 2)
        self.assertEqual(finalizer.calls, 1)
        self.assertEqual(decision.policy_revision, "authz-final-r9")
        self.assertNotIn("now", finalizer.kwargs)

    def test_cross_tenant_strength_revision_drift_fails_closed(self):
        admin = Principal(
            "platform-admin-1", PrincipalKind.PLATFORM_ADMIN_PRINCIPAL, "session-g7"
        )
        with self.assertRaises(AdmissionDenied):
            authorize_protected_operation(
                principal=admin,
                principal_authority=PrincipalAuthority(),
                declaration=cross_declaration(),
                placement_authority=PlacementAuthority(placement()),
                authorization_authority=AuthorizationAuthority(),
                context=None,
                now=NOW,
                strength_policy=StrengthPolicy(),
                strength_evidence=admin_strength(),
                runtime_binding=CONTROL_PLANE,
                runtime_authority=RuntimeAuthority(),
                final_admission_authority=Finalizer(
                    cross_final_evidence(
                        authentication_strength_policy_revision="security-policy-r8"
                    )
                ),
            )

    def test_cross_tenant_strength_policy_id_drift_fails_closed_even_same_revision(self):
        admin = Principal(
            "platform-admin-1", PrincipalKind.PLATFORM_ADMIN_PRINCIPAL, "session-g7"
        )
        with self.assertRaises(AdmissionDenied):
            authorize_protected_operation(
                principal=admin,
                principal_authority=PrincipalAuthority(),
                declaration=cross_declaration(),
                placement_authority=PlacementAuthority(placement()),
                authorization_authority=AuthorizationAuthority(),
                context=None,
                now=NOW,
                strength_policy=StrengthPolicy(),
                strength_evidence=admin_strength(),
                runtime_binding=CONTROL_PLANE,
                runtime_authority=RuntimeAuthority(),
                final_admission_authority=Finalizer(
                    cross_final_evidence(
                        authentication_strength_policy_id="platform-privileged-v2",
                        authentication_strength_policy_revision="security-policy-r7",
                    )
                ),
            )

    def test_cross_tenant_runtime_generation_or_profile_drift_fails_closed(self):
        admin = Principal(
            "platform-admin-1", PrincipalKind.PLATFORM_ADMIN_PRINCIPAL, "session-g7"
        )
        for evidence in (
            cross_final_evidence(executing_runtime_generation="runtime-control-g8"),
            cross_final_evidence(executing_runtime_profile_id="runtime.api@1"),
        ):
            with self.subTest(evidence=evidence), self.assertRaises(AdmissionDenied):
                authorize_protected_operation(
                    principal=admin,
                    principal_authority=PrincipalAuthority(),
                    declaration=cross_declaration(),
                    placement_authority=PlacementAuthority(placement()),
                    authorization_authority=AuthorizationAuthority(),
                    context=None,
                    now=NOW,
                    strength_policy=StrengthPolicy(),
                    strength_evidence=admin_strength(),
                    runtime_binding=CONTROL_PLANE,
                    runtime_authority=RuntimeAuthority(),
                    final_admission_authority=Finalizer(evidence),
                )

    def test_cross_tenant_valid_final_snapshot_uses_no_caller_time(self):
        admin = Principal(
            "platform-admin-1", PrincipalKind.PLATFORM_ADMIN_PRINCIPAL, "session-g7"
        )
        finalizer = Finalizer(cross_final_evidence())
        decision = authorize_protected_operation(
            principal=admin,
            principal_authority=PrincipalAuthority(),
            declaration=cross_declaration(),
            placement_authority=PlacementAuthority(placement()),
            authorization_authority=AuthorizationAuthority(),
            context=None,
            now=NOW,
            strength_policy=StrengthPolicy(),
            strength_evidence=admin_strength(),
            runtime_binding=CONTROL_PLANE,
            runtime_authority=RuntimeAuthority(),
            final_admission_authority=finalizer,
        )
        self.assertEqual(decision.policy_revision, "platform-authz-r10")
        self.assertNotIn("now", finalizer.kwargs)


if __name__ == "__main__":
    unittest.main(verbosity=2)