from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode
from urllib.request import Request, urlopen

BASE = os.environ.get("KEYCLOAK_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
ADMIN_USER = os.environ.get("KEYCLOAK_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("KEYCLOAK_ADMIN_PASSWORD", "d3-admin-password")
REALM = "d3evidence"
CLIENT_ID = "d3-bff"
CLIENT_SECRET = "d3-client-secret"
USER = "alice"
PASSWORD = "d3-user-password"
LOGOUT_PORT = int(os.environ.get("D3_LOGOUT_PORT", "18080"))
LOGOUT_URL = f"http://host.docker.internal:{LOGOUT_PORT}/backchannel-logout"


def request(method: str, url: str, *, token: str | None = None, form: dict[str, str] | None = None, body=None):
    headers = {}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if form is not None:
        data = urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, method=method, headers=headers)
    try:
        with urlopen(req, timeout=10) as resp:
            raw = resp.read()
            if not raw:
                return resp.status, None, dict(resp.headers)
            content_type = resp.headers.get("Content-Type", "")
            if "json" in content_type:
                return resp.status, json.loads(raw), dict(resp.headers)
            return resp.status, raw.decode(), dict(resp.headers)
    except HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {method} {url}: {raw}") from exc


def wait_ready() -> None:
    deadline = time.monotonic() + 90
    url = f"{BASE}/realms/master/.well-known/openid-configuration"
    while time.monotonic() < deadline:
        try:
            status, payload, _ = request("GET", url)
            if status == 200 and isinstance(payload, dict) and payload.get("issuer"):
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("Keycloak did not become ready before deadline")


def admin_token() -> str:
    _, payload, _ = request(
        "POST",
        f"{BASE}/realms/master/protocol/openid-connect/token",
        form={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": ADMIN_USER,
            "password": ADMIN_PASSWORD,
        },
    )
    return payload["access_token"]


def b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * ((4 - len(value) % 4) % 4))


def der_len(length: int) -> bytes:
    if length < 128:
        return bytes([length])
    encoded = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(encoded)]) + encoded


def der_integer(raw: bytes) -> bytes:
    raw = raw.lstrip(b"\x00") or b"\x00"
    if raw[0] & 0x80:
        raw = b"\x00" + raw
    return b"\x02" + der_len(len(raw)) + raw


def der_sequence(*parts: bytes) -> bytes:
    payload = b"".join(parts)
    return b"\x30" + der_len(len(payload)) + payload


def rsa_public_key_pem(n: str, e: str) -> bytes:
    der = der_sequence(der_integer(b64url_decode(n)), der_integer(b64url_decode(e)))
    pem_body = base64.encodebytes(der).replace(b"\n", b"")
    lines = [pem_body[i : i + 64] for i in range(0, len(pem_body), 64)]
    return b"-----BEGIN RSA PUBLIC KEY-----\n" + b"\n".join(lines) + b"\n-----END RSA PUBLIC KEY-----\n"


def verify_rs256(token: str, jwk: dict) -> None:
    parts = token.split(".")
    if len(parts) != 3:
        raise AssertionError("logout token is not compact JWS")
    signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    signature = b64url_decode(parts[2])
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "pub.pem").write_bytes(rsa_public_key_pem(jwk["n"], jwk["e"]))
        (root / "payload.bin").write_bytes(signing_input)
        (root / "sig.bin").write_bytes(signature)
        result = subprocess.run(
            [
                "openssl",
                "dgst",
                "-sha256",
                "-verify",
                str(root / "pub.pem"),
                "-signature",
                str(root / "sig.bin"),
                str(root / "payload.bin"),
            ],
            text=True,
            capture_output=True,
            timeout=10,
        )
        if result.returncode != 0 or "Verified OK" not in result.stdout:
            raise AssertionError(f"logout-token RS256 verification failed: {result.stdout} {result.stderr}")

        tampered = bytearray(signature)
        tampered[-1] ^= 1
        (root / "sig-bad.bin").write_bytes(bytes(tampered))
        bad = subprocess.run(
            [
                "openssl",
                "dgst",
                "-sha256",
                "-verify",
                str(root / "pub.pem"),
                "-signature",
                str(root / "sig-bad.bin"),
                str(root / "payload.bin"),
            ],
            text=True,
            capture_output=True,
            timeout=10,
        )
        if bad.returncode == 0:
            raise AssertionError("tampered logout-token signature unexpectedly verified")


class CaptureHandler(BaseHTTPRequestHandler):
    captured: queue.Queue[str] = queue.Queue(maxsize=4)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        parsed = parse_qs(raw.decode("utf-8"), strict_parsing=True)
        values = parsed.get("logout_token", [])
        if len(values) != 1:
            self.send_response(400)
            self.end_headers()
            return
        self.captured.put(values[0])
        self.send_response(200)
        self.end_headers()

    def log_message(self, fmt, *args):
        return


def configure_and_capture() -> str:
    token = admin_token()

    # Fresh evidence realm. A collision means the runner is not clean enough to trust.
    request("POST", f"{BASE}/admin/realms", token=token, body={"realm": REALM, "enabled": True})

    client = {
        "clientId": CLIENT_ID,
        "name": "D3 evidence BFF",
        "enabled": True,
        "protocol": "openid-connect",
        "publicClient": False,
        "secret": CLIENT_SECRET,
        "standardFlowEnabled": True,
        "directAccessGrantsEnabled": True,
        "serviceAccountsEnabled": False,
        "redirectUris": ["http://127.0.0.1:18081/callback"],
        "attributes": {
            "backchannel.logout.url": LOGOUT_URL,
            "backchannel.logout.session.required": "true",
            "backchannel.logout.revoke.offline.tokens": "false",
        },
    }
    request("POST", f"{BASE}/admin/realms/{REALM}/clients", token=token, body=client)

    user = {
        "username": USER,
        "enabled": True,
        "firstName": "D3",
        "lastName": "Evidence",
        "email": "d3-evidence@example.invalid",
        "emailVerified": True,
        "requiredActions": [],
        "credentials": [{"type": "password", "value": PASSWORD, "temporary": False}],
    }
    request("POST", f"{BASE}/admin/realms/{REALM}/users", token=token, body=user)
    _, users, _ = request("GET", f"{BASE}/admin/realms/{REALM}/users?username={USER}&exact=true", token=token)
    if not isinstance(users, list) or len(users) != 1:
        raise AssertionError("could not resolve exactly one evidence user")
    user_id = users[0]["id"]

    # Direct grant is evidence setup only; it creates a client-bound user session so the
    # administrative logout exercises the client's configured back-channel endpoint.
    _, user_tokens, _ = request(
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
    if not user_tokens.get("access_token"):
        raise AssertionError("evidence user session was not created")

    request("POST", f"{BASE}/admin/realms/{REALM}/users/{user_id}/logout", token=token)
    try:
        return CaptureHandler.captured.get(timeout=20)
    except queue.Empty as exc:
        raise AssertionError("Keycloak did not deliver a back-channel logout token") from exc


def main() -> int:
    wait_ready()
    server = ThreadingHTTPServer(("0.0.0.0", LOGOUT_PORT), CaptureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        logout_token = configure_and_capture()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    header_b64, payload_b64, _ = logout_token.split(".")
    header = json.loads(b64url_decode(header_b64))
    claims = json.loads(b64url_decode(payload_b64))

    if header.get("alg") != "RS256":
        raise AssertionError(f"unexpected logout-token alg: {header.get('alg')!r}")
    if not isinstance(header.get("kid"), str) or not header["kid"]:
        raise AssertionError("logout token lacks trusted key id")
    if "jku" in header or "x5u" in header:
        raise AssertionError("logout token contains untrusted remote-key indirection")

    _, jwks, _ = request("GET", f"{BASE}/realms/{REALM}/protocol/openid-connect/certs")
    keys = [k for k in jwks.get("keys", []) if k.get("kid") == header["kid"] and k.get("kty") == "RSA"]
    if len(keys) != 1:
        raise AssertionError("logout-token kid did not resolve to exactly one trusted RSA JWKS key")
    verify_rs256(logout_token, keys[0])

    expected_issuer = f"{BASE}/realms/{REALM}"
    if claims.get("iss") != expected_issuer:
        raise AssertionError(f"issuer mismatch: {claims.get('iss')!r}")
    aud = claims.get("aud")
    audiences = {aud} if isinstance(aud, str) else set(aud or [])
    if CLIENT_ID not in audiences:
        raise AssertionError(f"client audience missing: {aud!r}")
    if not isinstance(claims.get("iat"), int):
        raise AssertionError("logout token lacks integer iat")
    if not isinstance(claims.get("jti"), str) or not claims["jti"]:
        raise AssertionError("logout token lacks replay identity jti")
    if "nonce" in claims:
        raise AssertionError("logout token must not contain nonce")
    if not (isinstance(claims.get("sid"), str) or isinstance(claims.get("sub"), str)):
        raise AssertionError("logout token lacks sid/sub session-principal binding")
    event_uri = "http://schemas.openid.net/event/backchannel-logout"
    events = claims.get("events")
    if not isinstance(events, dict) or event_uri not in events:
        raise AssertionError("logout token lacks back-channel logout event claim")

    # JLMirror's current Keycloak record explicitly requires bounded time evidence including exp.
    # Do not weaken this assertion to make a candidate pass. A missing exp is a D3 finding.
    if not isinstance(claims.get("exp"), int) or claims["exp"] <= claims["iat"]:
        raise AssertionError(
            "D3-A contract requires bounded logout-token exp, but candidate did not provide a valid exp"
        )

    print(
        "d3_keycloak_backchannel=PASS "
        f"alg={header['alg']} kid_bound=true jti=true exp=true sid_or_sub=true issuer_audience=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
