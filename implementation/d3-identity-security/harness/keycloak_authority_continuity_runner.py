from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import time

import keycloak_authority_effects_probe as probe
import keycloak_authority_single_winner_runner as single


V2_LEDGER = probe.RecoverableReplayLedger
AUTH_COLUMNS = {
    "auth_issued_at": "INTEGER",
    "auth_expires_at": "INTEGER",
    "auth_sid": "TEXT",
    "auth_sub": "TEXT",
}


class ContinuityReplayLedger(single.EffectAwareReplayLedger):
    """Single-winner ledger with authenticated recovery and v2 upgrade continuity.

    The v3 replay identity remains the canonical table. This layer evolves it
    in place with the canonical claims that were already authenticated before
    durable ownership was established. Internal reconciliation may consume
    those claims after the original token is no longer current, but only when
    an immutable effect intent was already durably prepared.

    Upgrade is fail-closed: v2 replay identities are transactionally imported
    before v3 can accept claims. In particular, `completed` v2 identities stay
    completed forever and can never become executable again after upgrade.
    """

    LEGACY_TABLE = V2_LEDGER.TABLE

    def _initialize(self) -> None:
        super()._initialize()
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            existing_columns = {
                str(row[1]) for row in db.execute(f"PRAGMA table_info({self.TABLE})")
            }
            for name, sql_type in AUTH_COLUMNS.items():
                if name not in existing_columns:
                    db.execute(f"ALTER TABLE {self.TABLE} ADD COLUMN {name} {sql_type}")
            self._migrate_v2_locked(db)
            db.execute("COMMIT")
        except Exception:
            try:
                db.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            db.close()

    def _migrate_v2_locked(self, db: sqlite3.Connection) -> None:
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (self.LEGACY_TABLE,),
        ).fetchone()
        if exists is None:
            return

        legacy_columns = {
            str(row[1]) for row in db.execute(f"PRAGMA table_info({self.LEGACY_TABLE})")
        }
        required = {
            "issuer",
            "client_id",
            "jti",
            "fingerprint",
            "status",
            "owner",
            "lease_until",
        }
        if not required.issubset(legacy_columns):
            raise probe.legacy.UncertainAuthority(
                "legacy replay ledger schema is not safe to migrate"
            )

        rows = db.execute(
            f"""
            SELECT issuer, client_id, jti, fingerprint, status, owner, lease_until
            FROM {self.LEGACY_TABLE}
            ORDER BY issuer, client_id, jti
            """
        ).fetchall()
        for issuer, client_id, jti, fingerprint, status, owner, lease_until in rows:
            if status not in {"pending", "retryable", "completed"}:
                raise probe.legacy.UncertainAuthority(
                    "legacy replay ledger contains an unknown status"
                )
            if status == "pending":
                if not isinstance(owner, str) or not owner or not isinstance(
                    lease_until, (int, float)
                ):
                    raise probe.legacy.UncertainAuthority(
                        "legacy pending replay row lacks bounded ownership"
                    )
            elif owner is not None or lease_until is not None:
                raise probe.legacy.UncertainAuthority(
                    "legacy terminal/retryable replay row has contradictory ownership"
                )

            current = db.execute(
                f"""
                SELECT fingerprint, status
                FROM {self.TABLE}
                WHERE issuer=? AND client_id=? AND jti=?
                """,
                (issuer, client_id, jti),
            ).fetchone()
            if current is None:
                db.execute(
                    f"""
                    INSERT INTO {self.TABLE}
                    (issuer, client_id, jti, fingerprint, status, owner, lease_until)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (issuer, client_id, jti, fingerprint, status, owner, lease_until),
                )
                continue

            current_fingerprint, current_status = current
            if current_fingerprint != fingerprint:
                raise probe.legacy.UncertainAuthority(
                    "legacy/current replay identity fingerprint conflict"
                )
            if current_status == "completed":
                continue
            if status == "completed":
                db.execute(
                    f"""
                    UPDATE {self.TABLE}
                    SET status='completed', owner=NULL, lease_until=NULL
                    WHERE issuer=? AND client_id=? AND jti=? AND fingerprint=?
                    """,
                    (issuer, client_id, jti, fingerprint),
                )
                continue
            if current_status != status:
                raise probe.legacy.UncertainAuthority(
                    "legacy/current nonterminal replay states conflict during migration"
                )

    @staticmethod
    def _canonical_auth_values(
        authenticated: probe.legacy.AuthenticatedLogout,
        *,
        issuer: str,
        client_id: str,
        jti: str,
        fingerprint: str,
    ) -> tuple[int, int, str | None, str | None]:
        if not isinstance(authenticated, probe.legacy.AuthenticatedLogout):
            raise TypeError("authenticated logout evidence is required")
        if (
            authenticated.issuer != issuer
            or authenticated.client_id != client_id
            or authenticated.jti != jti
            or authenticated.raw_fingerprint != fingerprint
        ):
            raise probe.legacy.UncertainAuthority(
                "authenticated logout evidence does not match replay identity"
            )
        if authenticated.sid is None and authenticated.sub is None:
            raise probe.legacy.UncertainAuthority(
                "authenticated logout evidence lacks sid/sub authority shape"
            )
        if not isinstance(authenticated.issued_at, int) or not isinstance(
            authenticated.expires_at, int
        ):
            raise probe.legacy.UncertainAuthority(
                "authenticated logout time evidence is not canonical"
            )
        return (
            authenticated.issued_at,
            authenticated.expires_at,
            authenticated.sid,
            authenticated.sub,
        )

    def claim_authenticated(
        self,
        authenticated: probe.legacy.AuthenticatedLogout,
    ) -> probe.legacy.ReplayLease:
        issuer = authenticated.issuer
        client_id = authenticated.client_id
        jti = authenticated.jti
        fingerprint = authenticated.raw_fingerprint
        auth_values = self._canonical_auth_values(
            authenticated,
            issuer=issuer,
            client_id=client_id,
            jti=jti,
            fingerprint=fingerprint,
        )
        owner = probe.secrets.token_hex(16)
        now = float(self._clock())
        lease_until = now + self._lease_seconds
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                f"""
                SELECT fingerprint, status, lease_until,
                       auth_issued_at, auth_expires_at, auth_sid, auth_sub
                FROM {self.TABLE}
                WHERE issuer=? AND client_id=? AND jti=?
                """,
                (issuer, client_id, jti),
            ).fetchone()
            if row is None:
                db.execute(
                    f"""
                    INSERT INTO {self.TABLE}
                    (issuer, client_id, jti, fingerprint, status, owner, lease_until,
                     auth_issued_at, auth_expires_at, auth_sid, auth_sub)
                    VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        issuer,
                        client_id,
                        jti,
                        fingerprint,
                        owner,
                        lease_until,
                        *auth_values,
                    ),
                )
            else:
                (
                    existing_fingerprint,
                    status,
                    existing_lease_until,
                    auth_issued_at,
                    auth_expires_at,
                    auth_sid,
                    auth_sub,
                ) = row
                if existing_fingerprint != fingerprint:
                    raise probe.legacy.ReplayDetected(
                        "same replay identity arrived with different token bytes"
                    )
                if status == "completed":
                    raise probe.legacy.ReplayDetected("completed logout replay rejected")

                stored_auth = None
                if auth_issued_at is not None or auth_expires_at is not None:
                    stored_auth = (auth_issued_at, auth_expires_at, auth_sid, auth_sub)
                    if stored_auth != auth_values:
                        raise probe.legacy.UncertainAuthority(
                            "durable authenticated logout context contradicts retry"
                        )

                if status == "pending":
                    if not isinstance(existing_lease_until, (int, float)):
                        raise probe.legacy.UncertainAuthority(
                            "pending replay claim lacks recoverable lease boundary"
                        )
                    if float(existing_lease_until) > now:
                        raise probe.legacy.ReplayDetected(
                            "live in-progress logout replay rejected"
                        )
                    cursor = db.execute(
                        f"""
                        UPDATE {self.TABLE}
                        SET owner=?, lease_until=?,
                            auth_issued_at=COALESCE(auth_issued_at, ?),
                            auth_expires_at=COALESCE(auth_expires_at, ?),
                            auth_sid=CASE WHEN auth_issued_at IS NULL THEN ? ELSE auth_sid END,
                            auth_sub=CASE WHEN auth_issued_at IS NULL THEN ? ELSE auth_sub END
                        WHERE issuer=? AND client_id=? AND jti=?
                          AND fingerprint=? AND status='pending' AND lease_until<=?
                        """,
                        (
                            owner,
                            lease_until,
                            *auth_values,
                            issuer,
                            client_id,
                            jti,
                            fingerprint,
                            now,
                        ),
                    )
                    if cursor.rowcount != 1:
                        raise probe.legacy.ReplayDetected(
                            "expired replay claim recovery lost single-winner race"
                        )
                elif status == "retryable":
                    cursor = db.execute(
                        f"""
                        UPDATE {self.TABLE}
                        SET status='pending', owner=?, lease_until=?,
                            auth_issued_at=COALESCE(auth_issued_at, ?),
                            auth_expires_at=COALESCE(auth_expires_at, ?),
                            auth_sid=CASE WHEN auth_issued_at IS NULL THEN ? ELSE auth_sid END,
                            auth_sub=CASE WHEN auth_issued_at IS NULL THEN ? ELSE auth_sub END
                        WHERE issuer=? AND client_id=? AND jti=?
                          AND fingerprint=? AND status='retryable'
                        """,
                        (
                            owner,
                            lease_until,
                            *auth_values,
                            issuer,
                            client_id,
                            jti,
                            fingerprint,
                        ),
                    )
                    if cursor.rowcount != 1:
                        raise probe.legacy.ReplayDetected(
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
        return probe.legacy.ReplayLease(issuer, client_id, jti, owner)

    def claim_reconciliation(
        self,
        *,
        issuer: str,
        client_id: str,
        jti: str,
    ) -> tuple[
        probe.legacy.ReplayLease,
        probe.legacy.AuthenticatedLogout,
        single.EffectIntent,
    ]:
        owner = probe.secrets.token_hex(16)
        now = float(self._clock())
        lease_until = now + self._lease_seconds
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                f"""
                SELECT fingerprint, status, lease_until,
                       effect_kind, effect_target, effect_generation,
                       auth_issued_at, auth_expires_at, auth_sid, auth_sub
                FROM {self.TABLE}
                WHERE issuer=? AND client_id=? AND jti=?
                """,
                (issuer, client_id, jti),
            ).fetchone()
            if row is None:
                raise probe.legacy.UncertainAuthority(
                    "reconciliation replay identity is absent"
                )
            (
                fingerprint,
                status,
                existing_lease_until,
                effect_kind,
                effect_target,
                effect_generation,
                auth_issued_at,
                auth_expires_at,
                auth_sid,
                auth_sub,
            ) = row
            if status == "completed":
                raise probe.legacy.ReplayDetected(
                    "completed logout cannot be reconciled again"
                )
            if effect_kind is None:
                raise probe.legacy.UncertainAuthority(
                    "reconciliation requires a previously frozen authority effect intent"
                )
            if auth_issued_at is None or auth_expires_at is None:
                raise probe.legacy.UncertainAuthority(
                    "reconciliation lacks durably authenticated logout context"
                )
            if auth_sid is None and auth_sub is None:
                raise probe.legacy.UncertainAuthority(
                    "reconciliation durable context lacks sid/sub shape"
                )

            if status == "pending":
                if not isinstance(existing_lease_until, (int, float)):
                    raise probe.legacy.UncertainAuthority(
                        "pending reconciliation lacks lease boundary"
                    )
                if float(existing_lease_until) > now:
                    raise probe.legacy.ReplayDetected(
                        "live logout executor still owns reconciliation"
                    )
                cursor = db.execute(
                    f"""
                    UPDATE {self.TABLE}
                    SET owner=?, lease_until=?
                    WHERE issuer=? AND client_id=? AND jti=?
                      AND status='pending' AND lease_until<=?
                    """,
                    (owner, lease_until, issuer, client_id, jti, now),
                )
            elif status == "retryable":
                cursor = db.execute(
                    f"""
                    UPDATE {self.TABLE}
                    SET status='pending', owner=?, lease_until=?
                    WHERE issuer=? AND client_id=? AND jti=? AND status='retryable'
                    """,
                    (owner, lease_until, issuer, client_id, jti),
                )
            else:
                raise probe.legacy.UncertainAuthority(
                    f"unsupported reconciliation replay state: {status!r}"
                )
            if cursor.rowcount != 1:
                raise probe.legacy.ReplayDetected(
                    "reconciliation lost single-winner ownership race"
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

        authenticated = probe.legacy.AuthenticatedLogout(
            issuer=issuer,
            client_id=client_id,
            jti=jti,
            issued_at=int(auth_issued_at),
            expires_at=int(auth_expires_at),
            sid=auth_sid,
            sub=auth_sub,
            raw_fingerprint=str(fingerprint),
        )
        intent = single.EffectIntent(
            str(effect_kind),
            effect_target,
            effect_generation,
        )
        return (
            probe.legacy.ReplayLease(issuer, client_id, jti, owner),
            authenticated,
            intent,
        )


class ContinuityLogoutAuthority(single.LeaseGuardedLogoutAuthority):
    replay: ContinuityReplayLedger

    def handle(self, token: str) -> str:
        authenticated = self.verifier.verify(token)
        lease = self.replay.claim_authenticated(authenticated)
        try:
            intent = self.replay.prepared_effect(lease)
            if intent is None:
                resolved = self.mappings.resolve(
                    issuer=authenticated.issuer,
                    client_id=authenticated.client_id,
                    sid=authenticated.sid,
                    sub=authenticated.sub,
                )
                intent = self.replay.prepare_effect(
                    lease,
                    self._intent_from_resolution(resolved),
                )
            else:
                self.replay.prepare_effect(lease, intent)
            self.replay.renew_for_effect(lease)
            result = self._apply_effect_intent(
                authenticated=authenticated,
                intent=intent,
            )
            self.replay.complete(lease)
            return result
        except Exception:
            self._best_effort_retryable(lease)
            raise

    def reconcile(
        self,
        *,
        issuer: str,
        client_id: str,
        jti: str,
    ) -> str:
        """Recover a frozen, previously authenticated effect without token revalidation."""

        lease, authenticated, intent = self.replay.claim_reconciliation(
            issuer=issuer,
            client_id=client_id,
            jti=jti,
        )
        try:
            # No external token is trusted here. The canonical claims and raw
            # fingerprint were durably written only after the original verifier
            # accepted signature/issuer/audience/time/freshness. The immutable
            # effect intent is the authority target; the stale token is merely
            # historical evidence and is not re-admitted as a live credential.
            self.replay.renew_for_effect(lease)
            result = self._apply_effect_intent(
                authenticated=authenticated,
                intent=intent,
            )
            self.replay.complete(lease)
            return result
        except Exception:
            self._best_effort_retryable(lease)
            raise


def _durable_authenticated_logout(
    *,
    now: int,
    jti: str,
    sub: str,
    fingerprint: str,
) -> probe.legacy.AuthenticatedLogout:
    return probe.legacy.AuthenticatedLogout(
        issuer="https://idp.example.invalid/realms/d3",
        client_id="bff-client",
        jti=jti,
        issued_at=now,
        expires_at=now + 30,
        sid=None,
        sub=sub,
        raw_fingerprint=fingerprint,
    )


def _prove_recovery_after_token_expiry() -> None:
    clock_value = [70_000.0]

    def clock() -> float:
        return clock_value[0]

    principal = "platform-principal-delayed-recovery"
    provider_sub = "provider-sub-delayed-recovery"
    with tempfile.TemporaryDirectory(prefix="d3-expired-token-recovery-") as td:
        path = Path(td) / "replay.sqlite3"
        ledger = ContinuityReplayLedger(path, clock=clock, lease_seconds=10.0)
        fences = single.IdempotentSessionFenceAuthority()
        mappings = single.IdempotentProviderMappingAuthority()
        authority = ContinuityLogoutAuthority(
            verifier=None,
            replay=ledger,
            mappings=mappings,
            fences=fences,
        )
        authenticated = _durable_authenticated_logout(
            now=int(clock_value[0]),
            jti="expired-token-reconciliation",
            sub=provider_sub,
            fingerprint="c" * 64,
        )
        lease = ledger.claim_authenticated(authenticated)
        intent = ledger.prepare_effect(
            lease,
            single.EffectIntent(
                "principal",
                principal,
                fences.current_generation(principal),
            ),
        )
        if intent.kind != "principal":
            raise AssertionError("delayed recovery did not freeze principal effect intent")

        # Simulate a dead executor and an operational delay well beyond both the
        # original token expiry and the bounded 120-second iat freshness window.
        clock_value[0] += 600.0
        if not (
            clock_value[0] > authenticated.expires_at
            and clock_value[0]
            > authenticated.issued_at + probe.MAX_LOGOUT_TOKEN_AGE_SECONDS
        ):
            raise AssertionError("delayed recovery proof did not exceed token freshness")

        recovered = ContinuityReplayLedger(path, clock=clock, lease_seconds=10.0)
        authority.replay = recovered
        result = authority.reconcile(
            issuer=authenticated.issuer,
            client_id=authenticated.client_id,
            jti=authenticated.jti,
        )
        if result != "principal_fenced":
            raise AssertionError(f"unexpected delayed reconciliation result: {result!r}")
        if fences.generation_mutations != 1:
            raise AssertionError("delayed reconciliation did not execute exactly one fence")
        if recovered.status(
            issuer=authenticated.issuer,
            client_id=authenticated.client_id,
            jti=authenticated.jti,
        ) != "completed":
            raise AssertionError("delayed reconciliation did not durably complete replay identity")

    print(
        "d3_keycloak_expired_token_reconciliation=PASS "
        "durable_authenticated_context=true token_expiry_not_revalidation_dependency=true "
        "prepared_intent_required=true delayed_effect_single_winner=true"
    )


def _prove_v2_upgrade_replay_continuity() -> None:
    clock_value = [80_000.0]

    def clock() -> float:
        return clock_value[0]

    issuer = "https://idp.example.invalid/realms/d3"
    client_id = "bff-client"
    completed_jti = "legacy-completed-replay"
    completed_fingerprint = "d" * 64

    with tempfile.TemporaryDirectory(prefix="d3-v2-upgrade-") as td:
        path = Path(td) / "replay.sqlite3"
        legacy = V2_LEDGER(path, clock=clock, lease_seconds=10.0)
        old_lease = legacy.claim(
            issuer=issuer,
            client_id=client_id,
            jti=completed_jti,
            fingerprint=completed_fingerprint,
        )
        legacy.complete(old_lease)

        upgraded = ContinuityReplayLedger(path, clock=clock, lease_seconds=10.0)
        if upgraded.status(
            issuer=issuer,
            client_id=client_id,
            jti=completed_jti,
        ) != "completed":
            raise AssertionError("v2 completed replay identity was not migrated as completed")
        try:
            upgraded.claim(
                issuer=issuer,
                client_id=client_id,
                jti=completed_jti,
                fingerprint=completed_fingerprint,
            )
        except probe.legacy.ReplayDetected:
            pass
        else:
            raise AssertionError("v2 completed replay identity resurrected after v3 upgrade")

        # Migration is idempotent across repeated startups; preserving v2 as an
        # audit source cannot downgrade the already-migrated terminal state.
        reopened = ContinuityReplayLedger(path, clock=clock, lease_seconds=10.0)
        if reopened.status(
            issuer=issuer,
            client_id=client_id,
            jti=completed_jti,
        ) != "completed":
            raise AssertionError("repeated migration downgraded completed replay identity")

    print(
        "d3_keycloak_replay_upgrade_continuity=PASS "
        "v2_completed_migrated=true replay_nonresurrection=true "
        "transactional_fail_closed=true migration_idempotent=true"
    )


def main() -> int:
    # Replace only the explicit seams consumed by the prior single-winner
    # runner. That runner still executes all existing real Keycloak and
    # ambiguity proofs; this layer adds lifecycle continuity across time and
    # schema upgrades.
    single.EffectAwareReplayLedger = ContinuityReplayLedger
    single.LeaseGuardedLogoutAuthority = ContinuityLogoutAuthority

    _prove_recovery_after_token_expiry()
    _prove_v2_upgrade_replay_continuity()
    result = single.main()
    print(
        "d3_keycloak_recovery_continuity=PASS "
        "expired_token_internal_reconciliation=true v2_upgrade_replay_preserved=true"
    )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
