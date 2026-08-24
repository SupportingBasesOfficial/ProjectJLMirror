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
    PlacementEvidence,
    RuntimeLifecycle,
    authorize_protected_operation,
    construct_tenant_context,
)
from jlmirror_authority.fencing import FenceRecord, acquire_next_fence  # noqa: E402
from jlmirror_authority.machine import (  # noqa: E402
    MAX_MACHINE_JTI_BYTES,
    ReplayClaim,
    VerifiedMachineAssertion,
    authenticate_machine_assertion,
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

NOW = datetime(2026, 8, 24, 3, 50, tzinfo=timezone.utc)
MAX_ASSERTION_LIFETIME = timedelta(minutes=5)


def principal():
    return Principal("user-1", PrincipalKind.HUMAN_BROWSER_SESSION, "session-g1")


def placement(**overrides):
    values = dict(
        tenant_id="tenant-acme",
        cell_id="cell-a",
        placement_version="pv-9",
        runtime_generation="runtime-g12",
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
    values.update(overrides)
    return PlacementEvidence(**values)


class PlacementAuthority:
    def __init__(self, evidence):
        self.evidence = evidence
        self.boolean_gate = True

    def resolve_current(self, tenant_id):
        return self.evidence if self.evidence.tenant_id == tenant_id else None

    def context_is_current(self, context):
        return self.boolean_gate


class Authz:
    def evaluate(self, **kwargs):
        return AuthorizationDecision(True, True, "authz-r1")


class ExactFenceAuthority:
    def __init__(self):
        self.record = FenceRecord("tenant:acme", 7, "gen-7", "active")

    def current(self, fence_scope_id):
        return self.record if fence_scope_id == self.record.fence_scope_id else None

    def acquire_successor(self, **kwargs):
        if (
            kwargs["fence_scope_id"] != self.record.fence_scope_id
            or kwargs["expected_predecessor_epoch"] != self.record.current_fence_epoch
            or kwargs["expected_predecessor_generation_id"] != self.record.current_generation_id
        ):
            return None
        self.record = FenceRecord(
            self.record.fence_scope_id,
            self.record.current_fence_epoch + 1,
            kwargs["successor_generation_id"],
            kwargs["successor_state"],
        )
        return self.record


class MachineVerifier:
    def __init__(self, jti, *, issued_at=None, not_before=None, expires_at=None):
        self.jti = jti
        self.issued_at = issued_at or NOW - timedelta(seconds=1)
        self.not_before = not_before or NOW - timedelta(seconds=1)
        self.expires_at = expires_at or NOW + timedelta(minutes=1)

    def verify(self, **kwargs):
        return VerifiedMachineAssertion(
            client_principal="client-1",
            jti=self.jti,
            audience="https://api.example",
            issued_at=self.issued_at,
            not_before=self.not_before,
            expires_at=self.expires_at,
            key_generation="key-g7",
            replay_generation="replay-g4",
        )


class ReplayAuthority:
    def __init__(self):
        self.called = False

    def claim_once(self, **kwargs):
        self.called = True
        return ReplayClaim.CLAIMED


def construct(authority):
    evidence = authority.evidence
    return construct_tenant_context(
        principal=principal(),
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


class PanoramicAuthorityTests(unittest.TestCase):
    def declaration(self):
        return AuthorizationDeclaration(
            action="organization.memberships.manage",
            scope=ScopeClass.TENANT,
            tenant_required=True,
            step_up=StepUpClass.NONE,
            audit_class=AuditClass.PRIVILEGED,
        )

    def test_boolean_currentness_cannot_launder_changed_fence_or_generation(self):
        for field, value in (
            ("fence_epoch", 8),
            ("configuration_generation", "cfg-g5"),
            ("workload_credential_generation", "wc-g10"),
            ("network_policy_generation", "np-g7"),
        ):
            authority = PlacementAuthority(placement())
            context = construct(authority)
            authority.evidence = replace(authority.evidence, **{field: value})
            with self.subTest(field=field), self.assertRaises(AdmissionDenied):
                authorize_protected_operation(
                    principal=principal(),
                    declaration=self.declaration(),
                    placement_authority=authority,
                    authorization_authority=Authz(),
                    context=context,
                    now=NOW,
                )

    def test_boolean_false_or_truthy_string_still_denies(self):
        for gate in (False, "true", 1):
            authority = PlacementAuthority(placement())
            context = construct(authority)
            authority.boolean_gate = gate
            with self.subTest(gate=gate), self.assertRaises(AdmissionDenied):
                authorize_protected_operation(
                    principal=principal(),
                    declaration=self.declaration(),
                    placement_authority=authority,
                    authorization_authority=Authz(),
                    context=context,
                    now=NOW,
                )

    def test_fence_successor_requires_exact_predecessor_generation(self):
        authority = ExactFenceAuthority()
        with self.assertRaises(AdmissionDenied):
            acquire_next_fence(
                authority=authority,
                fence_scope_id="tenant:acme",
                expected_predecessor_epoch=7,
                expected_predecessor_generation_id="gen-wrong",
                successor_generation_id="gen-8",
            )
        self.assertEqual(authority.record.current_fence_epoch, 7)

    def test_fence_successor_exact_predecessor_advances_once(self):
        authority = ExactFenceAuthority()
        winner = acquire_next_fence(
            authority=authority,
            fence_scope_id="tenant:acme",
            expected_predecessor_epoch=7,
            expected_predecessor_generation_id="gen-7",
            successor_generation_id="gen-8",
        )
        self.assertEqual((winner.current_fence_epoch, winner.current_generation_id), (8, "gen-8"))

    def test_oversized_replay_identity_fails_before_replay_store(self):
        replay = ReplayAuthority()
        with self.assertRaises(AdmissionDenied):
            authenticate_machine_assertion(
                verifier=MachineVerifier("x" * (MAX_MACHINE_JTI_BYTES + 1)),
                replay_authority=replay,
                compact_assertion="opaque",
                expected_client_principal="client-1",
                expected_audience="https://api.example",
                current_key_generation="key-g7",
                current_replay_generation="replay-g4",
                current_max_assertion_lifetime=MAX_ASSERTION_LIFETIME,
                now=NOW,
            )
        self.assertFalse(replay.called)

    def test_malformed_machine_validity_interval_is_denied(self):
        verifier = MachineVerifier(
            "jti-1",
            issued_at=NOW,
            not_before=NOW + timedelta(minutes=2),
            expires_at=NOW + timedelta(minutes=1),
        )
        with self.assertRaises(AdmissionDenied):
            authenticate_machine_assertion(
                verifier=verifier,
                replay_authority=ReplayAuthority(),
                compact_assertion="opaque",
                expected_client_principal="client-1",
                expected_audience="https://api.example",
                current_key_generation="key-g7",
                current_replay_generation="replay-g4",
                current_max_assertion_lifetime=MAX_ASSERTION_LIFETIME,
                now=NOW,
            )

    def test_long_machine_assertion_is_denied_before_replay_store(self):
        replay = ReplayAuthority()
        verifier = MachineVerifier(
            "jti-long",
            issued_at=NOW - timedelta(seconds=1),
            not_before=NOW - timedelta(seconds=1),
            expires_at=NOW + timedelta(minutes=30),
        )
        with self.assertRaises(AdmissionDenied):
            authenticate_machine_assertion(
                verifier=verifier,
                replay_authority=replay,
                compact_assertion="opaque",
                expected_client_principal="client-1",
                expected_audience="https://api.example",
                current_key_generation="key-g7",
                current_replay_generation="replay-g4",
                current_max_assertion_lifetime=MAX_ASSERTION_LIFETIME,
                now=NOW,
            )
        self.assertFalse(replay.called)


if __name__ == "__main__":
    unittest.main(verbosity=2)
