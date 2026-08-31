from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
import tempfile
import threading
import time

import keycloak_authority_effects_probe as probe


DEFAULT_EFFECT_LEASE_SECONDS = probe.DEFAULT_REPLAY_CLAIM_LEASE_SECONDS


@dataclass(frozen=True)
class EffectIntent:
    kind: str
    target: str | None
    expected_generation: int | None

    def __post_init__(self) -> None:
        if self.kind == "sid":
            if not isinstance(self.target, str) or not self.target or self.expected_generation is not None:
                raise ValueError("sid effect intent requires only one exact local-session target")
            return
        if self.kind == "principal":
            if (
                not isinstance(self.target, str)
                or not self.target
                or not isinstance(self.expected_generation, int)
                or self.expected_generation < 1
            ):
                raise ValueError("principal effect intent requires target and positive expected generation")
            return
        if self.kind == "none":
            if self.target is not None or self.expected_generation is not None:
                raise ValueError("confirmed-absence intent cannot carry an authority target")
            return
        raise ValueError(f"unsupported logout effect intent: {self.kind!r}")


class EffectAwareReplayLedger:
    """Durable replay claim plus immutable recoverable authority-effect intent.

    Claim ownership is a lease. Before any authority mutation the current owner
    must renew that lease. The intended effect is durably frozen before the
    mutation, so takeover after an ambiguous crash replays the same target and
    the same expected principal generation instead of resolving fresh authority
    and accidentally widening or repeating the effect.
    """

    TABLE = "replay_ledger_v3"

    def __init__(
        self,
        path: Path,
        *,
        clock=time.time,
        lease_seconds: float = DEFAULT_EFFECT_LEASE_SECONDS,
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
                    effect_kind TEXT CHECK (effect_kind IN ('sid','principal','none') OR effect_kind IS NULL),
                    effect_target TEXT,
                    effect_generation INTEGER,
                    PRIMARY KEY (issuer, client_id, jti),
                    CHECK (
                        (status='pending' AND owner IS NOT NULL AND lease_until IS NOT NULL)
                        OR
                        (status IN ('retryable','completed') AND owner IS NULL AND lease_until IS NULL)
                    ),
                    CHECK (
                        (effect_kind IS NULL AND effect_target IS NULL AND effect_generation IS NULL)
                        OR
                        (effect_kind='sid' AND effect_target IS NOT NULL AND effect_generation IS NULL)
                        OR
                        (effect_kind='principal' AND effect_target IS NOT NULL AND effect_generation IS NOT NULL)
                        OR
                        (effect_kind='none' AND effect_target IS NULL AND effect_generation IS NULL)
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
    ) -> probe.legacy.ReplayLease:
        owner = probe.secrets.token_hex(16)
        now = float(self._clock())
        lease_until = now + self._lease_seconds
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                f"""
                SELECT fingerprint, status, lease_until
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
                existing_fingerprint, status, existing_lease_until = row
                if existing_fingerprint != fingerprint:
                    raise probe.legacy.ReplayDetected(
                        "same replay identity arrived with different token bytes"
                    )
                if status == "completed":
                    raise probe.legacy.ReplayDetected("completed logout replay rejected")
                if status == "pending":
                    if not isinstance(existing_lease_until, (int, float)):
                        raise probe.legacy.UncertainAuthority(
                            "pending replay claim lacks recoverable lease boundary"
                        )
                    if float(existing_lease_until) > now:
                        raise probe.legacy.ReplayDetected("live in-progress logout replay rejected")
                    cursor = db.execute(
                        f"""
                        UPDATE {self.TABLE}
                        SET owner=?, lease_until=?
                        WHERE issuer=? AND client_id=? AND jti=?
                          AND fingerprint=? AND status='pending' AND lease_until<=?
                        """,
                        (owner, lease_until, issuer, client_id, jti, fingerprint, now),
                    )
                    if cursor.rowcount != 1:
                        raise probe.legacy.ReplayDetected(
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
                        (owner, lease_until, issuer, client_id, jti, fingerprint),
                    )
                    if cursor.rowcount != 1:
                        raise probe.legacy.ReplayDetected("retry lease lost single-winner claim")
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

    def prepared_effect(self, lease: probe.legacy.ReplayLease) -> EffectIntent | None:
        now = float(self._clock())
        with self._connect() as db:
            row = db.execute(
                f"""
                SELECT status, owner, lease_until, effect_kind, effect_target, effect_generation
                FROM {self.TABLE}
                WHERE issuer=? AND client_id=? AND jti=?
                """,
                (lease.issuer, lease.client_id, lease.jti),
            ).fetchone()
        if row is None:
            raise probe.legacy.UncertainAuthority("replay claim disappeared before effect preparation")
        status, owner, lease_until, kind, target, generation = row
        if status != "pending" or owner != lease.owner:
            raise probe.legacy.UncertainAuthority("replay executor lost claim ownership")
        if not isinstance(lease_until, (int, float)) or float(lease_until) <= now:
            raise probe.legacy.UncertainAuthority("replay executor lease expired before effect preparation")
        if kind is None:
            return None
        return EffectIntent(str(kind), target, generation)

    def prepare_effect(self, lease: probe.legacy.ReplayLease, intent: EffectIntent) -> EffectIntent:
        now = float(self._clock())
        renewed_until = now + self._lease_seconds
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                f"""
                SELECT status, owner, lease_until, effect_kind, effect_target, effect_generation
                FROM {self.TABLE}
                WHERE issuer=? AND client_id=? AND jti=?
                """,
                (lease.issuer, lease.client_id, lease.jti),
            ).fetchone()
            if row is None:
                raise probe.legacy.UncertainAuthority("replay claim disappeared before effect intent")
            status, owner, lease_until, kind, target, generation = row
            if status != "pending" or owner != lease.owner:
                raise probe.legacy.UncertainAuthority("replay executor lost ownership before effect intent")
            if not isinstance(lease_until, (int, float)) or float(lease_until) <= now:
                raise probe.legacy.UncertainAuthority("replay executor lease expired before effect intent")

            existing = None if kind is None else EffectIntent(str(kind), target, generation)
            if existing is None:
                cursor = db.execute(
                    f"""
                    UPDATE {self.TABLE}
                    SET effect_kind=?, effect_target=?, effect_generation=?, lease_until=?
                    WHERE issuer=? AND client_id=? AND jti=?
                      AND status='pending' AND owner=? AND lease_until>?
                      AND effect_kind IS NULL
                    """,
                    (
                        intent.kind,
                        intent.target,
                        intent.expected_generation,
                        renewed_until,
                        lease.issuer,
                        lease.client_id,
                        lease.jti,
                        lease.owner,
                        now,
                    ),
                )
                if cursor.rowcount != 1:
                    raise probe.legacy.UncertainAuthority(
                        "effect intent preparation lost current-owner race"
                    )
                existing = intent
            elif existing != intent:
                raise probe.legacy.UncertainAuthority(
                    "durable logout effect intent contradicts recomputed authority"
                )
            else:
                cursor = db.execute(
                    f"""
                    UPDATE {self.TABLE}
                    SET lease_until=?
                    WHERE issuer=? AND client_id=? AND jti=?
                      AND status='pending' AND owner=? AND lease_until>?
                    """,
                    (
                        renewed_until,
                        lease.issuer,
                        lease.client_id,
                        lease.jti,
                        lease.owner,
                        now,
                    ),
                )
                if cursor.rowcount != 1:
                    raise probe.legacy.UncertainAuthority(
                        "effect intent renewal lost current-owner race"
                    )
            db.execute("COMMIT")
            return existing
        except Exception:
            try:
                db.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            db.close()

    def renew_for_effect(self, lease: probe.legacy.ReplayLease) -> None:
        now = float(self._clock())
        renewed_until = now + self._lease_seconds
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            cursor = db.execute(
                f"""
                UPDATE {self.TABLE}
                SET lease_until=?
                WHERE issuer=? AND client_id=? AND jti=?
                  AND status='pending' AND owner=? AND lease_until>?
                  AND effect_kind IS NOT NULL
                """,
                (
                    renewed_until,
                    lease.issuer,
                    lease.client_id,
                    lease.jti,
                    lease.owner,
                    now,
                ),
            )
            if cursor.rowcount != 1:
                db.execute("ROLLBACK")
                raise probe.legacy.UncertainAuthority(
                    "replay executor is stale or effect intent is not durably prepared"
                )
            db.execute("COMMIT")

    def _transition(self, lease: probe.legacy.ReplayLease, target: str) -> None:
        if target not in {"retryable", "completed"}:
            raise ValueError("invalid replay transition target")
        now = float(self._clock())
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            cursor = db.execute(
                f"""
                UPDATE {self.TABLE}
                SET status=?, owner=NULL, lease_until=NULL
                WHERE issuer=? AND client_id=? AND jti=?
                  AND status='pending' AND owner=? AND lease_until>?
                """,
                (
                    target,
                    lease.issuer,
                    lease.client_id,
                    lease.jti,
                    lease.owner,
                    now,
                ),
            )
            if cursor.rowcount != 1:
                raise AssertionError(
                    "replay lease transition lost live current ownership or was superseded"
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

    def complete(self, lease: probe.legacy.ReplayLease) -> None:
        self._transition(lease, "completed")

    def retryable(self, lease: probe.legacy.ReplayLease) -> None:
        self._transition(lease, "retryable")

    def status(self, *, issuer: str, client_id: str, jti: str) -> str | None:
        with self._connect() as db:
            row = db.execute(
                f"SELECT status FROM {self.TABLE} WHERE issuer=? AND client_id=? AND jti=?",
                (issuer, client_id, jti),
            ).fetchone()
        return None if row is None else str(row[0])


class IdempotentSessionFenceAuthority(probe.legacy.SessionFenceAuthority):
    """Monotonic local authority effects with replay-safe compare-and-set semantics."""

    def __init__(self) -> None:
        super().__init__()
        self._effect_lock = threading.RLock()

    def current_generation(self, principal_id: str) -> int:
        with self._effect_lock:
            return self.principal_generations.setdefault(principal_id, 1)

    def create(self, *, session_id: str, principal_id: str) -> probe.legacy.LocalSession:
        with self._effect_lock:
            return probe.legacy.LocalSession(
                session_id=session_id,
                principal_id=principal_id,
                principal_generation=self.principal_generations.setdefault(principal_id, 1),
            )

    def retire_exact_if_current(self, session_id: str) -> bool:
        with self._effect_lock:
            if session_id in self.retired_sessions:
                return False
            self.retired_sessions.add(session_id)
            self.sid_retire_mutations += 1
            return True

    def retire_exact(self, session_id: str) -> None:
        self.retire_exact_if_current(session_id)

    def fence_principal_if_generation(self, principal_id: str, expected_generation: int) -> bool:
        with self._effect_lock:
            current = self.principal_generations.setdefault(principal_id, 1)
            if current < expected_generation:
                raise probe.legacy.UncertainAuthority(
                    "principal generation regressed below durable logout effect intent"
                )
            if current > expected_generation:
                return False
            self.principal_generations[principal_id] = expected_generation + 1
            self.generation_mutations += 1
            return True

    def fence_principal(self, principal_id: str) -> None:
        with self._effect_lock:
            current = self.principal_generations.setdefault(principal_id, 1)
            self.principal_generations[principal_id] = current + 1
            self.generation_mutations += 1

    def current(self, session: probe.legacy.LocalSession) -> bool:
        with self._effect_lock:
            current_generation = self.principal_generations.setdefault(session.principal_id, 1)
            return (
                session.session_id not in self.retired_sessions
                and session.principal_generation == current_generation
            )


class IdempotentProviderMappingAuthority(probe.StrictProviderMappingAuthority):
    """Keep historical SID binding immutable while making retirement replay-idempotent."""

    def retire_prepared_sid(
        self,
        *,
        authenticated: probe.legacy.AuthenticatedLogout,
        expected_local_session_id: str,
    ) -> None:
        if authenticated.sid is None:
            raise probe.legacy.UncertainAuthority("prepared sid effect lost authenticated sid")
        key = (authenticated.issuer, authenticated.client_id, authenticated.sid)
        current = self.sid_bindings.get(key)
        if not isinstance(current, probe.legacy.ProviderSessionBinding):
            raise probe.legacy.UncertainAuthority("historical provider sid binding disappeared")
        if authenticated.sub is not None and current.sub != authenticated.sub:
            raise probe.legacy.UncertainAuthority("prepared sid effect encountered contradictory subject")
        if current.local_session_id != expected_local_session_id:
            raise probe.legacy.UncertainAuthority("prepared sid effect target drifted")
        if current.active:
            self.retire_sid(current)


class LeaseGuardedLogoutAuthority(probe.legacy.LogoutAuthority):
    """Execute only a live lease's immutable intent; reconcile ambiguous outcomes idempotently."""

    replay: EffectAwareReplayLedger
    mappings: IdempotentProviderMappingAuthority
    fences: IdempotentSessionFenceAuthority

    def _intent_from_resolution(
        self,
        resolved: probe.legacy.ProviderSessionBinding | str | None,
    ) -> EffectIntent:
        if isinstance(resolved, probe.legacy.ProviderSessionBinding):
            return EffectIntent("sid", resolved.local_session_id, None)
        if isinstance(resolved, str):
            return EffectIntent(
                "principal",
                resolved,
                self.fences.current_generation(resolved),
            )
        if resolved is None:
            return EffectIntent("none", None, None)
        raise probe.legacy.UncertainAuthority("provider mapping returned non-canonical resolution")

    def _apply_effect_intent(
        self,
        *,
        authenticated: probe.legacy.AuthenticatedLogout,
        intent: EffectIntent,
    ) -> str:
        if intent.kind == "sid":
            if intent.target is None:
                raise probe.legacy.UncertainAuthority("prepared sid effect lost exact session target")
            self.fences.retire_exact_if_current(intent.target)
            self.mappings.retire_prepared_sid(
                authenticated=authenticated,
                expected_local_session_id=intent.target,
            )
            return "sid_retired"
        if intent.kind == "principal":
            if authenticated.sid is not None or authenticated.sub is None:
                raise probe.legacy.UncertainAuthority(
                    "principal-wide prepared effect is not bound to a genuine sub-only logout"
                )
            if intent.target is None or intent.expected_generation is None:
                raise probe.legacy.UncertainAuthority("prepared principal effect is incomplete")
            self.fences.fence_principal_if_generation(
                intent.target,
                intent.expected_generation,
            )
            return "principal_fenced"
        if intent.kind == "none":
            return "confirmed_absent"
        raise probe.legacy.UncertainAuthority("prepared logout effect kind is unsupported")

    def _best_effort_retryable(self, lease: probe.legacy.ReplayLease) -> None:
        try:
            self.replay.retryable(lease)
        except (AssertionError, probe.legacy.UncertainAuthority):
            # A superseded/expired owner must not overwrite the new owner's durable state.
            return

    def handle(self, token: str) -> str:
        authenticated = self.verifier.verify(token)
        lease = self.replay.claim(
            issuer=authenticated.issuer,
            client_id=authenticated.client_id,
            jti=authenticated.jti,
            fingerprint=authenticated.raw_fingerprint,
        )
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
                # Recovery must consume the frozen intent instead of re-resolving
                # possibly newer subject/session placement.
                self.replay.prepare_effect(lease, intent)

            # This owner must still be live immediately before the local effect.
            # If takeover happens after renewal, the durable intent plus CAS/
            # idempotent mutation below makes either execution order converge.
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


def _synthetic_sub_logout(*, jti: str, principal_sub: str, fingerprint: str) -> probe.legacy.AuthenticatedLogout:
    now = int(time.time())
    return probe.legacy.AuthenticatedLogout(
        issuer="https://idp.example.invalid/realms/d3",
        client_id="bff-client",
        jti=jti,
        issued_at=now,
        expires_at=now + 60,
        sid=None,
        sub=principal_sub,
        raw_fingerprint=fingerprint,
    )


def _prove_stale_executor_cannot_double_fence() -> None:
    principal = "platform-principal-single-winner"

    # Case 1: owner A expires, owner B takes over and fences, then stale A reaches
    # the effect path. A cannot renew; even a worst-case late CAS cannot advance
    # the generation again or revoke a session created after B's legitimate fence.
    clock_value = [20_000.0]

    def clock() -> float:
        return clock_value[0]

    with tempfile.TemporaryDirectory(prefix="d3-effect-single-winner-") as td:
        path = Path(td) / "effect.sqlite3"
        ledger = EffectAwareReplayLedger(path, clock=clock, lease_seconds=10.0)
        fences = IdempotentSessionFenceAuthority()
        mappings = IdempotentProviderMappingAuthority()
        authority = LeaseGuardedLogoutAuthority(
            verifier=None,
            replay=ledger,
            mappings=mappings,
            fences=fences,
        )
        authenticated = _synthetic_sub_logout(
            jti="takeover-before-effect",
            principal_sub="provider-sub-single-winner",
            fingerprint="a" * 64,
        )
        lease_a = ledger.claim(
            issuer=authenticated.issuer,
            client_id=authenticated.client_id,
            jti=authenticated.jti,
            fingerprint=authenticated.raw_fingerprint,
        )
        intent = ledger.prepare_effect(
            lease_a,
            EffectIntent("principal", principal, fences.current_generation(principal)),
        )
        clock_value[0] += 11.0
        lease_b = ledger.claim(
            issuer=authenticated.issuer,
            client_id=authenticated.client_id,
            jti=authenticated.jti,
            fingerprint=authenticated.raw_fingerprint,
        )
        recovered_intent = ledger.prepared_effect(lease_b)
        if recovered_intent != intent:
            raise AssertionError("takeover did not preserve immutable effect intent")
        ledger.renew_for_effect(lease_b)
        authority._apply_effect_intent(authenticated=authenticated, intent=recovered_intent)
        post_fence_session = fences.create(
            session_id="post-fence-session",
            principal_id=principal,
        )
        if fences.generation_mutations != 1:
            raise AssertionError("legitimate takeover did not produce exactly one generation fence")

        try:
            ledger.renew_for_effect(lease_a)
        except probe.legacy.UncertainAuthority:
            pass
        else:
            raise AssertionError("superseded owner renewed effect authority after takeover")

        # Race backstop: if the old worker passed its lease check just before
        # takeover, replaying the same durable expected generation is a no-op.
        authority._apply_effect_intent(authenticated=authenticated, intent=intent)
        if fences.generation_mutations != 1 or not fences.current(post_fence_session):
            raise AssertionError("stale executor double-fenced post-logout session authority")
        ledger.complete(lease_b)

    # Case 2: A applies the effect but crashes before ledger completion. Recovery
    # reuses A's durable expected generation and observes the already-satisfied
    # monotonic fence rather than creating a second generation mutation.
    clock_value[0] = 30_000.0
    with tempfile.TemporaryDirectory(prefix="d3-effect-ambiguous-outcome-") as td:
        path = Path(td) / "effect.sqlite3"
        ledger = EffectAwareReplayLedger(path, clock=clock, lease_seconds=10.0)
        fences = IdempotentSessionFenceAuthority()
        mappings = IdempotentProviderMappingAuthority()
        authority = LeaseGuardedLogoutAuthority(
            verifier=None,
            replay=ledger,
            mappings=mappings,
            fences=fences,
        )
        authenticated = _synthetic_sub_logout(
            jti="crash-after-effect",
            principal_sub="provider-sub-ambiguous",
            fingerprint="b" * 64,
        )
        lease_a = ledger.claim(
            issuer=authenticated.issuer,
            client_id=authenticated.client_id,
            jti=authenticated.jti,
            fingerprint=authenticated.raw_fingerprint,
        )
        intent = ledger.prepare_effect(
            lease_a,
            EffectIntent("principal", principal, fences.current_generation(principal)),
        )
        ledger.renew_for_effect(lease_a)
        authority._apply_effect_intent(authenticated=authenticated, intent=intent)
        post_effect_session = fences.create(
            session_id="post-ambiguous-effect-session",
            principal_id=principal,
        )
        if fences.generation_mutations != 1:
            raise AssertionError("first ambiguous execution did not create exactly one fence")

        # No complete(): simulate crash after local authority mutation.
        clock_value[0] += 11.0
        recovered = EffectAwareReplayLedger(path, clock=clock, lease_seconds=10.0)
        lease_b = recovered.claim(
            issuer=authenticated.issuer,
            client_id=authenticated.client_id,
            jti=authenticated.jti,
            fingerprint=authenticated.raw_fingerprint,
        )
        recovered_intent = recovered.prepared_effect(lease_b)
        if recovered_intent != intent:
            raise AssertionError("ambiguous recovery changed durable effect intent")
        recovered.renew_for_effect(lease_b)
        authority.replay = recovered
        authority._apply_effect_intent(authenticated=authenticated, intent=recovered_intent)
        recovered.complete(lease_b)
        if fences.generation_mutations != 1 or not fences.current(post_effect_session):
            raise AssertionError("post-effect recovery repeated fence across ambiguous outcome")

    print(
        "d3_keycloak_effect_single_winner=PASS "
        "pre_effect_live_owner_required=true takeover_preserves_intent=true "
        "stale_race_cas_noop=true post_effect_recovery_idempotent=true "
        "newer_session_survives=true"
    )


def main() -> int:
    # Strengthen the existing authority harness only at explicit seams. The
    # underlying Keycloak/browser scenarios remain unchanged.
    probe.RecoverableReplayLedger = EffectAwareReplayLedger
    probe.StrictProviderMappingAuthority = IdempotentProviderMappingAuthority
    probe.legacy.LogoutAuthority = LeaseGuardedLogoutAuthority
    probe.legacy.SessionFenceAuthority = IdempotentSessionFenceAuthority

    _prove_stale_executor_cannot_double_fence()
    result = probe.main()
    print(
        "d3_keycloak_authority_single_winner_runner=PASS "
        "durable_effect_intent=true live_owner_gate=true effect_cas=true ambiguous_recovery=true"
    )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
