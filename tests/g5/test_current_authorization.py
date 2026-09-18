from __future__ import annotations

from datetime import datetime,timedelta,timezone
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"apps/g5-problem-health"))

from current_authorization import BoundProblemHealthAuthorization  # noqa: E402
from jlmirror_authority.model import AdmissionDenied,AuthenticationStrengthEvidence,Principal,PrincipalKind  # noqa: E402


def load_g1():
    path=ROOT/"apps/g1-identity-tenant-shell/bff_server.py"
    spec=importlib.util.spec_from_file_location("jlmirror_g1_g5_fixture",path)
    if spec is None or spec.loader is None:
        raise RuntimeError("G1 fixture cannot be loaded")
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    return module


G1=load_g1()
NOW=datetime(2026,9,18,0,0,tzinfo=timezone.utc)


class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.state=G1.FixtureAuthorityState()
        self.principal=Principal(
            principal_id="principal-a",
            kind=PrincipalKind.HUMAN_BROWSER_SESSION,
            credential_generation="principal-generation-a",
            active=True,
        )
        self.strength=AuthenticationStrengthEvidence(
            issuer="id.example",
            acr="urn:jlmirror:loa:1",
            amr=frozenset({"pwd"}),
            authenticated_at=NOW-timedelta(minutes=1),
            evidence_expires_at=NOW+timedelta(minutes=10),
            policy_version="fixture-auth-strength-v1",
            principal_id="principal-a",
            principal_credential_generation="principal-generation-a",
        )

    def auth(self):
        return BoundProblemHealthAuthorization(
            principal=self.principal,
            authentication_strength=self.strength,
            principal_authority=G1.FixturePrincipalAuthority(self.state),
            placement_authority=G1.FixturePlacementAuthority(self.state),
            authorization_authority=G1.FixtureAuthorizationAuthority(self.state),
            strength_policy=G1.FixtureStrengthPolicy(),
            final_admission_authority=G1.FixtureFinalAdmissionAuthority(self.state),
            now=NOW,
        )

    def test_g5_read_actions_are_admitted(self):
        for action in ("monitoring.resource.read","monitoring.problem.read","monitoring.health.read"):
            evidence=self.auth().require(actor_ref="principal-a",tenant_id="tenant-a",action=action)
            self.assertEqual(evidence.actor_principal_id,"principal-a")

    def test_later_gate_action_is_outside_g5_surface(self):
        with self.assertRaises(AdmissionDenied):
            self.auth().require(
                actor_ref="principal-a",
                tenant_id="tenant-a",
                action="monitoring.sync.read",
            )

    def test_cross_tenant_is_denied(self):
        with self.assertRaises(AdmissionDenied):
            self.auth().require(
                actor_ref="principal-a",
                tenant_id="tenant-b",
                action="monitoring.health.read",
            )

    def test_revocation_is_rechecked(self):
        auth=self.auth()
        auth.require(actor_ref="principal-a",tenant_id="tenant-a",action="monitoring.problem.read")
        self.state.set_mode(principal_id="principal-a",mode="revoked")
        with self.assertRaises(AdmissionDenied):
            auth.require(actor_ref="principal-a",tenant_id="tenant-a",action="monitoring.problem.read")


if __name__=="__main__":
    unittest.main()
