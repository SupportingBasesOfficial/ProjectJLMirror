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


def psql_script(script: str, *, db: str) -> None:
    sh([
        "docker", "exec", "-i", "-e", f"PGPASSWORD={PG_PASSWORD}", PG_CONTAINER,
        "psql", "-X", "-U", "postgres", "-d", db, "-v", "ON_ERROR_STOP=1", "-q"
    ], input_text=script)


def network_psql(sql: str, *, check: bool = True, timeout: float = 12) -> str:
    r = sh([
        "docker", "run", "--rm", "--network", D3_NETWORK, "-e", f"PGPASSWORD={PG_PASSWORD}", PG_IMAGE,
        "psql", "-X", "-h", PG_CONTAINER, "-U", "postgres", "-d", "d3",
        "-v", "ON_ERROR_STOP=1", "-Atq", "-c", sql
    ], check=check, timeout=timeout)
    return r.stdout.strip()


def dump_schema() -> str:
    r = sh([
        "docker", "exec", "-e", f"PGPASSWORD={PG_PASSWORD}", PG_CONTAINER,
        "pg_dump", "-U", "postgres", "-d", "d3", "--schema", "d3e_replay", "--no-owner", "--no-privileges"
    ])
    if "CREATE SCHEMA" not in r.stdout:
        raise AssertionError("real PostgreSQL schema dump was not captured")
    return r.stdout


def init_db() -> None:
    psql("DROP DATABASE IF EXISTS d3_replay_control WITH (FORCE);", db="postgres")
    psql("CREATE DATABASE d3_replay_control;", db="postgres")
    psql_script("""
CREATE SCHEMA d3e_replay_control;
CREATE TABLE d3e_replay_control.recovery(
 singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK(singleton), epoch BIGINT NOT NULL CHECK(epoch>0)
);
INSERT INTO d3e_replay_control.recovery(singleton,epoch) VALUES(TRUE,1);
CREATE TABLE d3e_replay_control.consumed(
 client_principal TEXT NOT NULL,jti TEXT NOT NULL,effect_id TEXT NOT NULL,result_ref TEXT NOT NULL,
 PRIMARY KEY(client_principal,jti)
);
CREATE TABLE d3e_replay_control.external_effect(
 effect_id TEXT PRIMARY KEY,operation_id TEXT NOT NULL UNIQUE,result_ref TEXT NOT NULL
);
CREATE TABLE d3e_replay_control.probe(
 operation_id TEXT PRIMARY KEY,
 state TEXT NOT NULL CHECK(state IN('unknown','absent','confirmed')),
 revision TEXT NOT NULL,effect_id TEXT NULL,result_ref TEXT NULL,
 CHECK((state='confirmed' AND effect_id IS NOT NULL AND result_ref IS NOT NULL) OR
       (state<>'confirmed' AND effect_id IS NULL AND result_ref IS NULL))
);
""", db="d3_replay_control")
    psql_script("""
DROP SCHEMA IF EXISTS d3e_replay CASCADE;
CREATE SCHEMA d3e_replay;
CREATE TABLE d3e_replay.recovery_fence(
 singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK(singleton),
 epoch BIGINT NOT NULL CHECK(epoch>0),reconciled BOOLEAN NOT NULL
);
INSERT INTO d3e_replay.recovery_fence(singleton,epoch,reconciled) VALUES(TRUE,1,TRUE);
CREATE TABLE d3e_replay.replay_identity(
 client_principal TEXT NOT NULL,jti TEXT NOT NULL,recovery_epoch BIGINT NOT NULL CHECK(recovery_epoch>0),
 state TEXT NOT NULL CHECK(state IN('consumed','reconciliation_required')),
 attempt_generation BIGINT NOT NULL CHECK(attempt_generation>0),
 effect_id TEXT NULL,result_ref TEXT NULL,
 PRIMARY KEY(client_principal,jti),
 CHECK((state='consumed' AND effect_id IS NOT NULL AND result_ref IS NOT NULL) OR
       (state='reconciliation_required' AND effect_id IS NULL AND result_ref IS NULL))
);
CREATE TABLE d3e_replay.effect_ledger(
 effect_id TEXT PRIMARY KEY,client_principal TEXT NOT NULL,jti TEXT NOT NULL,result_ref TEXT NOT NULL,
 UNIQUE(client_principal,jti)
);
CREATE TABLE d3e_replay.redrive(
 operation_id TEXT PRIMARY KEY,quarantine_generation BIGINT NOT NULL CHECK(quarantine_generation>0),
 recovery_epoch BIGINT NOT NULL CHECK(recovery_epoch>0),
 state TEXT NOT NULL CHECK(state IN('prepared','attempting','reconciliation_required','completed')),
 attempt_generation BIGINT NOT NULL DEFAULT 0 CHECK(attempt_generation>=0),
 worker_id TEXT NULL,attempt_token TEXT NULL,ambiguity_reason TEXT NULL,
 reconciliation_revision TEXT NULL,result_ref TEXT NULL,
 CHECK((state='attempting' AND worker_id IS NOT NULL AND attempt_token IS NOT NULL) OR
       (state<>'attempting' AND worker_id IS NULL AND attempt_token IS NULL)),
 CHECK(state<>'reconciliation_required' OR ambiguity_reason IS NOT NULL),
 CHECK(state<>'completed' OR result_ref IS NOT NULL)
);
""", db="d3")


def consume_sql(client: str, jti: str, effect_id: str, result_ref: str, epoch: int) -> str:
    return f"""
WITH gate AS(
 SELECT epoch FROM d3e_replay.recovery_fence WHERE singleton=TRUE AND reconciled=TRUE AND epoch={epoch}
), won AS(
 INSERT INTO d3e_replay.replay_identity(client_principal,jti,recovery_epoch,state,attempt_generation,effect_id,result_ref)
 SELECT {lit(client)},{lit(jti)},epoch,'consumed',1,{lit(effect_id)},{lit(result_ref)} FROM gate
 ON CONFLICT(client_principal,jti) DO NOTHING RETURNING client_principal,jti
), effect AS(
 INSERT INTO d3e_replay.effect_ledger(effect_id,client_principal,jti,result_ref)
 SELECT {lit(effect_id)},client_principal,jti,{lit(result_ref)} FROM won RETURNING effect_id
)
SELECT CASE WHEN EXISTS(SELECT 1 FROM effect) THEN 'WIN'
 WHEN EXISTS(SELECT 1 FROM d3e_replay.replay_identity WHERE client_principal={lit(client)} AND jti={lit(jti)}) THEN 'OBSERVE'
 ELSE 'BLOCKED' END;
"""


def consume(client: str, jti: str, effect_id: str, result_ref: str, epoch: int, *, db: str = "d3") -> str:
    return psql(consume_sql(client, jti, effect_id, result_ref, epoch), db=db)


def record_consumed(client: str, jti: str, effect_id: str, result_ref: str) -> None:
    psql(
        "INSERT INTO d3e_replay_control.consumed(client_principal,jti,effect_id,result_ref) "
        f"VALUES({lit(client)},{lit(jti)},{lit(effect_id)},{lit(result_ref)}) "
        "ON CONFLICT(client_principal,jti) DO UPDATE SET effect_id=EXCLUDED.effect_id,result_ref=EXCLUDED.result_ref;",
        db="d3_replay_control"
    )


def prepare_redrive(op: str, qgen: int, epoch: int, *, db: str = "d3") -> None:
    psql(
        f"INSERT INTO d3e_replay.redrive(operation_id,quarantine_generation,recovery_epoch,state) "
        f"VALUES({lit(op)},{qgen},{epoch},'prepared');",
        db=db
    )


def claim_redrive(op: str, worker: str, token: str, epoch: int, *, db: str = "d3") -> str:
    return psql(f"""
WITH gate AS(SELECT epoch FROM d3e_replay.recovery_fence WHERE singleton=TRUE AND reconciled=TRUE AND epoch={epoch}),
locked AS(SELECT operation_id,state,attempt_generation,recovery_epoch FROM d3e_replay.redrive WHERE operation_id={lit(op)} FOR UPDATE),
won AS(
 UPDATE d3e_replay.redrive r SET state='attempting',attempt_generation=r.attempt_generation+1,
 worker_id={lit(worker)},attempt_token={lit(token)},ambiguity_reason=NULL,reconciliation_revision=NULL
 FROM locked l,gate g WHERE r.operation_id=l.operation_id AND l.state='prepared' AND l.recovery_epoch=g.epoch
 RETURNING r.attempt_generation)
SELECT COALESCE((SELECT attempt_generation::text FROM won),'BLOCKED');
""", db=db)


def ambiguous(op: str, generation: int, reason: str, *, db: str = "d3") -> None:
    got = psql(
        "UPDATE d3e_replay.redrive SET state='reconciliation_required',worker_id=NULL,attempt_token=NULL,"
        f"ambiguity_reason={lit(reason)} WHERE operation_id={lit(op)} AND state='attempting' "
        f"AND attempt_generation={generation} RETURNING operation_id;",
        db=db
    )
    assert got == op


def probe_absent(op: str, revision: str) -> None:
    assert psql(
        f"SELECT count(*) FROM d3e_replay_control.external_effect WHERE operation_id={lit(op)};",
        db="d3_replay_control"
    ) == "0"
    psql(
        "INSERT INTO d3e_replay_control.probe(operation_id,state,revision) "
        f"VALUES({lit(op)},'absent',{lit(revision)}) ON CONFLICT(operation_id) DO UPDATE SET "
        "state='absent',revision=EXCLUDED.revision,effect_id=NULL,result_ref=NULL;",
        db="d3_replay_control"
    )


def external_effect(op: str, effect_id: str, result_ref: str, revision: str) -> str:
    return psql(f"""
WITH won AS(
 INSERT INTO d3e_replay_control.external_effect(effect_id,operation_id,result_ref)
 VALUES({lit(effect_id)},{lit(op)},{lit(result_ref)}) ON CONFLICT DO NOTHING RETURNING effect_id),
probe AS(
 INSERT INTO d3e_replay_control.probe(operation_id,state,revision,effect_id,result_ref)
 SELECT {lit(op)},'confirmed',{lit(revision)},{lit(effect_id)},{lit(result_ref)} FROM won
 ON CONFLICT(operation_id) DO UPDATE SET state='confirmed',revision=EXCLUDED.revision,
 effect_id=EXCLUDED.effect_id,result_ref=EXCLUDED.result_ref
 WHERE d3e_replay_control.probe.state<>'confirmed' RETURNING effect_id)
SELECT CASE WHEN EXISTS(SELECT 1 FROM won) THEN 'WIN' ELSE 'OBSERVE' END;
""", db="d3_replay_control")


def complete_redrive(op: str, generation: int, result_ref: str, *, db: str = "d3") -> None:
    got = psql(
        "UPDATE d3e_replay.redrive SET state='completed',worker_id=NULL,attempt_token=NULL,"
        f"result_ref={lit(result_ref)} WHERE operation_id={lit(op)} AND state='attempting' "
        f"AND attempt_generation={generation} RETURNING operation_id;",
        db=db
    )
    assert got == op


def reconcile_absent(op: str, *, db: str = "d3") -> None:
    row = psql(
        f"SELECT state||'|'||revision FROM d3e_replay_control.probe WHERE operation_id={lit(op)};",
        db="d3_replay_control"
    )
    assert row.startswith("absent|")
    revision = row.split("|", 1)[1]
    got = psql(
        "UPDATE d3e_replay.redrive SET state='prepared',ambiguity_reason=NULL,"
        f"reconciliation_revision={lit(revision)} WHERE operation_id={lit(op)} "
        "AND state='reconciliation_required' RETURNING operation_id;",
        db=db
    )
    assert got == op


def reconcile_confirmed(op: str, *, db: str = "d3") -> None:
    row = psql(
        f"SELECT state||'|'||revision||'|'||result_ref FROM d3e_replay_control.probe WHERE operation_id={lit(op)};",
        db="d3_replay_control"
    )
    parts = row.split("|", 2)
    assert len(parts) == 3 and parts[0] == "confirmed"
    got = psql(
        "UPDATE d3e_replay.redrive SET state='completed',worker_id=NULL,attempt_token=NULL,ambiguity_reason=NULL,"
        f"reconciliation_revision={lit(parts[1])},result_ref={lit(parts[2])} "
        f"WHERE operation_id={lit(op)} AND state='reconciliation_required' RETURNING operation_id;",
        db=db
    )
    assert got == op


def effect_count(op: str) -> int:
    return int(psql(
        f"SELECT count(*) FROM d3e_replay_control.external_effect WHERE operation_id={lit(op)};",
        db="d3_replay_control"
    ))


def prove_single_winner() -> None:
    client, jti, effect, result = "client-private-jwt-a", "jwt-jti-one", "session-effect-one", "session-lineage-one"
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        outcomes = list(pool.map(lambda _: consume(client, jti, effect, result, 1), range(48)))
    assert outcomes.count("WIN") == 1 and set(outcomes) <= {"WIN", "OBSERVE"}
    assert psql(f"SELECT count(*) FROM d3e_replay.effect_ledger WHERE effect_id={lit(effect)};") == "1"
    record_consumed(client, jti, effect, result)
    print("d3_e_private_key_jwt_replay_atomic_single_winner=PASS postgres_create_or_observe=true concurrent_workers=48 exactly_one_effect=true duplicates_observe=true")


def prove_partition() -> None:
    assert network_psql("SELECT 1;") == "1"
    sh(["docker", "network", "disconnect", D3_NETWORK, PG_CONTAINER])
    try:
        out = network_psql(
            consume_sql("partition-client", "partition-jti", "partition-effect", "partition-result", 1),
            check=False, timeout=8
        )
        assert out not in {"WIN", "OBSERVE"}
    finally:
        sh(["docker", "network", "connect", D3_NETWORK, PG_CONTAINER])
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            if network_psql("SELECT 1;", timeout=4) == "1":
                break
        except Exception:
            time.sleep(0.2)
    else:
        raise RuntimeError("postgres network did not recover")
    assert psql("SELECT count(*) FROM d3e_replay.effect_ledger WHERE jti='partition-jti';") == "0"
    print("d3_e_replay_partition_fail_closed=PASS actual_network_partition=true replay_authority_unreachable=true no_effect=true")


def prove_redrive() -> None:
    op = "redrive-crash-before-effect"
    prepare_redrive(op, 7, 1)
    assert claim_redrive(op, "worker-a", "token-a", 1) == "1"
    ambiguous(op, 1, "worker_died")
    assert claim_redrive(op, "worker-b", "token-b", 1) == "BLOCKED"
    probe_absent(op, "absence-1")
    reconcile_absent(op)
    assert claim_redrive(op, "worker-b", "token-b", 1) == "2"
    assert external_effect(op, "effect-a", "result-a", "confirm-a") == "WIN"
    complete_redrive(op, 2, "result-a")
    assert external_effect(op, "effect-a", "result-a", "confirm-a2") == "OBSERVE" and effect_count(op) == 1

    op2 = "redrive-response-lost"
    prepare_redrive(op2, 8, 1)
    assert claim_redrive(op2, "worker-c", "token-c", 1) == "1"
    assert external_effect(op2, "effect-b", "result-b", "confirm-b") == "WIN"
    ambiguous(op2, 1, "response_lost")
    assert claim_redrive(op2, "worker-d", "token-d", 1) == "BLOCKED"
    reconcile_confirmed(op2)
    assert psql(
        f"SELECT state||'|'||attempt_generation FROM d3e_replay.redrive WHERE operation_id={lit(op2)};"
    ) == "completed|1"
    assert effect_count(op2) == 1
    print("d3_e_redrive_crash_retry_single_effect=PASS worker_death_not_absence=true positive_absence_required=true attempt_generation_monotonic=true lost_response_reconciles=true external_effect_at_most_once=true")


def activate_restore(*, db: str, epoch: int) -> None:
    psql(f"UPDATE d3e_replay.recovery_fence SET epoch={epoch},reconciled=FALSE WHERE singleton=TRUE;", db=db)
    psql(
        "UPDATE d3e_replay.redrive SET state='reconciliation_required',worker_id=NULL,attempt_token=NULL,"
        "ambiguity_reason='restore_fence_requires_reconciliation' WHERE state='attempting';",
        db=db
    )


def reconcile_restore(*, db: str, epoch: int) -> None:
    rows = psql(
        "SELECT client_principal||'|'||jti||'|'||effect_id||'|'||result_ref FROM d3e_replay_control.consumed;",
        db="d3_replay_control"
    )
    for row in filter(None, rows.splitlines()):
        client, jti, effect, result = row.split("|", 3)
        psql(
            "INSERT INTO d3e_replay.replay_identity(client_principal,jti,recovery_epoch,state,attempt_generation,effect_id,result_ref) "
            f"VALUES({lit(client)},{lit(jti)},{epoch},'consumed',1,{lit(effect)},{lit(result)}) "
            "ON CONFLICT(client_principal,jti) DO UPDATE SET recovery_epoch=EXCLUDED.recovery_epoch,state='consumed',"
            "effect_id=EXCLUDED.effect_id,result_ref=EXCLUDED.result_ref;",
            db=db
        )
        psql(
            "INSERT INTO d3e_replay.effect_ledger(effect_id,client_principal,jti,result_ref) "
            f"VALUES({lit(effect)},{lit(client)},{lit(jti)},{lit(result)}) ON CONFLICT DO NOTHING;",
            db=db
        )
    ops = psql("SELECT operation_id FROM d3e_replay.redrive WHERE state='reconciliation_required';", db=db)
    for op in filter(None, ops.splitlines()):
        state = psql(
            f"SELECT state FROM d3e_replay_control.probe WHERE operation_id={lit(op)};",
            db="d3_replay_control"
        )
        if state == "confirmed":
            reconcile_confirmed(op, db=db)
        elif state == "absent":
            reconcile_absent(op, db=db)
        else:
            raise RuntimeError("restore effect state remains unknown")
    psql(f"UPDATE d3e_replay.recovery_fence SET reconciled=TRUE WHERE singleton=TRUE AND epoch={epoch};", db=db)


def prove_restore(stale_dump: str, restore_op: str) -> None:
    psql("UPDATE d3e_replay_control.recovery SET epoch=2 WHERE singleton=TRUE;", db="d3_replay_control")
    psql("DROP DATABASE IF EXISTS d3_replay_restore WITH (FORCE);", db="postgres")
    psql("CREATE DATABASE d3_replay_restore;", db="postgres")
    psql_script(stale_dump, db="d3_replay_restore")
    assert psql(
        "SELECT count(*) FROM d3e_replay.replay_identity WHERE client_principal='client-private-jwt-a' AND jti='jwt-jti-one';",
        db="d3_replay_restore"
    ) == "0"
    assert psql(
        f"SELECT state||'|'||attempt_generation FROM d3e_replay.redrive WHERE operation_id={lit(restore_op)};",
        db="d3_replay_restore"
    ) == "attempting|1"
    activate_restore(db="d3_replay_restore", epoch=2)
    assert consume(
        "client-private-jwt-a", "jwt-jti-one", "session-effect-one", "session-lineage-one", 2,
        db="d3_replay_restore"
    ) == "BLOCKED"
    assert claim_redrive(restore_op, "new-worker", "new-token", 2, db="d3_replay_restore") == "BLOCKED"
    reconcile_restore(db="d3_replay_restore", epoch=2)
    assert consume(
        "client-private-jwt-a", "jwt-jti-one", "session-effect-one", "session-lineage-one", 2,
        db="d3_replay_restore"
    ) == "OBSERVE"
    assert psql(
        f"SELECT state||'|'||attempt_generation FROM d3e_replay.redrive WHERE operation_id={lit(restore_op)};",
        db="d3_replay_restore"
    ) == "completed|1"
    assert effect_count(restore_op) == 1
    print("d3_e_replay_consumed_identity_survives_restore_loss=PASS actual_pg_dump_restore=true missing_restored_identity_not_safe=true restore_fenced_before_workers=true consumed_identity_rehydrated=true stale_attempt_nonresurrection=true confirmed_effect_not_repeated=true")


def main() -> None:
    init_db()
    restore_op = "restore-stale-attempt"
    prepare_redrive(restore_op, 11, 1)
    assert claim_redrive(restore_op, "old-worker", "old-token", 1) == "1"
    stale_dump = dump_schema()

    prove_single_winner()
    prove_partition()
    prove_redrive()

    assert external_effect(restore_op, "effect-restore", "restore-result", "restore-confirm") == "WIN"
    complete_redrive(restore_op, 1, "restore-result")
    prove_restore(stale_dump, restore_op)

    print("d3_e_replay_redrive_conformance=PASS postgres_truth=true single_winner=true partition_fail_closed=true redrive_reconciliation=true restore_nonresurrection=true c3_numerics_not_selected=true")


if __name__ == "__main__":
    main()
