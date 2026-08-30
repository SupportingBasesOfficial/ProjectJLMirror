from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
import http.cookiejar
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
from urllib.request import (
    HTTPRedirectHandler,
    HTTPCookieProcessor,
    Request,
    build_opener,
)

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jlmirror_authority.browser import (  # noqa: E402
    VerifiedOidcIdentity,
    begin_browser_auth,
    complete_browser_auth,
)
from jlmirror_authority.model import AdmissionDenied  # noqa: E402

from keycloak_backchannel_probe import (  # noqa: E402
    admin_token,
    b64url_decode,
    request,
    verify_rs256,
    wait_ready,
)

BASE = os.environ.get("KEYCLOAK_BASE_URL", "https://127.0.0.1:8443").rstrip("/")
REALM = "d3browser"
CLIENT_ID = "d3-browser-bff"
CLIENT_SECRET = "d3-browser-client-secret"
USER = "browser-alice"
PASSWORD = "d3-browser-user-password"
REDIRECT_URI = "https://bff.d3.invalid/callback"
PLATFORM_PRINCIPAL = "principal-d3-browser-evidence"


class LoginFormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.action: str | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "form" or self.action is not None:
            return
        values = dict(attrs)
        if values.get("id") == "kc-form-login" and isinstance(values.get("action"), str):
            self.action = unescape(values["action"])


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OneShotTransactionAuthority:
    def __init__(self, transaction) -> None:
        self._transaction = transaction

    def consume(self, transaction_id: str):
        current = self._transaction
        if current is None or current.transaction_id != transaction_id:
            return None
        self._transaction = None
        return current


def configure_realm() -> str:
    token = admin_token()
    request("POST", f"{BASE}/admin/realms", token=token, body={"realm": REALM, "enabled": True})
    request(
        "POST",
        f"{BASE}/admin/realms/{REALM}/clients",
        token=token,
        body={
            "clientId": CLIENT_ID,
            "name": "D3 browser evidence BFF",
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
    request(
        "POST",
        f"{BASE}/admin/realms/{REALM}/users",
        token=token,
        body={
            "username": USER,
            "enabled": True,
            "firstName": "D3",
            "lastName": "Browser Evidence",
            "email": "d3-browser-evidence@example.invalid",
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
    if not isinstance(users, list) or len(users) != 1 or not isinstance(users[0].get("id"), str):
        raise AssertionError("could not resolve exactly one browser evidence user")
    return users[0]["id"]


def _authorization_url(*, state: str, nonce: str, code_challenge: str) -> str:
    query = urlencode(
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
    return f"{BASE}/realms/{REALM}/protocol/openid-connect/auth?{query}"


def browser_login(*, state: str, nonce: str, code_challenge: str) -> tuple[str, str]:
    jar = http.cookiejar.CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar))
    auth_url = _authorization_url(state=state, nonce=nonce, code_challenge=code_challenge)
    with opener.open(auth_url, timeout=10) as response:
        html = response.read().decode("utf-8")
        final_url = response.geturl()

    parser = LoginFormParser()
    parser.feed(html)
    if parser.action is None:
        raise AssertionError("Keycloak authorization endpoint did not expose the expected login form")
    login_action = urljoin(final_url, parser.action)

    post_opener = build_opener(HTTPCookieProcessor(jar), NoRedirect())
    payload = urlencode({"username": USER, "password": PASSWORD, "credentialId": ""}).encode()
    req = Request(
        login_action,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    location: str | None = None
    try:
        with post_opener.open(req, timeout=10) as response:
            body = response.read().decode("utf-8", errors="replace")
            raise AssertionError(
                "Keycloak credential submission did not redirect to the registered callback; "
                f"status={response.status} body_prefix={body[:160]!r}"
            )
    except HTTPError as exc:
        if exc.code not in {302, 303}:
            body = exc.read().decode("utf-8", errors="replace")
            raise AssertionError(
                f"unexpected Keycloak login HTTP status {exc.code}: {body[:240]}"
            ) from exc
        location = exc.headers.get("Location")

    if not isinstance(location, str) or not location:
        raise AssertionError("Keycloak login redirect lacked Location")
    parsed = urlparse(location)
    expected = urlparse(REDIRECT_URI)
    if (parsed.scheme, parsed.netloc, parsed.path) != (expected.scheme, expected.netloc, expected.path):
        raise AssertionError(f"authorization response escaped exact registered redirect: {location!r}")
    if parsed.fragment:
        raise AssertionError("authorization-code flow unexpectedly returned a fragment")

    values = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
    if any(name in values for name in ("access_token", "id_token", "refresh_token")):
        raise AssertionError("browser redirect exposed a token instead of code-only response")
    codes = values.get("code", [])
    states = values.get("state", [])
    if len(codes) != 1 or len(states) != 1 or not codes[0] or not states[0]:
        raise AssertionError(f"authorization response lacked exactly one code/state: {values!r}")
    return codes[0], states[0]


def _token_form(*, code: str, verifier: str, redirect_uri: str) -> dict[str, str]:
    return {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": verifier,
    }


def expect_token_exchange_failure(*, code: str, verifier: str, redirect_uri: str, label: str) -> None:
    try:
        request(
            "POST",
            f"{BASE}/realms/{REALM}/protocol/openid-connect/token",
            form=_token_form(code=code, verifier=verifier, redirect_uri=redirect_uri),
        )
    except RuntimeError as exc:
        if "HTTP 400" not in str(exc):
            raise AssertionError(f"{label}: expected bounded 400 rejection, got {exc}") from exc
        return
    raise AssertionError(f"{label}: invalid authorization-code exchange unexpectedly succeeded")


class KeycloakOidcVerificationPort:
    def __init__(self, *, external_identity_mapping: dict[tuple[str, str], str]) -> None:
        self._mapping = dict(external_identity_mapping)
        self.last_claims: dict | None = None

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
        if expected_issuer != issuer or expected_client_id != CLIENT_ID or expected_redirect_uri != REDIRECT_URI:
            raise AdmissionDenied("OIDC adapter received an unexpected trusted registration binding")

        _, tokens, _ = request(
            "POST",
            f"{BASE}/realms/{REALM}/protocol/openid-connect/token",
            form=_token_form(
                code=authorization_code,
                verifier=pkce_verifier,
                redirect_uri=expected_redirect_uri,
            ),
        )
        if not isinstance(tokens, dict):
            raise AdmissionDenied("token endpoint returned malformed response")
        id_token = tokens.get("id_token")
        if not isinstance(id_token, str) or not id_token:
            raise AdmissionDenied("token endpoint omitted ID token")
        if not isinstance(tokens.get("access_token"), str) or not tokens["access_token"]:
            raise AdmissionDenied("token endpoint omitted server-side access token")

        parts = id_token.split(".")
        if len(parts) != 3:
            raise AdmissionDenied("ID token is not compact JWS")
        try:
            header = json.loads(b64url_decode(parts[0]))
            claims = json.loads(b64url_decode(parts[1]))
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise AdmissionDenied("ID token is not canonical JSON/JWS") from exc
        if not isinstance(header, dict) or not isinstance(claims, dict):
            raise AdmissionDenied("ID token header/claims are malformed")
        if header.get("alg") != "RS256":
            raise AdmissionDenied("ID token algorithm is outside the pinned evidence profile")
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid or "jku" in header or "x5u" in header:
            raise AdmissionDenied("ID token key selection is not trusted/bounded")

        _, jwks, _ = request("GET", f"{issuer}/protocol/openid-connect/certs")
        if not isinstance(jwks, dict):
            raise AdmissionDenied("trusted JWKS response is malformed")
        keys = [
            key
            for key in jwks.get("keys", [])
            if isinstance(key, dict) and key.get("kid") == kid and key.get("kty") == "RSA"
        ]
        if len(keys) != 1:
            raise AdmissionDenied("ID-token kid did not resolve to exactly one trusted RSA key")
        try:
            verify_rs256(id_token, keys[0])
        except AssertionError as exc:
            raise AdmissionDenied("ID-token signature verification failed") from exc

        if claims.get("iss") != issuer:
            raise AdmissionDenied("ID-token issuer mismatch")
        aud = claims.get("aud")
        audiences = {aud} if isinstance(aud, str) else set(aud or [])
        if CLIENT_ID not in audiences:
            raise AdmissionDenied("ID-token audience mismatch")
        azp = claims.get("azp")
        if azp is not None and azp != CLIENT_ID:
            raise AdmissionDenied("ID-token authorized-party mismatch")

        now = int(time.time())
        iat = claims.get("iat")
        exp = claims.get("exp")
        auth_time = claims.get("auth_time", iat)
        if not all(isinstance(value, int) for value in (iat, exp, auth_time)):
            raise AdmissionDenied("ID-token time claims are malformed")
        if iat > now + 5 or exp <= now or auth_time > now + 5:
            raise AdmissionDenied("ID-token time evidence is not current")
        nbf = claims.get("nbf")
        if nbf is not None and (not isinstance(nbf, int) or nbf > now + 5):
            raise AdmissionDenied("ID-token not-before evidence is not current")

        nonce = claims.get("nonce")
        sub = claims.get("sub")
        if not isinstance(nonce, str) or not nonce or not isinstance(sub, str) or not sub:
            raise AdmissionDenied("ID token lacks nonce or external subject")
        principal_id = self._mapping.get((issuer, sub))
        if not isinstance(principal_id, str) or not principal_id:
            raise AdmissionDenied("external subject has no trusted platform identity mapping")
        if principal_id == sub:
            raise AdmissionDenied("provider-native subject must not become platform principal identity")

        acr = claims.get("acr")
        if acr is not None and (not isinstance(acr, str) or not acr):
            raise AdmissionDenied("ID-token acr is malformed")
        raw_amr = claims.get("amr", [])
        if not isinstance(raw_amr, list) or not all(isinstance(item, str) and item for item in raw_amr):
            raise AdmissionDenied("ID-token amr is malformed")

        self.last_claims = claims
        return VerifiedOidcIdentity(
            principal_id=principal_id,
            issuer=issuer,
            client_id=CLIENT_ID,
            nonce=nonce,
            authenticated_at=datetime.fromtimestamp(auth_time, tz=timezone.utc),
            token_expires_at=datetime.fromtimestamp(exp, tz=timezone.utc),
            acr=acr,
            amr=frozenset(raw_amr),
            policy_version="keycloak-26.7.2-evidence",
        )


def new_initiation(*, session_binding: str):
    return begin_browser_auth(
        session_binding=session_binding,
        expected_issuer=f"{BASE}/realms/{REALM}",
        expected_client_id=CLIENT_ID,
        expected_redirect_uri=REDIRECT_URI,
        now=datetime.now(timezone.utc),
        lifetime=timedelta(minutes=5),
    )


def main() -> int:
    wait_ready()
    keycloak_user_id = configure_realm()
    issuer = f"{BASE}/realms/{REALM}"
    port = KeycloakOidcVerificationPort(
        external_identity_mapping={(issuer, keycloak_user_id): PLATFORM_PRINCIPAL}
    )

    initiation = new_initiation(session_binding="browser-session-A")
    code, returned_state = browser_login(
        state=initiation.state,
        nonce=initiation.nonce,
        code_challenge=initiation.pkce_challenge,
    )
    authority = OneShotTransactionAuthority(initiation.transaction)
    principal, strength = complete_browser_auth(
        transaction_authority=authority,
        oidc_port=port,
        transaction_id=initiation.transaction.transaction_id,
        initiating_session_binding="browser-session-A",
        returned_state=returned_state,
        authorization_code=code,
        now=datetime.now(timezone.utc),
    )
    if principal.principal_id != PLATFORM_PRINCIPAL:
        raise AssertionError("Keycloak external subject escaped the platform mapping boundary")
    if strength.issuer != issuer or strength.principal_id != PLATFORM_PRINCIPAL:
        raise AssertionError("trusted authentication-strength evidence lost issuer/principal binding")
    if not isinstance(strength.acr, str) or not strength.acr:
        raise AssertionError("Keycloak browser authentication did not propagate trusted acr evidence")

    try:
        complete_browser_auth(
            transaction_authority=authority,
            oidc_port=port,
            transaction_id=initiation.transaction.transaction_id,
            initiating_session_binding="browser-session-A",
            returned_state=returned_state,
            authorization_code=code,
            now=datetime.now(timezone.utc),
        )
    except AdmissionDenied:
        pass
    else:
        raise AssertionError("consumed browser authorization transaction was accepted twice")

    expect_token_exchange_failure(
        code=code,
        verifier=initiation.transaction.pkce_verifier,
        redirect_uri=REDIRECT_URI,
        label="authorization_code_replay",
    )

    bad_pkce = new_initiation(session_binding="browser-session-B")
    bad_pkce_code, _ = browser_login(
        state=bad_pkce.state,
        nonce=bad_pkce.nonce,
        code_challenge=bad_pkce.pkce_challenge,
    )
    expect_token_exchange_failure(
        code=bad_pkce_code,
        verifier="A" * 64,
        redirect_uri=REDIRECT_URI,
        label="wrong_pkce_verifier",
    )

    bad_redirect = new_initiation(session_binding="browser-session-C")
    bad_redirect_code, _ = browser_login(
        state=bad_redirect.state,
        nonce=bad_redirect.nonce,
        code_challenge=bad_redirect.pkce_challenge,
    )
    expect_token_exchange_failure(
        code=bad_redirect_code,
        verifier=bad_redirect.transaction.pkce_verifier,
        redirect_uri="https://bff.d3.invalid/wrong-callback",
        label="wrong_redirect_binding",
    )

    print(
        "d3_keycloak_browser=PASS code_flow=true pkce_s256=true state=true nonce=true "
        "code_single_use=true exact_redirect=true server_side_exchange=true "
        f"external_subject_mapping=true acr=true amr_count={len(strength.amr)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
