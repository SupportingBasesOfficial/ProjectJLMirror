from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jlmirror_authority.browser import require_authentication_strength  # noqa: E402
from jlmirror_authority.config import (  # noqa: E402
    ConfigurationSchema,
    ConfigurationSnapshot,
    require_classified_configuration,
)
from jlmirror_authority.model import (  # noqa: E402
    AdmissionDenied,
    AuthenticationStrengthEvidence,
    EnvironmentClass,
    Principal,
    PrincipalKind,
    SecretReference,
)
from jlmirror_authority.session import issue_browser_session  # noqa: E402

NOW = datetime(2026, 8, 24, 11, 0, tzinfo=timezone.utc)


class AlwaysPermitStrengthPolicy:
    def permits(self, **kwargs):
        return True


class ConfigurationAuthority:
    def __init__(self, result=True):
        self.result = result
        self.last_kwargs = None

    def admit_current(self, **kwargs):
        self.last_kwargs = kwargs
        return self.result


def strength_for(
    principal_id: str | None,
    credential_generation: str | None = None,
) -> AuthenticationStrengthEvidence:
    if principal_id is not None and credential_generation is None:
        credential_generation = "identity-g1"
    return AuthenticationStrengthEvidence(
        issuer="id.example",
        acr="loa2",
        amr=frozenset({"pwd", "otp"}),
        authenticated_at=NOW - timedelta(minutes=1),
        evidence_expires_at=NOW + timedelta(minutes=5),
        policy_version="security-policy-v7",
        principal_id=principal_id,
        principal_credential_generation=credential_generation,
    )


class SessionAuthority:
    def create(self, record):
        return True


class CapturingSessionAuthority:
    def __init__(self):
        self.record = None

    def create(self, record):
        self.record = record
        return True


class AuthenticationStrengthBindingTests(unittest.TestCase):
    def test_cross_principal_strength_evidence_fails_even_when_policy_permits(self):
        with self.assertRaises(AdmissionDenied):
            require_authentication_strength(
                policy=AlwaysPermitStrengthPolicy(),
                policy_id="privileged-v1",
                evidence=strength_for("user-a", "session-g2"),
                principal=Principal(
                    "user-b", PrincipalKind.HUMAN_BROWSER_SESSION, "session-g2"
                ),
                now=NOW,
            )

    def test_unbound_strength_evidence_is_inert_at_protected_boundary(self):
        with self.assertRaises(AdmissionDenied):
            require_authentication_strength(
                policy=AlwaysPermitStrengthPolicy(),
                policy_id="privileged-v1",
                evidence=strength_for(None),
                principal=Principal(
                    "user-a", PrincipalKind.HUMAN_BROWSER_SESSION, "session-g1"
                ),
                now=NOW,
            )

    def test_same_principal_other_session_strength_evidence_fails(self):
        with self.assertRaises(AdmissionDenied):
            require_authentication_strength(
                policy=AlwaysPermitStrengthPolicy(),
                policy_id="privileged-v1",
                evidence=strength_for("user-a", "session-old"),
                principal=Principal(
                    "user-a", PrincipalKind.HUMAN_BROWSER_SESSION, "session-current"
                ),
                now=NOW,
            )

    def test_strength_evidence_cannot_be_attached_to_another_users_session(self):
        with self.assertRaises(AdmissionDenied):
            issue_browser_session(
                authority=SessionAuthority(),
                principal=Principal(
                    "user-b", PrincipalKind.HUMAN_BROWSER_SESSION, "identity-g2"
                ),
                now=NOW,
                lifetime=timedelta(minutes=30),
                authentication_strength=strength_for("user-a", "identity-g1"),
            )

    def test_strength_evidence_from_other_generation_cannot_be_attached_to_same_user(self):
        with self.assertRaises(AdmissionDenied):
            issue_browser_session(
                authority=SessionAuthority(),
                principal=Principal(
                    "user-a", PrincipalKind.HUMAN_BROWSER_SESSION, "identity-current"
                ),
                now=NOW,
                lifetime=timedelta(minutes=30),
                authentication_strength=strength_for("user-a", "identity-old"),
            )

    def test_session_authority_rebinds_matching_assurance_to_new_session_generation(self):
        authority = CapturingSessionAuthority()
        source = Principal("user-a", PrincipalKind.HUMAN_BROWSER_SESSION, "identity-current")
        issue_browser_session(
            authority=authority,
            principal=source,
            now=NOW,
            lifetime=timedelta(minutes=30),
            authentication_strength=strength_for("user-a", "identity-current"),
        )
        self.assertIsNotNone(authority.record)
        self.assertEqual(authority.record.authentication_strength.principal_id, "user-a")
        self.assertEqual(
            authority.record.authentication_strength.principal_credential_generation,
            authority.record.session_generation,
        )


class ConfigurationTypeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.schema = ConfigurationSchema(
            public_keys=frozenset({"feature_enabled", "issuer_url", "retry_factor"}),
            secret_reference_classes={
                "session_key": frozenset({"secretref.web-session@1"})
            },
        )

    def admit(self, snapshot, *, authority=None, generation="cfg-g1"):
        authority = authority or ConfigurationAuthority(True)
        return require_classified_configuration(
            snapshot,
            authority=authority,
            runtime_profile_id="runtime.web-bff@1",
            environment_class=EnvironmentClass.PRODUCTION,
            expected_configuration_generation=generation,
        )

    def test_generation_must_be_an_explicit_string(self):
        for value in (1, True, object(), "", " cfg-g1 "):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ConfigurationSnapshot(value, {}, {}, schema=self.schema)  # type: ignore[arg-type]

    def test_public_configuration_is_restricted_to_finite_json_scalars(self):
        invalid_values = ({"nested": "value"}, ["x"], b"secret", object(), math.nan, math.inf)
        for value in invalid_values:
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                ConfigurationSnapshot(
                    "cfg-g1", {"issuer_url": value}, {}, schema=self.schema  # type: ignore[dict-item]
                )

    def test_secret_reference_mapping_requires_typed_reference_objects(self):
        with self.assertRaises(ValueError):
            ConfigurationSnapshot(
                "cfg-g1",
                {},
                {"session_key": "vault://raw-secret"},  # type: ignore[dict-item]
                schema=self.schema,
            )

    def test_schema_collections_cannot_launder_strings_into_character_sets(self):
        with self.assertRaises(ValueError):
            ConfigurationSchema("issuer_url", {})  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            ConfigurationSchema(
                frozenset(),
                {"session_key": "secretref.web-session@1"},  # type: ignore[dict-item]
            )

    def test_protected_configuration_boundary_rejects_non_snapshot_objects(self):
        with self.assertRaises(AdmissionDenied):
            require_classified_configuration({"configuration_generation": "cfg-g1"})  # type: ignore[arg-type]

    def test_schema_presence_cannot_self_assert_current_classification_authority(self):
        snapshot = ConfigurationSnapshot(
            "cfg-g1",
            {"issuer_url": "https://id.example"},
            {},
            schema=self.schema,
        )
        self.assertTrue(snapshot.classification_schema_present)
        with self.assertRaises(AdmissionDenied):
            require_classified_configuration(snapshot)
        with self.assertRaises(AdmissionDenied):
            self.admit(snapshot, authority=ConfigurationAuthority(False))

    def test_wrong_generation_fails_before_authority_admission(self):
        snapshot = ConfigurationSnapshot(
            "cfg-old", {"issuer_url": "https://id.example"}, {}, schema=self.schema
        )
        authority = ConfigurationAuthority(True)
        with self.assertRaises(AdmissionDenied):
            self.admit(snapshot, authority=authority, generation="cfg-current")
        self.assertIsNone(authority.last_kwargs)

    def test_valid_current_classified_snapshot_passes_with_runtime_environment_binding(self):
        snapshot = ConfigurationSnapshot(
            "cfg-g1",
            {
                "feature_enabled": True,
                "issuer_url": "https://id.example",
                "retry_factor": 1.5,
            },
            {
                "session_key": SecretReference(
                    "vault://prod/bff/session",
                    "secretref.web-session@1",
                    "secret-g1",
                )
            },
            schema=self.schema,
        )
        authority = ConfigurationAuthority(True)
        self.assertIs(self.admit(snapshot, authority=authority), snapshot)
        self.assertEqual(authority.last_kwargs["runtime_profile_id"], "runtime.web-bff@1")
        self.assertIs(authority.last_kwargs["environment_class"], EnvironmentClass.PRODUCTION)
        self.assertEqual(authority.last_kwargs["expected_configuration_generation"], "cfg-g1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
