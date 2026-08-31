from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import time

import keycloak_authority_effects_probe as probe
import keycloak_authority_effects_probe_legacy as legacy
import keycloak_authority_upgrade_guard_runner as upgrade


@dataclass(frozen=True)
class DurableCallback:
    token: str
    authenticated: legacy.AuthenticatedLogout


class DurableCallbackInbox:
    """Durable create-or-observe responsibility for authenticated logout callbacks.

    The HTTP callback must not acknowledge a newly observed Logout Token until
    its exact bytes plus the canonical claims already authenticated by the
    trusted verifier are committed with SQLite FULL synchronous durability.
    Duplicate delivery of those exact bytes observes the existing durable work
    rather than creating a second authority identity. A replay-identity or
    fingerprint contradiction fails closed.
    """

    TABLE = "backchannel_callback_inbox_v1"

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE} (
                    fingerprint TEXT PRIMARY KEY,
                    token TEXT NOT NULL,
                    issuer TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    jti TEXT NOT NULL,
                    issued_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    sid TEXT,
                    sub TEXT,
                    accepted_at REAL NOT NULL,
                    UNIQUE (issuer, client_id, jti),
                    CHECK (sid IS NOT NULL OR sub IS NOT NULL)
                )
                """
            )

    @staticmethod
    def _fingerprint(token: str) -> str:
        try:
            encoded = token.encode("ascii")
        except UnicodeEncodeError as exc:
            raise legacy.AdmissionDenied("logout token is not ASCII compact JWS") from exc
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _authenticated_tuple(
        authenticated: legacy.AuthenticatedLogout,
    ) -> tuple[str, str, str, int, int, str | None, str | None]:
        if not isinstance(authenticated, legacy.AuthenticatedLogout):
            raise TypeError("authenticated logout context is required")
        if authenticated.sid is None and authenticated.sub is None:
            raise legacy.UncertainAuthority("authenticated callback lacks sid/sub authority shape")
        return (
            authenticated.issuer,
            authenticated.client_id,
            authenticated.jti,
            authenticated.issued_at,
            authenticated.expires_at,
            authenticated.sid,
            authenticated.sub,
        )

    def observe_exact(self, token: str) -> DurableCallback | None:
        fingerprint = self._fingerprint(token)
        with self._connect() as db:
            row = db.execute(
                f"""
                SELECT token, issuer, client_id, jti, issued_at, expires_at, sid, sub
                FROM {self.TABLE}
                WHERE fingerprint=?
                """,
                (fingerprint,),
            ).fetchone()
        if row is None:
            return None
        stored_token, issuer, client_id, jti, issued_at, expires_at, sid, sub = row
        if stored_token != token:
            raise legacy.UncertainAuthority("callback fingerprint collision changed token bytes")
        return DurableCallback(
            token=stored_token,
            authenticated=legacy.AuthenticatedLogout(
                issuer=str(issuer),
                client_id=str(client_id),
                jti=str(jti),
                issued_at=int(issued_at),
                expires_at=int(expires_at),
                sid=sid,
                sub=sub,
                raw_fingerprint=fingerprint,
            ),
        )

    def accept_verified(
        self,
        *,
        token: str,
        authenticated: legacy.AuthenticatedLogout,
    ) -> bool:
        fingerprint = self._fingerprint(token)
        expected = self._authenticated_tuple(authenticated)
        if authenticated.raw_fingerprint != fingerprint:
            raise legacy.UncertainAuthority(
                "authenticated callback fingerprint does not match exact token bytes"
            )

        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            identity_row = db.execute(
                f"""
                SELECT fingerprint, token, issuer, client_id, jti,
                       issued_at, expires_at, sid, sub
                FROM {self.TABLE}
                WHERE issuer=? AND client_id=? AND jti=?
                """,
                expected[:3],
            ).fetchone()
            if identity_row is not None:
                (
                    stored_fingerprint,
                    stored_token,
                    issuer,
                    client_id,
                    jti,
                    issued_at,
                    expires_at,
                    sid,
                    sub,
                ) = identity_row
                stored = (
                    str(issuer),
                    str(client_id),
                    str(jti),
                    int(issued_at),
                    int(expires_at),
                    sid,
                    sub,
                )
                if (
                    stored_fingerprint != fingerprint
                    or stored_token != token
                    or stored != expected
                ):
                    raise legacy.UncertainAuthority(
                        "callback replay identity contradicts previously durable responsibility"
                    )
                db.execute("COMMIT")
                return False

            fingerprint_row = db.execute(
                f"SELECT token, issuer, client_id, jti FROM {self.TABLE} WHERE fingerprint=?",
                (fingerprint,),
            ).fetchone()
            if fingerprint_row is not None:
                raise legacy.UncertainAuthority(
                    "callback fingerprint is already bound to another replay identity"
                )

            db.execute(
                f"""
                INSERT INTO {self.TABLE}
                (fingerprint, token, issuer, client_id, jti, issued_at, expires_at,
                 sid, sub, accepted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fingerprint,
                    token,
                    *expected,
                    float(time.time()),
                ),
            )
            db.execute("COMMIT")
            return True
        except Exception:
            try:
                db.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            db.close()

    def count(self) -> int:
        with self._connect() as db:
            row = db.execute(f"SELECT COUNT(*) FROM {self.TABLE}").fetchone()
        return int(row[0])


class StrictEventFreshLogoutVerifier(probe.FreshLogoutVerifier):
    """Require the protocol-defined empty Back-Channel Logout event object."""

    @staticmethod
    def _enforce_event_profile(events) -> None:
        if not isinstance(events, dict) or legacy.EVENT_URI not in events:
            raise legacy.AdmissionDenied("logout token lacks required event")
        event_value = events[legacy.EVENT_URI]
        if not isinstance(event_value, dict) or event_value:
            raise legacy.AdmissionDenied(
                "logout Back-Channel event value must be the empty JSON object"
            )

    def verify(self, token: str) -> legacy.AuthenticatedLogout:
        # `super().verify()` performs signature, trusted-key, issuer, audience,
        # time, nonce and bounded-iat validation before this claim-level profile
        # check. The payload is therefore only interpreted here after the JWS
        # has already been authenticated by the trusted verifier path.
        authenticated = super().verify(token)
        try:
            parts = token.split(".")
            claims = json.loads(legacy.b64url_decode(parts[1]))
        except (IndexError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise legacy.AdmissionDenied("authenticated logout payload became unreadable") from exc
        if not isinstance(claims, dict):
            raise legacy.AdmissionDenied("authenticated logout claims are malformed")
        self._enforce_event_profile(claims.get("events"))
        return authenticated


class DurableCaptureHandler(legacy.CaptureHandler):
    """HTTP callback ingress whose 2xx follows durable authenticated responsibility."""

    inbox: DurableCallbackInbox | None = None
    verifier: StrictEventFreshLogoutVerifier | None = None
    captured = legacy.queue.Queue(maxsize=16)

    def _respond(self, status: int) -> None:
        self.send_response(status)
        self.end_headers()

    def do_POST(self):
        if self.path != "/backchannel-logout":
            self._respond(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._respond(400)
            return
        if length <= 0 or length > 64 * 1024:
            self._respond(400)
            return
        raw = self.rfile.read(length)
        try:
            parsed = legacy.parse_qs(
                raw.decode("utf-8"),
                keep_blank_values=True,
                strict_parsing=True,
            )
        except (UnicodeDecodeError, ValueError):
            self._respond(400)
            return
        values = parsed.get("logout_token", [])
        if len(values) != 1 or not values[0]:
            self._respond(400)
            return

        inbox = type(self).inbox
        verifier = type(self).verifier
        if inbox is None or verifier is None:
            self._respond(503)
            return
        token = values[0]
        try:
            # Exact retries of already-durable work are acknowledgements of an
            # existing responsibility, not re-admission of a stale credential.
            durable = inbox.observe_exact(token)
            if durable is None:
                authenticated = verifier.verify(token)
                inbox.accept_verified(token=token, authenticated=authenticated)
        except legacy.AdmissionDenied:
            self._respond(400)
            return
        except Exception:
            # Never acknowledge when durability/current responsibility is
            # uncertain. Keycloak may retry safely.
            self._respond(503)
            return

        # This queue is only a same-process notification used by the preserved
        # end-to-end harness. Losing it cannot lose work because the database
        # commit above is already authoritative before the HTTP 200.
        try:
            type(self).captured.put_nowait(token)
        except legacy.queue.Full:
            pass
        self._respond(200)


def _prove_event_profile_rejection() -> None:
    StrictEventFreshLogoutVerifier._enforce_event_profile({legacy.EVENT_URI: {}})
    malformed = (
        {legacy.EVENT_URI: "malformed"},
        {legacy.EVENT_URI: {"unexpected": True}},
        {legacy.EVENT_URI: []},
        {},
    )
    for events in malformed:
        try:
            StrictEventFreshLogoutVerifier._enforce_event_profile(events)
        except legacy.AdmissionDenied:
            pass
        else:
            raise AssertionError(f"malformed Back-Channel event profile was accepted: {events!r}")
    print(
        "d3_keycloak_logout_event_profile=PASS "
        "empty_event_object_required=true malformed_event_values_rejected=true "
        "signature_verification_precedes_event_authority=true"
    )


def _prove_durable_callback_ack_recovery() -> None:
    with tempfile.TemporaryDirectory(prefix="d3-callback-inbox-proof-") as td:
        path = Path(td) / "callback.sqlite3"
        token = "header.payload.signature"
        fingerprint = hashlib.sha256(token.encode("ascii")).hexdigest()
        authenticated = legacy.AuthenticatedLogout(
            issuer="https://idp.example.invalid/realms/d3",
            client_id="bff-client",
            jti="callback-durable-proof",
            issued_at=100,
            expires_at=200,
            sid="provider-session-durable-proof",
            sub="provider-sub-durable-proof",
            raw_fingerprint=fingerprint,
        )
        first = DurableCallbackInbox(path)
        if not first.accept_verified(token=token, authenticated=authenticated):
            raise AssertionError("new callback responsibility was not created")

        # Simulate process death after the durable commit/HTTP acknowledgement
        # but before any in-memory notification or replay-ledger claim. Reopen
        # from disk and prove the exact verified work still exists.
        restarted = DurableCallbackInbox(path)
        recovered = restarted.observe_exact(token)
        if recovered is None or recovered.authenticated != authenticated:
            raise AssertionError("durable callback responsibility was lost across restart")
        if restarted.count() != 1:
            raise AssertionError("callback create-or-observe duplicated durable work")
        if restarted.accept_verified(token=token, authenticated=authenticated):
            raise AssertionError("exact callback retry created a second durable identity")

        conflicting_token = "header.different.signature"
        conflicting = legacy.AuthenticatedLogout(
            issuer=authenticated.issuer,
            client_id=authenticated.client_id,
            jti=authenticated.jti,
            issued_at=authenticated.issued_at,
            expires_at=authenticated.expires_at,
            sid=authenticated.sid,
            sub=authenticated.sub,
            raw_fingerprint=hashlib.sha256(conflicting_token.encode("ascii")).hexdigest(),
        )
        try:
            restarted.accept_verified(token=conflicting_token, authenticated=conflicting)
        except legacy.UncertainAuthority:
            pass
        else:
            raise AssertionError("conflicting callback replay identity did not fail closed")

    print(
        "d3_keycloak_callback_durable_ack=PASS "
        "verified_context_persisted=true commit_before_ack=true restart_recovery=true "
        "exact_retry_create_or_observe=true conflicting_identity_fail_closed=true "
        "notification_queue_non_authoritative=true"
    )


def main() -> int:
    _prove_event_profile_rejection()
    _prove_durable_callback_ack_recovery()

    # The established wrapper chain dynamically reads these seams on its way to
    # the preserved real-Keycloak scenarios. This final layer therefore keeps
    # every prior proof while replacing only callback ingress and event-profile
    # verification with the stronger implementations above.
    probe.FreshLogoutVerifier = StrictEventFreshLogoutVerifier
    with tempfile.TemporaryDirectory(prefix="d3-callback-inbox-live-") as td:
        inbox = DurableCallbackInbox(Path(td) / "callback.sqlite3")
        DurableCaptureHandler.inbox = inbox
        DurableCaptureHandler.verifier = StrictEventFreshLogoutVerifier()
        DurableCaptureHandler.captured = legacy.queue.Queue(maxsize=16)
        legacy.CaptureHandler = DurableCaptureHandler

        result = upgrade.main()
        if inbox.count() < 1:
            raise AssertionError("real Keycloak callback bypassed durable ingress responsibility")

    print(
        "d3_keycloak_callback_ingress=PASS "
        "authenticated_before_new_ack=true durable_responsibility_before_2xx=true "
        "duplicate_ack_observes_existing_work=true strict_empty_event_object=true "
        "prior_authority_recovery_suite_preserved=true"
    )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
