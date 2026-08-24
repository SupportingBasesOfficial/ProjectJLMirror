from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import base64
import hashlib
import sys
import threading
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jlmirror_authority.browser import (  # noqa: E402
    VerifiedOidcIdentity,
    begin_browser_auth,
    complete_browser_auth,
    require_authentication_strength,
)
from jlmirror_authority.config import ConfigurationSnapshot  # noqa: E402
from jlmirror_authority.control_plane import (  # noqa: E402
    AuthorizationDecision,
    PlacementEvidence,
    RuntimeLifecycle,
    authorize_protected_operation,
    construct_tenant_context,
)
from jlmirror_authority.fencing import (  # noqa: E402
    MAX_SIGNED_BIGINT,
    FenceRecord,
    FenceToken,
    acquire_next_fence,
    admit_fenced_effect,
)
from jlmirror_authority.machine import (  # noqa: E402
    ReplayClaim,
    VerifiedMachineAssertion,
    authenticate_machine_assertion,
)
from jlmirror_authority.model import (  # noqa: E402
    AdmissionDenied,
    AuditClass,
    AuthenticationStrengthEvidence,
    AuthorizationDeclaration,
    EnvironmentClass,
    Principal,
    PrincipalKind,
    ScopeClass,
    SecretReference,
    StepUpClass,
)
from jlmirror_authority.runtime_profiles import (  # noqa: E402
    API_AUTH_BOUNDARY,
    CONTROL_PLANE,
    WEB_BFF,
)
from jlmirror_authority.workload import (  # noqa: E402
    VerifiedWorkloadPeer,
    admit_workload_peer,
    parse_workload_identity,
)

NOW = datetime(2026, 8, 24, 3, 0, tzinfo=timezone.utc)
OIDC_ISSUER = "https://id.example"
OIDC_CLIENT = "bff"
OIDC_REDIRECT = "https://app.example/callback"
MACHINE_MAX_LIFETIME = timedelta(minutes=5)


def human_principal(identifier: str = "user-1", generation: str = "session-g1") -> Principal:
    return Principal(identifier, PrincipalKind.HUMAN_BROWSER_SESSION, generation)


def begin_auth(session_binding: str = "browser-session-A"):
    return begin_browser_auth(
        session_binding=session_binding,
        expected_issuer=OIDC_ISSUER,
        expected_client_id=OIDC_CLIENT,
        expected_redirect_uri=OIDC_REDIRECT,
        now=NOW,
    )


class TxStore:
    def __init__(self, transaction):
        self._transaction = transaction
        self._lock = threading.Lock()

    def consume(self, transaction_id):
        with self._lock:
            if self._transaction is None or self._transaction.transaction_id != transaction_id:
                return None
            value = self._transaction
            self._transaction = None
            return value


class OidcPort:
    def __init__(self, *, nonce, issuer=OIDC_ISSUER, client_id=OIDC_CLIENT, acr="loa2"):
        self.nonce = nonce
        self.issuer = issuer
        self.client_id = client_id
        self.acr = acr
        self.last_kwargs = None

    def exchange_and_verify(self, **kwargs):
        self.last_kwargs = kwargs
        return VerifiedOidcIdentity(
            principal_id="user-1",
            issuer=self.issuer,
            client_id=self.client_id,
            nonce=self.nonce,
            authenticated_at=NOW - timedelta(minutes=1),
            token_expires_at=NOW + timedelta(minutes=10),
            acr=self.acr,
            amr=frozenset({"pwd", "otp"}),
            policy_version="security-policy-v7",
        )


class StrengthPolicy:
    def __init__(self, result=True):
        self.result = result

    def permits(self, **kwargs):
        return self.result if kwargs["policy_id"] == "privileged-v1" else False


class MachineVerifier:
    def __init__(self, assertion):
        self.assertion = assertion

    def verify(self, **kwargs):
        return self.assertion


class ReplayAuthority:
    def __init__(self, forced=None):
        self.forced = forced
        self._used = set()
        self._lock = threading.Lock()

    def claim_once(self, **kwargs):
        if self.forced is not None:
            return self.forced
        key = (kwargs["client_principal"], kwargs["jti"], kwargs["replay_generation"])
        with self._lock:
            if key in self._used:
                return ReplayClaim.ALREADY_USED
            self._used.add(key)
            return ReplayClaim.CLAIMED


class PlacementAuthority:
    def __init__(self, evidence):
        self.evidence = evidence
        self.boolean_gate = True

    def resolve_current(self, tenant_id):
        return self.evidence if self.evidence.tenant_id == tenant_id else None

    def context_is_current(self, context):
        return self.boolean_gate


class AuthzAuthority:
    def __init__(self, *, granted=True, current=True):
        self.granted = granted
        self.current = current

    def evaluate(self, **kwargs):
        return AuthorizationDecision(
            granted=self.granted,
            current=self.current,
            policy_revision="org-authz-r19",
        )


class FenceAuthority:
    def __init__(self, epoch=7, generation="gen-7"):
        self.record = FenceRecord("tenant:acme", epoch, generation, "active")
        self._lock = threading.Lock()

    def current(self, fence_scope_id):
        return self.record if fence_scope_id == self.record.fence_scope_id else None

    def acquire_successor(self, **kwargs):
        with self._lock:
            if (
                kwargs["fence_scope_id"] != self.record.fence_scope_id
                or kwargs["expected_predecessor_epoch"] != self.record.current_fence_epoch
                or kwargs["expected_predecessor_generation_id"] != self.record.current_generation_id
            ):
                return None
            self.record = FenceRecord(
                self.record.fence_scope_id,
                self.record.current_fence_epoch + 1,
                kwargs["successor_generation_id"],
                kwargs["successor_state"],
            )
            return self.record


def machine_assertion(**overrides):
    values = dict(
        client_principal="client-1",
        jti="jti-1",
        audience="https://api.example",
        issued_at=NOW - timedelta(seconds=5),
        not_before=NOW - timedelta(seconds=5),
        expires_at=NOW + timedelta(minutes=2),
        key_generation="key-g7",
        replay_generation="replay-g4",
    )
    values.update(overrides)
    return VerifiedMachineAssertion(**values)


def placement(**overrides):
    values = dict(
        tenant_id="tenant-acme",
        cell_id="cell-a",
        placement_version="pv-9",
        runtime_generation="runtime-g12",
        configuration_generation="cfg-g4",
        workload_credential_generation="wc-g9",
        network_policy_generation="np-g6",
        environment_class=EnvironmentClass.PRODUCTION,
        isolation_class="pooled",
        runtime_lifecycle=RuntimeLifecycle.ACTIVE,
        placement_current=True,
        operation_eligible=True,
        cell_admission_current=True,
        fence_scope_id="tenant:acme",
        fence_epoch=7,
    )
    values.update(overrides)
    return PlacementEvidence(**values)


def construct_context(
    authority: PlacementAuthority,
    *,
    principal: Principal | None = None,
    **destination_overrides,
):
    principal = principal or human_principal()
    evidence = authority.evidence
    values = dict(
        principal=principal,
        placement_authority=authority,
        tenant_id=evidence.tenant_id,
        destination_cell_id=evidence.cell_id,
        destination_runtime_generation=evidence.runtime_generation,
        destination_configuration_generation=evidence.configuration_generation,
        destination_workload_credential_generation=evidence.workload_credential_generation,
        destination_network_policy_generation=evidence.network_policy_generation,
        required_environment=evidence.environment_class,
        now=NOW,
        request_id="req-1",
        correlation_id="corr-1",
        operation_id="op-1",
    )
    values.update(destination_overrides)
    return construct_tenant_context(**values)


class BrowserTests(unittest.TestCase):
    def test_pkce_s256_and_entropy_envelope(self):
        init = begin_auth()
        expected = base64.urlsafe_b64encode(
            hashlib.sha256(init.transaction.pkce_verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        self.assertEqual(init.pkce_challenge, expected)
        self.assertGreaterEqual(len(init.transaction.pkce_verifier), 43)
        self.assertNotEqual(init.state, init.nonce)

    def test_transaction_pins_oidc_profile_and_redacts_transaction_secrets(self):
        init = begin_auth()
        transaction = init.transaction
        self.assertEqual(transaction.expected_issuer, OIDC_ISSUER)
        self.assertEqual(transaction.expected_client_id, OIDC_CLIENT)
        self.assertEqual(transaction.expected_redirect_uri, OIDC_REDIRECT)
        self.assertNotEqual(transaction.nonce_digest, init.nonce)
        for secret in (transaction.pkce_verifier, init.state, init.nonce, init.pkce_challenge):
            self.assertNotIn(secret, repr(transaction))
            self.assertNotIn(secret, repr(init))

    def test_transaction_is_one_shot_even_after_bad_state(self):
        init = begin_auth()
        store = TxStore(init.transaction)
        port = OidcPort(nonce=init.nonce)
        with self.assertRaises(AdmissionDenied):
            complete_browser_auth(
                transaction_authority=store,
                oidc_port=port,
                transaction_id=init.transaction.transaction_id,
                initiating_session_binding="browser-session-A",
                returned_state="wrong",
                authorization_code="code-1",
                now=NOW,
            )
        with self.assertRaises(AdmissionDenied):
            complete_browser_auth(
                transaction_authority=store,
                oidc_port=port,
                transaction_id=init.transaction.transaction_id,
                initiating_session_binding="browser-session-A",
                returned_state=init.state,
                authorization_code="code-1",
                now=NOW,
            )

    def test_cross_session_replay_is_denied(self):
        init = begin_auth()
        with self.assertRaises(AdmissionDenied):
            complete_browser_auth(
                transaction_authority=TxStore(init.transaction),
                oidc_port=OidcPort(nonce=init.nonce),
                transaction_id=init.transaction.transaction_id,
                initiating_session_binding="browser-session-B",
                returned_state=init.state,
                authorization_code="code-1",
                now=NOW,
            )

    def test_nonce_mismatch_is_denied(self):
        init = begin_auth()
        with self.assertRaises(AdmissionDenied):
            complete_browser_auth(
                transaction_authority=TxStore(init.transaction),
                oidc_port=OidcPort(nonce="wrong-nonce"),
                transaction_id=init.transaction.transaction_id,
                initiating_session_binding="browser-session-A",
                returned_state=init.state,
                authorization_code="code-1",
                now=NOW,
            )

    def test_wrong_verified_issuer_or_client_is_denied(self):
        for port in (
            OidcPort(nonce=begin_auth().nonce, issuer="https://evil.example"),
            OidcPort(nonce=begin_auth().nonce, client_id="other-client"),
        ):
            init = begin_auth()
            port.nonce = init.nonce
            with self.subTest(port=port), self.assertRaises(AdmissionDenied):
                complete_browser_auth(
                    transaction_authority=TxStore(init.transaction),
                    oidc_port=port,
                    transaction_id=init.transaction.transaction_id,
                    initiating_session_binding="browser-session-A",
                    returned_state=init.state,
                    authorization_code="code-1",
                    now=NOW,
                )

    def test_callback_uses_initiation_bound_issuer_client_redirect(self):
        init = begin_auth()
        port = OidcPort(nonce=init.nonce)
        complete_browser_auth(
            transaction_authority=TxStore(init.transaction),
            oidc_port=port,
            transaction_id=init.transaction.transaction_id,
            initiating_session_binding="browser-session-A",
            returned_state=init.state,
            authorization_code="code-1",
            now=NOW,
        )
        self.assertEqual(port.last_kwargs["expected_issuer"], OIDC_ISSUER)
        self.assertEqual(port.last_kwargs["expected_client_id"], OIDC_CLIENT)
        self.assertEqual(port.last_kwargs["expected_redirect_uri"], OIDC_REDIRECT)

    def test_valid_callback_yields_human_principal_and_strength_evidence(self):
        init = begin_auth()
        port = OidcPort(nonce=init.nonce)
        principal, strength = complete_browser_auth(
            transaction_authority=TxStore(init.transaction),
            oidc_port=port,
            transaction_id=init.transaction.transaction_id,
            initiating_session_binding="browser-session-A",
            returned_state=init.state,
            authorization_code="code-1",
            now=NOW,
        )
        self.assertEqual(principal.kind, PrincipalKind.HUMAN_BROWSER_SESSION)
        self.assertTrue(strength.is_current(NOW))
        self.assertEqual(port.last_kwargs["pkce_verifier"], init.transaction.pkce_verifier)

    def test_strength_missing_policy_denied_or_truthy_non_bool_fails_closed(self):
        evidence = AuthenticationStrengthEvidence(
            issuer="id.example",
            acr="loa2",
            amr=frozenset({"otp"}),
            authenticated_at=NOW - timedelta(minutes=1),
            evidence_expires_at=NOW + timedelta(minutes=1),
            policy_version="p7",
        )
        for policy, supplied in (
            (StrengthPolicy(True), None),
            (StrengthPolicy(False), evidence),
            (StrengthPolicy("true"), evidence),
        ):
            with self.subTest(result=policy.result), self.assertRaises(AdmissionDenied):
                require_authentication_strength(
                    policy=policy,
                    policy_id="privileged-v1",
                    evidence=supplied,
                    now=NOW,
                )


class MachineTests(unittest.TestCase):
    def _authenticate(self, assertion=None, replay=None, max_lifetime=MACHINE_MAX_LIFETIME):
        return authenticate_machine_assertion(
            verifier=MachineVerifier(assertion or machine_assertion()),
            replay_authority=replay or ReplayAuthority(),
            compact_assertion="opaque-jwt-never-logged",
            expected_client_principal="client-1",
            expected_audience="https://api.example",
            current_key_generation="key-g7",
            current_replay_generation="replay-g4",
            current_max_assertion_lifetime=max_lifetime,
            now=NOW,
        )

    def test_valid_assertion_yields_attributable_machine_principal(self):
        principal = self._authenticate()
        self.assertEqual(principal.kind, PrincipalKind.MACHINE_API_PRINCIPAL)
        self.assertEqual(principal.principal_id, "client-1")

    def test_wrong_audience_and_stale_key_are_denied(self):
        with self.assertRaises(AdmissionDenied):
            self._authenticate(machine_assertion(audience="https://other.example"))
        with self.assertRaises(AdmissionDenied):
            self._authenticate(machine_assertion(key_generation="key-old"))

    def test_unavailable_or_unproven_replay_authority_fails_closed(self):
        for state in (ReplayClaim.AUTHORITY_UNAVAILABLE, ReplayClaim.CONTINUITY_UNPROVEN):
            with self.subTest(state=state), self.assertRaises(AdmissionDenied):
                self._authenticate(replay=ReplayAuthority(state))

    def test_duplicate_jti_is_rejected(self):
        replay = ReplayAuthority()
        self._authenticate(replay=replay)
        with self.assertRaises(AdmissionDenied):
            self._authenticate(replay=replay)

    def test_concurrent_duplicate_jti_has_one_winner(self):
        replay = ReplayAuthority()
        barrier = threading.Barrier(32)
        outcomes = []
        lock = threading.Lock()

        def run():
            barrier.wait()
            try:
                self._authenticate(replay=replay)
                outcome = "accepted"
            except AdmissionDenied:
                outcome = "denied"
            with lock:
                outcomes.append(outcome)

        threads = [threading.Thread(target=run) for _ in range(32)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(outcomes.count("accepted"), 1)
        self.assertEqual(outcomes.count("denied"), 31)

    def test_long_lived_assertion_is_denied_by_current_security_policy(self):
        assertion = machine_assertion(
            issued_at=NOW - timedelta(seconds=1),
            not_before=NOW - timedelta(seconds=1),
            expires_at=NOW + timedelta(minutes=10),
        )
        with self.assertRaises(AdmissionDenied):
            self._authenticate(assertion)

    def test_missing_or_invalid_lifetime_policy_fails_closed(self):
        for policy in (timedelta(0), timedelta(seconds=-1), None):
            with self.subTest(policy=policy), self.assertRaises(AdmissionDenied):
                self._authenticate(max_lifetime=policy)


class WorkloadTests(unittest.TestCase):
    def peer(self):
        return VerifiedWorkloadPeer(
            spiffe_id="spiffe://jlmirror.example/environment.production@1/runtime.api@1/api-01",
            certificate_not_before=NOW - timedelta(minutes=1),
            certificate_not_after=NOW + timedelta(minutes=5),
            trust_bundle_generation="tb-4",
            workload_credential_generation="wc-9",
        )

    def test_canonical_spiffe_identity_parses(self):
        identity = parse_workload_identity(self.peer().spiffe_id)
        self.assertEqual(identity.environment_class, EnvironmentClass.PRODUCTION)
        self.assertEqual(identity.runtime_profile_id, "runtime.api@1")

    def test_noncanonical_spiffe_forms_are_denied(self):
        invalid = (
            "spiffe://jlmirror.example/environment.production@1/runtime.api@1/a%2Fb",
            "spiffe://user@jlmirror.example/environment.production@1/runtime.api@1/api-01",
            "spiffe://jlmirror.example/environment.production@1/runtime.api@1/api-01?x=1",
            "spiffe://jlmirror.example/environment.production@1/runtime.api@1/a/b",
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(AdmissionDenied):
                parse_workload_identity(value)

    def test_workload_peer_rejects_cross_environment_and_stale_bundle(self):
        with self.assertRaises(AdmissionDenied):
            admit_workload_peer(
                peer=self.peer(),
                expected_trust_domain="jlmirror.example",
                expected_environment=EnvironmentClass.VALIDATION,
                allowed_runtime_profiles=frozenset({"runtime.api@1"}),
                current_trust_bundle_generation="tb-4",
                current_workload_credential_generation="wc-9",
                now=NOW,
            )
        with self.assertRaises(AdmissionDenied):
            admit_workload_peer(
                peer=self.peer(),
                expected_trust_domain="jlmirror.example",
                expected_environment=EnvironmentClass.PRODUCTION,
                allowed_runtime_profiles=frozenset({"runtime.api@1"}),
                current_trust_bundle_generation="tb-5",
                current_workload_credential_generation="wc-9",
                now=NOW,
            )

    def test_workload_identity_returns_service_principal_not_tenant_principal(self):
        principal = admit_workload_peer(
            peer=self.peer(),
            expected_trust_domain="jlmirror.example",
            expected_environment=EnvironmentClass.PRODUCTION,
            allowed_runtime_profiles=frozenset({"runtime.api@1"}),
            current_trust_bundle_generation="tb-4",
            current_workload_credential_generation="wc-9",
            now=NOW,
        )
        self.assertEqual(principal.kind, PrincipalKind.INTERNAL_SERVICE_PRINCIPAL)
        self.assertNotIn("tenant", principal.principal_id)


class ControlPlaneTests(unittest.TestCase):
    def test_constructs_context_bound_to_principal_and_all_current_generations(self):
        authority = PlacementAuthority(placement())
        principal = human_principal()
        context = construct_context(authority, principal=principal)
        self.assertTrue(context.matches_principal(principal))
        self.assertEqual(context.placement_version, "pv-9")
        self.assertEqual(context.runtime_generation, "runtime-g12")
        self.assertEqual(context.configuration_generation, "cfg-g4")
        self.assertEqual(context.workload_credential_generation, "wc-g9")
        self.assertEqual(context.network_policy_generation, "np-g6")
        self.assertEqual(context.fence_epoch, 7)
        self.assertEqual(context.request_id, "req-1")
        self.assertEqual(context.correlation_id, "corr-1")
        self.assertEqual(context.operation_id, "op-1")

    def test_destination_currentness_mismatch_is_denied_for_every_runtime_dimension(self):
        authority = PlacementAuthority(placement())
        cases = {
            "destination_cell_id": "cell-b",
            "destination_runtime_generation": "runtime-old",
            "destination_configuration_generation": "cfg-old",
            "destination_workload_credential_generation": "wc-old",
            "destination_network_policy_generation": "np-old",
        }
        for field, value in cases.items():
            with self.subTest(field=field), self.assertRaises(AdmissionDenied):
                construct_context(authority, **{field: value})

    def test_draining_and_missing_currentness_predicates_are_denied(self):
        for evidence in (
            placement(runtime_lifecycle=RuntimeLifecycle.DRAINING),
            placement(placement_current=False),
            placement(operation_eligible=False),
            placement(cell_admission_current=False),
        ):
            with self.subTest(evidence=evidence), self.assertRaises(AdmissionDenied):
                construct_context(PlacementAuthority(evidence))

    def test_current_owning_authorization_is_required_after_context(self):
        placement_authority = PlacementAuthority(placement())
        context = construct_context(placement_authority)
        declaration = AuthorizationDeclaration(
            action="organization.memberships.manage",
            scope=ScopeClass.TENANT,
            tenant_required=True,
            step_up=StepUpClass.NONE,
            audit_class=AuditClass.PRIVILEGED,
        )
        for authz in (AuthzAuthority(granted=False), AuthzAuthority(current=False)):
            with self.assertRaises(AdmissionDenied):
                authorize_protected_operation(
                    principal=human_principal(),
                    declaration=declaration,
                    placement_authority=placement_authority,
                    authorization_authority=authz,
                    context=context,
                    now=NOW,
                )

    def test_context_cannot_be_reused_by_different_principal_or_generation(self):
        placement_authority = PlacementAuthority(placement())
        context = construct_context(placement_authority, principal=human_principal("user-1", "session-g1"))
        declaration = AuthorizationDeclaration(
            action="organization.memberships.read",
            scope=ScopeClass.TENANT,
            tenant_required=True,
            step_up=StepUpClass.NONE,
            audit_class=AuditClass.NORMAL,
        )
        for principal in (
            human_principal("user-2", "session-g1"),
            human_principal("user-1", "session-g2"),
        ):
            with self.subTest(principal=principal), self.assertRaises(AdmissionDenied):
                authorize_protected_operation(
                    principal=principal,
                    declaration=declaration,
                    placement_authority=placement_authority,
                    authorization_authority=AuthzAuthority(),
                    context=context,
                    now=NOW,
                )

    def test_context_revalidation_detects_each_generation_drift(self):
        declaration = AuthorizationDeclaration(
            action="organization.memberships.read",
            scope=ScopeClass.TENANT,
            tenant_required=True,
            step_up=StepUpClass.NONE,
            audit_class=AuditClass.NORMAL,
        )
        for field, value in (
            ("placement_version", "pv-10"),
            ("runtime_generation", "runtime-g13"),
            ("configuration_generation", "cfg-g5"),
            ("workload_credential_generation", "wc-g10"),
            ("network_policy_generation", "np-g7"),
            ("fence_epoch", 8),
        ):
            authority = PlacementAuthority(placement())
            context = construct_context(authority)
            authority.evidence = replace(authority.evidence, **{field: value})
            with self.subTest(field=field), self.assertRaises(AdmissionDenied):
                authorize_protected_operation(
                    principal=human_principal(),
                    declaration=declaration,
                    placement_authority=authority,
                    authorization_authority=AuthzAuthority(),
                    context=context,
                    now=NOW,
                )

    def test_truthy_non_boolean_currentness_port_is_denied(self):
        authority = PlacementAuthority(placement())
        context = construct_context(authority)
        authority.boolean_gate = "true"
        declaration = AuthorizationDeclaration(
            action="organization.memberships.read",
            scope=ScopeClass.TENANT,
            tenant_required=True,
            step_up=StepUpClass.NONE,
            audit_class=AuditClass.NORMAL,
        )
        with self.assertRaises(AdmissionDenied):
            authorize_protected_operation(
                principal=human_principal(),
                declaration=declaration,
                placement_authority=authority,
                authorization_authority=AuthzAuthority(),
                context=context,
                now=NOW,
            )

    def test_privileged_step_up_is_independent_of_permission(self):
        placement_authority = PlacementAuthority(placement())
        principal = Principal("admin-1", PrincipalKind.PLATFORM_ADMIN_PRINCIPAL, "cg-1")
        context = construct_context(placement_authority, principal=principal)
        declaration = AuthorizationDeclaration(
            action="platform.tenants.suspend",
            scope=ScopeClass.TENANT,
            tenant_required=True,
            step_up=StepUpClass.REQUIRED,
            audit_class=AuditClass.SECURITY_CRITICAL,
            authentication_strength_policy_id="privileged-v1",
        )
        with self.assertRaises(AdmissionDenied):
            authorize_protected_operation(
                principal=principal,
                declaration=declaration,
                placement_authority=placement_authority,
                authorization_authority=AuthzAuthority(granted=True),
                context=context,
                now=NOW,
                strength_policy=StrengthPolicy(True),
                strength_evidence=None,
            )


class FencingTests(unittest.TestCase):
    def test_effect_requires_exact_scope_epoch_and_generation(self):
        current = FenceRecord("tenant:acme", 7, "gen-7", "active")
        admit_fenced_effect(token=FenceToken("tenant:acme", 7, "gen-7"), current=current)
        for token in (
            FenceToken("tenant:acme", 6, "gen-7"),
            FenceToken("tenant:acme", 8, "gen-7"),
            FenceToken("tenant:other", 7, "gen-7"),
            FenceToken("tenant:acme", 7, "gen-other"),
        ):
            with self.subTest(token=token), self.assertRaises(AdmissionDenied):
                admit_fenced_effect(token=token, current=current)

    def test_concurrent_successor_acquisition_has_one_predecessor_winner(self):
        authority = FenceAuthority()
        barrier = threading.Barrier(24)
        outcomes = []
        lock = threading.Lock()

        def run(index):
            barrier.wait()
            try:
                record = acquire_next_fence(
                    authority=authority,
                    fence_scope_id="tenant:acme",
                    expected_predecessor_epoch=7,
                    successor_generation_id=f"gen-next-{index}",
                )
                outcome = ("accepted", record.current_fence_epoch)
            except AdmissionDenied:
                outcome = ("denied", None)
            with lock:
                outcomes.append(outcome)

        threads = [threading.Thread(target=run, args=(index,)) for index in range(24)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sum(1 for state, _ in outcomes if state == "accepted"), 1)
        self.assertEqual(authority.record.current_fence_epoch, 8)

    def test_bigint_exhaustion_fails_closed(self):
        with self.assertRaises(AdmissionDenied):
            acquire_next_fence(
                authority=FenceAuthority(MAX_SIGNED_BIGINT, "gen-max"),
                fence_scope_id="tenant:acme",
                expected_predecessor_epoch=MAX_SIGNED_BIGINT,
                successor_generation_id="never",
            )


class ConfigAndRuntimeTests(unittest.TestCase):
    def test_secret_reference_repr_redacts_reference_id(self):
        ref = SecretReference("vault://prod/bff/session", "secretref.web-session@1", "sg-3")
        text = repr(ref)
        self.assertNotIn("vault://prod/bff/session", text)
        self.assertIn("secretref.web-session@1", text)

    def test_config_cannot_duplicate_secret_as_public_value(self):
        ref = SecretReference("vault://prod/bff/session", "secretref.web-session@1", "sg-3")
        with self.assertRaises(ValueError):
            ConfigurationSnapshot("cfg-9", {"session_key": "raw-secret"}, {"session_key": ref})

    def test_config_evidence_exposes_reference_class_not_reference_id(self):
        ref = SecretReference("vault://prod/bff/session", "secretref.web-session@1", "sg-3")
        view = ConfigurationSnapshot("cfg-9", {"feature": True}, {"session_key": ref}).evidence_view()
        self.assertNotIn("vault://prod/bff/session", repr(view))
        self.assertEqual(view["secret_reference_classes"]["session_key"], "secretref.web-session@1")

    def test_wave1_serving_profiles_do_not_admit_recovery_environment(self):
        for binding in (WEB_BFF, API_AUTH_BOUNDARY, CONTROL_PLANE):
            binding.admit_environment(EnvironmentClass.PRODUCTION)
            with self.assertRaises(AdmissionDenied):
                binding.admit_environment(EnvironmentClass.RECOVERY)


if __name__ == "__main__":
    unittest.main(verbosity=2)
