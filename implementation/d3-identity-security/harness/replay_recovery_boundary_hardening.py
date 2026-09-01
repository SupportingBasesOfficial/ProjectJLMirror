#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import time

import replay_recovery_conformance_runner as core

_BARRIER_NAME = "d3e-recovery-admission-barrier-v1"
_ORIGINAL_INIT_DB = core.init_db
_ORIGINAL_CAPTURE_BOUNDARY = core.RecoveryWitnessPort.capture_boundary


def _barrier_expr() -> str:
    return f"hashtextextended('{_BARRIER_NAME}',0)"


def _install_admission_barrier_functions() -> None:
    barrier = _barrier_expr()
    core.psql_script(
        f"""
CREATE OR REPLACE FUNCTION d3e_replay.consume_private_jwt(
    p_client TEXT,
    p_jti TEXT,
    p_fingerprint TEXT,
    p_effect_id TEXT,
    p_result_ref TEXT,
    p_expected_epoch BIGINT
) RETURNS TEXT
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog,d3e_replay
AS $$
DECLARE
    prior d3e_replay.replay_identity%ROWTYPE;
    gate_ok BOOLEAN;
BEGIN
    -- Every admission transaction holds the shared side until commit. Recovery
    -- capture takes the exclusive side before closing the fence, which drains
    -- all already-admitted consumers and prevents a post-scan commit race.
    PERFORM pg_advisory_xact_lock_shared({barrier});
    PERFORM pg_advisory_xact_lock(hashtextextended('jwt:' || p_client || E'\\x1f' || p_jti,0));

    SELECT TRUE INTO gate_ok
      FROM d3e_replay.recovery_fence
     WHERE singleton=TRUE AND epoch=p_expected_epoch AND reconciled=TRUE;
    IF gate_ok IS DISTINCT FROM TRUE THEN
        RETURN 'BLOCKED';
    END IF;

    SELECT * INTO prior
      FROM d3e_replay.replay_identity
     WHERE client_principal=p_client AND jti=p_jti
     FOR UPDATE;

    IF FOUND THEN
        IF prior.recovery_epoch<>p_expected_epoch THEN
            RETURN 'BLOCKED';
        END IF;
        IF prior.assertion_fingerprint=p_fingerprint
           AND prior.effect_id=p_effect_id
           AND prior.result_ref=p_result_ref THEN
            RETURN 'OBSERVE';
        END IF;
        RETURN 'CONFLICT';
    END IF;

    INSERT INTO d3e_replay.replay_identity(
        client_principal,jti,assertion_fingerprint,recovery_epoch,state,effect_id,result_ref
    ) VALUES(p_client,p_jti,p_fingerprint,p_expected_epoch,'consumed',p_effect_id,p_result_ref);

    INSERT INTO d3e_replay.effect_ledger(effect_id,client_principal,jti,result_ref)
    VALUES(p_effect_id,p_client,p_jti,p_result_ref);

    RETURN 'WIN';
END;
$$;

CREATE OR REPLACE FUNCTION d3e_replay.claim_redrive(
    p_operation_id TEXT,p_worker_id TEXT,p_attempt_token TEXT,p_expected_epoch BIGINT
) RETURNS BIGINT
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog,d3e_replay
AS $$
DECLARE
    item d3e_replay.redrive%ROWTYPE;
    gate_ok BOOLEAN;
    next_generation BIGINT;
BEGIN
    -- Redrive admission shares the same barrier: capture cannot seal while an
    -- admitted claim is still able to create a provider capability.
    PERFORM pg_advisory_xact_lock_shared({barrier});
    PERFORM pg_advisory_xact_lock(hashtextextended('redrive:' || p_operation_id,0));
    SELECT TRUE INTO gate_ok FROM d3e_replay.recovery_fence
     WHERE singleton=TRUE AND epoch=p_expected_epoch AND reconciled=TRUE;
    IF gate_ok IS DISTINCT FROM TRUE THEN RETURN NULL; END IF;

    SELECT * INTO item FROM d3e_replay.redrive
     WHERE operation_id=p_operation_id FOR UPDATE;
    IF NOT FOUND OR item.state<>'prepared' OR item.recovery_epoch<>p_expected_epoch THEN
        RETURN NULL;
    END IF;
    next_generation := item.attempt_generation + 1;
    UPDATE d3e_replay.redrive
       SET state='attempting',attempt_generation=next_generation,
           worker_id=p_worker_id,attempt_token=p_attempt_token,
           ambiguity_reason=NULL,provider_revision=NULL,result_ref=NULL
     WHERE operation_id=p_operation_id;
    RETURN next_generation;
END;
$$;
"""
    )


def hardened_init_db() -> None:
    _ORIGINAL_INIT_DB()
    _install_admission_barrier_functions()


def close_admission_and_drain() -> None:
    """Drain old admissions, close the DB gate, then release the barrier.

    The session-level exclusive advisory lock conflicts with the transaction-
    scoped shared lock held by every consume/claim. No external/provider call is
    made while this lock is held: it exists only long enough to drain admitted
    DB transactions and atomically close the recovery fence.
    """
    barrier = _barrier_expr()
    core.psql(
        f"SELECT pg_advisory_lock({barrier}); "
        "UPDATE d3e_replay.recovery_fence SET reconciled=FALSE WHERE singleton=TRUE; "
        f"SELECT pg_advisory_unlock({barrier});"
    )
    if core.psql(
        "SELECT reconciled::text FROM d3e_replay.recovery_fence WHERE singleton=TRUE;"
    ) != "false":
        raise RuntimeError("recovery admission barrier did not close the gate")


def capture_boundary_structured(
    self: core.RecoveryWitnessPort,
    *,
    next_epoch: int,
    provider_outcomes: dict[str, dict],
) -> None:
    """Serialize consumed identities as structured JSON, never delimiters."""
    if core.psql(
        "SELECT reconciled::text FROM d3e_replay.recovery_fence WHERE singleton=TRUE;"
    ) != "false":
        raise RuntimeError("recovery witness capture requires closed admission")
    raw = core.psql(
        "SELECT COALESCE(json_agg(json_build_object("
        "'client',client_principal,'jti',jti,'fingerprint',assertion_fingerprint,"
        "'effect_id',effect_id,'result_ref',result_ref) "
        "ORDER BY client_principal,jti)::text,'[]') "
        "FROM d3e_replay.replay_identity WHERE state='consumed';"
    )
    consumed = json.loads(raw or "[]")
    if not isinstance(consumed, list) or any(not isinstance(item, dict) for item in consumed):
        raise RuntimeError("structured replay witness capture returned malformed rows")
    self.write({
        "epoch": next_epoch,
        "admission_open": False,
        "boundary": f"F-{next_epoch}",
        "consumed": consumed,
        "provider_outcomes": provider_outcomes,
    })


def validate_consumed_restore_exact(witness: core.RecoveryWitnessPort) -> None:
    """Prevalidate restored identities field-by-field before any upsert."""
    payload = witness.read()
    for item in payload.get("consumed", []):
        raw = core.psql(
            "SELECT COALESCE(row_to_json(x)::text,'') FROM ("
            "SELECT assertion_fingerprint AS fingerprint,effect_id,result_ref "
            "FROM d3e_replay.replay_identity "
            f"WHERE client_principal={core.lit(item['client'])} AND jti={core.lit(item['jti'])}"
            ") x;"
        )
        if not raw:
            continue
        prior = json.loads(raw)
        expected = {
            "fingerprint": item["fingerprint"],
            "effect_id": item["effect_id"],
            "result_ref": item["result_ref"],
        }
        if prior != expected:
            raise RuntimeError("recovery continuity conflicts with restored replay identity")


def _docker_psql_command(sql: str) -> list[str]:
    return [
        "docker", "exec", "-e", f"PGPASSWORD={core.PG_PASSWORD}", core.PG_CONTAINER,
        "psql", "-X", "-U", "postgres", "-d", "d3", "-v", "ON_ERROR_STOP=1", "-Atq", "-c", sql,
    ]


def prove_recovery_consumer_barrier() -> None:
    hardened_init_db()
    witness = core.RecoveryWitnessPort()
    witness.initialize()
    barrier = _barrier_expr()
    sql = (
        "BEGIN; "
        f"SELECT pg_advisory_xact_lock_shared({barrier}); "
        "SELECT pg_sleep(1.0); "
        "SELECT d3e_replay.consume_private_jwt("
        "'barrier|client','barrier\njti','barrier-fp','barrier-effect','barrier-result',1); "
        "COMMIT;"
    )
    proc = subprocess.Popen(
        _docker_psql_command(sql), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    deadline = time.time() + 5
    while time.time() < deadline:
        shared = core.psql(
            "SELECT count(*) FROM pg_locks "
            "WHERE locktype='advisory' AND granted AND mode='ShareLock';"
        )
        if int(shared or "0") > 0:
            break
        time.sleep(0.05)
    else:
        proc.kill()
        raise RuntimeError("consumer barrier negative control never acquired shared lock")

    close_admission_and_drain()
    stdout, stderr = proc.communicate(timeout=5)
    if proc.returncode != 0:
        raise RuntimeError(f"barrier consumer failed: {stderr.strip()[:500]}")
    if "WIN" not in stdout:
        raise RuntimeError("in-flight consumer did not commit before recovery capture")

    capture_boundary_structured(witness, next_epoch=2, provider_outcomes={})
    payload = witness.read()
    captured = [item for item in payload["consumed"] if item.get("effect_id") == "barrier-effect"]
    if len(captured) != 1:
        raise RuntimeError("drained in-flight consumer was omitted from recovery witness")
    item = captured[0]
    if item["client"] != "barrier|client" or item["jti"] != "barrier\njti":
        raise RuntimeError("structured recovery witness corrupted delimiter-bearing claims")
    if core.consume_sql(
        "post-close-client", "post-close-jti", "post-close-fp", "post-close-effect", "post-close-result", 1
    ) != "BLOCKED":
        raise RuntimeError("new replay admission succeeded after recovery gate closure")

    print(
        "d3_e_recovery_consumer_drain_barrier=PASS "
        "shared_xact_admission_lock=true exclusive_capture_barrier=true "
        "in_flight_consumer_drained_before_witness=true new_consumers_blocked_after_close=true "
        "structured_consumed_json=true delimiter_claims_round_trip=true long_db_txn_over_external_call=false"
    )


def install() -> None:
    core.init_db = hardened_init_db
    core.RecoveryWitnessPort.capture_boundary = capture_boundary_structured


install()
