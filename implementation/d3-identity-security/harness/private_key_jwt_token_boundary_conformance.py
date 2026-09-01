#!/usr/bin/env python3
from __future__ import annotations

import base64
import concurrent.futures
import hashlib
import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import replay_recovery_conformance_runner as core

AUDIENCE = "https://jlmirror.invalid/oauth2/token"
PRIVATE_KEY = Path("/tmp/jlmirror-d3e-private-key-jwt.pem")
PUBLIC_KEY = Path("/tmp/jlmirror-d3e-private-key-jwt.pub.pem")
REPLICA_PORTS = (18082, 18083)


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def generate_keypair() -> None:
    subprocess.run(
        ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(PRIVATE_KEY)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ["openssl", "pkey", "-in", str(PRIVATE_KEY), "-pubout", "-out", str(PUBLIC_KEY)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def sign_assertion(*, client: str, jti: str, audience: str = AUDIENCE, extra: dict | None = None) -> str:
    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT", "kid": "d3e-test-client-rsa"}
    claims = {
        "iss": client,
        "sub": client,
        "aud": audience,
        "jti": jti,
        "iat": now,
        "exp": now + 120,
    }
    if extra:
        claims.update(extra)
    signing_input = (
        b64url(json.dumps(header, sort_keys=True, separators=(",", ":")).encode())
        + "."
        + b64url(json.dumps(claims, sort_keys=True, separators=(",", ":")).encode())
    ).encode()
    signed = subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", str(PRIVATE_KEY)],
        input=signing_input,
        capture_output=True,
        check=True,
    ).stdout
    return signing_input.decode() + "." + b64url(signed)


def verify_assertion(assertion: str) -> tuple[str, str, str]:
    try:
        h64, p64, s64 = assertion.split(".", 2)
        header = json.loads(b64url_decode(h64))
        claims = json.loads(b64url_decode(p64))
        signature = b64url_decode(s64)
    except Exception as exc:
        raise ValueError("malformed private_key_jwt") from exc
    if header != {"alg": "RS256", "kid": "d3e-test-client-rsa", "typ": "JWT"}:
        raise ValueError("unexpected private_key_jwt header")
    client = claims.get("iss")
    if not isinstance(client, str) or claims.get("sub") != client:
        raise ValueError("private_key_jwt issuer/subject mismatch")
    if claims.get("aud") != AUDIENCE:
        raise ValueError("private_key_jwt audience mismatch")
    jti = claims.get("jti")
    if not isinstance(jti, str) or not jti:
        raise ValueError("private_key_jwt missing jti")
    now = int(time.time())
    if type(claims.get("iat")) is not int or type(claims.get("exp")) is not int:
        raise ValueError("private_key_jwt time claims malformed")
    if claims["iat"] > now + 5 or claims["exp"] <= now or claims["exp"] - claims["iat"] > 180:
        raise ValueError("private_key_jwt freshness invalid")

    signing_input = f"{h64}.{p64}".encode()
    with tempfile.NamedTemporaryFile(prefix="d3e-jwt-sig-", delete=False) as tmp:
        tmp.write(signature)
        sig_path = tmp.name
    try:
        result = subprocess.run(
            ["openssl", "dgst", "-sha256", "-verify", str(PUBLIC_KEY), "-signature", sig_path],
            input=signing_input,
            capture_output=True,
        )
        if result.returncode != 0:
            raise ValueError("private_key_jwt signature invalid")
    finally:
        Path(sig_path).unlink(missing_ok=True)
    fingerprint = hashlib.sha256(assertion.encode()).hexdigest()
    return client, jti, fingerprint


class TokenBoundaryHandler(BaseHTTPRequestHandler):
    server_version = "JLMirrorD3ETokenBoundary/1"

    def log_message(self, fmt, *args):
        return

    def send_json(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/health":
            self.send_json(200, {"ok": True, "replica": self.server.server_port})
            return
        self.send_json(404, {"error": "not_found"})

    def do_POST(self):
        if self.path != "/oauth2/token":
            self.send_json(404, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("content-length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            if payload.get("grant_type") != "client_credentials":
                raise ValueError("unsupported grant")
            assertion = payload.get("client_assertion")
            if not isinstance(assertion, str):
                raise ValueError("missing client_assertion")
            client, jti, fingerprint = verify_assertion(assertion)
        except ValueError as exc:
            self.send_json(401, {"error": "invalid_client", "detail": str(exc)})
            return
        witness = core.RecoveryWitnessPort()
        port = core.ReplayAuthorityPort(witness)
        outcome = port.consume(
            client,
            jti,
            fingerprint,
            f"token-effect:{client}:{jti}",
            f"token-result:{client}:{jti}",
            1,
        )
        status = 200 if outcome in {"WIN", "OBSERVE"} else 409
        self.send_json(status, {"outcome": outcome, "replica": self.server.server_port})


def serve(port: int) -> None:
    ThreadingHTTPServer(("127.0.0.1", port), TokenBoundaryHandler).serve_forever()


def call_replica(port: int, assertion: str) -> tuple[int, dict]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        body = json.dumps({
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": assertion,
        }, separators=(",", ":"))
        conn.request("POST", "/oauth2/token", body=body, headers={"content-type": "application/json"})
        response = conn.getresponse()
        return response.status, json.loads(response.read() or b"{}")
    finally:
        conn.close()


def wait_replica(port: int) -> None:
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
            conn.request("GET", "/health")
            response = conn.getresponse()
            data = json.loads(response.read())
            conn.close()
            if response.status == 200 and data.get("ok") is True:
                return
        except Exception:
            time.sleep(0.1)
    raise RuntimeError(f"token-boundary replica {port} did not start")


def main() -> None:
    generate_keypair()
    core.init_db()
    witness = core.RecoveryWitnessPort()
    witness.initialize()

    replicas = [
        subprocess.Popen([sys.executable, __file__, "--serve", str(port)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for port in REPLICA_PORTS
    ]
    try:
        for port in REPLICA_PORTS:
            wait_replica(port)

        assertion = sign_assertion(client="client-token-boundary", jti="shared-jti")
        with concurrent.futures.ThreadPoolExecutor(max_workers=24) as pool:
            futures = [
                pool.submit(call_replica, REPLICA_PORTS[i % 2], assertion)
                for i in range(48)
            ]
            responses = [future.result() for future in futures]
        outcomes = [body["outcome"] for status, body in responses if status == 200]
        assert outcomes.count("WIN") == 1
        assert outcomes.count("OBSERVE") == 47
        assert {body["replica"] for status, body in responses if status == 200} == set(REPLICA_PORTS)
        assert core.psql(
            "SELECT count(*) FROM d3e_replay.effect_ledger "
            "WHERE effect_id='token-effect:client-token-boundary:shared-jti';"
        ) == "1"

        conflict_assertion = sign_assertion(
            client="client-token-boundary", jti="shared-jti", extra={"nonce": "different-fingerprint"}
        )
        status, body = call_replica(REPLICA_PORTS[1], conflict_assertion)
        assert status == 409 and body["outcome"] == "CONFLICT"

        wrong_aud = sign_assertion(
            client="client-token-boundary", jti="wrong-aud-jti", audience="https://wrong.invalid/token"
        )
        status, body = call_replica(REPLICA_PORTS[0], wrong_aud)
        assert status == 401 and body["error"] == "invalid_client"

        h, p, s = assertion.split(".")
        tampered = h + "." + p + "." + ("A" if s[0] != "A" else "B") + s[1:]
        status, body = call_replica(REPLICA_PORTS[1], tampered)
        assert status == 401 and body["error"] == "invalid_client"

        print(
            "d3_e_private_key_jwt_replay_atomic_single_winner=PASS "
            "actual_token_endpoint=true token_boundary_replicas=2 rs256_signature_validated=true "
            "issuer_subject_audience_jti_freshness_validated=true shared_postgres_replay_authority=true "
            "concurrent_assertions=48 exactly_one_win=true duplicates_observe=true "
            "fingerprint_conflict_rejected=true invalid_signature_rejected=true wrong_audience_rejected=true "
            "replica_local_fallback_absent=true"
        )
    finally:
        for proc in replicas:
            proc.terminate()
        for proc in replicas:
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        PRIVATE_KEY.unlink(missing_ok=True)
        PUBLIC_KEY.unlink(missing_ok=True)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--serve":
        serve(int(sys.argv[2]))
    else:
        main()
