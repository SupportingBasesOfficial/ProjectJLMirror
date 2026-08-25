from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import threading
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
from jlmirror_authority.model import (  # noqa: E402
    AdmissionDenied,
    AuditClass,
    AuthorizationDeclaration,
    EnvironmentClass,
    Principal,
    PrincipalKind,
    ScopeClass,
    SecretReference,
    StepUpClass,
)
from jlmirror_authority.session import (  # noqa: E402
    BrowserSessionHandle,
    BrowserSessionRecord,
    issue_browser_session,
    resolve_browser_session,
    retire_browser_session,
    rotate_browser_session,
)
from jlmirror_authority.workload import parse_workload_identity  # noqa: E402

NOW = datetime(2026, 8, 24, 3, 30, tzinfo=timezone.utc)


class InMemorySessionAuthority:
    def __init__(self):
        self.records: dict[str, BrowserSessionRecord] = {}
        self._lock = threading.Lock()

    def create(self, record):
        with self._lock:
            if record.handle_digest in self.records:
                return False
            self.records[record.handle_digest] = record
            return True

    def resolve(self, handle_digest):
        with self._lock:
            return self.records.get(handle_digest)

    def rotate(self, *, predecessor_handle_digest, expected_predecessor_generation, successor):
        with self._lock:
            current = self.records.get(predecessor_handle_digest)
            if (
                current is None
                or current.retired
                or current.session_generation != expected_predecessor_generation
                or successor.handle_digest in self.records
            ):
                return False
            self.records[predecessor_handle_digest] = replace(current, retired=True)
            self.records[successor.handle_digest] = successor
            return True

    def retire(self, *, handle_digest, expected_generation):
        with self._lock:
            current = self.records.get(handle_digest)
            if current is None or current.retired or current.session_generation != expected_generation:
                return False
            self.records[handle_digest] = replace(current, retired=True)
            return True


class ConfigurationAuthority:
    def __init__(self, result=True):
        self.result = result

    def admit_current(self, **kwargs):
        return self.result


class BrowserSessionHardeningTests(unittest.TestCase):
    def setUp(self):
        self.authority = InMemorySessionAuthority()
        self.principal = Principal(
            "user-1", PrincipalKind.HUMAN_BROWSER_SESSION, "identity-g7"
        )

    def test_handle_is_high_entropy_opaque_and_repr_redacted(self):
        handle = issue_browser_session(
            authority=self.authority,
            principal=self.principal,
            now=NOW,
            lifetime=timedelta(minutes=30),
        )
        self.assertGreaterEqual(len(handle.value), 43)
        self.assertNotIn(handle.value, repr(handle))
        self.assertEqual(len(handle.digest), 64)
        record = resolve_browser_session(authority=self.authority, handle=handle, now=NOW)
        self.assertEqual(record.principal.credential_generation, record.session_generation)
        self.assertNotEqual(record.session_generation, "identity-g7")

    def test_unknown_and_expired_handles_fail_closed(self):
        with self.assertRaises(AdmissionDenied):
            resolve_browser_session(
                authority=self.authority,
                handle=BrowserSessionHandle("x" * 64),
                now=NOW,
            )
        handle = issue_browser_session(
            authority=self.authority,
            principal=self.principal,
            now=NOW,
            lifetime=timedelta(seconds=1),
        )
        with self.assertRaises(AdmissionDenied):
            resolve_browser_session(
                authority=self.authority, handle=handle, now=NOW + timedelta(seconds=2)
            )

    def test_rotation_atomically_retires_predecessor_and_changes_generation(self):
        old = issue_browser_session(
            authority=self.authority,
            principal=self.principal,
            now=NOW,
            lifetime=timedelta(minutes=30),
        )
        old_record = resolve_browser_session(authority=self.authority, handle=old, now=NOW)
        new = rotate_browser_session(
            authority=self.authority,
            predecessor=old,
            now=NOW + timedelta(seconds=1),
            lifetime=timedelta(minutes=30),
        )
        with self.assertRaises(AdmissionDenied):
            resolve_browser_session(authority=self.authority, handle=old, now=NOW + timedelta(seconds=2))
        new_record = resolve_browser_session(
            authority=self.authority, handle=new, now=NOW + timedelta(seconds=2)
        )
        self.assertNotEqual(old.value, new.value)
        self.assertNotEqual(old_record.session_generation, new_record.session_generation)
        self.assertEqual(new_record.principal.credential_generation, new_record.session_generation)

    def test_retirement_invalidates_cookie_even_if_handle_remains(self):
        handle = issue_browser_session(
            authority=self.authority,
            principal=self.principal,
            now=NOW,
            lifetime=timedelta(minutes=30),
        )
        retire_browser_session(authority=self.authority, handle=handle, now=NOW)
        with self.assertRaises(AdmissionDenied):
            resolve_browser_session(authority=self.authority, handle=handle, now=NOW)

    def test_machine_principal_cannot_become_browser_session(self):
        with self.assertRaises(AdmissionDenied):
            issue_browser_session(
                authority=self.authority,
                principal=Principal("machine-1", PrincipalKind.MACHINE_API_PRINCIPAL, "key-g1"),
                now=NOW,
                lifetime=timedelta(minutes=30),
            )


class ConfigurationClassificationTests(unittest.TestCase):
    def setUp(self):
        self.schema = ConfigurationSchema(
            public_keys=frozenset({"feature_enabled", "issuer_url"}),
            secret_reference_classes={
                "session_signing_key": frozenset({"secretref.web-session@1"}),
            },
        )
        self.reference = SecretReference(
            "vault://prod/bff/session",
            "secretref.web-session@1",
            "secret-g3",
        )
        self.authority = ConfigurationAuthority(True)

    def admit(self, snapshot, *, authority=None):
        return require_classified_configuration(
            snapshot,
            authority=authority or self.authority,
            runtime_profile_id="runtime.web-bff@1",
            environment_class=EnvironmentClass.PRODUCTION,
            expected_configuration_generation="cfg-g4",
        )

    def test_classified_snapshot_requires_current_external_authority(self):
        snapshot = ConfigurationSnapshot(
            "cfg-g4",
            {"feature_enabled": True, "issuer_url": "https://id.example"},
            {"session_signing_key": self.reference},
            schema=self.schema,
        )
        self.assertTrue(snapshot.classification_schema_present)
        self.assertIs(self.admit(snapshot), snapshot)
        with self.assertRaises(AdmissionDenied):
            self.admit(snapshot, authority=ConfigurationAuthority(False))

    def test_secret_classified_key_cannot_be_raw_public_value(self):
        with self.assertRaises(ValueError):
            ConfigurationSnapshot(
                "cfg-g4", {"session_signing_key": "raw-secret"}, {}, schema=self.schema
            )

    def test_unknown_key_and_wrong_secret_reference_class_are_rejected(self):
        with self.assertRaises(ValueError):
            ConfigurationSnapshot("cfg-g4", {"vendor_default": "x"}, {}, schema=self.schema)
        wrong = SecretReference("vault://prod/api/state", "secretref.state-port@1", "secret-g9")
        with self.assertRaises(ValueError):
            ConfigurationSnapshot(
                "cfg-g4", {}, {"session_signing_key": wrong}, schema=self.schema
            )

    def test_unclassified_snapshot_cannot_be_admitted_as_runtime_configuration(self):
        snapshot = ConfigurationSnapshot("cfg-g4", {"feature_enabled": True}, {})
        self.assertFalse(snapshot.classification_schema_present)
        with self.assertRaises(AdmissionDenied):
            self.admit(snapshot)

    def test_evidence_never_contains_secret_reference_locator_or_claims_current_authority(self):
        snapshot = ConfigurationSnapshot(
            "cfg-g4", {}, {"session_signing_key": self.reference}, schema=self.schema
        )
        evidence = snapshot.evidence_view()
        self.assertNotIn("vault://prod/bff/session", repr(evidence))
        self.assertNotIn("classification_proven", evidence)
        self.assertTrue(evidence["classification_schema_present"])


class BoundaryHardeningTests(unittest.TestCase):
    def test_malformed_spiffe_port_is_controlled_denial_not_parser_exception(self):
        with self.assertRaises(AdmissionDenied):
            parse_workload_identity(
                "spiffe://jlmirror.example:bad/environment.production@1/runtime.api@1/api-01"
            )

    def test_all_non_none_step_up_modes_require_policy_id(self):
        for mode in (StepUpClass.POLICY_DRIVEN, StepUpClass.REQUIRED):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                AuthorizationDeclaration(
                    action="platform.tenants.suspend",
                    scope=ScopeClass.TENANT,
                    tenant_required=True,
                    step_up=mode,
                    audit_class=AuditClass.SECURITY_CRITICAL,
                )

    def test_step_up_none_cannot_smuggle_policy_metadata(self):
        with self.assertRaises(ValueError):
            AuthorizationDeclaration(
                action="organization.memberships.read",
                scope=ScopeClass.TENANT,
                tenant_required=True,
                step_up=StepUpClass.NONE,
                audit_class=AuditClass.NORMAL,
                authentication_strength_policy_id="privileged-v1",
            )


class SqlPrivilegeHardeningTests(unittest.TestCase):
    def test_fence_sql_revokes_public_table_and_function_authority(self):
        text = (ROOT / "sql" / "wave1" / "001_platform_authority_fence.sql").read_text(
            encoding="utf-8"
        )
        required = (
            "REVOKE ALL ON TABLE platform.authority_fences FROM PUBLIC;",
            "REVOKE ALL ON FUNCTION platform.initialize_authority_fence(text, text, text) FROM PUBLIC;",
            "REVOKE ALL ON FUNCTION platform.advance_authority_fence(text, bigint, text, text, text) FROM PUBLIC;",
            'authority_fences.fence_scope_id COLLATE "C" = p_fence_scope_id COLLATE "C"',
            'authority_fences.current_generation_id COLLATE "C" = p_expected_predecessor_generation_id COLLATE "C"',
            'authority_fences.authority_state COLLATE "C" = \'active\' COLLATE "C"',
            "CONSTRAINT wave1_fence_scope_id_canonical",
            "btrim(fence_scope_id) <> ''",
            "CONSTRAINT wave1_fence_generation_canonical",
            "btrim(current_generation_id) <> ''",
            "CONSTRAINT wave1_fence_state_canonical",
            "btrim(authority_state) <> ''",
        )
        for fragment in required:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)