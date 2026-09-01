#!/usr/bin/env python3
"""Final D3-E recovery transition hardening.

This layer makes witness-open/database-closed a retryable recovery state and
loads the canonical provider capability patch before any provider process starts.
"""
from __future__ import annotations

import replay_recovery_conformance_runner as core
import replay_recovery_boundary_hardening as boundary
import replay_recovery_provider_capability_hardening as provider_capability
import replay_recovery_capability_binding as base


def _read_epoch(payload: dict) -> int:
    try:
        epoch = int(payload["epoch"])
    except Exception as exc:
        raise RuntimeError("recovery witness epoch is malformed") from exc
    if epoch <= 0:
        raise RuntimeError("recovery witness epoch is invalid")
    return epoch


def _enter_recovery_quarantine_retryable(witness: core.RecoveryWitnessPort) -> dict:
    # Always close and drain the rollback-subject database first. This remains
    # fail-closed even when the external witness is missing or malformed.
    boundary.close_admission_and_drain()
    if core.psql("SELECT reconciled::text FROM d3e_replay.recovery_fence WHERE singleton=TRUE;") != "false":
        raise RuntimeError("local recovery quarantine did not close before witness validation")

    payload = witness.read()
    epoch = _read_epoch(payload)
    admission_open = payload.get("admission_open")
    if admission_open not in {False, True}:
        raise RuntimeError("recovery witness admission state is malformed")

    # admission_open=True with DB still closed is the safe partial handoff that
    # occurs when the process crashes after durable witness publication but
    # before the final PostgreSQL reopen. Treat it as resumable, never as proof
    # that the rollback-subject database is already current.
    core.psql(
        f"UPDATE d3e_replay.recovery_fence SET epoch={epoch},reconciled=FALSE WHERE singleton=TRUE;"
    )
    state = core.psql(
        "SELECT epoch::text||'|'||reconciled::text FROM d3e_replay.recovery_fence WHERE singleton=TRUE;"
    )
    if state != f"{epoch}|false":
        raise RuntimeError("local recovery quarantine did not bind witness epoch")
    return payload


def recover_from_witness_retryable(witness: core.RecoveryWitnessPort) -> None:
    payload = _enter_recovery_quarantine_retryable(witness)
    epoch = _read_epoch(payload)
    boundary.validate_consumed_restore_exact(witness)
    base._validate_restored_redrive_capabilities(payload)
    base._restore_consumed(payload, epoch)
    base._restore_provider_outcomes(payload, epoch)
    unresolved = core.psql(
        "SELECT count(*) FROM d3e_replay.redrive WHERE state IN('attempting','reconciliation_required');"
    )
    if unresolved != "0":
        raise RuntimeError("recovery cannot reopen with unresolved provider capabilities")

    if payload.get("admission_open") is False:
        witness.open_after_reconciliation()
    reopened = witness.read()
    if reopened.get("epoch") != epoch or reopened.get("admission_open") is not True:
        raise RuntimeError("recovery witness did not durably reopen")

    core.psql(
        f"UPDATE d3e_replay.recovery_fence SET reconciled=TRUE "
        f"WHERE singleton=TRUE AND epoch={epoch} AND reconciled=FALSE;"
    )
    local = core.psql(
        "SELECT epoch::text||'|'||reconciled::text FROM d3e_replay.recovery_fence WHERE singleton=TRUE;"
    )
    if local != f"{epoch}|true":
        raise RuntimeError("database admission did not follow durable witness publication")


def prove_partial_reopen_is_retryable() -> None:
    core.init_db()
    witness = core.RecoveryWitnessPort()
    witness.initialize()
    boundary.close_admission_and_drain()
    witness.write({
        "epoch": 2,
        "admission_open": True,
        "boundary": "F-2-partial-reopen",
        "consumed": [],
        "provider_outcomes": {},
    })
    if core.psql("SELECT reconciled::text FROM d3e_replay.recovery_fence WHERE singleton=TRUE;") != "false":
        raise RuntimeError("partial reopen control did not preserve closed database gate")
    recover_from_witness_retryable(witness)
    if core.psql("SELECT epoch::text||'|'||reconciled::text FROM d3e_replay.recovery_fence WHERE singleton=TRUE;") != "2|true":
        raise RuntimeError("partial reopen recovery was not retryable")
    print(
        "d3_e_recovery_partial_reopen_retry=PASS "
        "witness_open_db_closed_state_recognized=true "
        "recovery_revalidation_repeated=true database_reopened_last=true"
    )


# Install the retryable recovery transition for every later import.
base._enter_recovery_quarantine = _enter_recovery_quarantine_retryable
base.recover_from_witness_exact = recover_from_witness_retryable
