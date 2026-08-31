from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import queue
import secrets
import sqlite3
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jlmirror_authority.model import AdmissionDenied, Principal, PrincipalKind  # noqa: E402

from keycloak_backchannel_probe import (  # noqa: E402
    admin_token,
    b64url_decode,
    request,
    verify_rs256,
    wait_ready,
)

BASE = os.environ.get("KEYCLOAK_BASE_URL", "https://127.0.0.1:8443").rstrip("/")
REALM = "d3authority"
CLIENT_ID = "d3-authority-bff"
CLIENT_SECRET = "d3-authority-client-secret"
USER = "authority-alice"
PASSWORD = "d3-authority-user-password"
PLATFORM_PRINCIPAL = "principal-d3-authority"
RELINKED_PRINCIPAL = "principal-d3-relinked"
OTHER_PRINCIPAL = "principal-d3-other"
LOGOUT_PORT = int(os.environ.get("D3_AUTHORITY_LOGOUT_PORT", "18082"))
LOGOUT_URL = f"http://host.docker.internal:{LOGOUT_PORT}/backchannel-logout"
EVENT_URI = "http://schemas.openid.net/event/backchannel-logout"


class UncertainAuthority(RuntimeError):
    pass


class ReplayDetected(AdmissionDenied):
    pass


class CaptureHandler(BaseHTTPRequestHandler):
    captured: queue.Queue[str] = queue.Queue(maxsize=16)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 64 * 1024:
            self.send_response(400)
            self.end_headers()
            return
        raw = self.rfile.read(length)
        try:
            parsed = parse_qs(
                raw.decode("utf-8"),
                keep_blank_values=True,
                strict_parsing=True,
            )
        except (UnicodeDecodeError, ValueError):
            self.send_response(400)
            self.end_headers()
            return
        values = parsed.get("logout_token", [])
        if len(values) != 1 or not values[0]:
            self.send_response(400)
            self.end_headers()
            return
        self.captured.put(values[0])
        self.send_response(200)
        self.end_headers()

    def log_message(self, fmt, *args):
        return


@dataclass(frozen=True)
class AuthenticatedLogout:
    issuer: str
    client_id: str
    jti: str
    issued_at: int
    expires_at: int
    sid: str | None
    sub: str | None
    raw_fingerprint: str


class LogoutVerifier:
    def __init__(self) -> None:
        self.issuer = f"{BASE}/realms/{REALM}"

    def verify(self, token: str) -> AuthenticatedLogout:
        if not isinstance(token, str) or not token or len(token.encode("utf-8")) > 32 * 1024:
            raise AdmissionDenied("logout token outside bounded wire profile")
        parts = token.split(".")
        if len(parts) != 3:
            raise AdmissionDenied("logout token is not compact JWS")
        try:
            header = json.loads(b64url_decode(parts[0]))
            claims = json.loads(b64url_decode(parts[1]))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AdmissionDenied("logout token is not canonical JSON/JWS") from exc
        if not isinstance(header, dict) or not isinstance(claims, dict):
            raise AdmissionDenied("logout token header/claims are malformed")
        if header.get("alg") != "RS256":
            raise AdmissionDenied("logout token algorithm outside trusted profile")
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid or "jku" in header or "x5u" in header:
            raise AdmissionDenied("logout token key selection outside trusted profile")
        _, jwks, _ = request("GET", f"{self.issuer}/protocol/openid-connect/certs")
        if not isinstance(jwks, dict):
            raise AdmissionDenied("trusted JWKS response is malformed")
        keys = [
            key
            for key in jwks.get("keys", [])
            if isinstance(key, dict) and key.get("kid") == kid and key.get("kty") == "RSA"
        ]
        if len(keys) != 1:
            raise AdmissionDenied("logout-token kid did not resolve to one trusted RSA key")
        try:
            verify_rs256(token, keys[0])
        except AssertionError as exc:
            raise AdmissionDenied("logout-token signature verification failed") from exc

        if claims.get("iss") != self.issuer:
            raise AdmissionDenied("logout-token issuer mismatch")
        aud = claims.get("aud")
        audiences = {aud} if isinstance(aud, str) else set(aud or [])
        if CLIENT_ID not in audiences:
            raise AdmissionDenied("logout-token audience mismatch")
        iat = claims.get("iat")
        exp = claims.get("exp")
        jti = claims.get("jti")
        if (
            not isinstance(iat, int)
            or not isinstance(exp, int)
            or exp <= iat
            or not isinstance(jti, str)
            or not jti
        ):
            raise AdmissionDenied("logout-token bounded time/replay claims are malformed")
        now = int(time.time())
        if iat > now + 5 or exp <= now:
            raise AdmissionDenied("logout token is not current")
        if "nonce" in claims:
            raise AdmissionDenied("logout token must not carry nonce")
        events = claims.get("events")
        if not isinstance(events, dict) or EVENT_URI not in events:
            raise AdmissionDenied("logout token lacks required event")
        sid = claims.get("sid")
        sub = claims.get("sub")
        if sid is not None and (not isinstance(sid, str) or not sid):
            raise AdmissionDenied("logout-token sid is malformed")
        if sub is not None and (not isinstance(sub, str) or not sub):
            raise AdmissionDenied("logout-token sub is malformed")
        if sid is None and sub is None:
            raise AdmissionDenied("logout token lacks both sid and sub")
        return AuthenticatedLogout(
            issuer=self.issuer,
            client_id=CLIENT_ID,
            jti=jti,
            issued_at=iat,
            expires_at=exp,
            sid=sid,
            sub=sub,
            raw_fingerprint=hashlib.sha256(token.encode("ascii")).hexdigest(),
        )


@dataclass(frozen=True)
class ReplayLease:
    issuer: str
    client_id: str
    jti: str
    owner: str


class DurableReplayLedger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS replay_ledger (
                    issuer TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    jti TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('pending','retryable','completed')),
                    owner TEXT,
                    PRIMARY KEY (issuer, client_id, jti)
                )
                """
            )

    def claim(
        self,
        *,
        issuer: str,
        client_id: str,
        jti: str,
        fingerprint: str,
    ) -> ReplayLease:
        owner = secrets.token_hex(16)
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """
                SELECT fingerprint, status
                FROM replay_ledger
                WHERE issuer=? AND client_id=? AND jti=?
                """,
                (issuer, client_id, jti),
            ).fetchone()
            if row is None:
                db.execute(
                    """
                    INSERT INTO replay_ledger
                    (issuer, client_id, jti, fingerprint, status, owner)
                    VALUES (?, ?, ?, ?, 'pending', ?)
                    """,
                    (issuer, client_id, jti, fingerprint, owner),
                )
            else:
                existing_fingerprint, status = row
                if existing_fingerprint != fingerprint:
                    raise ReplayDetected("same replay identity arrived with different token bytes")
                if status == "completed":
                    raise ReplayDetected("completed logout replay rejected")
                if status == "pending":
                    raise ReplayDetected("concurrent/in-progress logout replay rejected")
                if status != "retryable":
                    raise AssertionError(f"unexpected replay status: {status!r}")
                cursor = db.execute(
                    """
                    UPDATE replay_ledger
                    SET status='pending', owner=?
                    WHERE issuer=? AND client_id=? AND jti=? AND status='retryable'
                    """,
                    (owner, issuer, client_id, jti),
                )
                if cursor.rowcount != 1:
                    raise ReplayDetected("retry lease lost single-winner claim")
            db.execute("COMMIT")
        except Exception:
            try:
                db.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            db.close()
        return ReplayLease(issuer, client_id, jti, owner)

    def _transition(self, lease: ReplayLease, target: str) -> None:
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            cursor = db.execute(
                """
                UPDATE replay_ledger
                SET status=?, owner=NULL
                WHERE issuer=? AND client_id=? AND jti=?
                  AND status='pending' AND owner=?
                """,
                (
                    target,
                    lease.issuer,
                    lease.client_id,
                    lease.jti,
                    lease.owner,
                ),
            )
            if cursor.rowcount != 1:
                raise AssertionError("replay lease transition lost current ownership")
            db.execute("COMMIT")
        except Exception:
            try:
                db.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            db.close()

    def complete(self, lease: ReplayLease) -> None:
        self._transition(lease, "completed")

    def retryable(self, lease: ReplayLease) -> None:
        self._transition(lease, "retryable")

    def status(self, *, issuer: str, client_id: str, jti: str) -> str | None:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT status FROM replay_ledger
                WHERE issuer=? AND client_id=? AND jti=?
                """,
                (issuer, client_id, jti),
            ).fetchone()
        return None if row is None else str(row[0])


@dataclass(frozen=True)
class ProviderSessionBinding:
    issuer: str
    client_id: str
    sid: str
    sub: str
    principal_id: str
    local_session_id: str
    active: bool = True


class ProviderMappingAuthority:
    def __init__(self) -> None:
        self.sid_bindings: dict[tuple[str, str, str], ProviderSessionBinding] = {}
        self.subject_current: dict[tuple[str, str], str] = {}
        self.available = True
        self.lookup_count = 0

    def bind(
        self,
        *,
        issuer: str,
        client_id: str,
        sid: str,
        sub: str,
        principal_id: str,
        local_session_id: str,
    ) -> None:
        if sid in {principal_id, local_session_id} or sub == principal_id:
            raise AssertionError("provider-native identity collided with platform identity in evidence setup")
        key = (issuer, client_id, sid)
        if key in self.sid_bindings:
            raise AssertionError("duplicate provider sid binding")
        self.sid_bindings[key] = ProviderSessionBinding(
            issuer=issuer,
            client_id=client_id,
            sid=sid,
            sub=sub,
            principal_id=principal_id,
            local_session_id=local_session_id,
        )
        self.subject_current[(issuer, sub)] = principal_id

    def unlink_subject(self, *, issuer: str, sub: str) -> None:
        self.subject_current.pop((issuer, sub), None)

    def relink_subject(self, *, issuer: str, sub: str, principal_id: str) -> None:
        self.subject_current[(issuer, sub)] = principal_id

    def resolve(
        self,
        *,
        issuer: str,
        client_id: str,
        sid: str | None,
        sub: str | None,
    ) -> ProviderSessionBinding | str | None:
        self.lookup_count += 1
        if not self.available:
            raise UncertainAuthority("provider mapping currentness unavailable")

        if sid is not None:
            binding = self.sid_bindings.get((issuer, client_id, sid))
            if binding is not None:
                if sub is not None and binding.sub != sub:
                    raise UncertainAuthority("authenticated sid/sub mapping is contradictory")
                if binding.active:
                    return binding
                return None

        if sub is not None:
            return self.subject_current.get((issuer, sub))
        return None

    def retire_sid(self, binding: ProviderSessionBinding) -> None:
        key = (binding.issuer, binding.client_id, binding.sid)
        current = self.sid_bindings.get(key)
        if current != binding:
            raise UncertainAuthority("provider session binding changed during logout effect")
        self.sid_bindings[key] = ProviderSessionBinding(
            issuer=current.issuer,
            client_id=current.client_id,
            sid=current.sid,
            sub=current.sub,
            principal_id=current.principal_id,
            local_session_id=current.local_session_id,
            active=False,
        )


@dataclass(frozen=True)
class LocalSession:
    session_id: str
    principal_id: str
    principal_generation: int


class SessionFenceAuthority:
    def __init__(self) -> None:
        self.principal_generations: dict[str, int] = {}
        self.retired_sessions: set[str] = set()
        self.generation_mutations = 0
        self.sid_retire_mutations = 0

    def current_generation(self, principal_id: str) -> int:
        return self.principal_generations.setdefault(principal_id, 1)

    def create(self, *, session_id: str, principal_id: str) -> LocalSession:
        return LocalSession(
            session_id=session_id,
            principal_id=principal_id,
            principal_generation=self.current_generation(principal_id),
        )

    def retire_exact(self, session_id: str) -> None:
        self.retired_sessions.add(session_id)
        self.sid_retire_mutations += 1

    def fence_principal(self, principal_id: str) -> None:
        self.principal_generations[principal_id] = self.current_generation(principal_id) + 1
        self.generation_mutations += 1

    def current(self, session: LocalSession) -> bool:
        return (
            session.session_id not in self.retired_sessions
            and session.principal_generation == self.current_generation(session.principal_id)
        )


class LogoutAuthority:
    def __init__(
        self,
        *,
        verifier: LogoutVerifier,
        replay: DurableReplayLedger,
        mappings: ProviderMappingAuthority,
        fences: SessionFenceAuthority,
    ) -> None:
        self.verifier = verifier
        self.replay = replay
        self.mappings = mappings
        self.fences = fences

    def handle(self, token: str) -> str:
        authenticated = self.verifier.verify(token)
        lease = self.replay.claim(
            issuer=authenticated.issuer,
            client_id=authenticated.client_id,
            jti=authenticated.jti,
            fingerprint=authenticated.raw_fingerprint,
        )
        try:
            resolved = self.mappings.resolve(
                issuer=authenticated.issuer,
                client_id=authenticated.client_id,
                sid=authenticated.sid,
                sub=authenticated.sub,
            )
            if isinstance(resolved, ProviderSessionBinding):
                self.fences.retire_exact(resolved.local_session_id)
                self.mappings.retire_sid(resolved)
                result = "sid_retired"
            elif isinstance(resolved, str):
                self.fences.fence_principal(resolved)
                result = "principal_fenced"
            elif resolved is None:
                result = "confirmed_absent"
            else:
                raise UncertainAuthority("provider mapping returned non-canonical resolution")
        except Exception:
            self.replay.retryable(lease)
            raise
        self.replay.complete(lease)
        return result

    def apply_authenticated_sub_only_for_fence_proof(
        self,
        authenticated: AuthenticatedLogout,
    ) -> str:
        if authenticated.sid is not None or authenticated.sub is None:
            raise ValueError("sub-only normalized proof requires sid absent and sub present")
        resolved = self.mappings.resolve(
            issuer=authenticated.issuer,
            client_id=authenticated.client_id,
            sid=None,
            sub=authenticated.sub,
        )
        if not isinstance(resolved, str):
            raise AssertionError("sub-only normalized logout did not resolve one platform principal")
        self.fences.fence_principal(resolved)
        return resolved


@dataclass(frozen=True)
class LocalCurrentness:
    session: bool
    membership: bool
    permission: bool
    tenant_access: bool


def existing_session_admitted(*, local: LocalCurrentness) -> bool:
    return (
        local.session is True
        and local.membership is True
        and local.permission is True
        and local.tenant_access is True
    )


def new_login_admitted(*, idp_available: bool) -> bool:
    return idp_available is True


def step_up_admitted(*, idp_available: bool, local: LocalCurrentness) -> bool:
    return idp_available is True and existing_session_admitted(local=local)


class PlatformAuthorization:
    def __init__(self) -> None:
        self.tenant_memberships: set[tuple[str, str]] = set()

    def allow(self, principal_id: str, tenant_id: str) -> None:
        self.tenant_memberships.add((principal_id, tenant_id))

    def permits(self, principal_id: str, tenant_id: str) -> bool:
        return (principal_id, tenant_id) in self.tenant_memberships


def _b64url_json(value: dict) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _alg_none_variant(token: str) -> str:
    parts = token.split(".")
    header = json.loads(b64url_decode(parts[0]))
    header["alg"] = "none"
    return f"{_b64url_json(header)}.{parts[1]}."


def _signature_tamper(token: str) -> str:
    parts = token.split(".")
    signature = bytearray(b64url_decode(parts[2]))
    if not signature:
        raise AssertionError("cannot tamper empty signature")
    signature[-1] ^= 1
    encoded = base64.urlsafe_b64encode(bytes(signature)).rstrip(b"=").decode()
    return f"{parts[0]}.{parts[1]}.{encoded}"


def configure_realm() -> str:
    token = admin_token()
    request(
        "POST",
        f"{BASE}/admin/realms",
        token=token,
        body={"realm": REALM, "enabled": True},
    )
    request(
        "POST",
        f"{BASE}/admin/realms/{REALM}/clients",
        token=token,
        body={
            "clientId": CLIENT_ID,
            "name": "D3 authority evidence BFF",
            "enabled": True,
            "protocol": "openid-connect",
            "publicClient": False,
            "secret": CLIENT_SECRET,
            "standardFlowEnabled": True,
            "directAccessGrantsEnabled": True,
            "serviceAccountsEnabled": False,
            "redirectUris": ["https://bff.d3.invalid/callback"],
            "attributes": {
                "backchannel.logout.url": LOGOUT_URL,
                "backchannel.logout.session.required": "true",
                "backchannel.logout.revoke.offline.tokens": "false",
            },
        },
    )
    _, clients, _ = request(
        "GET",
        f"{BASE}/admin/realms/{REALM}/clients?clientId={CLIENT_ID}",
        token=token,
    )
    if not isinstance(clients, list) or len(clients) != 1:
        raise AssertionError("could not resolve exactly one authority evidence client")
    client_uuid = clients[0].get("id")
    if not isinstance(client_uuid, str) or not client_uuid:
        raise AssertionError("authority evidence client lacks id")

    for mapper in (
        {
            "name": "d3-groups",
            "protocol": "openid-connect",
            "protocolMapper": "oidc-group-membership-mapper",
            "consentRequired": False,
            "config": {
                "claim.name": "groups",
                "full.path": "true",
                "id.token.claim": "true",
                "access.token.claim": "true",
                "userinfo.token.claim": "false",
            },
        },
        {
            "name": "d3-provider-organization",
            "protocol": "openid-connect",
            "protocolMapper": "oidc-hardcoded-claim-mapper",
            "consentRequired": False,
            "config": {
                "claim.name": "organization",
                "claim.value": "tenant-admin-org",
                "jsonType.label": "String",
                "id.token.claim": "true",
                "access.token.claim": "true",
                "userinfo.token.claim": "false",
            },
        },
    ):
        request(
            "POST",
            f"{BASE}/admin/realms/{REALM}/clients/{client_uuid}/protocol-mappers/models",
            token=token,
            body=mapper,
        )

    request(
        "POST",
        f"{BASE}/admin/realms/{REALM}/roles",
        token=token,
        body={"name": "tenant-admin", "description": "provider-native role; never platform authority"},
    )
    _, role, _ = request(
        "GET",
        f"{BASE}/admin/realms/{REALM}/roles/tenant-admin",
        token=token,
    )
    if not isinstance(role, dict) or not isinstance(role.get("id"), str):
        raise AssertionError("provider evidence role creation failed")

    request(
        "POST",
        f"{BASE}/admin/realms/{REALM}/groups",
        token=token,
        body={"name": "tenant-admin-group"},
    )
    _, groups, _ = request(
        "GET",
        f"{BASE}/admin/realms/{REALM}/groups?search=tenant-admin-group&exact=true",
        token=token,
    )
    if not isinstance(groups, list) or len(groups) != 1:
        raise AssertionError("provider evidence group creation failed")
    group_id = groups[0].get("id")
    if not isinstance(group_id, str) or not group_id:
        raise AssertionError("provider evidence group lacks id")

    request(
        "POST",
        f"{BASE}/admin/realms/{REALM}/users",
        token=token,
        body={
            "username": USER,
            "enabled": True,
            "firstName": "D3",
            "lastName": "Authority Evidence",
            "email": "d3-authority@example.invalid",
            "emailVerified": True,
            "requiredActions": [],
            "credentials": [{"type": "password", "value": PASSWORD, "temporary": False}],
        },
    )
    _, users, _ = request(
        "GET",
        f"{BASE}/admin/realms/{REALM}/users?username={USER}&exact=true",
        token=token,
    )
    if not isinstance(users, list) or len(users) != 1:
        raise AssertionError("could not resolve authority evidence user")
    user_id = users[0].get("id")
    if not isinstance(user_id, str) or not user_id:
        raise AssertionError("authority evidence user lacks id")

    request(
        "POST",
        f"{BASE}/admin/realms/{REALM}/users/{user_id}/role-mappings/realm",
        token=token,
        body=[role],
    )
    request(
        "PUT",
        f"{BASE}/admin/realms/{REALM}/users/{user_id}/groups/{group_id}",
        token=token,
        body={},
    )
    return user_id


def _verify_id_token(raw: str) -> dict:
    issuer = f"{BASE}/realms/{REALM}"
    parts = raw.split(".")
    if len(parts) != 3:
        raise AssertionError("ID token is not compact JWS")
    header = json.loads(b64url_decode(parts[0]))
    claims = json.loads(b64url_decode(parts[1]))
    if header.get("alg") != "RS256":
        raise AssertionError("unexpected ID-token algorithm")
    kid = header.get("kid")
    if not isinstance(kid, str) or not kid or "jku" in header or "x5u" in header:
        raise AssertionError("untrusted ID-token key selection")
    _, jwks, _ = request("GET", f"{issuer}/protocol/openid-connect/certs")
    if not isinstance(jwks, dict):
        raise AssertionError("trusted ID-token JWKS malformed")
    keys = [
        key
        for key in jwks.get("keys", [])
        if isinstance(key, dict) and key.get("kid") == kid and key.get("kty") == "RSA"
    ]
    if len(keys) != 1:
        raise AssertionError("ID-token kid did not resolve uniquely")
    verify_rs256(raw, keys[0])
    if claims.get("iss") != issuer:
        raise AssertionError("ID-token issuer mismatch")
    aud = claims.get("aud")
    audiences = {aud} if isinstance(aud, str) else set(aud or [])
    if CLIENT_ID not in audiences:
        raise AssertionError("ID-token audience mismatch")
    return claims


def create_provider_session() -> dict:
    _, tokens, _ = request(
        "POST",
        f"{BASE}/realms/{REALM}/protocol/openid-connect/token",
        form={
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "username": USER,
            "password": PASSWORD,
            "scope": "openid",
        },
    )
    if not isinstance(tokens, dict) or not isinstance(tokens.get("id_token"), str):
        raise AssertionError("direct-grant evidence session did not return ID token")
    claims = _verify_id_token(tokens["id_token"])
    if not isinstance(claims.get("sub"), str) or not claims["sub"]:
        raise AssertionError("ID token lacks provider subject")
    sid = claims.get("sid", claims.get("session_state"))
    if not isinstance(sid, str) or not sid:
        raise AssertionError("ID token lacks provider session identity")
    claims["_d3_sid"] = sid
    return claims


def trigger_admin_logout(user_id: str) -> str:
    token = admin_token()
    request(
        "POST",
        f"{BASE}/admin/realms/{REALM}/users/{user_id}/logout",
        token=token,
    )
    try:
        return CaptureHandler.captured.get(timeout=20)
    except queue.Empty as exc:
        raise AssertionError("Keycloak did not deliver back-channel logout token") from exc


def assert_provider_claims_non_authority(
    *,
    claims: dict,
    external_sub: str,
    authorization: PlatformAuthorization,
) -> None:
    realm_access = claims.get("realm_access")
    roles = realm_access.get("roles", []) if isinstance(realm_access, dict) else []
    if "tenant-admin" not in roles:
        raise AssertionError(f"signed Keycloak role evidence missing: {roles!r}")
    groups = claims.get("groups")
    if not isinstance(groups, list) or not any("tenant-admin-group" in str(value) for value in groups):
        raise AssertionError(f"signed Keycloak group evidence missing: {groups!r}")
    if claims.get("organization") != "tenant-admin-org":
        raise AssertionError("signed Keycloak organization-like claim evidence missing")

    if external_sub == PLATFORM_PRINCIPAL:
        raise AssertionError("provider subject collided with platform principal")
    if authorization.permits(PLATFORM_PRINCIPAL, "tenant-red"):
        raise AssertionError("provider-native role/group/organization escalated platform authorization")
    authorization.allow(OTHER_PRINCIPAL, "tenant-red")
    if authorization.permits(PLATFORM_PRINCIPAL, "tenant-red"):
        raise AssertionError("unrelated platform membership leaked to mapped principal")


def _expect_denied(callable_, label: str) -> None:
    try:
        callable_()
    except AdmissionDenied:
        return
    raise AssertionError(f"{label}: expected AdmissionDenied")


def main() -> int:
    wait_ready()
    user_id = configure_realm()
    issuer = f"{BASE}/realms/{REALM}"
    verifier = LogoutVerifier()
    mappings = ProviderMappingAuthority()
    fences = SessionFenceAuthority()
    authorization = PlatformAuthorization()

    server = ThreadingHTTPServer(("0.0.0.0", LOGOUT_PORT), CaptureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with tempfile.TemporaryDirectory(prefix="d3-keycloak-replay-") as td:
            replay_path = Path(td) / "logout-replay.sqlite3"
            replay = DurableReplayLedger(replay_path)
            authority = LogoutAuthority(
                verifier=verifier,
                replay=replay,
                mappings=mappings,
                fences=fences,
            )

            first_claims = create_provider_session()
            first_sub = first_claims["sub"]
            first_sid = first_claims["_d3_sid"]
            local_first = fences.create(
                session_id="session-platform-001",
                principal_id=PLATFORM_PRINCIPAL,
            )
            mappings.bind(
                issuer=issuer,
                client_id=CLIENT_ID,
                sid=first_sid,
                sub=first_sub,
                principal_id=PLATFORM_PRINCIPAL,
                local_session_id=local_first.session_id,
            )
            assert_provider_claims_non_authority(
                claims=first_claims,
                external_sub=first_sub,
                authorization=authorization,
            )

            mappings.unlink_subject(issuer=issuer, sub=first_sub)
            mappings.relink_subject(
                issuer=issuer,
                sub=first_sub,
                principal_id=RELINKED_PRINCIPAL,
            )

            first_logout = trigger_admin_logout(user_id)
            before_lookup = mappings.lookup_count
            _expect_denied(
                lambda: verifier.verify(_signature_tamper(first_logout)),
                "tampered_logout_signature",
            )
            _expect_denied(
                lambda: verifier.verify(_alg_none_variant(first_logout)),
                "alg_none_logout",
            )
            if mappings.lookup_count != before_lookup:
                raise AssertionError("invalid logout token reached provider identity mapping")

            authenticated_first = verifier.verify(first_logout)
            if authenticated_first.sid != first_sid or authenticated_first.sub != first_sub:
                raise AssertionError(
                    "Keycloak logout sid/sub did not preserve authenticated provider session binding"
                )
            result = authority.handle(first_logout)
            if result != "sid_retired" or fences.current(local_first):
                raise AssertionError("valid Keycloak sid logout failed to retire exact platform session")

            replay = DurableReplayLedger(replay_path)
            authority = LogoutAuthority(
                verifier=verifier,
                replay=replay,
                mappings=mappings,
                fences=fences,
            )
            lookup_before_replay = mappings.lookup_count
            _expect_denied(lambda: authority.handle(first_logout), "completed_logout_replay")
            if mappings.lookup_count != lookup_before_replay:
                raise AssertionError("completed replay reached mapping/effect authority after reopen")

            other_scope_lease = replay.claim(
                issuer=f"{issuer}/other-trusted-scope",
                client_id=f"{CLIENT_ID}-other",
                jti=authenticated_first.jti,
                fingerprint=authenticated_first.raw_fingerprint,
            )
            replay.complete(other_scope_lease)

            second_claims = create_provider_session()
            second_sid = second_claims["_d3_sid"]
            second_sub = second_claims["sub"]
            local_second = fences.create(
                session_id="session-platform-002",
                principal_id=PLATFORM_PRINCIPAL,
            )
            mappings.bind(
                issuer=issuer,
                client_id=CLIENT_ID,
                sid=second_sid,
                sub=second_sub,
                principal_id=PLATFORM_PRINCIPAL,
                local_session_id=local_second.session_id,
            )
            mappings.available = False
            second_logout = trigger_admin_logout(user_id)
            authenticated_second = verifier.verify(second_logout)
            try:
                authority.handle(second_logout)
            except UncertainAuthority:
                pass
            else:
                raise AssertionError("mapping uncertainty was acknowledged as confirmed absence")
            if replay.status(
                issuer=issuer,
                client_id=CLIENT_ID,
                jti=authenticated_second.jti,
            ) != "retryable":
                raise AssertionError("mapping uncertainty did not leave durable retryable replay state")
            if not fences.current(local_second):
                raise AssertionError("uncertain mapping caused an unproven revocation effect")

            mappings.available = True
            if authority.handle(second_logout) != "sid_retired":
                raise AssertionError("retry after mapping recovery did not complete exact sid retirement")
            if fences.current(local_second):
                raise AssertionError("recovered mapping failed to retire mapped session")

            third_claims = create_provider_session()
            third_logout = trigger_admin_logout(user_id)
            authenticated_third = verifier.verify(third_logout)
            before_absent_mutations = (
                fences.sid_retire_mutations,
                fences.generation_mutations,
            )
            if authority.handle(third_logout) != "confirmed_absent":
                raise AssertionError("confirmed no-active-mapping did not resolve idempotently")
            after_absent_mutations = (
                fences.sid_retire_mutations,
                fences.generation_mutations,
            )
            if before_absent_mutations != after_absent_mutations:
                raise AssertionError("confirmed absence guessed a revocation target")
            if authenticated_third.sub != third_claims["sub"]:
                raise AssertionError("third provider session subject unexpectedly drifted")

            mappings.subject_current[(issuer, first_sub)] = PLATFORM_PRINCIPAL
            many_sessions = [
                fences.create(
                    session_id=f"bulk-session-{index:04d}",
                    principal_id=PLATFORM_PRINCIPAL,
                )
                for index in range(512)
            ]
            generation_mutations_before = fences.generation_mutations
            normalized_sub_only = AuthenticatedLogout(
                issuer=issuer,
                client_id=CLIENT_ID,
                jti="normalized-sub-only-proof",
                issued_at=int(time.time()),
                expires_at=int(time.time()) + 60,
                sid=None,
                sub=first_sub,
                raw_fingerprint="0" * 64,
            )
            resolved_principal = authority.apply_authenticated_sub_only_for_fence_proof(
                normalized_sub_only
            )
            if resolved_principal != PLATFORM_PRINCIPAL:
                raise AssertionError("sub-only mapping resolved wrong platform principal")
            if fences.generation_mutations != generation_mutations_before + 1:
                raise AssertionError("principal-wide logout used more than one generation mutation")
            if any(fences.current(session) for session in many_sessions):
                raise AssertionError("principal generation fence left stale sessions authorizing")

            current = LocalCurrentness(True, True, True, True)
            if not existing_session_admitted(local=current):
                raise AssertionError("fully current local authority was rejected during IdP outage model")
            if new_login_admitted(idp_available=False):
                raise AssertionError("new login admitted while IdP unavailable")
            if step_up_admitted(idp_available=False, local=current):
                raise AssertionError("step-up admitted while IdP unavailable")
            for stale in (
                LocalCurrentness(False, True, True, True),
                LocalCurrentness(True, False, True, True),
                LocalCurrentness(True, True, False, True),
                LocalCurrentness(True, True, True, False),
            ):
                if existing_session_admitted(local=stale):
                    raise AssertionError("stale JLMirror local authority was frozen as current")

            provider_principal = Principal(
                principal_id=PLATFORM_PRINCIPAL,
                kind=PrincipalKind.HUMAN_BROWSER_SESSION,
                credential_generation="session-provider-mapped",
            )
            if provider_principal.principal_id in {first_sub, first_sid}:
                raise AssertionError("provider identity was laundered into platform identity")

            print(
                "d3_keycloak_authority_effects=PASS "
                "signature_before_mapping=true durable_replay=true retryable_uncertainty=true "
                "sid_sub_scoped_mapping=true unlink_relink_sid_history=true "
                "principal_wide_generation_fence=true bulk_sessions=512 "
                "idp_outage_currentness_join=true provider_roles_groups_organizations_non_authority=true"
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
