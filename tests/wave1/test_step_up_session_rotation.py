from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jlmirror_authority.model import (  # noqa: E402
    AdmissionDenied,
    AuthenticationStrengthEvidence,
    Principal,
    PrincipalKind,
)
from jlmirror_authority.session import (  # noqa: E402
    issue_browser_session,
    resolve_browser_session,
    rotate_browser_session,
)

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


class SessionAuthority:
    def __init__(self):
        self.records = {}
        self.rotate_calls = 0

    def create(self, record):
        if record.handle_digest in self.records:
            return False
        self.records[record.handle_digest] = record
        return True

    def resolve(self, handle_digest):
        return self.records.get(handle_digest)

    def rotate(self, *, predecessor_handle_digest, expected_predecessor_generation, successor):
        self.rotate_calls += 1
        predecessor = self.records.get(predecessor_handle_digest)
        if predecessor is None or predecessor.session_generation != expected_predecessor_generation:
            return False
        del self.records[predecessor_handle_digest]
        self.records[successor.handle_digest] = successor
        return True

    def retire(self, **kwargs):
        return False


def assurance(principal: Principal) -> AuthenticationStrengthEvidence:
    return AuthenticationStrengthEvidence(
        issuer="id.example",
        acr="loa2",
        amr=frozenset({"pwd", "otp"}),
        authenticated_at=NOW - timedelta(seconds=10),
        evidence_expires_at=NOW + timedelta(minutes=5),
        policy_version="security-policy-v7",
        principal_id=principal.principal_id,
        principal_credential_generation=principal.credential_generation,
    )


class StepUpSessionRotationTests(unittest.TestCase):
    def test_same_principal_reauthentication_atomically_replaces_session_and_rebinds_assurance(self):
        authority = SessionAuthority()
        initial = Principal(
            "user-a", PrincipalKind.HUMAN_BROWSER_SESSION, "identity-login-g1"
        )
        old_handle = issue_browser_session(
            authority=authority,
            principal=initial,
            now=NOW,
            lifetime=timedelta(minutes=30),
        )
        reauthenticated = Principal(
            "user-a", PrincipalKind.HUMAN_BROWSER_SESSION, "reauth-g2"
        )
        new_handle = rotate_browser_session(
            authority=authority,
            predecessor=old_handle,
            now=NOW + timedelta(seconds=5),
            lifetime=timedelta(minutes=30),
            reauthenticated_principal=reauthenticated,
            authentication_strength=assurance(reauthenticated),
        )

        with self.assertRaises(AdmissionDenied):
            resolve_browser_session(authority=authority, handle=old_handle, now=NOW + timedelta(seconds=6))
        successor = resolve_browser_session(
            authority=authority, handle=new_handle, now=NOW + timedelta(seconds=6)
        )
        self.assertEqual(successor.principal.principal_id, "user-a")
        self.assertEqual(
            successor.authentication_strength.principal_credential_generation,
            successor.session_generation,
        )
        self.assertEqual(authority.rotate_calls, 1)

    def test_reauthentication_as_another_principal_is_rejected_before_atomic_rotate(self):
        authority = SessionAuthority()
        old_handle = issue_browser_session(
            authority=authority,
            principal=Principal(
                "user-a", PrincipalKind.HUMAN_BROWSER_SESSION, "identity-login-g1"
            ),
            now=NOW,
            lifetime=timedelta(minutes=30),
        )
        attacker = Principal(
            "user-b", PrincipalKind.HUMAN_BROWSER_SESSION, "reauth-attacker-g1"
        )
        with self.assertRaises(AdmissionDenied):
            rotate_browser_session(
                authority=authority,
                predecessor=old_handle,
                now=NOW + timedelta(seconds=5),
                lifetime=timedelta(minutes=30),
                reauthenticated_principal=attacker,
                authentication_strength=assurance(attacker),
            )
        self.assertEqual(authority.rotate_calls, 0)

    def test_reauthentication_without_fresh_assurance_does_not_inherit_old_assurance(self):
        authority = SessionAuthority()
        initial = Principal(
            "user-a", PrincipalKind.HUMAN_BROWSER_SESSION, "identity-login-g1"
        )
        old_handle = issue_browser_session(
            authority=authority,
            principal=initial,
            now=NOW,
            lifetime=timedelta(minutes=30),
            authentication_strength=assurance(initial),
        )
        reauthenticated = Principal(
            "user-a", PrincipalKind.HUMAN_BROWSER_SESSION, "reauth-g2"
        )
        new_handle = rotate_browser_session(
            authority=authority,
            predecessor=old_handle,
            now=NOW + timedelta(seconds=5),
            lifetime=timedelta(minutes=30),
            reauthenticated_principal=reauthenticated,
            authentication_strength=None,
        )
        successor = resolve_browser_session(
            authority=authority, handle=new_handle, now=NOW + timedelta(seconds=6)
        )
        self.assertIsNone(successor.authentication_strength)


if __name__ == "__main__":
    unittest.main(verbosity=2)
