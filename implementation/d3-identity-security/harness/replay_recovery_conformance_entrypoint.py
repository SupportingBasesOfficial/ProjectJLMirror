#!/usr/bin/env python3
from __future__ import annotations

import os

import replay_recovery_conformance_runner as core


def prove_whole_restore_strict(
    port: core.ReplayAuthorityPort,
    witness: core.RecoveryWitnessPort,
) -> None:
    """Exercise a rollback of the complete PostgreSQL replay authority.

    The PostgreSQL snapshot deliberately contains the old local recovery fence.
    The trusted recovery witness is outside that rollback domain. After restore,
    the stale DB must therefore be unable to self-certify admission even though
    its own local fence says epoch 1 is reconciled.
    """
    op = "restore-post-r-effect"
    core.prepare_redrive(op, 1)
    assert core.claim(op, "restore-worker", "restore-token", 1) == "1"

    stale_dump = core.whole_database_dump()

    assert port.consume(
        "restore-client",
        "restore-jti",
        "restore-fp",
        "restore-session-effect",
        "restore-session-result",
        1,
    ) == "WIN"
    provider_effect = core.provider_send(
        op,
        1,
        "restore-token",
        "restore-provider-effect",
        "restore-provider-result",
    )
    assert provider_effect["outcome"] == "WIN"
    assert core.complete_provider(
        op,
        1,
        "restore-provider-result",
        provider_effect["revision"],
    )

    core.capture_recovery_boundary(witness, next_epoch=2, ops=[op])
    assert port.consume(
        "post-f-client",
        "post-f-jti",
        "post-f-fp",
        "post-f-effect",
        "post-f-result",
        1,
    ) == "BLOCKED"

    core.restore_whole_database(stale_dump)

    # The rollback really removed the post-snapshot consumed identity and rolled
    # the DB-local fence back. Do not rely on psql's abbreviated t/f display:
    # explicit text conversion is true/false in PostgreSQL expressions.
    assert core.psql(
        "SELECT count(*) FROM d3e_replay.replay_identity WHERE jti='restore-jti';"
    ) == "0"
    assert core.psql(
        "SELECT epoch FROM d3e_replay.recovery_fence WHERE singleton=TRUE;"
    ) == "1"
    assert core.psql(
        "SELECT reconciled::text FROM d3e_replay.recovery_fence WHERE singleton=TRUE;"
    ) == "true"

    surviving = witness.read()
    assert surviving["epoch"] == 2
    assert surviving["admission_open"] is False
    assert surviving["boundary"] == "F-2"

    # A stale epoch-1 caller must lose to the external witness even though the
    # restored DB-local fence looks healthy. The epoch-2 caller is also closed
    # until reconciliation has rehydrated the consumed identities/outcomes.
    assert port.consume(
        "restore-client",
        "restore-jti",
        "restore-fp",
        "restore-session-effect",
        "restore-session-result",
        1,
    ) == "BLOCKED"
    assert port.consume(
        "restore-client",
        "restore-jti",
        "restore-fp",
        "restore-session-effect",
        "restore-session-result",
        2,
    ) == "BLOCKED"

    saved = witness.path.with_suffix(".saved")
    os.replace(witness.path, saved)
    try:
        assert port.consume(
            "missing-witness",
            "mw-jti",
            "mw-fp",
            "mw-effect",
            "mw-result",
            2,
        ) == "BLOCKED"
        try:
            core.recover_from_witness(witness)
        except RuntimeError:
            pass
        else:
            raise AssertionError("recovery opened without surviving continuity witness")
    finally:
        os.replace(saved, witness.path)

    core.recover_from_witness(witness)
    assert port.consume(
        "restore-client",
        "restore-jti",
        "restore-fp",
        "restore-session-effect",
        "restore-session-result",
        2,
    ) == "OBSERVE"
    assert port.consume(
        "restore-client",
        "restore-jti",
        "restore-fp",
        "restore-session-effect",
        "restore-session-result",
        1,
    ) == "BLOCKED"
    assert core.psql(
        f"SELECT state||'|'||attempt_generation FROM d3e_replay.redrive "
        f"WHERE operation_id={core.lit(op)};"
    ) == "completed|1"
    assert core.provider_status(op)["effect"]["effect_id"] == "restore-provider-effect"

    print(
        "d3_e_replay_consumed_identity_survives_restore_loss=PASS "
        "whole_database_restore=true rollback_includes_local_control=true "
        "rollback_local_epoch=1 surviving_external_epoch=2 "
        "surviving_recovery_witness_external_to_snapshot=true stale_epoch_callers_fenced=true "
        "missing_witness_fail_closed=true consumed_identity_rehydrated=true "
        "ambiguous_external_effect_reconciled=true confirmed_effect_not_repeated=true"
    )


def main() -> None:
    if core.WITNESS_PATH.exists():
        core.WITNESS_PATH.unlink()
    if core.PROVIDER_STATE.exists():
        core.PROVIDER_STATE.unlink()

    provider_proc = core.subprocess.Popen(
        [core.sys.executable, core.__file__, "--provider-server"],
        stdout=core.subprocess.DEVNULL,
        stderr=core.subprocess.DEVNULL,
    )
    try:
        core.wait_provider()
        core.init_db()
        witness = core.RecoveryWitnessPort()
        witness.initialize()
        port = core.ReplayAuthorityPort(witness)

        core.prove_single_winner(port)
        core.prove_duplicate_recovery_gate_order(port)
        core.prove_partition()
        core.prove_redrive_external_boundary()
        core.prove_absence_effect_race()
        prove_whole_restore_strict(port, witness)

        print(
            "d3_e_replay_redrive_conformance=PASS postgres_replay_truth=true "
            "recovery_witness_recovery_only=true single_winner=true partition_fail_closed=true "
            "external_effect_network_boundary=true whole_restore_nonresurrection=true "
            "c3_numerics_not_selected=true topology_not_selected=true"
        )
        print(
            "d3_e_replay_recovery_entrypoint=PASS "
            "stale_db_cannot_self_certify=true external_recovery_epoch_wins=true"
        )
    finally:
        provider_proc.terminate()
        try:
            provider_proc.wait(timeout=3)
        except core.subprocess.TimeoutExpired:
            provider_proc.kill()


if __name__ == "__main__":
    main()
