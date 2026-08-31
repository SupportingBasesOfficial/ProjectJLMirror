from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from html import unescape
from html.parser import HTMLParser
import http.cookiejar
import json
import os
from pathlib import Path
import struct
import sys
import time
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, HTTPCookieProcessor, Request, build_opener

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jlmirror_authority.browser import (  # noqa: E402
    VerifiedOidcIdentity,
    begin_browser_auth,
    complete_browser_auth,
    require_authentication_strength,
)
from jlmirror_authority.model import AdmissionDenied  # noqa: E402
from jlmirror_authority.session import (  # noqa: E402
    BrowserSessionRecord,
    issue_browser_session,
    resolve_browser_session,
    rotate_browser_session,
)

from keycloak_backchannel_probe import (  # noqa: E402
    admin_token,
    b64url_decode,
    request,
    verify_rs256,
    wait_ready,
)

BASE = os.environ.get("KEYCLOAK_BASE_URL", "https://127.0.0.1:8443").rstrip("/")
REALM = "d3mfa"
CLIENT_ID = "d3-mfa-bff"
CLIENT_SECRET = "d3-mfa-client-secret"
REDIRECT_URI = "https://bff.d3.invalid/mfa-callback"
MFA_USER = "mfa-alice"
BASIC_USER = "basic-bob"
PASSWORD = "d3-mfa-password"
MFA_PRINCIPAL = "principal-d3-mfa"
BASIC_PRINCIPAL = "principal-d3-basic"

AUTHN_REF_VALUE = "default.reference.value"
AUTHN_REF_MAX_AGE = "default.reference.maxAge"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.forms: list[dict[str, object]] = []
        self._form: dict[str, object] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)
        if tag.lower() == "form":
            self._form = {
                "id": values.get("id"),
                "action": unescape(values.get("action", "")),
                "inputs": {},
            }
            self.forms.append(self._form)
            return
        if tag.lower() == "input" and self._form is not None:
            name = values.get("name")
            if isinstance(name, str) and name:
                inputs = self._form["inputs"]
                assert isinstance(inputs, dict)
                inputs[name] = unescape(values.get("value", ""))

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "form":
            self._form = None

    def by_id(self, form_id: str) -> dict[str, object]:
        matches = [form for form in self.forms if form.get("id") == form_id]
        if len(matches) != 1:
            raise AssertionError(f"expected exactly one form {form_id!r}, got {len(matches)}")
        return matches[0]


def _open_no_redirect(opener, request: Request):
    try:
        return opener.open(request, timeout=10)
    except HTTPError as exc:
        if exc.code in {302, 303}:
            return exc
        raise


def _post_form(opener, action: str, payload: dict[str, str]):
    return _open_no_redirect(
        opener,
        Request(
            action,
            data=urlencode(payload).encode(),
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        ),
    )


def _response_status(response) -> int:
    return int(getattr(response, "status", getattr(response, "code", 0)))


def _parse_callback_location(location: str) -> tuple[str, str] | None:
    parsed = urlparse(location)
    expected = urlparse(REDIRECT_URI)
    if (parsed.scheme, parsed.netloc, parsed.path) != (
        expected.scheme,
        expected.netloc,
        expected.path,
    ):
        return None
    if parsed.fragment:
        raise AssertionError("BFF callback must not carry a URI fragment")
    values = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
    codes = values.get("code", [])
    states = values.get("state", [])
    if len(codes) != 1 or len(states) != 1 or not codes[0] or not states[0]:
        raise AssertionError(f"callback lacked exactly one code/state: {values!r}")
    return codes[0], states[0]


def _same_keycloak_origin(url: str) -> bool:
    candidate = urlparse(url)
    trusted = urlparse(BASE)
    return (
        candidate.scheme == trusted.scheme
        and candidate.netloc == trusted.netloc
        and candidate.scheme == "https"
    )


def _navigate_bounded(
    opener,
    response,
    *,
    expected_page_form: str | None,
    max_internal_redirects: int = 8,
) -> tuple[str, str] | tuple[str, str, dict[str, object]]:
    """Follow only same-origin Keycloak redirects or terminate at the exact BFF callback."""

    current = response
    for hop in range(max_internal_redirects + 1):
        status = _response_status(current)
        current_url = current.geturl()
        if status in {302, 303}:
            location = current.headers.get("Location")
            if not isinstance(location, str) or not location:
                raise AssertionError("authentication redirect lacked Location")
            absolute = urljoin(current_url, unescape(location))
            callback = _parse_callback_location(absolute)
            if callback is not None:
                try:
                    current.close()
                finally:
                    return callback

            if not _same_keycloak_origin(absolute):
                raise AssertionError(
                    f"authentication redirect escaped trusted Keycloak origin: {absolute!r}"
                )
            if hop >= max_internal_redirects:
                raise AssertionError("authentication exceeded bounded internal redirect budget")
            try:
                current.close()
            finally:
                current = _open_no_redirect(
                    opener,
                    Request(absolute, method="GET"),
                )
            continue

        if status != 200:
            body = current.read().decode("utf-8", errors="replace")
            raise AssertionError(
                f"authentication navigation returned unexpected status={status} "
                f"url={current_url!r} body_prefix={body[:240]!r}"
            )

        body = current.read().decode("utf-8", errors="replace")
        final_url = current.geturl()
        current.close()
        if not _same_keycloak_origin(final_url):
            raise AssertionError(
                f"authentication page escaped trusted Keycloak origin: {final_url!r}"
            )
        if expected_page_form is None:
            raise AssertionError(
                f"authentication stopped on an unexpected Keycloak page: {final_url!r}"
            )
        parser = FormParser()
        parser.feed(body)
        form = parser.by_id(expected_page_form)
        return body, final_url, form

    raise AssertionError("unreachable bounded-navigation state")


def _expect_callback_navigation(opener, response) -> tuple[str, str]:
    result = _navigate_bounded(opener, response, expected_page_form=None)
    if len(result) != 2:
        raise AssertionError("authentication stopped before reaching the BFF callback")
    return result


def _expect_keycloak_form(opener, response, form_id: str) -> tuple[str, dict[str, object]]:
    result = _navigate_bounded(opener, response, expected_page_form=form_id)
    if len(result) != 3:
        raise AssertionError(f"authentication reached BFF callback before required form {form_id!r}")
    _, final_url, form = result
    return final_url, form


def _totp(secret: str, *, now: int | None = None) -> str:
    compact = "".join(secret.split()).upper()
    padding = "=" * ((8 - len(compact) % 8) % 8)
    key = base64.b32decode(compact + padding, casefold=True)
    timestamp = int(time.time() if now is None else now)
    counter = timestamp // 30
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF) % 1_000_000
    return f"{code:06d}"


def _stable_totp(secret: str) -> str:
    remainder = 30 - (int(time.time()) % 30)
    if remainder <= 3:
        time.sleep(remainder + 1)
    return _totp(secret)


def _configure_authn_reference(token: str, provider_id: str, value: str) -> None:
    _, executions, _ = request(
        "GET",
        f"{BASE}/admin/realms/{REALM}/authentication/flows/browser/executions",
        token=token,
    )
    if not isinstance(executions, list):
        raise AssertionError("browser execution list is malformed")
    matches = [
        item
        for item in executions
        if isinstance(item, dict) and item.get("providerId") == provider_id
    ]
    if len(matches) != 1:
        raise AssertionError(
            f"expected one {provider_id!r} browser execution, found {len(matches)}"
        )
    execution = matches[0]
    execution_id = execution.get("id")
    if not isinstance(execution_id, str) or not execution_id:
        raise AssertionError("browser execution lacks id")
    config_id = execution.get("authenticationConfig")
    config_values = {
        AUTHN_REF_VALUE: value,
        AUTHN_REF_MAX_AGE: "300",
    }
    if isinstance(config_id, str) and config_id:
        _, current, _ = request(
            "GET",
            f"{BASE}/admin/realms/{REALM}/authentication/config/{config_id}",
            token=token,
        )
        if not isinstance(current, dict):
            raise AssertionError("authenticator config is malformed")
        existing = current.get("config")
        merged = dict(existing) if isinstance(existing, dict) else {}
        merged.update(config_values)
        body = dict(current)
        body["config"] = merged
        request(
            "PUT",
            f"{BASE}/admin/realms/{REALM}/authentication/config/{config_id}",
            token=token,
            body=body,
        )
    else:
        request(
            "POST",
            f"{BASE}/admin/realms/{REALM}/authentication/executions/{execution_id}/config",
            token=token,
            body={
                "alias": f"d3-amr-{value}",
                "config": config_values,
            },
        )


def configure_realm() -> tuple[str, str]:
    token = admin_token()
    request(
        "POST",
        f"{BASE}/admin/realms",
        token=token,
        body={
            "realm": REALM,
            "enabled": True,
            "otpPolicyType": "totp",
            "otpPolicyAlgorithm": "HmacSHA1",
            "otpPolicyDigits": 6,
            "otpPolicyPeriod": 30,
            "otpPolicyLookAheadWindow": 1,
        },
    )
    request(
        "POST",
        f"{BASE}/admin/realms/{REALM}/clients",
        token=token,
        body={
            "clientId": CLIENT_ID,
            "name": "D3 MFA evidence BFF",
            "enabled": True,
            "protocol": "openid-connect",
            "publicClient": False,
            "secret": CLIENT_SECRET,
            "standardFlowEnabled": True,
            "directAccessGrantsEnabled": False,
            "serviceAccountsEnabled": False,
            "redirectUris": [REDIRECT_URI],
        },
    )
    _, clients, _ = request(
        "GET",
        f"{BASE}/admin/realms/{REALM}/clients?clientId={CLIENT_ID}",
        token=token,
    )
    if not isinstance(clients, list) or len(clients) != 1:
        raise AssertionError("could not resolve exactly one MFA evidence client")
    client_uuid = clients[0].get("id")
    if not isinstance(client_uuid, str) or not client_uuid:
        raise AssertionError("MFA evidence client lacks internal id")

    for mapper in ("oidc-amr-mapper", "oidc-acr-mapper"):
        request(
            "POST",
            f"{BASE}/admin/realms/{REALM}/clients/{client_uuid}/protocol-mappers/models",
            token=token,
            body={
                "name": f"d3-{mapper}",
                "protocol": "openid-connect",
                "protocolMapper": mapper,
                "consentRequired": False,
                "config": {
                    "id.token.claim": "true",
                    "access.token.claim": "true",
                },
            },
        )

    _configure_authn_reference(token, "auth-username-password-form", "password")
    _configure_authn_reference(token, "auth-otp-form", "totp")

    users = (
        (MFA_USER, ["CONFIGURE_TOTP"]),
        (BASIC_USER, []),
    )
    resolved: dict[str, str] = {}
    for username, required_actions in users:
        request(
            "POST",
            f"{BASE}/admin/realms/{REALM}/users",
            token=token,
            body={
                "username": username,
                "enabled": True,
                "firstName": "D3",
                "lastName": "MFA Evidence",
                "email": f"{username}@example.invalid",
                "emailVerified": True,
                "requiredActions": required_actions,
                "credentials": [
                    {"type": "password", "value": PASSWORD, "temporary": False}
                ],
            },
        )
        _, matches, _ = request(
            "GET",
            f"{BASE}/admin/realms/{REALM}/users?username={username}&exact=true",
            token=token,
        )
        if not isinstance(matches, list) or len(matches) != 1:
            raise AssertionError(f"could not resolve exactly one user {username!r}")
        user_id = matches[0].get("id")
        if not isinstance(user_id, str) or not user_id:
            raise AssertionError(f"user {username!r} lacks internal id")
        resolved[username] = user_id
    return resolved[MFA_USER], resolved[BASIC_USER]


def _authorization_url(*, state: str, nonce: str, code_challenge: str) -> str:
    return (
        f"{BASE}/realms/{REALM}/protocol/openid-connect/auth?"
        + urlencode(
            {
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "response_type": "code",
                "scope": "openid",
                "state": state,
                "nonce": nonce,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
    )


def _open_login(opener, *, state: str, nonce: str, code_challenge: str) -> tuple[str, str]:
    response = _open_no_redirect(
        opener,
        Request(
            _authorization_url(
                state=state,
                nonce=nonce,
                code_challenge=code_challenge,
            ),
            method="GET",
        ),
    )
    final_url, form = _expect_keycloak_form(opener, response, "kc-form-login")
    action = form.get("action")
    if not isinstance(action, str) or not action:
        raise AssertionError("login form lacks action")
    return urljoin(final_url, action), final_url


def _submit_password(opener, action: str, username: str):
    return _post_form(
        opener,
        action,
        {
            "username": username,
            "password": PASSWORD,
            "credentialId": "",
        },
    )


def enroll_totp_and_get_code(
    *,
    state: str,
    nonce: str,
    code_challenge: str,
) -> tuple[str, str, str]:
    jar = http.cookiejar.CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar), NoRedirect())
    action, _ = _open_login(
        opener,
        state=state,
        nonce=nonce,
        code_challenge=code_challenge,
    )
    password_response = _submit_password(opener, action, MFA_USER)
    final_url, form = _expect_keycloak_form(
        opener,
        password_response,
        "kc-totp-settings-form",
    )
    form_action = form.get("action")
    inputs = form.get("inputs")
    if not isinstance(form_action, str) or not form_action or not isinstance(inputs, dict):
        raise AssertionError("TOTP enrollment form is malformed")
    secret = inputs.get("totpSecret")
    if not isinstance(secret, str) or not secret:
        raise AssertionError("TOTP enrollment did not expose bounded enrollment secret")
    payload = {
        "totp": _stable_totp(secret),
        "totpSecret": secret,
        "userLabel": "d3-evidence-device",
    }
    if isinstance(inputs.get("mode"), str) and inputs["mode"]:
        payload["mode"] = inputs["mode"]
    enrollment_response = _post_form(
        opener,
        urljoin(final_url, form_action),
        payload,
    )
    authorization_code, returned_state = _expect_callback_navigation(
        opener,
        enrollment_response,
    )
    return authorization_code, returned_state, secret


def login_with_totp(
    *,
    state: str,
    nonce: str,
    code_challenge: str,
    secret: str,
) -> tuple[str, str]:
    jar = http.cookiejar.CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar), NoRedirect())
    action, _ = _open_login(
        opener,
        state=state,
        nonce=nonce,
        code_challenge=code_challenge,
    )
    password_response = _submit_password(opener, action, MFA_USER)
    final_url, form = _expect_keycloak_form(
        opener,
        password_response,
        "kc-otp-login-form",
    )
    form_action = form.get("action")
    if not isinstance(form_action, str) or not form_action:
        raise AssertionError("OTP login form lacks action")
    otp_response = _post_form(
        opener,
        urljoin(final_url, form_action),
        {"otp": _stable_totp(secret)},
    )
    return _expect_callback_navigation(opener, otp_response)


def login_password_only(*, state: str, nonce: str, code_challenge: str) -> tuple[str, str]:
    jar = http.cookiejar.CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar), NoRedirect())
    action, _ = _open_login(
        opener,
        state=state,
        nonce=nonce,
        code_challenge=code_challenge,
    )
    response = _submit_password(opener, action, BASIC_USER)
    return _expect_callback_navigation(opener, response)


def _token_form(*, code: str, verifier: str) -> dict[str, str]:
    return {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier,
    }


class VerificationPort:
    def __init__(self, mapping: dict[tuple[str, str], str]) -> None:
        self._mapping = dict(mapping)

    def exchange_and_verify(
        self,
        *,
        authorization_code: str,
        pkce_verifier: str,
        expected_issuer: str,
        expected_client_id: str,
        expected_redirect_uri: str,
    ) -> VerifiedOidcIdentity:
        issuer = f"{BASE}/realms/{REALM}"
        if (
            expected_issuer != issuer
            or expected_client_id != CLIENT_ID
            or expected_redirect_uri != REDIRECT_URI
        ):
            raise AdmissionDenied("trusted OIDC registration binding mismatch")
        _, tokens, _ = request(
            "POST",
            f"{issuer}/protocol/openid-connect/token",
            form=_token_form(code=authorization_code, verifier=pkce_verifier),
        )
        if not isinstance(tokens, dict):
            raise AdmissionDenied("token endpoint returned malformed response")
        raw = tokens.get("id_token")
        if not isinstance(raw, str) or not raw:
            raise AdmissionDenied("token endpoint omitted ID token")
        parts = raw.split(".")
        if len(parts) != 3:
            raise AdmissionDenied("ID token is not compact JWS")
        try:
            header = json.loads(b64url_decode(parts[0]))
            claims = json.loads(b64url_decode(parts[1]))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AdmissionDenied("ID token is malformed") from exc
        if not isinstance(header, dict) or not isinstance(claims, dict):
            raise AdmissionDenied("ID-token objects are malformed")
        if header.get("alg") != "RS256":
            raise AdmissionDenied("ID token algorithm outside pinned profile")
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid or "jku" in header or "x5u" in header:
            raise AdmissionDenied("ID-token key selection outside trusted profile")
        _, jwks, _ = request("GET", f"{issuer}/protocol/openid-connect/certs")
        if not isinstance(jwks, dict):
            raise AdmissionDenied("trusted JWKS is malformed")
        keys = [
            key
            for key in jwks.get("keys", [])
            if isinstance(key, dict) and key.get("kid") == kid and key.get("kty") == "RSA"
        ]
        if len(keys) != 1:
            raise AdmissionDenied("ID-token kid did not resolve uniquely")
        try:
            verify_rs256(raw, keys[0])
        except AssertionError as exc:
            raise AdmissionDenied("ID-token signature verification failed") from exc

        if claims.get("iss") != issuer:
            raise AdmissionDenied("issuer mismatch")
        aud = claims.get("aud")
        audiences = {aud} if isinstance(aud, str) else set(aud or [])
        if CLIENT_ID not in audiences:
            raise AdmissionDenied("audience mismatch")
        now = int(time.time())
        for claim_name in ("iat", "exp"):
            if not isinstance(claims.get(claim_name), int):
                raise AdmissionDenied(f"{claim_name} missing/malformed")
        if claims["iat"] > now + 5 or claims["exp"] <= now:
            raise AdmissionDenied("token time evidence is not current")
        nonce = claims.get("nonce")
        sub = claims.get("sub")
        if not isinstance(nonce, str) or not nonce or not isinstance(sub, str) or not sub:
            raise AdmissionDenied("nonce/sub missing")
        principal_id = self._mapping.get((issuer, sub))
        if not isinstance(principal_id, str):
            raise AdmissionDenied("external subject mapping unavailable")
        if principal_id == sub:
            raise AdmissionDenied("provider subject became platform principal")
        acr = claims.get("acr")
        raw_amr = claims.get("amr")
        if not isinstance(acr, str) or not acr:
            raise AdmissionDenied("trusted ACR evidence missing")
        if not isinstance(raw_amr, list) or not all(
            isinstance(value, str) and value for value in raw_amr
        ):
            raise AdmissionDenied("trusted AMR evidence missing/malformed")
        auth_time = claims.get("auth_time", claims["iat"])
        if not isinstance(auth_time, int):
            raise AdmissionDenied("auth_time malformed")
        return VerifiedOidcIdentity(
            principal_id=principal_id,
            issuer=issuer,
            client_id=CLIENT_ID,
            nonce=nonce,
            authenticated_at=datetime.fromtimestamp(auth_time, tz=timezone.utc),
            token_expires_at=datetime.fromtimestamp(claims["exp"], tz=timezone.utc),
            acr=acr,
            amr=frozenset(raw_amr),
            policy_version="keycloak-26.7.2-mfa-evidence",
        )


class OneShotTransactionAuthority:
    def __init__(self, transaction) -> None:
        self._transaction = transaction

    def consume(self, transaction_id: str):
        current = self._transaction
        if current is None or current.transaction_id != transaction_id:
            return None
        self._transaction = None
        return current


class MemorySessionAuthority:
    def __init__(self) -> None:
        self.records: dict[str, BrowserSessionRecord] = {}

    def create(self, record: BrowserSessionRecord) -> bool:
        if record.handle_digest in self.records:
            return False
        self.records[record.handle_digest] = record
        return True

    def resolve(self, handle_digest: str) -> BrowserSessionRecord | None:
        return self.records.get(handle_digest)

    def rotate(
        self,
        *,
        predecessor_handle_digest: str,
        expected_predecessor_generation: str,
        successor: BrowserSessionRecord,
    ) -> bool:
        current = self.records.get(predecessor_handle_digest)
        if (
            current is None
            or current.retired
            or current.session_generation != expected_predecessor_generation
            or successor.handle_digest in self.records
        ):
            return False
        self.records[predecessor_handle_digest] = BrowserSessionRecord(
            handle_digest=current.handle_digest,
            principal=current.principal,
            session_generation=current.session_generation,
            created_at=current.created_at,
            expires_at=current.expires_at,
            retired=True,
            authentication_strength=current.authentication_strength,
        )
        self.records[successor.handle_digest] = successor
        return True

    def retire(self, *, handle_digest: str, expected_generation: str) -> bool:
        current = self.records.get(handle_digest)
        if current is None or current.retired or current.session_generation != expected_generation:
            return False
        self.records[handle_digest] = BrowserSessionRecord(
            handle_digest=current.handle_digest,
            principal=current.principal,
            session_generation=current.session_generation,
            created_at=current.created_at,
            expires_at=current.expires_at,
            retired=True,
            authentication_strength=current.authentication_strength,
        )
        return True


@dataclass(frozen=True)
class MfaPolicy:
    required_amr: frozenset[str] = frozenset({"password", "totp"})

    def permits(self, *, policy_id: str, evidence, now: datetime) -> bool:
        return (
            policy_id == "security.mfa.admin@1"
            and isinstance(evidence.acr, str)
            and bool(evidence.acr)
            and self.required_amr.issubset(evidence.amr)
            and evidence.is_current(now)
        )


def _initiation(session_binding: str):
    return begin_browser_auth(
        session_binding=session_binding,
        expected_issuer=f"{BASE}/realms/{REALM}",
        expected_client_id=CLIENT_ID,
        expected_redirect_uri=REDIRECT_URI,
        now=datetime.now(timezone.utc),
        lifetime=timedelta(minutes=5),
    )


def _complete(initiation, code: str, state: str, port: VerificationPort, binding: str):
    return complete_browser_auth(
        transaction_authority=OneShotTransactionAuthority(initiation.transaction),
        oidc_port=port,
        transaction_id=initiation.transaction.transaction_id,
        initiating_session_binding=binding,
        returned_state=state,
        authorization_code=code,
        now=datetime.now(timezone.utc),
    )


def _expect_denied(callable_, label: str) -> None:
    try:
        callable_()
    except AdmissionDenied:
        return
    raise AssertionError(f"{label}: expected fail-closed AdmissionDenied")


def main() -> int:
    wait_ready()
    mfa_user_id, basic_user_id = configure_realm()
    issuer = f"{BASE}/realms/{REALM}"
    port = VerificationPort(
        {
            (issuer, mfa_user_id): MFA_PRINCIPAL,
            (issuer, basic_user_id): BASIC_PRINCIPAL,
        }
    )

    enroll_init = _initiation("mfa-enroll-session")
    enroll_code, enroll_state, secret = enroll_totp_and_get_code(
        state=enroll_init.state,
        nonce=enroll_init.nonce,
        code_challenge=enroll_init.pkce_challenge,
    )
    enrolled_principal, enrolled_strength = _complete(
        enroll_init,
        enroll_code,
        enroll_state,
        port,
        "mfa-enroll-session",
    )
    if enrolled_principal.principal_id != MFA_PRINCIPAL:
        raise AssertionError("MFA enrollment mapped to wrong platform principal")
    if "password" not in enrolled_strength.amr:
        raise AssertionError(
            f"password authenticator reference missing during enrollment: {sorted(enrolled_strength.amr)!r}"
        )

    basic_init = _initiation("basic-session")
    basic_code, basic_state = login_password_only(
        state=basic_init.state,
        nonce=basic_init.nonce,
        code_challenge=basic_init.pkce_challenge,
    )
    basic_principal, basic_strength = _complete(
        basic_init,
        basic_code,
        basic_state,
        port,
        "basic-session",
    )
    if basic_strength.amr != frozenset({"password"}):
        raise AssertionError(
            f"password-only AMR set drifted: {sorted(basic_strength.amr)!r}"
        )

    mfa_init = _initiation("mfa-login-session")
    mfa_code, mfa_state = login_with_totp(
        state=mfa_init.state,
        nonce=mfa_init.nonce,
        code_challenge=mfa_init.pkce_challenge,
        secret=secret,
    )
    mfa_principal, mfa_strength = _complete(
        mfa_init,
        mfa_code,
        mfa_state,
        port,
        "mfa-login-session",
    )
    if mfa_strength.amr != frozenset({"password", "totp"}):
        raise AssertionError(
            f"MFA AMR set did not prove password+totp: {sorted(mfa_strength.amr)!r}"
        )
    if not isinstance(mfa_strength.acr, str) or not mfa_strength.acr:
        raise AssertionError("MFA flow did not provide trusted ACR context")

    authority = MemorySessionAuthority()
    now = datetime.now(timezone.utc)
    basic_handle = issue_browser_session(
        authority=authority,
        principal=basic_principal,
        now=now,
        lifetime=timedelta(minutes=30),
        authentication_strength=basic_strength,
    )
    basic_record = resolve_browser_session(authority=authority, handle=basic_handle, now=now)
    _expect_denied(
        lambda: require_authentication_strength(
            policy=MfaPolicy(),
            policy_id="security.mfa.admin@1",
            evidence=basic_record.authentication_strength,
            principal=basic_record.principal,
            now=now,
        ),
        "password_only_step_up",
    )

    mfa_handle = issue_browser_session(
        authority=authority,
        principal=mfa_principal,
        now=now,
        lifetime=timedelta(minutes=30),
        authentication_strength=mfa_strength,
    )
    mfa_record = resolve_browser_session(authority=authority, handle=mfa_handle, now=now)
    require_authentication_strength(
        policy=MfaPolicy(),
        policy_id="security.mfa.admin@1",
        evidence=mfa_record.authentication_strength,
        principal=mfa_record.principal,
        now=now,
    )

    rotated = rotate_browser_session(
        authority=authority,
        predecessor=mfa_handle,
        now=now + timedelta(seconds=1),
        lifetime=timedelta(minutes=30),
    )
    rotated_record = resolve_browser_session(
        authority=authority,
        handle=rotated,
        now=now + timedelta(seconds=1),
    )
    _expect_denied(
        lambda: require_authentication_strength(
            policy=MfaPolicy(),
            policy_id="security.mfa.admin@1",
            evidence=mfa_record.authentication_strength,
            principal=rotated_record.principal,
            now=now + timedelta(seconds=1),
        ),
        "stale_generation_strength_reuse",
    )
    require_authentication_strength(
        policy=MfaPolicy(),
        policy_id="security.mfa.admin@1",
        evidence=rotated_record.authentication_strength,
        principal=rotated_record.principal,
        now=now + timedelta(seconds=1),
    )

    print(
        "d3_keycloak_mfa_step_up=PASS "
        f"acr={mfa_strength.acr} amr={','.join(sorted(mfa_strength.amr))} "
        "password_only_denied=true exact_session_generation=true "
        "mfa_required_action=true real_totp=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
