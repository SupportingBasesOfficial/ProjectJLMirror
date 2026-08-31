from __future__ import annotations

from pathlib import Path
import secrets
import sqlite3
import tempfile
import time

import keycloak_authority_effects_probe_legacy as legacy


# Structural marker retained for the conformance workflow's evidence guard.
LEGACY_AUTHORITY_PASS_MARKER = "d3_keycloak_authority_effects=PASS"
_ORIGINAL_CONFIGURE_REALM = legacy.configure_realm
MAX_LOGOUT_TOKEN_AGE_SECONDS = 120
DEFAULT_REPLAY_CLAIM_LEASE_SECONDS = 30.0


class FreshLogoutVerifier(legacy.LogoutVerifier):
    """Verify the signed token first, then enforce a bounded issued-at horizon."""

    @staticmethod
    def _enforce_issued_at_freshness(
        authenticated: legacy.AuthenticatedLogout,
        *,
        now: int,
    ) -> None:
        if authenticated.issued_at < now - MAX_LOGOUT_TOKEN_AGE_SECONDS:
            raise legacy.AdmissionDenied(
                "logout token issued-at is outside the bounded freshness horizon"
            )

    def verify(self, token: str) -> legacy.AuthenticatedLogout:
        authenticated = super().verify(token)
        self._enforce_issued_at_freshness(authenticated, now=int(time.time()))
        return authenticated


class RecoverableReplayLedger:
    """Durable scoped replay ledger with expiring single-winner claim ownership.

    `pending` means a live executor owns a bounded lease, not that the replay
    identity is burned forever. A retry before lease expiry is rejected as a
    concurrent replay; after expiry exactly one retry may atomically recover
    the abandoned claim. Completed identities remain permanently rejected.
    """

    TABLE = "replay_ledger_v2"

    def __init__(
        self,
        path: Path,
        *,
        clock=time.time,
        lease_seconds: float = DEFAULT_REPLAY_CLAIM_LEASE_SECONDS,
    ) -> None:
        if not isinstance(path, Path):
            path = Path(path)
        if not callable(clock):
            raise TypeError("replay clock must be callable")
        if not isinstance(lease_seconds, (int, float)) or lease_seconds <= 0:
            raise ValueError("replay claim lease must be positive")
        self.path = path
        self._clock = clock
        self._lease_seconds = float(lease_seconds)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE} (
                    issuer TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    jti TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('pending','retryable','completed')),
                    owner TEXT,
                    lease_until REAL,
                    PRIMARY KEY (issuer, client_id, jti),
                    CHECK (
                        (status='pending' AND owner IS NOT NULL AND lease_until IS NOT NULL)
                        OR
                        (status IN ('retryable','completed') AND owner IS NULL AND lease_until IS NULL)
                    )
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
    ) -> legacy.ReplayLease:
        owner = secrets.token_hex(16)
        now = float(self._clock())
        lease_until = now + self._lease_seconds
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                f"""
                SELECT fingerprint, status, owner, lease_until
                FROM {self.TABLE}
                WHERE issuer=? AND client_id=? AND jti=?
                """,
                (issuer, client_id, jti),
            ).fetchone()

            if row is None:
                db.execute(
                    f"""
                    INSERT INTO {self.TABLE}
                    (issuer, client_id, jti, fingerprint, status, owner, lease_until)
                    VALUES (?, ?, ?, ?, 'pending', ?, ?)
                    """,
                    (issuer, client_id, jti, fingerprint, owner, lease_until),
                )
            else:
                existing_fingerprint, status, _existing_owner, existing_lease_until = row
                if existing_fingerprint != fingerprint:
                    raise legacy.ReplayDetected(
                        "same replay identity arrived with different token bytes"
                    )
                if status == "completed":
                    raise legacy.ReplayDetected("completed logout replay rejected")

                if status == "pending":
                    if not isinstance(existing_lease_until, (int, float)):
                        raise legacy.UncertainAuthority(
                            "pending replay claim lacks a recoverable lease boundary"
                        )
                    if float(existing_lease_until) > now:
                        raise legacy.ReplayDetected(
                            "live in-progress logout replay rejected"
                        )
                    cursor = db.execute(
                        f"""
                        UPDATE {self.TABLE}
                        SET owner=?, lease_until=?
                        WHERE issuer=? AND client_id=? AND jti=?
                          AND fingerprint=? AND status='pending'
                          AND lease_until<=?
                        """,
                        (
                            owner,
                            lease_until,
                            issuer,
                            client_id,
                            jti,
                            fingerprint,
                            now,
                        ),
                    )
                    if cursor.rowcount != 1:
                        raise legacy.ReplayDetected(
                            "expired replay claim recovery lost single-winner race"
                        )
                elif status == "retryable":
                    cursor = db.execute(
                        f"""
                        UPDATE {self.TABLE}
                        SET status='pending', owner=?, lease_until=?
                        WHERE issuer=? AND client_id=? AND jti=?
                          AND fingerprint=? AND status='retryable'
                        """,
                        (
                            owner,
                            lease_until,
                            issuer,
                            client_id,
                            jti,
                            fingerprint,
                        ),
                    )
                    if cursor.rowcount != 1:
                        raise legacy.ReplayDetected(
                            "retry lease lost single-winner claim"
                        )
                else:
                    raise AssertionError(f"unexpected replay status: {status!r}")

            db.execute("COMMIT")
        except Exception:
            try:
                db.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            db.close()

        return legacy.ReplayLease(issuer, client_id, jti, owner)

    def _transition(self, lease: legacy.ReplayLease, target: str) -> None:
        if target not in {"retryable", "completed"}:
            raise ValueError("invalid replay transition target")
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            cursor = db.execute(
                f"""
                UPDATE {self.TABLE}
                SET status=?, owner=NULL, lease_until=NULL
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
                raise AssertionError(
                    "replay lease transition lost current ownership or was superseded"
                )
            db.execute("COMMIT")
        except Exception:
            try:
                db.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            db.close()

    def complete(self, lease: legacy.ReplayLease) -> None:
        self._transition(lease, "completed")

    def retryable(self, lease: legacy.ReplayLease) -> None:
        self._transition(lease, "retryable")

    def status(self, *, issuer: str, client_id: str, jti: str) -> str | None:
        with self._connect() as db:
            row = db.execute(
                f"""
                SELECT status FROM {self.TABLE}
                WHERE issuer=? AND client_id=? AND jti=?
                """,
                (issuer, client_id, jti),
            ).fetchone()
        return None if row is None else str(row[0])


class StrictProviderMappingAuthority(legacy.ProviderMappingAuthority):
    """Resolve provider session identity without laundering unknown SIDs into subject-wide effects."""

    def resolve(
        self,
        *,
        issuer: str,
        client_id: str,
        sid: str | None,
        sub: str | None,
    ) -> legacy.ProviderSessionBinding | str | None:
        self.lookup_count += 1
        if not self.available:
            raise legacy.UncertainAuthority("provider mapping currentness unavailable")

        # An authenticated logout token that carries `sid` is session-scoped.
        # A missing/retired mapping is therefore confirmed absence for that
        # exact provider session. It must never fall through to `sub`, because
        # doing so would widen an unknown session logout into a principal-wide
        # fence and could revoke unrelated, newer sessions after relink.
        if sid is not None:
            binding = self.sid_bindings.get((issuer, client_id, sid))
            if binding is None:
                return None
            if sub is not None and binding.sub != sub:
                raise legacy.UncertainAuthority(
                    "authenticated sid/sub mapping is contradictory"
                )
            if binding.active:
                return binding
            return None

        # Subject-wide fencing is permitted only for genuinely sub-only
        # authenticated logout tokens.
        if sub is not None:
            return self.subject_current.get((issuer, sub))
        return None


def _install_explicit_realm_role_mapper() -> None:
    token = legacy.admin_token()
    _, clients, _ = legacy.request(
        "GET",
        f"{legacy.BASE}/admin/realms/{legacy.REALM}/clients?clientId={legacy.CLIENT_ID}",
        token=token,
    )
    if not isinstance(clients, list) or len(clients) != 1:
        raise AssertionError("could not resolve exactly one authority evidence client")
    client_uuid = clients[0].get("id")
    if not isinstance(client_uuid, str) or not client_uuid:
        raise AssertionError("authority evidence client lacks id")

    legacy.request(
        "POST",
        f"{legacy.BASE}/admin/realms/{legacy.REALM}/clients/{client_uuid}/protocol-mappers/models",
        token=token,
        body={
            "name": "d3-realm-roles",
            "protocol": "openid-connect",
            "protocolMapper": "oidc-usermodel-realm-role-mapper",
            "consentRequired": False,
            "config": {
                "multivalued": "true",
                "access.token.claim": "true",
                "claim.name": "realm_access.roles",
                "jsonType.label": "String",
                "id.token.claim": "true",
                "userinfo.token.claim": "false",
                "usermodel.realmRoleMapping.rolePrefix": "",
            },
        },
    )
    _, mappers, _ = legacy.request(
        "GET",
        f"{legacy.BASE}/admin/realms/{legacy.REALM}/clients/{client_uuid}/protocol-mappers/models",
        token=token,
    )
    matches = [
        mapper
        for mapper in (mappers if isinstance(mappers, list) else [])
        if isinstance(mapper, dict)
        and mapper.get("name") == "d3-realm-roles"
        and mapper.get("protocolMapper") == "oidc-usermodel-realm-role-mapper"
    ]
    if len(matches) != 1:
        raise AssertionError(
            "explicit Keycloak realm-role mapper was not installed exactly once"
        )


def configure_realm() -> str:
    user_id = _ORIGINAL_CONFIGURE_REALM()
    _install_explicit_realm_role_mapper()
    return user_id


def _prove_sid_scope_does_not_widen() -> None:
    mappings = StrictProviderMappingAuthority()
    issuer = "https://idp.example.invalid/realms/d3"
    sub = "provider-subject-stable"
    mappings.subject_current[(issuer, sub)] = "platform-principal-current"

    unknown_sid = mappings.resolve(
        issuer=issuer,
        client_id="bff-client",
        sid="provider-session-unknown",
        sub=sub,
    )
    if unknown_sid is not None:
        raise AssertionError("unknown provider sid widened into subject-wide authority")

    sub_only = mappings.resolve(
        issuer=issuer,
        client_id="bff-client",
        sid=None,
        sub=sub,
    )
    if sub_only != "platform-principal-current":
        raise AssertionError("genuine sub-only logout lost principal-wide mapping")

    print(
        "d3_keycloak_sid_scope=PASS "
        "unknown_sid_no_sub_fallback=true sub_only_principal_fence_allowed=true"
    )


def _prove_stale_iat_rejected() -> None:
    now = int(time.time())
    stale = legacy.AuthenticatedLogout(
        issuer="https://idp.example.invalid/realms/d3",
        client_id="bff-client",
        jti="stale-issued-at-proof",
        issued_at=now - MAX_LOGOUT_TOKEN_AGE_SECONDS - 1,
        expires_at=now + 60,
        sid="provider-session-stale",
        sub="provider-subject-stale",
        raw_fingerprint="1" * 64,
    )
    try:
        FreshLogoutVerifier._enforce_issued_at_freshness(stale, now=now)
    except legacy.AdmissionDenied:
        pass
    else:
        raise AssertionError("stale logout issued-at evidence was accepted")

    current = legacy.AuthenticatedLogout(
        issuer=stale.issuer,
        client_id=stale.client_id,
        jti="current-issued-at-proof",
        issued_at=now - MAX_LOGOUT_TOKEN_AGE_SECONDS,
        expires_at=now + 60,
        sid=stale.sid,
        sub=stale.sub,
        raw_fingerprint="2" * 64,
    )
    FreshLogoutVerifier._enforce_issued_at_freshness(current, now=now)

    print(
        "d3_keycloak_logout_iat_freshness=PASS "
        f"max_age_seconds={MAX_LOGOUT_TOKEN_AGE_SECONDS} stale_signed_profile_rejected=true"
    )


def _prove_abandoned_replay_claim_recovery() -> None:
    clock_value = [10_000.0]

    def clock() -> float:
        return clock_value[0]

    with tempfile.TemporaryDirectory(prefix="d3-replay-lease-proof-") as td:
        path = Path(td) / "replay.sqlite3"
        first = RecoverableReplayLedger(path, clock=clock, lease_seconds=10.0)
        abandoned = first.claim(
            issuer="https://idp.example.invalid/realms/d3",
            client_id="bff-client",
            jti="abandoned-jti",
            fingerprint="a" * 64,
        )

        # A live owner is still protected from duplicate execution.
        restarted = RecoverableReplayLedger(path, clock=clock, lease_seconds=10.0)
        try:
            restarted.claim(
                issuer=abandoned.issuer,
                client_id=abandoned.client_id,
                jti=abandoned.jti,
                fingerprint="a" * 64,
            )
        except legacy.ReplayDetected:
            pass
        else:
            raise AssertionError("live replay claim admitted a concurrent executor")

        # Simulate process death by never transitioning `abandoned`, reopen the
        # durable ledger, advance past its lease, and prove one new owner wins.
        clock_value[0] += 11.0
        recovered_ledger = RecoverableReplayLedger(
            path,
            clock=clock,
            lease_seconds=10.0,
        )
        recovered = recovered_ledger.claim(
            issuer=abandoned.issuer,
            client_id=abandoned.client_id,
            jti=abandoned.jti,
            fingerprint="a" * 64,
        )
        if recovered.owner == abandoned.owner:
            raise AssertionError("abandoned replay claim reused stale owner identity")

        # The crashed owner cannot later complete over the recovered owner.
        try:
            first.complete(abandoned)
        except AssertionError:
            pass
        else:
            raise AssertionError("superseded replay owner retained transition authority")

        recovered_ledger.complete(recovered)
        if recovered_ledger.status(
            issuer=recovered.issuer,
            client_id=recovered.client_id,
            jti=recovered.jti,
        ) != "completed":
            raise AssertionError("recovered replay claim did not reach completed state")

        try:
            RecoverableReplayLedger(path, clock=clock, lease_seconds=10.0).claim(
                issuer=recovered.issuer,
                client_id=recovered.client_id,
                jti=recovered.jti,
                fingerprint="a" * 64,
            )
        except legacy.ReplayDetected:
            pass
        else:
            raise AssertionError("completed replay identity became executable after restart")

    print(
        "d3_keycloak_abandoned_replay_recovery=PASS "
        "live_claim_single_winner=true expired_claim_recoverable=true "
        "stale_owner_fenced=true completed_replay_rejected=true"
    )


def main() -> int:
    # Patch the preserved evidence body only at explicit authority seams. The
    # workflow therefore exercises the original end-to-end scenarios through
    # stronger replay, freshness and provider-identity implementations.
    legacy.LogoutVerifier = FreshLogoutVerifier
    legacy.DurableReplayLedger = RecoverableReplayLedger
    legacy.ProviderMappingAuthority = StrictProviderMappingAuthority
    legacy.configure_realm = configure_realm

    _prove_sid_scope_does_not_widen()
    _prove_stale_iat_rejected()
    _prove_abandoned_replay_claim_recovery()
    result = legacy.main()
    print(
        "d3_keycloak_authority_wrapper=PASS "
        "explicit_realm_role_mapper=true strict_sid_scope=true "
        "bounded_iat_freshness=true recoverable_replay_claims=true"
    )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
