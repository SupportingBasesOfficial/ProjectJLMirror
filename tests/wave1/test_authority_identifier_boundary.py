from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jlmirror_authority.config import (  # noqa: E402
    ConfigurationSchema,
    ConfigurationSnapshot,
    require_classified_configuration,
)
from jlmirror_authority.machine import authenticate_machine_assertion  # noqa: E402
from jlmirror_authority.model import AdmissionDenied, EnvironmentClass  # noqa: E402
from jlmirror_authority.workload import VerifiedWorkloadPeer  # noqa: E402

NOW = datetime(2026, 8, 24, 14, 40, tzinfo=timezone.utc)


class ExplodingVerifier:
    def __init__(self) -> None:
        self.called = False

    def verify(self, **kwargs):
        self.called = True
        raise AssertionError("malformed authority identifiers must fail before verifier port")


class NeverReplay:
    def claim_once(self, **kwargs):
        raise AssertionError("replay authority must not be reached")


class ExplodingConfigAuthority:
    def __init__(self) -> None:
        self.called = False

    def admit_current(self, **kwargs):
        self.called = True
        raise AssertionError("malformed generation must fail before config authority")


class AuthorityIdentifierBoundaryTests(unittest.TestCase):
    def test_machine_authority_ids_fail_before_verifier_port(self):
        cases = {
            "expected_client_principal": "client id",
            "current_key_generation": "key generation",
            "current_replay_generation": "replay generation",
        }
        for field, value in cases.items():
            verifier = ExplodingVerifier()
            kwargs = dict(
                verifier=verifier,
                replay_authority=NeverReplay(),
                compact_assertion="opaque",
                expected_client_principal="client-1",
                expected_audience="https://api.example",
                current_key_generation="key-g1",
                current_replay_generation="replay-g1",
                current_max_assertion_lifetime=timedelta(minutes=5),
                now=NOW,
            )
            kwargs[field] = value
            with self.subTest(field=field), self.assertRaises(AdmissionDenied):
                authenticate_machine_assertion(**kwargs)
            self.assertFalse(verifier.called)

    def test_workload_generation_ids_use_authority_identifier_grammar(self):
        for field in ("trust_bundle_generation", "workload_credential_generation"):
            kwargs = dict(
                spiffe_id="spiffe://jlmirror.example/environment.production@1/runtime.api@1/api-1",
                certificate_not_before=NOW - timedelta(minutes=1),
                certificate_not_after=NOW + timedelta(minutes=1),
                trust_bundle_generation="tb-g1",
                workload_credential_generation="wc-g1",
            )
            kwargs[field] = "generation with spaces"
            with self.subTest(field=field), self.assertRaises(ValueError):
                VerifiedWorkloadPeer(**kwargs)

    def test_configuration_snapshot_generation_is_canonical(self):
        schema = ConfigurationSchema(public_keys=frozenset({"mode"}), secret_reference_classes={})
        with self.assertRaises(ValueError):
            ConfigurationSnapshot(
                configuration_generation="cfg generation",
                public_values={"mode": "safe"},
                secret_references={},
                schema=schema,
            )

    def test_expected_configuration_generation_fails_before_authority_port(self):
        schema = ConfigurationSchema(public_keys=frozenset({"mode"}), secret_reference_classes={})
        snapshot = ConfigurationSnapshot(
            configuration_generation="cfg-g1",
            public_values={"mode": "safe"},
            secret_references={},
            schema=schema,
        )
        authority = ExplodingConfigAuthority()
        with self.assertRaises(AdmissionDenied):
            require_classified_configuration(
                snapshot,
                authority=authority,
                runtime_profile_id="runtime.api@1",
                environment_class=EnvironmentClass.PRODUCTION,
                expected_configuration_generation="cfg generation",
            )
        self.assertFalse(authority.called)


if __name__ == "__main__":
    unittest.main(verbosity=2)
