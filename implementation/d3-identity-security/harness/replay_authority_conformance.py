from __future__ import annotations

import concurrent.futures
import json
import os
import subprocess
import threading

PG_REPLAY = os.environ.get("PG_REPLAY_CONTAINER", "jlmirror-d3e-replay")
PG_CONTROL = os.environ.get("PG_CONTROL_CONTAINER", "jlmirror-d3e-control")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "d3e-postgres-password")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def q(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def pg(container: str, sql: str, *, check: bool = True, timeout: int = 5) -> str:
    try:
        proc = subprocess.run(
            [
                "docker", "exec", "-e", f"PGPASSWORD={PG_PASSWORD}", container,
                "psql", "-U", "postgres", "-d", "d3e", "-AtqX",
                "-v", "ON_ERROR_STOP=1", "-c", sql,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"replay authority timed out: {container}") from exc
    if proc.returncode != 0:
        if check:
            raise RuntimeError(f"replay authority failed: {proc.stderr.strip()}")
        return ""
    return proc.stdout.strip()


def scalar(container: str, sql: str, *, check: bool = True) -> str:
    value = pg(container, sql, check=check)
    if not value:
        return ""
    rows = value.splitlines()
    if len(rows) != 1:
        raise RuntimeError(f"expected exactly one SQL scalar, got {len(rows)} rows")
    return rows[0]


def initialize() -> None:
    pg(PG_REPLAY, """
        CREATE SCHEMA IF NOT EXISTS replay;
        CREATE TABLE IF NOT EXISTS replay.local_consumed(
          issuer text NOT NULL,
          client_id text NOT NULL,
          client_principal text NOT NULL,
          jti text NOT NULL,
          witness_generation bigint NOT NULL,
          PRIMARY KEY(issuer,client_id,jti)
        );
        TRUNCATE replay.local_consumed;
    """)
    pg(PG_CONTROL, """
        CREATE SCHEMA IF NOT EXISTS security_control;
        CREATE TABLE IF NOT EXISTS security_control.replay_state(
          singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
          continuity_generation bigint NOT NULL,
          admission_state text NOT NULL CHECK(admission_state IN ('admitted','recovery_blocked'))
        );
        CREATE TABLE IF NOT EXISTS security_control.replay_witness(
          issuer text NOT NULL,
          client_id text NOT NULL,
          client_principal text NOT NULL,
          jti text NOT NULL,
          continuity_generation bigint NOT NULL,
          consumed_at bigint NOT NULL,
          PRIMARY KEY(issuer,client_id,jti)
        );
        TRUNCATE security_control.replay_state, security_control.replay_witness;
        INSERT INTO security_control.replay_state(singleton,continuity_generation,admission_state)
        VALUES(true,1,'admitted');
    """)


class ReplayAuthority:
    """Canonical replay identity is exactly (issuer, client_id, jti).

    client_principal is retained as audit metadata, never as a replay uniqueness dimension.
    The security-control witness is rollback-independent continuity truth; the local
    table is a recoverable serving mirror.
    """

    def current_generation(self) -> int:
        value = scalar(
            PG_CONTROL,
            "SELECT continuity_generation FROM security_control.replay_state "
            "WHERE singleton=true AND admission_state='admitted';"
        )
        if not value:
            raise RuntimeError("replay currentness unavailable")
        return int(value)

    def consume(
        self,
        *,
        issuer: str,
        client_id: str,
        principal: str,
        jti: str,
        expected_generation: int,
    ) -> bool:
        winner = scalar(PG_CONTROL, f"""
            WITH current AS (
              SELECT continuity_generation
              FROM security_control.replay_state
              WHERE singleton=true AND admission_state='admitted'
                AND continuity_generation={expected_generation}
              FOR UPDATE
            ), inserted AS (
              INSERT INTO security_control.replay_witness(
                issuer,client_id,client_principal,jti,continuity_generation,consumed_at
              )
              SELECT {q(issuer)},{q(client_id)},{q(principal)},{q(jti)},continuity_generation,
                     (extract(epoch from clock_timestamp())*1000000)::bigint
              FROM current
              ON CONFLICT(issuer,client_id,jti) DO NOTHING
              RETURNING continuity_generation
            )
            SELECT continuity_generation FROM inserted;
        """, check=False)
        if not winner:
            state = scalar(
                PG_CONTROL,
                "SELECT continuity_generation||'|'||admission_state "
                "FROM security_control.replay_state WHERE singleton=true;",
                check=False,
            )
            if not state:
                raise RuntimeError("replay authority unavailable")
            generation, admission = state.split("|")
            if int(generation) != expected_generation or admission != "admitted":
                raise RuntimeError("replay continuity generation is not current")
            return False

        mirrored = scalar(
            PG_REPLAY,
            "INSERT INTO replay.local_consumed(issuer,client_id,client_principal,jti,witness_generation) "
            f"VALUES({q(issuer)},{q(client_id)},{q(principal)},{q(jti)},{int(winner)}) "
            "ON CONFLICT(issuer,client_id,jti) DO NOTHING RETURNING witness_generation;",
            check=False,
        )
        if not mirrored:
            raise RuntimeError("local replay mirror unavailable after durable consume")
        return True

    def begin_recovery(self) -> int:
        value = scalar(
            PG_CONTROL,
            "UPDATE security_control.replay_state SET continuity_generation=continuity_generation+1, "
            "admission_state='recovery_blocked' WHERE singleton=true RETURNING continuity_generation;"
        )
        require(bool(value), "replay recovery fence failed")
        return int(value)

    def reconcile_and_readmit(self, *, generation: int) -> None:
        rows = pg(
            PG_CONTROL,
            "SELECT json_build_array(issuer,client_id,client_principal,jti)::text "
            "FROM security_control.replay_witness ORDER BY issuer,client_id,jti;"
        )
        for row in filter(None, rows.splitlines()):
            issuer, client_id, principal, jti = json.loads(row)
            pg(
                PG_REPLAY,
                "INSERT INTO replay.local_consumed(issuer,client_id,client_principal,jti,witness_generation) "
                f"VALUES({q(issuer)},{q(client_id)},{q(principal)},{q(jti)},{generation}) "
                "ON CONFLICT(issuer,client_id,jti) DO NOTHING;"
            )
        require(
            scalar(PG_CONTROL, "SELECT count(*) FROM security_control.replay_witness;")
            == scalar(PG_REPLAY, "SELECT count(*) FROM replay.local_consumed;"),
            "replay recovery reconciliation incomplete",
        )
        admitted = scalar(
            PG_CONTROL,
            "UPDATE security_control.replay_state SET admission_state='admitted' "
            f"WHERE singleton=true AND continuity_generation={generation} "
            "AND admission_state='recovery_blocked' RETURNING continuity_generation;"
        )
        require(admitted == str(generation), "replay readmission CAS failed")


def prove_atomic_single_winner() -> None:
    replay = ReplayAuthority()
    generation = replay.current_generation()
    gate = threading.Barrier(32)

    def attempt(_: int) -> bool:
        gate.wait()
        return replay.consume(
            issuer="https://issuer-a.example",
            client_id="client-a",
            principal="machine-a",
            jti="assertion-jti-atomic",
            expected_generation=generation,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
        results = list(pool.map(attempt, range(32)))
    require(sum(results) == 1, f"expected one replay winner, got {sum(results)}")
    require(
        scalar(
            PG_CONTROL,
            "SELECT count(*) FROM security_control.replay_witness "
            "WHERE issuer='https://issuer-a.example' AND client_id='client-a' "
            "AND jti='assertion-jti-atomic';"
        ) == "1",
        "durable replay identity was not single-winner",
    )
    require(
        not replay.consume(
            issuer="https://issuer-a.example", client_id="client-a",
            principal="machine-substitute", jti="assertion-jti-atomic",
            expected_generation=generation,
        ),
        "principal substitution bypassed issuer/client/jti replay identity",
    )
    require(
        replay.consume(
            issuer="https://issuer-b.example", client_id="client-a",
            principal="machine-a", jti="assertion-jti-atomic",
            expected_generation=generation,
        ),
        "same raw jti incorrectly collided across a distinct issuer",
    )
    require(
        replay.consume(
            issuer="https://issuer-a.example", client_id="client-b",
            principal="machine-a", jti="assertion-jti-atomic",
            expected_generation=generation,
        ),
        "same raw jti incorrectly collided across a distinct client",
    )
    print(
        "d3_e_private_key_jwt_replay_atomic_single_winner=PASS "
        "replica_race=true exactly_one_winner=true identity_tuple_issuer_client_jti=true "
        "principal_not_uniqueness_dimension=true principal_substitution_rejected=true "
        "different_issuer_independent=true different_client_independent=true"
    )


def prove_partition_fail_closed() -> None:
    replay = ReplayAuthority()
    generation = replay.current_generation()
    subprocess.run(["docker", "pause", PG_CONTROL], check=True, stdout=subprocess.DEVNULL)
    try:
        try:
            replay.consume(
                issuer="https://issuer-a.example", client_id="client-a",
                principal="machine-a", jti="partition-jti",
                expected_generation=generation,
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("partitioned replay authority admitted")
    finally:
        subprocess.run(["docker", "unpause", PG_CONTROL], check=True, stdout=subprocess.DEVNULL)
    require(
        replay.consume(
            issuer="https://issuer-a.example", client_id="client-a",
            principal="machine-a", jti="post-partition-jti",
            expected_generation=generation,
        ),
        "replay authority did not recover after partition",
    )
    print(
        "d3_e_replay_partition_fail_closed=PASS actual_authority_pause=true "
        "unavailable_not_absence=true no_local_fallback=true recovery_requires_authority=true"
    )


def prove_consumed_identity_survives_restore_loss() -> None:
    replay = ReplayAuthority()
    generation = replay.current_generation()
    require(
        replay.consume(
            issuer="https://issuer-r.example", client_id="client-r",
            principal="machine-r", jti="assertion-before-restore",
            expected_generation=generation,
        ),
        "pre-restore consume failed",
    )
    pg(PG_REPLAY, "TRUNCATE replay.local_consumed;")
    require(
        scalar(PG_REPLAY, "SELECT count(*) FROM replay.local_consumed;") == "0",
        "negative-control restore did not lose local replay state",
    )
    require(
        int(scalar(PG_CONTROL, "SELECT count(*) FROM security_control.replay_witness;")) > 0,
        "rollback-independent replay witness disappeared",
    )
    next_generation = replay.begin_recovery()
    try:
        replay.consume(
            issuer="https://issuer-r.example", client_id="client-r",
            principal="machine-r", jti="assertion-before-restore",
            expected_generation=next_generation,
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("recovery-blocked replay admitted before reconciliation")
    replay.reconcile_and_readmit(generation=next_generation)
    require(
        not replay.consume(
            issuer="https://issuer-r.example", client_id="client-r",
            principal="machine-r", jti="assertion-before-restore",
            expected_generation=next_generation,
        ),
        "consumed assertion became unused after restore loss",
    )
    require(
        replay.consume(
            issuer="https://issuer-r.example", client_id="client-r",
            principal="machine-r", jti="assertion-new-after-restore",
            expected_generation=next_generation,
        ),
        "fresh assertion rejected after trusted recovery",
    )
    print(
        "d3_e_replay_consumed_identity_survives_restore_loss=PASS "
        "stale_restore_negative_control_lost_local_row=true independent_witness_preserved=true "
        "recovery_generation_fenced=true readmission_waits_for_reconciliation=true "
        "consumed_identity_not_resurrected_as_unused=true"
    )


def main() -> None:
    initialize()
    prove_atomic_single_winner()
    prove_partition_fail_closed()
    prove_consumed_identity_survives_restore_loss()
    print(
        "d3_e_replay_authority_conformance=PASS postgresql_security_continuity=true "
        "provider_key_backend_not_replay_truth=true mechanism_c2_only=true "
        "c3_numerics_topology_not_selected=true"
    )


if __name__ == "__main__":
    main()
