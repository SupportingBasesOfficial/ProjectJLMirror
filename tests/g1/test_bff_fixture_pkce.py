from __future__ import annotations

import base64
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from jlmirror_authority.model import AdmissionDenied  # noqa: E402


def _load_bff_module():
    path = ROOT / "apps/g1-identity-tenant-shell/bff_server.py"
    spec = importlib.util.spec_from_file_location("jlmirror_g1_bff_fixture_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load G1 BFF module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FixturePkceTests(unittest.TestCase):
    def test_fixture_rejects_wrong_pkce_verifier(self):
        module = _load_bff_module()
        oidc = module.FixtureOidc()
        correct_verifier = "A" * 43
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(correct_verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        oidc.register(
            authorization_code="fixture-code",
            nonce="fixture-nonce",
            pkce_challenge=challenge,
        )
        with self.assertRaisesRegex(AdmissionDenied, "PKCE S256"):
            oidc.exchange_and_verify(
                authorization_code="fixture-code",
                pkce_verifier="B" * 43,
                expected_issuer="https://identity.example.test/realms/jlmirror",
                expected_client_id="jlmirror-bff",
                expected_redirect_uri="https://app.example.test/auth/callback",
            )


if __name__ == "__main__":
    unittest.main()
