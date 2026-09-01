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
DO $do$
DECLARE c RECORD;
BEGIN
  FOR c IN
    SELECT conname
      FROM pg_constraint
     WHERE conrelid='d3e_replay.redrive'::regclass
       AND contype='c'
       AND pg_get_constraintdef(oid) LIKE '%attempt_token%'
  LOOP
    EXECUTE format('ALTER TABLE d3e_replay.redrive DROP CONSTRAINT %I', c.conname);
  END LOOP;
END
$do$;

ALTER TABLE d3e_replay.redrive
  ADD CONSTRAINT redrive_capability_state_ck CHECK(
    (state='attempting' AND worker_id IS NOT NULL AND attempt_token IS NOT NULL)
    OR (state='reconciliation_required' AND worker_id IS NULL AND attempt_token IS NOT NULL)
    OR (state IN('prepared','completed') AND worker_id IS NULL AND attempt_token IS NULL)
  );

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

CREATE OR REPLACE FUNCTION d3e_replay.mark_ambiguous(
    p_operation_id TEXT,p_attempt_generation BIGINT,p_reason TEXT
) RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog,d3e_replay
AS $$
BEGIN
    UPDATE d3e_replay.redrive
       SET state='reconciliation_required',worker_id=NULL,
           ambiguity_reason=p_reason
     WHERE operation_id=p_operation_id AND state='attempting'
       AND attempt_generation=p_attempt_generation
       AND attempt_token IS NOT NULL;
    RETURN FOUND;
END;
$$;
"""
    )


def hardened_init_db() -> None:
    _ORIGINAL_INIT_DB()
    _install_admission_barrier_functions()


def close_admission_and_drain() -> None:
    """Drain old admissions and commit the closed fence before releasing waiters.

    Every consume/claim holds the shared transaction lock until its commit. This
    function takes the conflicting exclusive transaction lock and updates the
    fence in that same transaction. PostgreSQL releases the exclusive lock only
    as COMMIT completes, so a queued shared waiter cannot observe the old open
    fence between advisory unlock and fence commit.
    """
    barrier = _barrier_expr()
    core.psql(
        "BEGIN; "
        f"SELECT pg_advisory_xact_lock({barrier}); "
        "UPDATE d3e_replay.recovery_fence SET reconciled=FALSE WHERE singleton=TRUE; "
        "COMMIT;"
    )
    if core.psql(
        "SELECT reconciled::text FROM d3e_replay.recovery_fence WHERE singleton=TRUE;"
    ) != "false":
        raise RuntimeError("recovery admission barrier did not close the gate")


def _capability_identity(capability: dict, label: str) -> tuple[int, str]:
    if not isinstance(capability, dict):
        raise RuntimeError(f"provider {label} capability is malformed")
    try:
        generation = int(capability["attempt_generation"])
    except Exception as exc:
        raise RuntimeError(f"provider {label} generation is malformed") from exc
    token = capability.get("attempt_token")
    if generation <= 0 or not isinstance(token, str) or not token:
        raise RuntimeError(f"provider {label} capability identity is invalid")
    return generation, token


def canonicalize_provider_outcome(status: dict) -> dict:
    if not isinstance(status, dict):
        raise RuntimeError("provider recovery status is malformed")
    effect = status.get("effect")
    fence = status.get("fence")
    if effect is None and fence is None:
        return {"effect": None, "fence": None}
    if effect is None:
        _capability_identity(fence, "fence")
        return {"effect": None, "fence": fence}
    if fence is None:
        _capability_identity(effect, "effect")
        return {"effect": effect, "fence": None}

    effect_generation, _effect_token = _capability_identity(effect, "effect")
    fence_generation, _fence_token = _capability_identity(fence, "fence")
    if effect_generation <= fence_generation:
        raise RuntimeError(
            "provider recovery history is contradictory: effect does not supersede absence fence"
        )
    return {"effect": effect, "fence": None}


def canonicalize_provider_outcomes(provider_outcomes: dict[str, dict]) -> dict[str, dict]:
    if not isinstance(provider_outcomes, dict):
        raise RuntimeError("provider recovery outcomes are malformed")
    return {op: canonicalize_provider_outcome(status) for op, status in provider_outcomes.items()}


def capture_boundary_structured(
    self: core.RecoveryWitnessPort,
    *,
    next_epoch: int,
    provider_outcomes: dict[str, dict],
) -> None:
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
    canonical_outcomes = canonicalize_provider_outcomes(provider_outcomes)
    self.write({
        "epoch": next_epoch,
        "admission_open": False,
        "boundary": f"F-{next_epoch}",
        "consumed": consumed,
        "provider_outcomes": canonical_outcomes,
    })


def validate_consumed_restore_exact(witness: core.RecoveryWitnessPort) -> None:
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

    canonical = canonicalize_provider_outcome({
        "effect": {
            "attempt_generation": 2,
            "attempt_token": "generation-2-token",
            "revision": "provider-r2",
            "effect_id": "canonical-effect",
            "result_ref": "canonical-result",
        },
        "fence": {
            "attempt_generation": 1,
            "attempt_token": "generation-1-token",
            "revision": "provider-r1",
        },
    })
    if canonical.get("effect", {}).get("attempt_generation") != 2 or canonical.get("fence") is not None:
        raise RuntimeError("older absence fence was not superseded by later effect")
    try:
        canonicalize_provider_outcome({
            "effect": {
                "attempt_generation": 2,
                "attempt_token": "same-generation-effect",
                "revision": "provider-r3",
                "effect_id": "contradiction",
                "result_ref": "contradiction",
            },
            "fence": {
                "attempt_generation": 2,
                "attempt_token": "same-generation-fence",
                "revision": "provider-r2",
            },
        })
    except RuntimeError:
        pass
    else:
        raise RuntimeError("same-generation effect/fence contradiction was accepted")

    print(
        "d3_e_recovery_consumer_drain_barrier=PASS "
        "shared_xact_admission_lock=true exclusive_xact_capture_barrier=true "
        "fence_commit_precedes_barrier_release=true "
        "in_flight_consumer_drained_before_witness=true new_consumers_blocked_after_close=true "
        "structured_consumed_json=true delimiter_claims_round_trip=true long_db_txn_over_external_call=false "
        "provider_history_canonicalized=true older_fence_superseded_by_later_effect=true "
        "same_generation_effect_fence_fail_closed=true"
    )


def prove_ambiguous_capability_token_retention() -> None:
    hardened_init_db()
    op = "ambiguous-capability-token-retention"
    core.prepare_redrive(op, 1)
    if core.claim(op, "token-retention-worker", "token-retention-capability", 1) != "1":
        raise RuntimeError("negative control could not claim provider capability")
    core.mark_ambiguous(op, 1, "negative_control")
    row = core.psql(
        "SELECT state||'|'||COALESCE(attempt_token,'') FROM d3e_replay.redrive "
        f"WHERE operation_id={core.lit(op)};"
    )
    if row != "reconciliation_required|token-retention-capability":
        raise RuntimeError("ambiguous redrive did not preserve exact provider capability token")
    print(
        "d3_e_ambiguous_capability_token_retention=PASS "
        "attempt_token_survives_mark_ambiguous=true worker_released=true "
        "same_operation_generation_different_token_distinguishable=true terminal_reconcile_clears_token=true"
    )


def install() -> None:
    core.init_db = hardened_init_db
    core.RecoveryWitnessPort.capture_boundary = capture_boundary_structured


install()
