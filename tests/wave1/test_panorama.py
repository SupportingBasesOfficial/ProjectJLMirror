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
from jlmirror_authority.fencing import (  # noqa: E402
    FenceRecord,
    acquire_next_fence,
)
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


def placement(**overrides):
    values = dict(
        tenant_id="tenant-acme",
        cell_id="cell-a",
        placement_version="pv-9",
        runtime_generation="runtime-g12",
        environment_class=EnvironmentClass.PRODUCTION,
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
    def __init__(self, jti):
        self.jti = jti

    def verify(self, **kwargs):
        return VerifiedMachineAssertion(
            client_principal="client-1",
            jti=self.jti,
            audience="https://api.example",
            issued_at=NOW - timedelta(seconds=1),
            not_before=NOW - timedelta(seconds=1),
            expires_at=NOW + timedelta(minutes=1),
            key_generation="key-g7",
            replay_generation="replay-g4",
        )


class ReplayAuthority:
    def __init__(self):
        self.called = False

    def claim_once(self, **kwargs):
        self.called = True
        return ReplayClaim.CLAIMED


class PanoramicAuthorityTests(unittest.TestCase):
    def test_boolean_currentness_cannot_launder_changed_fence(self):
        authority = PlacementAuthority(placement())
        context = construct_tenant_context(
            placement_authority=authority,
            tenant_id="tenant-acme",
            destination_cell_id="cell-a",
            destination_runtime_generation="runtime-g12",
            required_environment=EnvironmentClass.PRODUCTION,
            now=NOW,
        )
        authority.evidence = replace(authority.evidence, fence_epoch=8)
        declaration = AuthorizationDeclaration(
            action="organization.memberships.manage",
            scope=ScopeClass.TENANT,
            tenant_required=True,
            step_up=StepUpClass.NONE,
            audit_class=AuditClass.PRIVILEGED,
        )
        with self.assertRaises(AdmissionDenied):
            authorize_protected_operation(
                principal=Principal(
                    "user-1", PrincipalKind.HUMAN_BROWSER_SESSION, "session-g1"
                ),
                declaration=declaration,
                placement_authority=authority,
                authorization_authority=Authz(),
                context=context,
                now=NOW,
            )

    def test_boolean_false_still_denies_even_if_exact_evidence_matches(self):
        authority = PlacementAuthority(placement())
        context = construct_tenant_context(
            placement_authority=authority,
            tenant_id="tenant-acme",
            destination_cell_id="cell-a",
            destination_runtime_generation="runtime-g12",
            required_environment=EnvironmentClass.PRODUCTION,
            now=NOW,
        )
        authority.boolean_gate = False
        declaration = AuthorizationDeclaration(
            action="organization.memberships.read",
            scope=ScopeClass.TENANT,
            tenant_required=True,
            step_up=StepUpClass.NONE,
            audit_class=AuditClass.NORMAL,
        )
        with self.assertRaises(AdmissionDenied):
            authorize_protected_operation(
                principal=Principal("user-1", PrincipalKind.HUMAN_BROWSER_SESSION, "session-g1"),
                declaration=declaration,
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
                now=NOW,
            )
        self.assertFalse(replay.called)

    def test_malformed_machine_validity_interval_is_denied(self):
        class BadVerifier:
            def verify(self, **kwargs):
                return VerifiedMachineAssertion(
                    client_principal="client-1",
                    jti="jti-1",
                    audience="https://api.example",
                    issued_at=NOW,
                    not_before=NOW + timedelta(minutes=2),
                    expires_at=NOW + timedelta(minutes=1),
                    key_generation="key-g7",
                    replay_generation="replay-g4",
                )

        with self.assertRaises(AdmissionDenied):
            authenticate_machine_assertion(
                verifier=BadVerifier(),
                replay_authority=ReplayAuthority(),
                compact_assertion="opaque",
                expected_client_principal="client-1",
                expected_audience="https://api.example",
                current_key_generation="key-g7",
                current_replay_generation="replay-g4",
                now=NOW,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
