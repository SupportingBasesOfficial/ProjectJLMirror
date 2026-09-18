from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "apps/g3-resource-inventory"))

from current_authorization import BoundResourceAuthorization  # noqa: E402
from jlmirror_authority.model import AdmissionDenied, AuthenticationStrengthEvidence, Principal, PrincipalKind  # noqa: E402


def load_g1():
    path = ROOT / "apps/g1-identity-tenant-shell/bff_server.py"
    spec = importlib.util.spec_from_file_location("jlmirror_g1_g3_fixture", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("G1 fixture cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


G1 = load_g1()
NOW = datetime(2026, 9, 18, 0, 0, tzinfo=timezone.utc)


class AuthorizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = G1.FixtureAuthorityState()
        self.principal = Principal(
            principal_id="principal-a",
            kind=PrincipalKind.HUMAN_BROWSER_SESSION,
            credential_generation="principal-generation-a",
            active=True,
        )
        self.strength = AuthenticationStrengthEvidence(
            issuer="id.example",
            acr="urn:jlmirror:loa:1",
            amr=frozenset({"pwd"}),
            authenticated_at=NOW - timedelta(minutes=1),
            evidence_expires_at=NOW + timedelta(minutes=10),
            policy_version="fixture-auth-strength-v1",
            principal_id="principal-a",
            principal_credential_generation="principal-generation-a",
        )

    def auth(self):
        return BoundResourceAuthorization(
            principal=self.principal,
            authentication_strength=self.strength,
            principal_authority=G1.FixturePrincipalAuthority(self.state),
            placement_authority=G1.FixturePlacementAuthority(self.state),
            authorization_authority=G1.FixtureAuthorizationAuthority(self.state),
            strength_policy=G1.FixtureStrengthPolicy(),
            final_admission_authority=G1.FixtureFinalAdmissionAuthority(self.state),
            now=NOW,
        )

    def test_resource_read_is_admitted(self):
        evidence = self.auth().require(
            actor_ref="principal-a",
            tenant_id="tenant-a",
            action="monitoring.resource.read",
        )
        self.assertEqual(evidence.actor_principal_id, "principal-a")
        self.assertEqual(evidence.authorization_decision_ref, "fixture-current-admission-r1")

    def test_other_monitoring_action_is_outside_g3_surface(self):
        with self.assertRaises(AdmissionDenied):
            self.auth().require(
                actor_ref="principal-a",
                tenant_id="tenant-a",
                action="monitoring.source.read",
            )

    def test_cross_tenant_is_denied(self):
        with self.assertRaises(AdmissionDenied):
            self.auth().require(
                actor_ref="principal-a",
                tenant_id="tenant-b",
                action="monitoring.resource.read",
            )

    def test_revocation_is_rechecked(self):
        auth = self.auth()
        auth.require(actor_ref="principal-a", tenant_id="tenant-a", action="monitoring.resource.read")
        self.state.set_mode(principal_id="principal-a", mode="revoked")
        with self.assertRaises(AdmissionDenied):
            auth.require(actor_ref="principal-a", tenant_id="tenant-a", action="monitoring.resource.read")


if __name__ == "__main__":
    unittest.main()
