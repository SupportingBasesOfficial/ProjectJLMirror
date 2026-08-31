from __future__ import annotations

from pathlib import Path
import tempfile

import keycloak_authority_continuity_runner as continuity
import keycloak_authority_effects_probe as probe
import keycloak_authority_single_winner_runner as single


class UpgradeGuardedContinuityReplayLedger(continuity.ContinuityReplayLedger):
    """Permit automatic v2 migration only for terminal replay identities.

    A v2 `completed` row is unambiguous negative authority: that replay identity
    must remain permanently consumed, so it can be imported transactionally.

    A v2 `pending` or `retryable` row predates durable authenticated context and
    immutable effect intent. After process/schema upgrade we cannot prove
    whether its authority effect was absent, partially applied, or applied just
    before a crash. Automatically making such a row executable could double
    fence; discarding it could lose a legitimate logout. Startup therefore
    fails closed and requires an explicit reconciliation/migration decision
    outside this automatic evidence path.
    """

    def _migrate_v2_locked(self, db) -> None:
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

        super()._migrate_v2_locked(db)


def _prove_legacy_nonterminal_upgrade_fails_closed() -> None:
    clock_value = [90_000.0]

    def clock() -> float:
        return clock_value[0]

    issuer = "https://idp.example.invalid/realms/d3"
    client_id = "bff-client"

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


def main() -> int:
    # Patch the continuity layer's governed seam before its existing proofs and
    # the complete single-winner/real-Keycloak suite run. Dynamic lookup inside
    # continuity.main() then uses this upgrade-guarded ledger everywhere.
    continuity.ContinuityReplayLedger = UpgradeGuardedContinuityReplayLedger
    single.EffectAwareReplayLedger = UpgradeGuardedContinuityReplayLedger

    _prove_legacy_nonterminal_upgrade_fails_closed()
    result = continuity.main()
    print(
        "d3_keycloak_authority_upgrade_guard=PASS "
        "terminal_replay_migration=true nonterminal_fail_closed=true "
        "expired_token_reconciliation=true"
    )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
