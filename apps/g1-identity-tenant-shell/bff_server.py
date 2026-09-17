from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import ssl
from threading import Lock
from urllib.parse import parse_qs, quote, unquote, urlparse

from jlmirror_authority.browser import VerifiedOidcIdentity
from jlmirror_authority.model import AdmissionDenied
from jlmirror_authority.session import BrowserSessionRecord
from jlmirror_g1.csrf import CsrfKeyRing
from jlmirror_g1.shell import IdentityTenantShell, TenantShellAdmission


ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
SESSION_COOKIE = "__Host-jlmirror_session"
CSRF_COOKIE = "__Host-jlmirror_csrf"
BINDING_COOKIE = "__Host-jlmirror_login"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Transactions:
    def __init__(self) -> None:
        self._values = {}
        self._lock = Lock()

    def create(self, transaction) -> bool:
        with self._lock:
            if transaction.transaction_id in self._values:
                return False
            self._values[transaction.transaction_id] = transaction
            return True

    def consume(self, transaction_id: str):
        with self._lock:
            return self._values.pop(transaction_id, None)


class FixtureOidc:
    def __init__(self) -> None:
        self._nonce_by_code: dict[str, str] = {}
        self._lock = Lock()

    def register(self, *, authorization_code: str, nonce: str) -> None:
        with self._lock:
            self._nonce_by_code[authorization_code] = nonce

    def exchange_and_verify(
        self,
        *,
        authorization_code: str,
        pkce_verifier: str,
        expected_issuer: str,
        expected_client_id: str,
        expected_redirect_uri: str,
    ) -> VerifiedOidcIdentity:
        del pkce_verifier, expected_redirect_uri
        with self._lock:
            nonce = self._nonce_by_code.pop(authorization_code, None)
        if nonce is None:
            raise AdmissionDenied("fixture authorization code is absent or already consumed")
        now = utcnow()
        return VerifiedOidcIdentity(
            principal_id="principal-a",
            issuer=expected_issuer,
            client_id=expected_client_id,
            nonce=nonce,
            authenticated_at=now - timedelta(seconds=1),
            token_expires_at=now + timedelta(minutes=10),
            acr="urn:jlmirror:loa:1",
            amr=frozenset({"pwd"}),
            policy_version="fixture-auth-strength-v1",
        )


class Sessions:
    def __init__(self) -> None:
        self._values: dict[str, BrowserSessionRecord] = {}
        self._lock = Lock()

    def create(self, record: BrowserSessionRecord) -> bool:
        with self._lock:
            if record.handle_digest in self._values:
                return False
            self._values[record.handle_digest] = record
            return True

    def resolve(self, handle_digest: str):
        with self._lock:
            return self._values.get(handle_digest)

    def rotate(
        self,
        *,
        predecessor_handle_digest: str,
        expected_predecessor_generation: str,
        successor: BrowserSessionRecord,
    ) -> bool:
        with self._lock:
            current = self._values.get(predecessor_handle_digest)
            if (
                current is None
                or current.retired
                or current.session_generation != expected_predecessor_generation
            ):
                return False
            self._values[predecessor_handle_digest] = replace(current, retired=True)
            self._values[successor.handle_digest] = successor
            return True

    def retire(self, *, handle_digest: str, expected_generation: str) -> bool:
        with self._lock:
            current = self._values.get(handle_digest)
            if current is None or current.retired or current.session_generation != expected_generation:
                return False
            self._values[handle_digest] = replace(current, retired=True)
            return True


class FixtureTenantAdmission:
    def __init__(self) -> None:
        self._mode_by_principal: dict[str, str] = {}
        self._lock = Lock()

    def set_mode(self, *, principal_id: str, mode: str) -> None:
        if mode not in {"allowed", "revoked", "forbidden"}:
            raise ValueError("unsupported fixture authority mode")
        with self._lock:
            self._mode_by_principal[principal_id] = mode

    def mode_for(self, principal_id: str) -> str:
        with self._lock:
            return self._mode_by_principal.get(principal_id, "allowed")

    def require_current(self, *, principal, tenant_id: str, now: datetime, authentication_strength) -> TenantShellAdmission:
        if authentication_strength is None or authentication_strength.is_current(now) is not True:
            raise AdmissionDenied("current authentication strength is unavailable")
        mode = self.mode_for(principal.principal_id)
        if mode == "revoked":
            raise AdmissionDenied("current authority is revoked")
        if mode == "forbidden" or tenant_id != "tenant-a":
            raise AdmissionDenied("current tenant authority denied")
        return TenantShellAdmission(
            tenant_id="tenant-a",
            admission_revision="fixture-current-admission-r1",
        )


class DisabledOidc:
    def exchange_and_verify(self, **kwargs):
        del kwargs
        raise AdmissionDenied("OIDC adapter is not configured")


class DisabledTenantAdmission:
    def require_current(self, **kwargs):
        del kwargs
        raise AdmissionDenied("current tenant authority adapter is not configured")


class AppState:
    def __init__(self, *, fixture_enabled: bool) -> None:
        self.transactions = Transactions()
        self.sessions = Sessions()
        self.oidc = FixtureOidc() if fixture_enabled else DisabledOidc()
        self.tenant_admission = (
            FixtureTenantAdmission() if fixture_enabled else DisabledTenantAdmission()
        )
        self.csrf = CsrfKeyRing(
            current_version="csrf-v2",
            previous_version="csrf-v1",
            keys={
                "csrf-v2": b"2" * 32,
                "csrf-v1": b"1" * 32,
            },
        )
        self.lineage_by_session_digest: dict[str, str] = {}
        self.lock = Lock()
        self.shell = IdentityTenantShell(
            transactions=self.transactions,
            oidc=self.oidc,
            sessions=self.sessions,
            tenant_admission=self.tenant_admission,
            issuer="https://identity.example.test/realms/jlmirror",
            client_id="jlmirror-bff",
            redirect_uri="https://app.example.test/auth/callback",
            authorization_transaction_lifetime=timedelta(minutes=5),
            session_lifetime=timedelta(hours=1),
        )


class G1Server(ThreadingHTTPServer):
    def __init__(self, server_address, handler, *, fixture_enabled: bool):
        super().__init__(server_address, handler)
        self.fixture_enabled = fixture_enabled
        self.state = AppState(fixture_enabled=fixture_enabled)


class Handler(BaseHTTPRequestHandler):
    server: G1Server

    def log_message(self, format: str, *args) -> None:
        if getattr(self.server, "fixture_enabled", False):
            return
        super().log_message(format, *args)

    def _origin(self) -> str:
        host, port = self.server.server_address[:2]
        display_host = "127.0.0.1" if host in {"0.0.0.0", ""} else host
        return f"https://{display_host}:{port}"

    def _send_json(self, status: int, body: dict) -> None:
        payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(payload)

    def _send_static(self, path: Path, content_type: str) -> None:
        payload = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; connect-src 'self'; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(payload)

    def _cookie_values(self, name: str) -> list[str]:
        values: list[str] = []
        for header in self.headers.get_all("Cookie", []):
            for part in header.split(";"):
                item = part.strip()
                if "=" not in item:
                    continue
                key, value = item.split("=", 1)
                if key == name:
                    values.append(unquote(value))
        return values

    def _single_cookie(self, name: str) -> str | None:
        values = self._cookie_values(name)
        return values[0] if len(values) == 1 else None

    def _set_cookie(
        self,
        name: str,
        value: str,
        *,
        http_only: bool,
        max_age: int,
        same_site: str = "Strict",
    ) -> None:
        attributes = [
            f"{name}={quote(value, safe='._~-')}",
            "Path=/",
            "Secure",
            f"SameSite={same_site}",
            f"Max-Age={max_age}",
        ]
        if http_only:
            attributes.append("HttpOnly")
        self.send_header("Set-Cookie", "; ".join(attributes))

    def _clear_cookie(self, name: str, *, http_only: bool) -> None:
        attributes = [
            f"{name}=",
            "Path=/",
            "Secure",
            "SameSite=Strict",
            "Max-Age=0",
        ]
        if http_only:
            attributes.append("HttpOnly")
        self.send_header("Set-Cookie", "; ".join(attributes))

    def _redirect(self, location: str, cookies: list[tuple[str, str, bool, int, str]] = []) -> None:
        self.send_response(HTTPStatus.FOUND)
        for name, value, http_only, max_age, same_site in cookies:
            self._set_cookie(
                name,
                value,
                http_only=http_only,
                max_age=max_age,
                same_site=same_site,
            )
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        if parsed.path in {"/", "/index.html"}:
            self._send_static(FRONTEND / "index.html", "text/html; charset=utf-8")
            return
        if parsed.path == "/app.mjs":
            self._send_static(FRONTEND / "app.mjs", "text/javascript; charset=utf-8")
            return
        if parsed.path == "/shell-state.mjs":
            self._send_static(FRONTEND / "shell-state.mjs", "text/javascript; charset=utf-8")
            return
        if parsed.path.startswith("/bff/v1/tenants/") and parsed.path.endswith("/shell"):
            self._handle_shell(parsed.path)
            return
        if parsed.path == "/__fixture__/login/start":
            self._fixture_login_start(parse_qs(parsed.query))
            return
        if parsed.path == "/__fixture__/idp/callback":
            self._fixture_login_callback(parse_qs(parsed.query))
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"state": "unavailable"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/bff/v1/logout":
            self._handle_logout()
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"state": "unavailable"})

    def _fixture_login_start(self, query: dict[str, list[str]]) -> None:
        if not self.server.fixture_enabled:
            self._send_json(HTTPStatus.NOT_FOUND, {"state": "unavailable"})
            return
        target_tenant = query.get("target_tenant", ["tenant-a"])[0]
        scenario = query.get("scenario", ["allowed"])[0]
        mode = query.get("mode", ["allowed"])[0]
        if scenario not in {"allowed", "cross-tenant", "revoked", "csrf-reject", "logout"}:
            self._send_json(HTTPStatus.BAD_REQUEST, {"state": "unavailable"})
            return
        if mode not in {"allowed", "revoked", "forbidden"}:
            self._send_json(HTTPStatus.BAD_REQUEST, {"state": "unavailable"})
            return
        browser_binding = secrets.token_urlsafe(32)
        start = self.server.state.shell.begin_login(browser_binding=browser_binding, now=utcnow())
        authorization_code = f"fixture:{start.transaction_id}"
        self.server.state.oidc.register(
            authorization_code=authorization_code,
            nonce=start.nonce,
        )
        location = (
            "/__fixture__/idp/callback?"
            f"transaction_id={quote(start.transaction_id)}&"
            f"state={quote(start.state)}&"
            f"authorization_code={quote(authorization_code)}&"
            f"target_tenant={quote(target_tenant)}&"
            f"scenario={quote(scenario)}&"
            f"mode={quote(mode)}"
        )
        self._redirect(
            location,
            cookies=[(BINDING_COOKIE, browser_binding, True, 300, "Lax")],
        )

    def _fixture_login_callback(self, query: dict[str, list[str]]) -> None:
        if not self.server.fixture_enabled:
            self._send_json(HTTPStatus.NOT_FOUND, {"state": "unavailable"})
            return
        binding = self._single_cookie(BINDING_COOKIE)
        required = ("transaction_id", "state", "authorization_code", "target_tenant", "scenario", "mode")
        if binding is None or any(len(query.get(name, [])) != 1 for name in required):
            self._send_json(HTTPStatus.BAD_REQUEST, {"state": "unavailable"})
            return
        try:
            handle = self.server.state.shell.finish_login(
                transaction_id=query["transaction_id"][0],
                browser_binding=binding,
                returned_state=query["state"][0],
                authorization_code=query["authorization_code"][0],
                now=utcnow(),
            )
        except AdmissionDenied:
            self._send_json(HTTPStatus.UNAUTHORIZED, {"state": "unauthenticated"})
            return

        self.server.state.tenant_admission.set_mode(
            principal_id="principal-a",
            mode=query["mode"][0],
        )
        lineage = secrets.token_urlsafe(24)
        with self.server.state.lock:
            self.server.state.lineage_by_session_digest[handle.digest] = lineage
        csrf = self.server.state.csrf.issue(session_lineage_id=lineage)
        target = (
            f"/?tenant={quote(query['target_tenant'][0])}"
            f"&scenario={quote(query['scenario'][0])}"
        )
        self._redirect(
            target,
            cookies=[
                (SESSION_COOKIE, handle.value, True, 3600, "Strict"),
                (CSRF_COOKIE, csrf, False, 3600, "Strict"),
                (BINDING_COOKIE, "", True, 0, "Lax"),
            ],
        )

    def _handle_shell(self, path: str) -> None:
        parts = path.split("/")
        if len(parts) != 6:
            self._send_json(HTTPStatus.NOT_FOUND, {"state": "unavailable"})
            return
        tenant_id = unquote(parts[4])
        session = self._single_cookie(SESSION_COOKIE)
        if session is None:
            self._send_json(HTTPStatus.UNAUTHORIZED, {"state": "unauthenticated"})
            return
        try:
            view = self.server.state.shell.open_shell(
                session_capability=session,
                tenant_id=tenant_id,
                now=utcnow(),
            )
        except AdmissionDenied:
            from jlmirror_authority.session import BrowserSessionHandle

            try:
                handle = BrowserSessionHandle(session)
                record = self.server.state.sessions.resolve(handle.digest)
                admission = self.server.state.tenant_admission
                mode = (
                    admission.mode_for(record.principal.principal_id)
                    if self.server.fixture_enabled
                    and isinstance(admission, FixtureTenantAdmission)
                    and record is not None
                    else "forbidden"
                )
            except Exception:
                mode = "forbidden"
            state = "revoked" if mode == "revoked" else "forbidden"
            self._send_json(HTTPStatus.FORBIDDEN, {"state": state})
            return
        self._send_json(
            HTTPStatus.OK,
            {
                "state": view.state,
                "tenant_id": view.tenant_id,
                "principal_id": view.principal_id,
                "admission_revision": view.admission_revision,
            },
        )

    def _handle_logout(self) -> None:
        origin_values = self.headers.get_all("Origin", [])
        csrf_headers = self.headers.get_all("X-JLMirror-CSRF", [])
        session = self._single_cookie(SESSION_COOKIE)
        csrf_cookie = self._single_cookie(CSRF_COOKIE)
        if (
            origin_values != [self._origin()]
            or len(csrf_headers) != 1
            or session is None
            or csrf_cookie is None
        ):
            self._send_json(HTTPStatus.FORBIDDEN, {"state": "forbidden"})
            return

        from jlmirror_authority.session import BrowserSessionHandle

        try:
            handle = BrowserSessionHandle(session)
            with self.server.state.lock:
                lineage = self.server.state.lineage_by_session_digest.get(handle.digest)
            if lineage is None or not self.server.state.csrf.validate(
                token=csrf_headers[0],
                session_lineage_id=lineage,
            ):
                raise AdmissionDenied("CSRF binding is not current")
            if not secrets.compare_digest(csrf_cookie, csrf_headers[0]):
                raise AdmissionDenied("CSRF cookie/header mismatch")
            self.server.state.shell.logout(session_capability=session, now=utcnow())
        except (AdmissionDenied, ValueError):
            self._send_json(HTTPStatus.FORBIDDEN, {"state": "forbidden"})
            return

        with self.server.state.lock:
            self.server.state.lineage_by_session_digest.pop(handle.digest, None)
        self.send_response(HTTPStatus.NO_CONTENT)
        self._clear_cookie(SESSION_COOKIE, http_only=True)
        self._clear_cookie(CSRF_COOKIE, http_only=False)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8444)
    parser.add_argument("--certfile", required=True)
    parser.add_argument("--keyfile", required=True)
    parser.add_argument("--fixture", action="store_true")
    args = parser.parse_args()

    server = G1Server((args.host, args.port), Handler, fixture_enabled=args.fixture)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(args.certfile, args.keyfile)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
