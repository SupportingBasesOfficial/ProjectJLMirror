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
from jlmirror_authority.fencing import FenceRecord, FenceToken  # noqa: E402
from jlmirror_authority.machine import authenticate_machine_assertion  # noqa: E402
from jlmirror_authority.model import (  # noqa: E402
    AdmissionDenied,
    AuditClass,
    AuthorizationDeclaration,
    EnvironmentClass,
    Principal,
    PrincipalKind,
    ScopeClass,
    StepUpClass,
    TenantContext,
)
from jlmirror_authority.session import issue_browser_session  # noqa: E402

NOW = datetime(2026, 8, 24, 5, 0, tzinfo=timezone.utc)


def placement(**overrides):
    values = dict(
        tenant_id="tenant-acme",
        cell_id="cell-a",
        placement_version="pv-1",
        runtime_generation="runtime-g1",
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
    values.update(overrides)
    return PlacementEvidence(**values)


class PlacementAuthority:
    def __init__(self, evidence, gate=True):
        self.evidence = evidence
        self.gate = gate

    def resolve_current(self, tenant_id):
        return self.evidence

    def context_is_current(self, context):
        return self.gate


class GoodAuthz:
    def evaluate(self, **kwargs):
        return AuthorizationDecision(True, True, "authz-r1")


class TypeLaunderingTests(unittest.TestCase):
    def test_principal_active_must_be_literal_boolean(self):
        for value in ("false", "true", 0, 1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Principal("user-1", PrincipalKind.HUMAN_BROWSER_SESSION, "cg-1", active=value)

    def test_placement_currentness_fields_must_be_literal_booleans(self):
        for field in ("placement_current", "operation_eligible", "cell_admission_current"):
            for value in ("false", "true", 0, 1):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    placement(**{field: value})

    def test_authorization_decision_must_be_literal_booleans(self):
        for field in ("granted", "current"):
            for value in ("false", "true", 0, 1):
                kwargs = dict(granted=True, current=True, policy_revision="authz-r1")
                kwargs[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    AuthorizationDecision(**kwargs)

    def test_bool_cannot_launder_as_fence_epoch(self):
        with self.assertRaises(ValueError):
            FenceRecord("tenant:acme", True, "gen-1", "active")
        with self.assertRaises(ValueError):
            FenceToken("tenant:acme", True, "gen-1")
        with self.assertRaises(ValueError):
            placement(fence_epoch=True)

    def test_tenant_context_bool_epoch_and_string_enums_are_rejected(self):
        base = dict(
            tenant_id="tenant-acme",
            principal_id="user-1",
            principal_kind=PrincipalKind.HUMAN_BROWSER_SESSION,
            principal_credential_generation="cg-1",
            cell_id="cell-a",
            placement_version="pv-1",
            runtime_generation="runtime-g1",
            configuration_generation="cfg-g1",
            workload_credential_generation="wc-g1",
            network_policy_generation="np-g1",
            environment_class=EnvironmentClass.PRODUCTION,
            isolation_class="pooled",
            fence_scope_id="tenant:acme",
            fence_epoch=1,
            constructed_at=NOW,
        )
        with self.assertRaises(ValueError):
            TenantContext(**{**base, "fence_epoch": True})
        with self.assertRaises(ValueError):
            TenantContext(**{**base, "principal_kind": "human_browser_session"})
        with self.assertRaises(ValueError):
            TenantContext(**{**base, "environment_class": "environment.production@1"})

    def test_truthy_currentness_port_result_is_not_authority(self):
        evidence = placement()
        authority = PlacementAuthority(evidence)
        principal = Principal("user-1", PrincipalKind.HUMAN_BROWSER_SESSION, "cg-1")
        context = construct_tenant_context(
            principal=principal,
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
        declaration = AuthorizationDeclaration(
            action="organization.memberships.read",
            scope=ScopeClass.TENANT,
            tenant_required=True,
            step_up=StepUpClass.NONE,
            audit_class=AuditClass.NORMAL,
        )
        for value in ("true", 1, object()):
            authority.gate = value
            with self.subTest(value=value), self.assertRaises(AdmissionDenied):
                authorize_protected_operation(
                    principal=principal,
                    declaration=declaration,
                    placement_authority=authority,
                    authorization_authority=GoodAuthz(),
                    context=context,
                    now=NOW,
                )

    def test_malformed_authorization_port_result_is_denied(self):
        evidence = placement()
        authority = PlacementAuthority(evidence)
        principal = Principal("user-1", PrincipalKind.HUMAN_BROWSER_SESSION, "cg-1")
        context = construct_tenant_context(
            principal=principal,
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
        declaration = AuthorizationDeclaration(
            action="organization.memberships.read",
            scope=ScopeClass.TENANT,
            tenant_required=True,
            step_up=StepUpClass.NONE,
            audit_class=AuditClass.NORMAL,
        )

        class BadAuthz:
            def evaluate(self, **kwargs):
                return {"granted": "true", "current": "true"}

        with self.assertRaises(AdmissionDenied):
            authorize_protected_operation(
                principal=principal,
                declaration=declaration,
                placement_authority=authority,
                authorization_authority=BadAuthz(),
                context=context,
                now=NOW,
            )

    def test_session_authority_truthy_create_result_is_not_success(self):
        class BadSessionAuthority:
            def create(self, record):
                return "true"

        with self.assertRaises(AdmissionDenied):
            issue_browser_session(
                authority=BadSessionAuthority(),
                principal=Principal("user-1", PrincipalKind.HUMAN_BROWSER_SESSION, "id-g1"),
                now=NOW,
                lifetime=timedelta(minutes=5),
            )

    def test_machine_verifier_must_return_typed_evidence(self):
        class BadVerifier:
            def verify(self, **kwargs):
                return {"client_principal": "client-1"}

        class Replay:
            def claim_once(self, **kwargs):
                raise AssertionError("malformed verifier result must fail before replay authority")

        with self.assertRaises(AdmissionDenied):
            authenticate_machine_assertion(
                verifier=BadVerifier(),
                replay_authority=Replay(),
                compact_assertion="opaque",
                expected_client_principal="client-1",
                expected_audience="https://api.example",
                current_key_generation="key-g1",
                current_replay_generation="replay-g1",
                current_max_assertion_lifetime=timedelta(minutes=5),
                now=NOW,
            )


class SqlDefaultPrivilegeTests(unittest.TestCase):
    def test_default_public_function_execute_is_revoked_before_first_function_creation(self):
        text = (ROOT / "sql" / "wave1" / "001_platform_authority_fence.sql").read_text(
            encoding="utf-8"
        )
        revoke = (
            "ALTER DEFAULT PRIVILEGES IN SCHEMA platform\n"
            "    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;"
        )
        create = "CREATE OR REPLACE FUNCTION platform.initialize_authority_fence("
        self.assertIn(revoke, text)
        self.assertIn(create, text)
        self.assertLess(text.index(revoke), text.index(create))


if __name__ == "__main__":
    unittest.main(verbosity=2)
