#!/usr/bin/env python3
from __future__ import annotations

import concurrent.futures
import os
import subprocess
import time

PG_CONTAINER = os.environ.get("PG_CONTAINER", "jlmirror-d3e-postgres")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "d3-postgres-password")
PG_IMAGE = os.environ["POSTGRES_IMAGE"]
D3_NETWORK = os.environ.get("D3_NETWORK", "jlmirror-d3e-conformance")


def sh(args: list[str], *, input_text: str | None = None, timeout: float = 30, check: bool = True):
    r = subprocess.run(args, input=input_text, text=True, capture_output=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(f"command failed rc={r.returncode}: {r.stderr.strip()[:600]}")
    return r


def lit(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def psql(sql: str, *, db: str = "d3", check: bool = True) -> str:
    r = sh([
        "docker", "exec", "-e", f"PGPASSWORD={PG_PASSWORD}", PG_CONTAINER,
        "psql", "-X", "-U", "postgres", "-d", db, "-v", "ON_ERROR_STOP=1", "-Atq", "-c", sql
    ], check=check)
    return r.stdout.strip()


def psql_script(script: str, *, db: str = "d3") -> None:
    sh([
        "docker", "exec", "-i", "-e", f"PGPASSWORD={PG_PASSWORD}", PG_CONTAINER,
        "psql", "-X", "-U", "postgres", "-d", db, "-v", "ON_ERROR_STOP=1", "-q"
    ], input_text=script)


def network_psql(sql: str, *, check: bool = True, timeout: float = 12):
    return sh([
        "docker", "run", "--rm", "--network", D3_NETWORK, "-e", f"PGPASSWORD={PG_PASSWORD}", PG_IMAGE,
        "psql", "-X", "-h", PG_CONTAINER, "-U", "postgres", "-d", "d3",
        "-v", "ON_ERROR_STOP=1", "-Atq", "-c", sql
    ], check=check, timeout=timeout)


def dump_app_schema() -> str:
    r = sh([
        "docker", "exec", "-e", f"PGPASSWORD={PG_PASSWORD}", PG_CONTAINER,
        "pg_dump", "-U", "postgres", "-d", "d3", "--schema", "d3e_replay",
        "--no-owner", "--no-privileges"
    ])
    if "CREATE SCHEMA d3e_replay" not in r.stdout:
        raise AssertionError("real PostgreSQL app-schema dump was not captured")
    if "d3e_replay_control" in r.stdout:
        raise AssertionError("fresh recovery/effect authority leaked into stale app snapshot")
    return r.stdout


def init_db() -> None:
    psql_script(r"""
DROP SCHEMA IF EXISTS d3e_replay CASCADE;
DROP SCHEMA IF EXISTS d3e_replay_control CASCADE;

CREATE SCHEMA d3e_replay_control;
CREATE TABLE d3e_replay_control.recovery(
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK(singleton),
    epoch BIGINT NOT NULL CHECK(epoch > 0)
);
INSERT INTO d3e_replay_control.recovery(singleton, epoch) VALUES(TRUE, 1);

CREATE TABLE d3e_replay_control.consumed(
    client_principal TEXT NOT NULL,
    jti TEXT NOT NULL,
    effect_id TEXT NOT NULL,
    result_ref TEXT NOT NULL,
    PRIMARY KEY(client_principal, jti),
    UNIQUE(effect_id)
);

CREATE TABLE d3e_replay_control.external_effect(
    operation_id TEXT PRIMARY KEY,
    effect_id TEXT NOT NULL UNIQUE,
    result_ref TEXT NOT NULL
);

CREATE TABLE d3e_replay_control.probe(
    operation_id TEXT PRIMARY KEY,
    attempt_generation BIGINT NOT NULL CHECK(attempt_generation > 0),
    attempt_token TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN('open','absent','confirmed')),
    revision TEXT NOT NULL,
    effect_id TEXT NULL,
    result_ref TEXT NULL,
    CHECK(
        (state='confirmed' AND effect_id IS NOT NULL AND result_ref IS NOT NULL)
        OR (state IN('open','absent') AND effect_id IS NULL AND result_ref IS NULL)
    )
);

CREATE SCHEMA d3e_replay;
CREATE TABLE d3e_replay.recovery_fence(
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK(singleton),
    epoch BIGINT NOT NULL CHECK(epoch > 0),
    reconciled BOOLEAN NOT NULL
);
INSERT INTO d3e_replay.recovery_fence(singleton, epoch, reconciled)
VALUES(TRUE, 1, TRUE);

CREATE TABLE d3e_replay.replay_identity(
    client_principal TEXT NOT NULL,
    jti TEXT NOT NULL,
    recovery_epoch BIGINT NOT NULL CHECK(recovery_epoch > 0),
    state TEXT NOT NULL CHECK(state IN('consumed','reconciliation_required')),
    attempt_generation BIGINT NOT NULL CHECK(attempt_generation > 0),
    effect_id TEXT NULL,
    result_ref TEXT NULL,
    PRIMARY KEY(client_principal, jti),
    CHECK(
        (state='consumed' AND effect_id IS NOT NULL AND result_ref IS NOT NULL)
        OR (state='reconciliation_required' AND effect_id IS NULL AND result_ref IS NULL)
    )
);

CREATE TABLE d3e_replay.effect_ledger(
    effect_id TEXT PRIMARY KEY,
    client_principal TEXT NOT NULL,
    jti TEXT NOT NULL,
    result_ref TEXT NOT NULL,
    UNIQUE(client_principal, jti)
);

CREATE TABLE d3e_replay.redrive(
    operation_id TEXT PRIMARY KEY,
    quarantine_generation BIGINT NOT NULL CHECK(quarantine_generation > 0),
    recovery_epoch BIGINT NOT NULL CHECK(recovery_epoch > 0),
    state TEXT NOT NULL CHECK(state IN('prepared','attempting','reconciliation_required','completed')),
    attempt_generation BIGINT NOT NULL DEFAULT 0 CHECK(attempt_generation >= 0),
    worker_id TEXT NULL,
    attempt_token TEXT NULL,
    ambiguity_reason TEXT NULL,
    reconciliation_revision TEXT NULL,
    result_ref TEXT NULL,
    CHECK(
        (state='attempting' AND worker_id IS NOT NULL AND attempt_token IS NOT NULL)
        OR (state<>'attempting' AND worker_id IS NULL AND attempt_token IS NULL)
    ),
    CHECK(state<>'reconciliation_required' OR ambiguity_reason IS NOT NULL),
    CHECK(state<>'completed' OR result_ref IS NOT NULL)
);

CREATE FUNCTION d3e_replay.consume_private_jwt(
    p_client TEXT, p_jti TEXT, p_effect_id TEXT, p_result_ref TEXT, p_expected_epoch BIGINT
) RETURNS TEXT
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, d3e_replay, d3e_replay_control
AS $$
DECLARE
    prior d3e_replay.replay_identity%ROWTYPE;
    gate_ok BOOLEAN;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('jwt:' || p_client || E'\x1f' || p_jti, 0));

    SELECT * INTO prior
      FROM d3e_replay.replay_identity
     WHERE client_principal=p_client AND jti=p_jti
     FOR UPDATE;

    IF FOUND THEN
        IF prior.state='consumed'
           AND prior.effect_id=p_effect_id
           AND prior.result_ref=p_result_ref THEN
            RETURN 'OBSERVE';
        END IF;
        RETURN 'CONFLICT';
    END IF;

    SELECT TRUE INTO gate_ok
      FROM d3e_replay_control.recovery c
      JOIN d3e_replay.recovery_fence f
        ON f.singleton=TRUE
       AND f.epoch=c.epoch
       AND f.reconciled=TRUE
     WHERE c.singleton=TRUE
       AND c.epoch=p_expected_epoch;

    IF gate_ok IS DISTINCT FROM TRUE THEN
        RETURN 'BLOCKED';
    END IF;

    INSERT INTO d3e_replay.replay_identity(
        client_principal,jti,recovery_epoch,state,attempt_generation,effect_id,result_ref
    ) VALUES(p_client,p_jti,p_expected_epoch,'consumed',1,p_effect_id,p_result_ref);

    INSERT INTO d3e_replay.effect_ledger(effect_id,client_principal,jti,result_ref)
    VALUES(p_effect_id,p_client,p_jti,p_result_ref);

    INSERT INTO d3e_replay_control.consumed(client_principal,jti,effect_id,result_ref)
    VALUES(p_client,p_jti,p_effect_id,p_result_ref);

    RETURN 'WIN';
END;
$$;

CREATE FUNCTION d3e_replay.claim_redrive(
    p_operation_id TEXT, p_worker_id TEXT, p_attempt_token TEXT, p_expected_epoch BIGINT
) RETURNS BIGINT
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, d3e_replay, d3e_replay_control
AS $$
DECLARE
    item d3e_replay.redrive%ROWTYPE;
    prior d3e_replay_control.probe%ROWTYPE;
    next_generation BIGINT;
    gate_ok BOOLEAN;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('redrive:' || p_operation_id, 0));

    SELECT TRUE INTO gate_ok
      FROM d3e_replay_control.recovery c
      JOIN d3e_replay.recovery_fence f
        ON f.singleton=TRUE
       AND f.epoch=c.epoch
       AND f.reconciled=TRUE
     WHERE c.singleton=TRUE
       AND c.epoch=p_expected_epoch;
    IF gate_ok IS DISTINCT FROM TRUE THEN
        RETURN NULL;
    END IF;

    SELECT * INTO item
      FROM d3e_replay.redrive
     WHERE operation_id=p_operation_id
     FOR UPDATE;
    IF NOT FOUND
       OR item.state<>'prepared'
       OR item.recovery_epoch<>p_expected_epoch THEN
        RETURN NULL;
    END IF;

    SELECT * INTO prior
      FROM d3e_replay_control.probe
     WHERE operation_id=p_operation_id
     FOR UPDATE;
    IF FOUND AND (
        prior.attempt_generation<>item.attempt_generation
        OR prior.state<>'absent'
    ) THEN
        RETURN NULL;
    END IF;

    next_generation := item.attempt_generation + 1;

    INSERT INTO d3e_replay_control.probe(
        operation_id,attempt_generation,attempt_token,state,revision,effect_id,result_ref
    ) VALUES(
        p_operation_id,next_generation,p_attempt_token,'open',
        'attempt-' || next_generation::text || '-open',NULL,NULL
    )
    ON CONFLICT(operation_id) DO UPDATE SET
        attempt_generation=EXCLUDED.attempt_generation,
        attempt_token=EXCLUDED.attempt_token,
        state='open',
        revision=EXCLUDED.revision,
        effect_id=NULL,
        result_ref=NULL;

    UPDATE d3e_replay.redrive
       SET state='attempting',
           attempt_generation=next_generation,
           worker_id=p_worker_id,
           attempt_token=p_attempt_token,
           ambiguity_reason=NULL,
           reconciliation_revision=NULL,
           result_ref=NULL
     WHERE operation_id=p_operation_id;

    RETURN next_generation;
END;
$$;

CREATE FUNCTION d3e_replay.reserve_absence(
    p_operation_id TEXT, p_attempt_generation BIGINT, p_revision TEXT
) RETURNS TEXT
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, d3e_replay, d3e_replay_control
AS $$
DECLARE
    item d3e_replay.redrive%ROWTYPE;
    probe d3e_replay_control.probe%ROWTYPE;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('redrive:' || p_operation_id, 0));

    SELECT * INTO item
      FROM d3e_replay.redrive
     WHERE operation_id=p_operation_id
     FOR UPDATE;
    IF NOT FOUND
       OR item.state<>'reconciliation_required'
       OR item.attempt_generation<>p_attempt_generation THEN
        RETURN 'BLOCKED';
    END IF;

    SELECT * INTO probe
      FROM d3e_replay_control.probe
     WHERE operation_id=p_operation_id
     FOR UPDATE;
    IF NOT FOUND OR probe.attempt_generation<>p_attempt_generation THEN
        RETURN 'BLOCKED';
    END IF;
    IF probe.state='confirmed' THEN
        RETURN 'CONFIRMED';
    END IF;
    IF probe.state='absent' THEN
        RETURN 'ABSENT';
    END IF;
    IF EXISTS(
        SELECT 1 FROM d3e_replay_control.external_effect
         WHERE operation_id=p_operation_id
    ) THEN
        RAISE EXCEPTION 'open effect probe conflicts with durable external effect';
    END IF;

    UPDATE d3e_replay_control.probe
       SET state='absent',revision=p_revision,effect_id=NULL,result_ref=NULL
     WHERE operation_id=p_operation_id;
    RETURN 'ABSENT';
END;
$$;

CREATE FUNCTION d3e_replay.record_external_effect(
    p_operation_id TEXT,
    p_attempt_generation BIGINT,
    p_attempt_token TEXT,
    p_effect_id TEXT,
    p_result_ref TEXT,
    p_revision TEXT
) RETURNS TEXT
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, d3e_replay, d3e_replay_control
AS $$
DECLARE
    probe d3e_replay_control.probe%ROWTYPE;
    existing d3e_replay_control.external_effect%ROWTYPE;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('redrive:' || p_operation_id, 0));

    SELECT * INTO probe
      FROM d3e_replay_control.probe
     WHERE operation_id=p_operation_id
     FOR UPDATE;
    IF NOT FOUND
       OR probe.attempt_generation<>p_attempt_generation
       OR probe.attempt_token<>p_attempt_token THEN
        RETURN 'BLOCKED';
    END IF;

    IF probe.state='absent' THEN
        RETURN 'BLOCKED';
    END IF;

    IF probe.state='confirmed' THEN
        IF probe.effect_id=p_effect_id AND probe.result_ref=p_result_ref THEN
            RETURN 'OBSERVE';
        END IF;
        RETURN 'CONFLICT';
    END IF;

    SELECT * INTO existing
      FROM d3e_replay_control.external_effect
     WHERE operation_id=p_operation_id
     FOR UPDATE;
    IF FOUND THEN
        IF existing.effect_id=p_effect_id AND existing.result_ref=p_result_ref THEN
            UPDATE d3e_replay_control.probe
               SET state='confirmed',revision=p_revision,
                   effect_id=p_effect_id,result_ref=p_result_ref
             WHERE operation_id=p_operation_id;
            RETURN 'OBSERVE';
        END IF;
        RETURN 'CONFLICT';
    END IF;

    INSERT INTO d3e_replay_control.external_effect(operation_id,effect_id,result_ref)
    VALUES(p_operation_id,p_effect_id,p_result_ref);

    UPDATE d3e_replay_control.probe
       SET state='confirmed',revision=p_revision,
           effect_id=p_effect_id,result_ref=p_result_ref
     WHERE operation_id=p_operation_id;

    RETURN 'WIN';
END;
$$;

CREATE FUNCTION d3e_replay.reconcile_absent(p_operation_id TEXT) RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, d3e_replay, d3e_replay_control
AS $$
DECLARE
    item d3e_replay.redrive%ROWTYPE;
    probe d3e_replay_control.probe%ROWTYPE;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('redrive:' || p_operation_id, 0));

    SELECT * INTO item
      FROM d3e_replay.redrive
     WHERE operation_id=p_operation_id
     FOR UPDATE;
    SELECT * INTO probe
      FROM d3e_replay_control.probe
     WHERE operation_id=p_operation_id
     FOR UPDATE;

    IF item.state<>'reconciliation_required'
       OR probe.state<>'absent'
       OR probe.attempt_generation<>item.attempt_generation THEN
        RETURN FALSE;
    END IF;

    UPDATE d3e_replay.redrive
       SET state='prepared',
           worker_id=NULL,
           attempt_token=NULL,
           ambiguity_reason=NULL,
           reconciliation_revision=probe.revision,
           result_ref=NULL
     WHERE operation_id=p_operation_id;
    RETURN TRUE;
END;
$$;

CREATE FUNCTION d3e_replay.reconcile_confirmed(p_operation_id TEXT) RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, d3e_replay, d3e_replay_control
AS $$
DECLARE
    item d3e_replay.redrive%ROWTYPE;
    probe d3e_replay_control.probe%ROWTYPE;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('redrive:' || p_operation_id, 0));

    SELECT * INTO item
      FROM d3e_replay.redrive
     WHERE operation_id=p_operation_id
     FOR UPDATE;
    SELECT * INTO probe
      FROM d3e_replay_control.probe
     WHERE operation_id=p_operation_id
     FOR UPDATE;

    IF item.state<>'reconciliation_required'
       OR probe.state<>'confirmed'
       OR probe.attempt_generation<>item.attempt_generation THEN
        RETURN FALSE;
    END IF;

    UPDATE d3e_replay.redrive
       SET state='completed',
           worker_id=NULL,
           attempt_token=NULL,
           ambiguity_reason=NULL,
           reconciliation_revision=probe.revision,
           result_ref=probe.result_ref
     WHERE operation_id=p_operation_id;
    RETURN TRUE;
END;
$$;

CREATE FUNCTION d3e_replay.complete_redrive(
    p_operation_id TEXT,p_attempt_generation BIGINT,p_result_ref TEXT
) RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, d3e_replay, d3e_replay_control
AS $$
DECLARE
    item d3e_replay.redrive%ROWTYPE;
    probe d3e_replay_control.probe%ROWTYPE;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('redrive:' || p_operation_id, 0));

    SELECT * INTO item
      FROM d3e_replay.redrive
     WHERE operation_id=p_operation_id
     FOR UPDATE;
    SELECT * INTO probe
      FROM d3e_replay_control.probe
     WHERE operation_id=p_operation_id
     FOR UPDATE;

    IF item.state<>'attempting'
       OR item.attempt_generation<>p_attempt_generation
       OR probe.state<>'confirmed'
       OR probe.attempt_generation<>p_attempt_generation
       OR probe.result_ref<>p_result_ref THEN
        RETURN FALSE;
    END IF;

    UPDATE d3e_replay.redrive
       SET state='completed',
           worker_id=NULL,
           attempt_token=NULL,
           ambiguity_reason=NULL,
           reconciliation_revision=probe.revision,
           result_ref=probe.result_ref
     WHERE operation_id=p_operation_id;
    RETURN TRUE;
END;
$$;
""")


def consume(client: str, jti: str, effect_id: str, result_ref: str, epoch: int) -> str:
    return psql(
        "SELECT d3e_replay.consume_private_jwt("
        f"{lit(client)},{lit(jti)},{lit(effect_id)},{lit(result_ref)},{epoch});"
    )


def prepare_redrive(op: str, qgen: int, epoch: int) -> None:
    psql(
        "INSERT INTO d3e_replay.redrive(operation_id,quarantine_generation,recovery_epoch,state) "
        f"VALUES({lit(op)},{qgen},{epoch},'prepared');"
    )


def claim_redrive(op: str, worker: str, token: str, epoch: int) -> str:
    value = psql(
        "SELECT COALESCE(d3e_replay.claim_redrive("
        f"{lit(op)},{lit(worker)},{lit(token)},{epoch})::text,'BLOCKED');"
    )
    return value or "BLOCKED"


def ambiguous(op: str, generation: int, reason: str) -> None:
    got = psql(
        "UPDATE d3e_replay.redrive "
        "SET state='reconciliation_required',worker_id=NULL,attempt_token=NULL,"
        f"ambiguity_reason={lit(reason)} "
        f"WHERE operation_id={lit(op)} AND state='attempting' "
        f"AND attempt_generation={generation} RETURNING operation_id;"
    )
    assert got == op


def reserve_absence(op: str, generation: int, revision: str) -> str:
    return psql(
        f"SELECT d3e_replay.reserve_absence({lit(op)},{generation},{lit(revision)});"
    )


def external_effect(
    op: str,
    generation: int,
    token: str,
    effect_id: str,
    result_ref: str,
    revision: str,
) -> str:
    return psql(
        "SELECT d3e_replay.record_external_effect("
        f"{lit(op)},{generation},{lit(token)},{lit(effect_id)},{lit(result_ref)},{lit(revision)});"
    )


def reconcile_absent(op: str) -> bool:
    return psql(f"SELECT d3e_replay.reconcile_absent({lit(op)});") == "t"


def reconcile_confirmed(op: str) -> bool:
    return psql(f"SELECT d3e_replay.reconcile_confirmed({lit(op)});") == "t"


def complete_redrive(op: str, generation: int, result_ref: str) -> bool:
    return psql(
        f"SELECT d3e_replay.complete_redrive({lit(op)},{generation},{lit(result_ref)});"
    ) == "t"


def effect_count(op: str) -> int:
    return int(psql(
        f"SELECT count(*) FROM d3e_replay_control.external_effect WHERE operation_id={lit(op)};"
    ))


def prove_single_winner() -> None:
    client = "client-private-jwt-a"
    jti = "jwt-jti-one"
    effect = "session-effect-one"
    result = "session-lineage-one"

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        outcomes = list(pool.map(lambda _: consume(client, jti, effect, result, 1), range(48)))

    assert outcomes.count("WIN") == 1
    assert outcomes.count("OBSERVE") == 47
    assert psql(
        f"SELECT count(*) FROM d3e_replay.effect_ledger WHERE effect_id={lit(effect)};"
    ) == "1"
    assert psql(
        "SELECT count(*) FROM d3e_replay_control.consumed "
        f"WHERE client_principal={lit(client)} AND jti={lit(jti)};"
    ) == "1"

    assert consume(client, jti, "conflicting-effect", "conflicting-result", 1) == "CONFLICT"
    assert psql(
        f"SELECT count(*) FROM d3e_replay.effect_ledger WHERE client_principal={lit(client)} AND jti={lit(jti)};"
    ) == "1"

    assert consume("client-private-jwt-b", jti, "session-effect-two", "session-lineage-two", 1) == "WIN"

    print(
        "d3_e_private_key_jwt_replay_atomic_single_winner=PASS "
        "postgres_create_or_observe=true concurrent_workers=48 exactly_one_effect=true "
        "duplicates_observe=true conflicting_same_identity_rejected=true client_principal_scope=true "
        "recovery_evidence_atomic_with_effect=true"
    )


def prove_partition() -> None:
    assert network_psql("SELECT 1;").stdout.strip() == "1"
    sh(["docker", "network", "disconnect", D3_NETWORK, PG_CONTAINER])
    try:
        attempt = network_psql(
            "SELECT d3e_replay.consume_private_jwt("
            "'partition-client','partition-jti','partition-effect','partition-result',1);",
            check=False,
            timeout=8,
        )
        assert attempt.returncode != 0
    finally:
        sh(["docker", "network", "connect", D3_NETWORK, PG_CONTAINER])

    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            if network_psql("SELECT 1;", timeout=4).stdout.strip() == "1":
                break
        except Exception:
            time.sleep(0.2)
    else:
        raise RuntimeError("postgres network did not recover")

    assert psql(
        "SELECT count(*) FROM d3e_replay.effect_ledger WHERE jti='partition-jti';"
    ) == "0"
    assert psql(
        "SELECT count(*) FROM d3e_replay_control.consumed WHERE jti='partition-jti';"
    ) == "0"

    print(
        "d3_e_replay_partition_fail_closed=PASS actual_network_partition=true "
        "replay_authority_unreachable=true no_effect=true no_consumed_identity=true"
    )


def prove_redrive() -> None:
    op = "redrive-crash-before-effect"
    prepare_redrive(op, 7, 1)
    assert claim_redrive(op, "worker-a", "token-a", 1) == "1"
    ambiguous(op, 1, "worker_died")
    assert claim_redrive(op, "worker-b", "token-b", 1) == "BLOCKED"
    assert reserve_absence(op, 1, "absence-1") == "ABSENT"
    assert external_effect(op, 1, "token-a", "late-effect", "late-result", "late-confirm") == "BLOCKED"
    assert reconcile_absent(op)
    assert claim_redrive(op, "worker-b", "token-b", 1) == "2"
    assert external_effect(op, 2, "token-b", "effect-a", "result-a", "confirm-a") == "WIN"
    assert complete_redrive(op, 2, "result-a")
    assert external_effect(op, 2, "token-b", "effect-a", "result-a", "confirm-a2") == "OBSERVE"
    assert external_effect(op, 2, "token-b", "other-effect", "other-result", "bad") == "CONFLICT"
    assert effect_count(op) == 1

    op2 = "redrive-response-lost"
    prepare_redrive(op2, 8, 1)
    assert claim_redrive(op2, "worker-c", "token-c", 1) == "1"
    assert external_effect(op2, 1, "token-c", "effect-b", "result-b", "confirm-b") == "WIN"
    ambiguous(op2, 1, "response_lost")
    assert claim_redrive(op2, "worker-d", "token-d", 1) == "BLOCKED"
    assert reserve_absence(op2, 1, "should-not-win") == "CONFIRMED"
    assert reconcile_confirmed(op2)
    assert psql(
        f"SELECT state||'|'||attempt_generation FROM d3e_replay.redrive WHERE operation_id={lit(op2)};"
    ) == "completed|1"
    assert effect_count(op2) == 1

    print(
        "d3_e_redrive_crash_retry_single_effect=PASS worker_death_not_absence=true "
        "positive_absence_fences_old_attempt=true delayed_old_effect_blocked=true "
        "attempt_generation_monotonic=true lost_response_reconciles=true "
        "conflicting_result_rejected=true external_effect_at_most_once=true"
    )


def prove_absence_effect_race() -> None:
    op = "redrive-absence-effect-race"
    prepare_redrive(op, 9, 1)
    assert claim_redrive(op, "race-worker", "race-token", 1) == "1"
    ambiguous(op, 1, "race_ambiguity")

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        absence_future = pool.submit(reserve_absence, op, 1, "race-absence")
        effect_future = pool.submit(
            external_effect,
            op, 1, "race-token", "race-effect", "race-result", "race-confirm",
        )
        absence_result = absence_future.result()
        effect_result = effect_future.result()

    if absence_result == "ABSENT":
        assert effect_result == "BLOCKED"
        assert reconcile_absent(op)
        assert claim_redrive(op, "race-worker-2", "race-token-2", 1) == "2"
        assert external_effect(
            op, 2, "race-token-2", "race-effect", "race-result", "race-confirm-2"
        ) == "WIN"
        assert complete_redrive(op, 2, "race-result")
        final_generation = 2
    else:
        assert absence_result == "CONFIRMED"
        assert effect_result == "WIN"
        assert reconcile_confirmed(op)
        final_generation = 1

    assert effect_count(op) == 1
    assert psql(
        f"SELECT state||'|'||attempt_generation FROM d3e_replay.redrive WHERE operation_id={lit(op)};"
    ) == f"completed|{final_generation}"

    print(
        "d3_e_redrive_absence_effect_race_single_winner=PASS "
        "same_operation_serialization=true absence_and_effect_mutually_exclusive=true "
        "absence_is_capability_fence=true exactly_one_external_effect=true"
    )


def advance_recovery_epoch(epoch: int) -> None:
    got = psql(
        f"UPDATE d3e_replay_control.recovery SET epoch={epoch} "
        "WHERE singleton=TRUE RETURNING epoch;"
    )
    assert got == str(epoch)


def restore_stale_app_schema(stale_dump: str) -> None:
    psql("DROP SCHEMA d3e_replay CASCADE;")
    psql_script(stale_dump)


def activate_restore(epoch: int) -> None:
    psql(
        f"UPDATE d3e_replay.recovery_fence SET epoch={epoch},reconciled=FALSE WHERE singleton=TRUE;"
    )
    psql(
        f"UPDATE d3e_replay.redrive SET recovery_epoch={epoch},"
        "state='reconciliation_required',worker_id=NULL,attempt_token=NULL,"
        "ambiguity_reason='restore_fence_requires_reconciliation' "
        "WHERE state='attempting' OR (state='prepared' AND attempt_generation>0);"
    )


def rehydrate_consumed(epoch: int) -> None:
    rows = psql(
        "SELECT client_principal||'|'||jti||'|'||effect_id||'|'||result_ref "
        "FROM d3e_replay_control.consumed ORDER BY client_principal,jti;"
    )
    for row in filter(None, rows.splitlines()):
        client, jti, effect, result = row.split("|", 3)
        prior = psql(
            "SELECT COALESCE(effect_id,'')||'|'||COALESCE(result_ref,'') "
            "FROM d3e_replay.replay_identity "
            f"WHERE client_principal={lit(client)} AND jti={lit(jti)};"
        )
        if prior and prior != f"{effect}|{result}":
            raise RuntimeError("restored replay identity conflicts with current consumed authority")
        psql(
            "INSERT INTO d3e_replay.replay_identity("
            "client_principal,jti,recovery_epoch,state,attempt_generation,effect_id,result_ref"
            f") VALUES({lit(client)},{lit(jti)},{epoch},'consumed',1,{lit(effect)},{lit(result)}) "
            "ON CONFLICT(client_principal,jti) DO UPDATE SET "
            "recovery_epoch=EXCLUDED.recovery_epoch,state='consumed',"
            "effect_id=EXCLUDED.effect_id,result_ref=EXCLUDED.result_ref;"
        )
        psql(
            "INSERT INTO d3e_replay.effect_ledger(effect_id,client_principal,jti,result_ref) "
            f"VALUES({lit(effect)},{lit(client)},{lit(jti)},{lit(result)}) "
            "ON CONFLICT(effect_id) DO NOTHING;"
        )


def reconcile_restore(epoch: int) -> None:
    rehydrate_consumed(epoch)
    ops = psql(
        "SELECT operation_id FROM d3e_replay.redrive "
        "WHERE state='reconciliation_required' ORDER BY operation_id;"
    )
    for op in filter(None, ops.splitlines()):
        state = psql(
            f"SELECT state FROM d3e_replay_control.probe WHERE operation_id={lit(op)};"
        )
        if state == "confirmed":
            assert reconcile_confirmed(op)
        elif state == "absent":
            assert reconcile_absent(op)
        else:
            raise RuntimeError("restore effect state remains unknown")

    unresolved = psql(
        "SELECT count(*) FROM d3e_replay.redrive WHERE state='reconciliation_required';"
    )
    assert unresolved == "0"
    psql(
        f"UPDATE d3e_replay.recovery_fence SET reconciled=TRUE "
        f"WHERE singleton=TRUE AND epoch={epoch};"
    )


def prove_restore(stale_dump: str, restore_op: str) -> None:
    advance_recovery_epoch(2)
    restore_stale_app_schema(stale_dump)

    assert psql(
        "SELECT count(*) FROM d3e_replay.replay_identity "
        "WHERE client_principal='client-private-jwt-a' AND jti='jwt-jti-one';"
    ) == "0"
    assert psql(
        f"SELECT state||'|'||attempt_generation FROM d3e_replay.redrive "
        f"WHERE operation_id={lit(restore_op)};"
    ) == "attempting|1"

    assert consume(
        "client-private-jwt-a", "jwt-jti-one", "session-effect-one", "session-lineage-one", 1
    ) == "BLOCKED"
    assert consume(
        "client-private-jwt-a", "jwt-jti-one", "session-effect-one", "session-lineage-one", 2
    ) == "BLOCKED"
    assert claim_redrive(restore_op, "stale-worker", "stale-token", 1) == "BLOCKED"
    assert claim_redrive(restore_op, "new-worker", "new-token", 2) == "BLOCKED"

    activate_restore(2)
    assert consume(
        "client-private-jwt-a", "jwt-jti-one", "session-effect-one", "session-lineage-one", 2
    ) == "BLOCKED"
    assert claim_redrive(restore_op, "new-worker", "new-token", 2) == "BLOCKED"

    reconcile_restore(2)

    assert consume(
        "client-private-jwt-a", "jwt-jti-one", "session-effect-one", "session-lineage-one", 2
    ) == "OBSERVE"
    assert psql(
        f"SELECT state||'|'||attempt_generation FROM d3e_replay.redrive "
        f"WHERE operation_id={lit(restore_op)};"
    ) == "completed|1"
    assert effect_count(restore_op) == 1

    print(
        "d3_e_replay_consumed_identity_survives_restore_loss=PASS "
        "actual_pg_dump_restore=true fresh_recovery_epoch_external_to_stale_snapshot=true "
        "missing_restored_identity_not_safe=true stale_epoch_callers_fenced=true "
        "restore_fenced_before_workers=true consumed_identity_rehydrated=true "
        "stale_attempt_nonresurrection=true confirmed_effect_not_repeated=true"
    )


def main() -> None:
    init_db()

    restore_op = "restore-stale-attempt"
    prepare_redrive(restore_op, 11, 1)
    assert claim_redrive(restore_op, "old-worker", "old-token", 1) == "1"
    stale_dump = dump_app_schema()

    prove_single_winner()
    prove_partition()
    prove_redrive()
    prove_absence_effect_race()

    assert external_effect(
        restore_op, 1, "old-token", "effect-restore", "restore-result", "restore-confirm"
    ) == "WIN"
    assert complete_redrive(restore_op, 1, "restore-result")

    prove_restore(stale_dump, restore_op)

    print(
        "d3_e_replay_redrive_conformance=PASS postgres_truth=true "
        "single_winner=true partition_fail_closed=true "
        "absence_effect_race_serialized=true redrive_reconciliation=true "
        "restore_nonresurrection=true c3_numerics_not_selected=true"
    )


if __name__ == "__main__":
    main()
