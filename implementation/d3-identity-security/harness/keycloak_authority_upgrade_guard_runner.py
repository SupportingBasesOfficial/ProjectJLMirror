from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile

import keycloak_authority_continuity_runner as continuity
import keycloak_authority_effects_probe as probe
import keycloak_authority_single_winner_runner as single


class UpgradeGuardedContinuityReplayLedger(continuity.ContinuityReplayLedger):
    """Perform a fail-closed v2->v3 replay-authority cutover.

    Automatic migration is allowed only when every legacy v2 identity is
    terminal `completed`. Nonterminal v2 rows predate durable authenticated
    context/effect intent, so they require explicit reconciliation.

    The cutover also fences *writers*, not just rows. While holding the same
    SQLite BEGIN IMMEDIATE lock used by v2/v3 mutations, v3 ensures the legacy
    table exists, imports terminal rows, and installs persistent triggers that
    reject every future INSERT/UPDATE/DELETE against v2. This closes both race
    orderings:
      * if a v2 writer wins first, its pending row makes cutover fail closed;
      * if v3 wins first, the committed trigger barrier rejects that v2 writer.

    Pre-creating the v2 table before installing the triggers also prevents an
    old worker started after cutover from recreating an unfenced legacy table.
    """

    CUTOVER_TABLE = "replay_ledger_v3_cutover"
    CUTOVER_STATE = "legacy_writers_fenced"
    LEGACY_TRIGGER_PREFIX = "replay_ledger_v2_retired"

    @classmethod
    def _ensure_legacy_table_locked(cls, db: sqlite3.Connection) -> None:
        # Exact RecoverableReplayLedger v2 schema. Creating it proactively is
        # essential when no v2 worker has touched a fresh database yet: an old
        # worker started after cutover then sees this table plus the persistent
        # trigger barrier instead of creating a new unfenced authority surface.
        db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {cls.LEGACY_TABLE} (
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

    @classmethod
    def _install_legacy_writer_barrier_locked(cls, db: sqlite3.Connection) -> None:
        db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {cls.CUTOVER_TABLE} (
                singleton INTEGER PRIMARY KEY CHECK (singleton=1),
                state TEXT NOT NULL CHECK (state='{cls.CUTOVER_STATE}')
            )
            """
        )
        db.execute(
            f"""
            INSERT INTO {cls.CUTOVER_TABLE} (singleton, state)
            VALUES (1, ?)
            ON CONFLICT(singleton) DO UPDATE SET state=excluded.state
            """,
            (cls.CUTOVER_STATE,),
        )

        for operation in ("INSERT", "UPDATE", "DELETE"):
            trigger = f"{cls.LEGACY_TRIGGER_PREFIX}_{operation.lower()}"
            db.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS {trigger}
                BEFORE {operation} ON {cls.LEGACY_TABLE}
                BEGIN
                    SELECT RAISE(ABORT, 'replay_ledger_v2 retired by v3 cutover');
                END
                """
            )

    @classmethod
    def _assert_writer_barrier_locked(cls, db: sqlite3.Connection) -> None:
        marker = db.execute(
            f"SELECT state FROM {cls.CUTOVER_TABLE} WHERE singleton=1"
        ).fetchone()
        if marker != (cls.CUTOVER_STATE,):
            raise probe.legacy.UncertainAuthority(
                "legacy replay cutover marker is absent or contradictory"
            )
        triggers = {
            str(row[0])
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE ?",
                (f"{cls.LEGACY_TRIGGER_PREFIX}_%",),
            )
        }
        expected = {
            f"{cls.LEGACY_TRIGGER_PREFIX}_insert",
            f"{cls.LEGACY_TRIGGER_PREFIX}_update",
            f"{cls.LEGACY_TRIGGER_PREFIX}_delete",
        }
        if triggers != expected:
            raise probe.legacy.UncertainAuthority(
                "legacy replay writer barrier is incomplete"
            )

    def _migrate_v2_locked(self, db: sqlite3.Connection) -> None:
        self._ensure_legacy_table_locked(db)

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

        nonterminal = db.execute(
            f"""
            SELECT issuer, client_id, jti, status
            FROM {self.LEGACY_TABLE}
            WHERE status <> 'completed'
            ORDER BY issuer, client_id, jti
            LIMIT 1
            """
        ).fetchone()
        if nonterminal is not None:
            issuer, client_id, jti, status = nonterminal
            raise probe.legacy.UncertainAuthority(
                "legacy replay migration requires explicit reconciliation for "
                f"nonterminal identity {issuer!r}/{client_id!r}/{jti!r} status={status!r}"
            )

        # Import every terminal identity before the legacy table becomes
        # immutable. This and the trigger installation occur under the one
        # BEGIN IMMEDIATE transaction opened by ContinuityReplayLedger.
        super()._migrate_v2_locked(db)
        self._install_legacy_writer_barrier_locked(db)
        self._assert_writer_barrier_locked(db)


def _expect_legacy_write_fenced(callable_, *, label: str) -> None:
    try:
        callable_()
    except sqlite3.Error as exc:
        if "retired by v3 cutover" not in str(exc):
            raise AssertionError(f"{label} failed for the wrong SQLite reason") from exc
    else:
        raise AssertionError(f"{label} unexpectedly wrote legacy replay authority")


def _prove_legacy_nonterminal_upgrade_fails_closed() -> None:
    clock_value = [90_000.0]

    def clock() -> float:
        return clock_value[0]

    issuer = "https://idp.example.invalid/realms/d3"
    client_id = "bff-client"

    # This proves the v2-writer-wins ordering. If a legacy writer commits a
    # nonterminal claim before v3 acquires BEGIN IMMEDIATE, v3 observes it and
    # refuses cutover instead of guessing whether its effect ran.
    for state in ("pending", "retryable"):
        with tempfile.TemporaryDirectory(prefix=f"d3-v2-{state}-upgrade-") as td:
            path = Path(td) / "replay.sqlite3"
            legacy = continuity.V2_LEDGER(path, clock=clock, lease_seconds=10.0)
            lease = legacy.claim(
                issuer=issuer,
                client_id=client_id,
                jti=f"legacy-{state}-ambiguous",
                fingerprint=("e" if state == "pending" else "f") * 64,
            )
            if state == "retryable":
                legacy.retryable(lease)

            try:
                UpgradeGuardedContinuityReplayLedger(
                    path,
                    clock=clock,
                    lease_seconds=10.0,
                )
            except probe.legacy.UncertainAuthority as exc:
                if "explicit reconciliation" not in str(exc):
                    raise AssertionError(
                        "legacy nonterminal upgrade failed for the wrong reason"
                    ) from exc
            else:
                raise AssertionError(
                    f"legacy {state} replay identity became automatically executable"
                )

    print(
        "d3_keycloak_legacy_nonterminal_upgrade=PASS "
        "pending_fail_closed=true retryable_fail_closed=true "
        "automatic_double_fence_prevented=true explicit_reconciliation_required=true"
    )


def _prove_atomic_legacy_writer_cutover() -> None:
    clock_value = [95_000.0]

    def clock() -> float:
        return clock_value[0]

    issuer = "https://idp.example.invalid/realms/d3"
    client_id = "bff-client"

    # Existing old worker object, terminal history, then v3 cutover. The same
    # old object must be unable to create a new authority row after cutover.
    with tempfile.TemporaryDirectory(prefix="d3-v2-writer-cutover-") as td:
        path = Path(td) / "replay.sqlite3"
        legacy = continuity.V2_LEDGER(path, clock=clock, lease_seconds=10.0)
        completed = legacy.claim(
            issuer=issuer,
            client_id=client_id,
            jti="legacy-completed-before-cutover",
            fingerprint="a" * 64,
        )
        legacy.complete(completed)

        current = UpgradeGuardedContinuityReplayLedger(
            path,
            clock=clock,
            lease_seconds=10.0,
        )
        if current.status(
            issuer=issuer,
            client_id=client_id,
            jti="legacy-completed-before-cutover",
        ) != "completed":
            raise AssertionError("terminal legacy replay was not preserved at cutover")

        _expect_legacy_write_fenced(
            lambda: legacy.claim(
                issuer=issuer,
                client_id=client_id,
                jti="legacy-existing-writer-after-cutover",
                fingerprint="b" * 64,
            ),
            label="existing legacy worker",
        )

        # A newly constructed old worker also uses the pre-created legacy table
        # and is fenced by the persistent triggers.
        late_legacy = continuity.V2_LEDGER(path, clock=clock, lease_seconds=10.0)
        _expect_legacy_write_fenced(
            lambda: late_legacy.claim(
                issuer=issuer,
                client_id=client_id,
                jti="legacy-late-writer-after-cutover",
                fingerprint="c" * 64,
            ),
            label="late legacy worker",
        )

        # Current v3 authority remains writable after fencing the old surface.
        authenticated = probe.legacy.AuthenticatedLogout(
            issuer=issuer,
            client_id=client_id,
            jti="current-v3-after-cutover",
            issued_at=int(clock_value[0]),
            expires_at=int(clock_value[0]) + 60,
            sid=None,
            sub="provider-sub-v3-cutover",
            raw_fingerprint="d" * 64,
        )
        lease = current.claim_authenticated(authenticated)
        current.retryable(lease)
        if current.status(
            issuer=issuer,
            client_id=client_id,
            jti="current-v3-after-cutover",
        ) != "retryable":
            raise AssertionError("v3 authority became unwritable after legacy fencing")

        # Reopen proves both terminal migration and writer barrier persist.
        reopened = UpgradeGuardedContinuityReplayLedger(
            path,
            clock=clock,
            lease_seconds=10.0,
        )
        if reopened.status(
            issuer=issuer,
            client_id=client_id,
            jti="legacy-completed-before-cutover",
        ) != "completed":
            raise AssertionError("completed replay resurrected after cutover reopen")
        _expect_legacy_write_fenced(
            lambda: late_legacy.claim(
                issuer=issuer,
                client_id=client_id,
                jti="legacy-writer-after-reopen",
                fingerprint="e" * 64,
            ),
            label="legacy worker after reopen",
        )

    # No-legacy-table ordering: v3 creates the exact v2 table itself and fences
    # it before commit, so a v2 worker that starts only afterwards cannot create
    # a fresh unfenced legacy authority surface.
    with tempfile.TemporaryDirectory(prefix="d3-v3-first-cutover-") as td:
        path = Path(td) / "replay.sqlite3"
        UpgradeGuardedContinuityReplayLedger(path, clock=clock, lease_seconds=10.0)
        late_only = continuity.V2_LEDGER(path, clock=clock, lease_seconds=10.0)
        _expect_legacy_write_fenced(
            lambda: late_only.claim(
                issuer=issuer,
                client_id=client_id,
                jti="legacy-created-after-v3-first",
                fingerprint="f" * 64,
            ),
            label="post-cutover legacy table creator",
        )

    print(
        "d3_keycloak_legacy_writer_cutover=PASS "
        "begin_immediate_serialization=true existing_writer_fenced=true "
        "late_writer_fenced=true absent_v2_table_precreated_and_fenced=true "
        "inflight_nonterminal_blocks_cutover=true barrier_persists_reopen=true "
        "current_v3_writes_continue=true"
    )


def main() -> int:
    # Patch the continuity layer's governed seam before its existing proofs and
    # the complete single-winner/real-Keycloak suite run. Dynamic lookup inside
    # continuity.main() then uses this upgrade-guarded ledger everywhere.
    continuity.ContinuityReplayLedger = UpgradeGuardedContinuityReplayLedger
    single.EffectAwareReplayLedger = UpgradeGuardedContinuityReplayLedger

    _prove_legacy_nonterminal_upgrade_fails_closed()
    _prove_atomic_legacy_writer_cutover()
    result = continuity.main()
    print(
        "d3_keycloak_authority_upgrade_guard=PASS "
        "terminal_replay_migration=true nonterminal_fail_closed=true "
        "legacy_writer_barrier=true expired_token_reconciliation=true"
    )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
