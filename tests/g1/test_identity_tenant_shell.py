from __future__ import annotations

from dataclasses import replace
import base64
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from jlmirror_authority.browser import VerifiedOidcIdentity  # noqa: E402
from jlmirror_authority.model import AdmissionDenied  # noqa: E402
from jlmirror_authority.session import BrowserSessionRecord  # noqa: E402
from jlmirror_g1.shell import (  # noqa: E402
    IdentityTenantShell,
    TenantShellAdmission,
)


NOW = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)


class Transactions:
    def __init__(self) -> None:
        self.values = {}

    def create(self, transaction) -> bool:
        if transaction.transaction_id in self.values:
            return False
        self.values[transaction.transaction_id] = transaction
        return True

    def consume(self, transaction_id: str):
        return self.values.pop(transaction_id, None)


class Oidc:
    def __init__(self) -> None:
        self.nonce = "unset"
        self.calls = []

    def exchange_and_verify(
        self,
        *,
        authorization_code: str,
        pkce_verifier: str,
        expected_issuer: str,
        expected_client_id: str,
        expected_redirect_uri: str,
    ) -> VerifiedOidcIdentity:
        self.calls.append(
            (
                authorization_code,
                pkce_verifier,
                expected_issuer,
                expected_client_id,
                expected_redirect_uri,
            )
        )
        return VerifiedOidcIdentity(
            principal_id="principal-a",
            issuer=expected_issuer,
            client_id=expected_client_id,
            nonce=self.nonce,
            authenticated_at=NOW,
            token_expires_at=NOW + timedelta(minutes=10),
            acr="urn:example:loa:1",
            amr=frozenset({"pwd"}),
            policy_version="auth-strength-v1",
        )


class Sessions:
    def __init__(self) -> None:
        self.values: dict[str, BrowserSessionRecord] = {}

    def create(self, record: BrowserSessionRecord) -> bool:
        if record.handle_digest in self.values:
            return False
        self.values[record.handle_digest] = record
        return True

    def resolve(self, handle_digest: str):
        return self.values.get(handle_digest)

    def rotate(self, *, predecessor_handle_digest: str, expected_predecessor_generation: str, successor: BrowserSessionRecord) -> bool:
        current = self.values.get(predecessor_handle_digest)
        if current is None or current.retired or current.session_generation != expected_predecessor_generation:
            return False
        self.values[predecessor_handle_digest] = replace(current, retired=True)
        self.values[successor.handle_digest] = successor
        return True

    def retire(self, *, handle_digest: str, expected_generation: str) -> bool:
        current = self.values.get(handle_digest)
        if current is None or current.retired or current.session_generation != expected_generation:
            return False
        self.values[handle_digest] = replace(current, retired=True)
        return True


class TenantAdmission:
    def __init__(self) -> None:
        self.calls = []
        self.denied = False
        self.return_tenant = None

    def require_current(self, *, principal, tenant_id: str, now: datetime, authentication_strength) -> TenantShellAdmission:
        self.calls.append((principal, tenant_id, now, authentication_strength))
        if self.denied:
            raise AdmissionDenied("current tenant authority denied")
        return TenantShellAdmission(
            tenant_id=self.return_tenant or tenant_id,
            admission_revision="tenant-authz-rev-7",
        )


class G1IdentityTenantShellTests(unittest.TestCase):
    def setUp(self) -> None:
        self.transactions = Transactions()
        self.oidc = Oidc()
        self.sessions = Sessions()
        self.tenant_admission = TenantAdmission()
        self.shell = IdentityTenantShell(
            transactions=self.transactions,
            oidc=self.oidc,
            sessions=self.sessions,
            tenant_admission=self.tenant_admission,
            issuer="https://identity.example.test/realms/jlmirror",
            client_id="jlmirror-bff",
            redirect_uri="https://app.example.test/auth/callback",
            authorization_transaction_lifetime=timedelta(minutes=5),
            session_lifetime=timedelta(hours=1),
        )

    def login(self):
        start = self.shell.begin_login(browser_binding="browser-binding-a", now=NOW)
        self.oidc.nonce = start.nonce
        handle = self.shell.finish_login(
            transaction_id=start.transaction_id,
            browser_binding="browser-binding-a",
            returned_state=start.state,
            authorization_code="authorization-code-a",
            now=NOW,
        )
        return start, handle

    def test_login_uses_pkce_transaction_and_issues_only_opaque_server_session(self):
        start, handle = self.login()
        self.assertNotIn(start.transaction_id, self.transactions.values)
        self.assertGreaterEqual(len(handle.value), 43)
        self.assertNotIn("authorization-code-a", handle.value)
        self.assertNotIn("principal-a", handle.value)
        record = self.sessions.resolve(handle.digest)
        self.assertIsNotNone(record)
        self.assertEqual(record.principal.principal_id, "principal-a")
        verifier = self.oidc.calls[0][1]
        derived_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        self.assertEqual(derived_challenge, start.pkce_challenge)
        self.assertEqual(self.oidc.calls[0][2:], (
            "https://identity.example.test/realms/jlmirror",
            "jlmirror-bff",
            "https://app.example.test/auth/callback",
        ))

    def test_transaction_is_single_use(self):
        start, _handle = self.login()
        with self.assertRaises(AdmissionDenied):
            self.shell.finish_login(
                transaction_id=start.transaction_id,
                browser_binding="browser-binding-a",
                returned_state=start.state,
                authorization_code="authorization-code-b",
                now=NOW,
            )

    def test_browser_binding_mismatch_fails_closed(self):
        start = self.shell.begin_login(browser_binding="browser-binding-a", now=NOW)
        self.oidc.nonce = start.nonce
        with self.assertRaises(AdmissionDenied):
            self.shell.finish_login(
                transaction_id=start.transaction_id,
                browser_binding="browser-binding-other",
                returned_state=start.state,
                authorization_code="authorization-code-a",
                now=NOW,
            )
        self.assertEqual(self.sessions.values, {})

    def test_open_shell_rechecks_current_tenant_authority(self):
        _start, handle = self.login()
        view = self.shell.open_shell(
            session_capability=handle.value,
            tenant_id="tenant-a",
            now=NOW + timedelta(seconds=1),
        )
        self.assertEqual(view.tenant_id, "tenant-a")
        self.assertEqual(view.principal_id, "principal-a")
        self.assertEqual(view.state, "ready")
        self.assertEqual(len(self.tenant_admission.calls), 1)
        principal, tenant_id, _, strength = self.tenant_admission.calls[0]
        self.assertEqual(principal.principal_id, "principal-a")
        self.assertEqual(tenant_id, "tenant-a")
        self.assertIsNotNone(strength)
        self.assertEqual(strength.principal_id, "principal-a")

    def test_revoked_or_forbidden_tenant_fails_closed_even_with_current_session(self):
        _start, handle = self.login()
        self.tenant_admission.denied = True
        with self.assertRaises(AdmissionDenied):
            self.shell.open_shell(
                session_capability=handle.value,
                tenant_id="tenant-a",
                now=NOW + timedelta(seconds=1),
            )

    def test_cross_tenant_admission_evidence_is_rejected(self):
        _start, handle = self.login()
        self.tenant_admission.return_tenant = "tenant-b"
        with self.assertRaisesRegex(AdmissionDenied, "another tenant"):
            self.shell.open_shell(
                session_capability=handle.value,
                tenant_id="tenant-a",
                now=NOW + timedelta(seconds=1),
            )

    def test_logout_retires_session_and_prevents_stale_reuse(self):
        _start, handle = self.login()
        self.shell.logout(session_capability=handle.value, now=NOW + timedelta(seconds=1))
        with self.assertRaises(AdmissionDenied):
            self.shell.open_shell(
                session_capability=handle.value,
                tenant_id="tenant-a",
                now=NOW + timedelta(seconds=2),
            )

    def test_expired_session_fails_before_tenant_admission(self):
        _start, handle = self.login()
        with self.assertRaises(AdmissionDenied):
            self.shell.open_shell(
                session_capability=handle.value,
                tenant_id="tenant-a",
                now=NOW + timedelta(hours=2),
            )
        self.assertEqual(self.tenant_admission.calls, [])


if __name__ == "__main__":
    unittest.main()
