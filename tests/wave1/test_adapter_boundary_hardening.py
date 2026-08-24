from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jlmirror_authority.browser import (  # noqa: E402
    begin_browser_auth,
    complete_browser_auth,
)
from jlmirror_authority.machine import (  # noqa: E402
    ReplayClaim,
    VerifiedMachineAssertion,
    authenticate_machine_assertion,
)
from jlmirror_authority.model import AdmissionDenied, EnvironmentClass  # noqa: E402
from jlmirror_authority.workload import (  # noqa: E402
    VerifiedWorkloadPeer,
    admit_workload_peer,
)

NOW = datetime(2026, 8, 24, 11, 15, tzinfo=timezone.utc)
BROWSER_TRANSACTION_LIFETIME = timedelta(minutes=5)


class TxStore:
    def __init__(self, transaction):
        self.transaction = transaction

    def consume(self, transaction_id):
        if self.transaction is None or self.transaction.transaction_id != transaction_id:
            return None
        value = self.transaction
        self.transaction = None
        return value


class MalformedOidcPort:
    def exchange_and_verify(self, **kwargs):
        return {"principal_id": "user-1"}


class MachineVerifier:
    def __init__(self, assertion):
        self.assertion = assertion

    def verify(self, **kwargs):
        return self.assertion


class ReplayAuthority:
    def __init__(self):
        self.called = False

    def claim_once(self, **kwargs):
        self.called = True
        return ReplayClaim.CLAIMED


class AdapterBoundaryTests(unittest.TestCase):
    def test_malformed_oidc_adapter_result_is_controlled_denial(self):
        initiation = begin_browser_auth(
            session_binding="browser-A",
            expected_issuer="https://id.example",
            expected_client_id="bff",
            expected_redirect_uri="https://app.example/callback",
            now=NOW,
            lifetime=BROWSER_TRANSACTION_LIFETIME,
        )
        with self.assertRaises(AdmissionDenied):
            complete_browser_auth(
                transaction_authority=TxStore(initiation.transaction),
                oidc_port=MalformedOidcPort(),
                transaction_id=initiation.transaction.transaction_id,
                initiating_session_binding="browser-A",
                returned_state=initiation.state,
                authorization_code="opaque-code",
                now=NOW,
            )

    def test_machine_malformed_current_generation_fails_before_replay_claim(self):
        replay = ReplayAuthority()
        assertion = VerifiedMachineAssertion(
            client_principal="client-1",
            jti="jti-1",
            audience="https://api.example",
            issued_at=NOW - timedelta(seconds=1),
            not_before=NOW - timedelta(seconds=1),
            expires_at=NOW + timedelta(minutes=1),
            key_generation="",
            replay_generation="replay-g1",
        )
        with self.assertRaises(AdmissionDenied):
            authenticate_machine_assertion(
                verifier=MachineVerifier(assertion),
                replay_authority=replay,
                compact_assertion="opaque-jwt",
                expected_client_principal="client-1",
                expected_audience="https://api.example",
                current_key_generation="",
                current_replay_generation="replay-g1",
                current_max_assertion_lifetime=timedelta(minutes=5),
                now=NOW,
            )
        self.assertFalse(replay.called)

    def test_machine_noncanonical_principal_fails_before_replay_claim(self):
        replay = ReplayAuthority()
        assertion = VerifiedMachineAssertion(
            client_principal="client id with spaces",
            jti="jti-2",
            audience="https://api.example",
            issued_at=NOW - timedelta(seconds=1),
            not_before=NOW - timedelta(seconds=1),
            expires_at=NOW + timedelta(minutes=1),
            key_generation="key-g1",
            replay_generation="replay-g1",
        )
        with self.assertRaises(AdmissionDenied):
            authenticate_machine_assertion(
                verifier=MachineVerifier(assertion),
                replay_authority=replay,
                compact_assertion="opaque-jwt",
                expected_client_principal="client id with spaces",
                expected_audience="https://api.example",
                current_key_generation="key-g1",
                current_replay_generation="replay-g1",
                current_max_assertion_lifetime=timedelta(minutes=5),
                now=NOW,
            )
        self.assertFalse(replay.called)

    def test_workload_string_profile_set_cannot_launder_as_exact_allowlist(self):
        peer = VerifiedWorkloadPeer(
            spiffe_id=(
                "spiffe://jlmirror.example/environment.production@1/runtime.api@1/api-1"
            ),
            certificate_not_before=NOW - timedelta(minutes=1),
            certificate_not_after=NOW + timedelta(minutes=1),
            trust_bundle_generation="tb-g1",
            workload_credential_generation="wc-g1",
        )
        with self.assertRaises(AdmissionDenied):
            admit_workload_peer(
                peer=peer,
                expected_trust_domain="jlmirror.example",
                expected_environment=EnvironmentClass.PRODUCTION,
                allowed_runtime_profiles="runtime.api@1",  # type: ignore[arg-type]
                current_trust_bundle_generation="tb-g1",
                current_workload_credential_generation="wc-g1",
                now=NOW,
            )

    def test_workload_empty_current_generation_cannot_match_empty_adapter_generation(self):
        peer = VerifiedWorkloadPeer(
            spiffe_id=(
                "spiffe://jlmirror.example/environment.production@1/runtime.api@1/api-1"
            ),
            certificate_not_before=NOW - timedelta(minutes=1),
            certificate_not_after=NOW + timedelta(minutes=1),
            trust_bundle_generation="tb-g1",
            workload_credential_generation="wc-g1",
        )
        with self.assertRaises(AdmissionDenied):
            admit_workload_peer(
                peer=peer,
                expected_trust_domain="jlmirror.example",
                expected_environment=EnvironmentClass.PRODUCTION,
                allowed_runtime_profiles=frozenset({"runtime.api@1"}),
                current_trust_bundle_generation="",
                current_workload_credential_generation="wc-g1",
                now=NOW,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
