from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jlmirror_authority.browser import begin_browser_auth, complete_browser_auth  # noqa: E402
from jlmirror_authority.model import AdmissionDenied  # noqa: E402

NOW = datetime(2026, 8, 24, 15, 0, tzinfo=timezone.utc)
BROWSER_TRANSACTION_LIFETIME = timedelta(minutes=5)


class OneShotTransactionAuthority:
    def __init__(self, transaction):
        self.transaction = transaction

    def consume(self, transaction_id):
        if self.transaction is None or self.transaction.transaction_id != transaction_id:
            return None
        value = self.transaction
        self.transaction = None
        return value


class ExplodingOidcPort:
    def __init__(self) -> None:
        self.called = False

    def exchange_and_verify(self, **kwargs):
        self.called = True
        raise AssertionError("not-yet-current transaction must fail before IdP adapter")


class BrowserTransactionCurrentnessTests(unittest.TestCase):
    def test_clock_before_transaction_creation_fails_before_oidc_port(self):
        initiation = begin_browser_auth(
            session_binding="browser-A",
            expected_issuer="https://id.example",
            expected_client_id="bff",
            expected_redirect_uri="https://app.example/callback",
            now=NOW,
            lifetime=BROWSER_TRANSACTION_LIFETIME,
        )
        oidc = ExplodingOidcPort()
        with self.assertRaises(AdmissionDenied):
            complete_browser_auth(
                transaction_authority=OneShotTransactionAuthority(initiation.transaction),
                oidc_port=oidc,
                transaction_id=initiation.transaction.transaction_id,
                initiating_session_binding="browser-A",
                returned_state=initiation.state,
                authorization_code="opaque-code",
                now=NOW - timedelta(seconds=1),
            )
        self.assertFalse(oidc.called)

    def test_exact_creation_time_is_current(self):
        initiation = begin_browser_auth(
            session_binding="browser-A",
            expected_issuer="https://id.example",
            expected_client_id="bff",
            expected_redirect_uri="https://app.example/callback",
            now=NOW,
            lifetime=BROWSER_TRANSACTION_LIFETIME,
        )

        class TypedPort:
            def exchange_and_verify(self, **kwargs):
                from jlmirror_authority.browser import VerifiedOidcIdentity

                return VerifiedOidcIdentity(
                    principal_id="user-1",
                    issuer="https://id.example",
                    client_id="bff",
                    nonce=initiation.nonce,
                    authenticated_at=NOW,
                    token_expires_at=NOW + timedelta(minutes=5),
                    acr="mfa",
                    amr=frozenset({"pwd", "otp"}),
                    policy_version="policy-1",
                )

        principal, _ = complete_browser_auth(
            transaction_authority=OneShotTransactionAuthority(initiation.transaction),
            oidc_port=TypedPort(),
            transaction_id=initiation.transaction.transaction_id,
            initiating_session_binding="browser-A",
            returned_state=initiation.state,
            authorization_code="opaque-code",
            now=NOW,
        )
        self.assertEqual(principal.principal_id, "user-1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
