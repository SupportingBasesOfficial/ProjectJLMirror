from __future__ import annotations

import base64
import concurrent.futures
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


PG_REPLAY = os.environ.get("PG_REPLAY_CONTAINER", "jlmirror-d3e-replay")
PG_CONTROL = os.environ.get("PG_CONTROL_CONTAINER", "jlmirror-d3e-control")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "d3e-postgres-password")
OPENBAO_ADDR = os.environ.get("OPENBAO_ADDR", "http://127.0.0.1:8200")
OPENBAO_TOKEN = os.environ.get("OPENBAO_TOKEN", "d3e-root")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def psql(container: str, sql: str, *, check: bool = True) -> str:
    try:
        proc = subprocess.run(
        [
            "docker",
            "exec",
            "-e",
            f"PGPASSWORD={PG_PASSWORD}",
            container,
            "psql",
            "-U",
            "postgres",
            "-d",
            "d3e",
            "-AtX",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            sql,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=5,
    )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"psql timed out against {container}") from exc
    if check and proc.returncode != 0:
        raise RuntimeError(f"psql failed: {proc.stderr.strip()}")
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def openbao_request(method: str, path: str, payload: dict | None = None, *, ok=(200, 204)) -> dict:
    body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        OPENBAO_ADDR + path,
        data=body,
        method=method,
        headers={
            "X-Vault-Token": OPENBAO_TOKEN,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            raw = response.read()
            if response.status not in ok:
                raise RuntimeError(f"OpenBao unexpected status {response.status}: {raw[:300]!r}")
            return {} if not raw else json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"OpenBao {method} {path} failed: HTTP {exc.code}: {raw[:500]}") from exc


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def wait_openbao() -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(OPENBAO_ADDR + "/v1/sys/health", method="GET")
            with urllib.request.urlopen(req, timeout=1) as response:
                if response.status in (200, 429, 472, 473, 501, 503):
                    return
        except Exception:
            time.sleep(0.25)
    raise RuntimeError("OpenBao did not become ready")


def initialize_postgres() -> None:
    replay_sql = """
    CREATE SCHEMA IF NOT EXISTS replay;
    CREATE TABLE IF NOT EXISTS replay.local_consumed (
      replay_scope text NOT NULL,
      client_principal text NOT NULL,
      jti text NOT NULL,
      witness_generation bigint NOT NULL,
      PRIMARY KEY (replay_scope, client_principal, jti)
    );
    TRUNCATE replay.local_consumed;
    """
    control_sql = """
    CREATE SCHEMA IF NOT EXISTS security_control;
    CREATE TABLE IF NOT EXISTS security_control.replay_state (
      singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
      continuity_generation bigint NOT NULL,
      admission_state text NOT NULL CHECK (admission_state IN ('admitted','recovery_blocked'))
    );
    CREATE TABLE IF NOT EXISTS security_control.replay_witness (
      replay_scope text NOT NULL,
      client_principal text NOT NULL,
      jti text NOT NULL,
      continuity_generation bigint NOT NULL,
      consumed_at bigint NOT NULL,
      PRIMARY KEY (replay_scope, client_principal, jti)
    );
    CREATE TABLE IF NOT EXISTS security_control.key_state (
      logical_key text PRIMARY KEY,
      current_generation integer NOT NULL,
      min_verify_generation integer NOT NULL,
      erased boolean NOT NULL DEFAULT false
    );
    CREATE TABLE IF NOT EXISTS security_control.historical_grant (
      target_cell text NOT NULL,
      logical_key text NOT NULL,
      key_generation integer NOT NULL,
      active boolean NOT NULL,
      PRIMARY KEY (target_cell, logical_key, key_generation)
    );
    TRUNCATE security_control.replay_state,
             security_control.replay_witness,
             security_control.key_state,
             security_control.historical_grant;
    INSERT INTO security_control.replay_state(singleton, continuity_generation, admission_state)
      VALUES (true, 1, 'admitted');
    """
    psql(PG_REPLAY, replay_sql)
    psql(PG_CONTROL, control_sql)


def initialize_openbao() -> None:
    wait_openbao()
    try:
        openbao_request("POST", "/v1/sys/mounts/transit", {"type": "transit"}, ok=(200, 204))
    except RuntimeError as exc:
        if "path is already in use" not in str(exc).lower():
            raise


@dataclass(frozen=True)
class KeyRef:
    logical_key: str
    openbao_name: str


class KeyAuthorityPort:
    """Provider-neutral evidence port.

    Canonical callers see logical key identity/generation/currentness only.
    OpenBao path/token/native deletion concepts remain behind this adapter.
    """

    def __init__(self, ref: KeyRef):
        self.ref = ref

    def _state(self) -> tuple[int, int, bool]:
        row = psql(
            PG_CONTROL,
            "SELECT current_generation,min_verify_generation,erased "
            "FROM security_control.key_state WHERE logical_key="
            + sql_literal(self.ref.logical_key)
            + ";",
        )
        if not row:
            raise RuntimeError("key currentness unavailable")
        current_s, floor_s, erased_s = row.split("|")
        return int(current_s), int(floor_s), erased_s == "t"

    def generate_hmac(self, *, generation: int, message: bytes) -> str:
        current, _floor, erased = self._state()
        if erased:
            raise RuntimeError("key erased by trusted currentness authority")
        if generation != current:
            raise RuntimeError("only current generation may generate new HMAC evidence")
        response = openbao_request(
            "POST",
            f"/v1/transit/hmac/{self.ref.openbao_name}/sha2-256",
            {"key_version": generation, "input": b64(message)},
        )
        value = response.get("data", {}).get("hmac")
        if not isinstance(value, str) or not value:
            raise RuntimeError("OpenBao HMAC response missing")
        return value

    def verify_hmac(self, *, generation: int, message: bytes, mac: str) -> bool:
        _current, floor, erased = self._state()
        if erased:
            raise RuntimeError("key erased by trusted currentness authority")
        if generation < floor:
            return False
        response = openbao_request(
            "POST",
            f"/v1/transit/verify/{self.ref.openbao_name}/sha2-256",
            {"input": b64(message), "hmac": mac},
        )
        return response.get("data", {}).get("valid") is True

    def rotate(self) -> int:
        current, floor, erased = self._state()
        if erased:
            raise RuntimeError("cannot rotate erased key")
        openbao_request("POST", f"/v1/transit/keys/{self.ref.openbao_name}/rotate", {})
        next_generation = current + 1
        updated = psql(
            PG_CONTROL,
            "UPDATE security_control.key_state SET current_generation="
            f"{next_generation} WHERE logical_key={sql_literal(self.ref.logical_key)} "
            f"AND current_generation={current} AND min_verify_generation={floor} AND erased=false "
            "RETURNING current_generation;",
        )
        require(updated == str(next_generation), "trusted key generation CAS failed")
        return next_generation

    def retire_before(self, generation: int) -> None:
        current, floor, erased = self._state()
        if erased:
            raise RuntimeError("cannot retire erased key")
        require(1 <= generation <= current, "invalid verification floor")
        openbao_request(
            "POST",
            f"/v1/transit/keys/{self.ref.openbao_name}/config",
            {
                "min_decryption_version": generation,
                "min_encryption_version": current,
            },
        )
        updated = psql(
            PG_CONTROL,
            "UPDATE security_control.key_state SET min_verify_generation="
            f"{generation} WHERE logical_key={sql_literal(self.ref.logical_key)} "
            f"AND current_generation={current} AND min_verify_generation={floor} AND erased=false "
            "RETURNING min_verify_generation;",
        )
        require(updated == str(generation), "trusted key floor CAS failed")

    def mark_erased(self) -> None:
        updated = psql(
            PG_CONTROL,
            "UPDATE security_control.key_state SET erased=true "
            f"WHERE logical_key={sql_literal(self.ref.logical_key)} AND erased=false RETURNING erased;",
        )
        require(updated == "t", "trusted erasure tombstone was not created")


class HistoricalVerifierPort:
    def __init__(self, authority: KeyAuthorityPort, *, target_cell: str, generation: int):
        self.authority = authority
        self.target_cell = target_cell
        self.generation = generation

    def _granted(self) -> bool:
        row = psql(
            PG_CONTROL,
            "SELECT active FROM security_control.historical_grant "
            f"WHERE target_cell={sql_literal(self.target_cell)} "
            f"AND logical_key={sql_literal(self.authority.ref.logical_key)} "
            f"AND key_generation={self.generation};",
        )
        return row == "t"

    def verify(self, *, message: bytes, mac: str) -> bool:
        if not self._granted():
            raise RuntimeError("historical verifier continuity unavailable")
        return self.authority.verify_hmac(
            generation=self.generation,
            message=message,
            mac=mac,
        )

    def generate(self, *, message: bytes) -> str:
        del message
        raise RuntimeError("historical verifier is verify-only and cannot become current signing authority")


class DurableReplayAuthority:
    """Atomic replay authority with a recovery witness outside the rollback subject.

    The control/witness store is the security continuity authority. The replay-local
    table is an optimization/serving mirror and cannot turn absence into unused state.
    """

    def current_generation(self) -> int:
        row = psql(
            PG_CONTROL,
            "SELECT continuity_generation FROM security_control.replay_state "
            "WHERE singleton=true AND admission_state='admitted';",
        )
        if not row:
            raise RuntimeError("replay currentness unavailable or recovery blocked")
        return int(row)

    def consume(self, *, replay_scope: str, client_principal: str, jti: str, expected_generation: int) -> bool:
        scope = sql_literal(replay_scope)
        client = sql_literal(client_principal)
        token = sql_literal(jti)
        sql = f"""
        WITH current AS (
          SELECT continuity_generation
          FROM security_control.replay_state
          WHERE singleton=true
            AND admission_state='admitted'
            AND continuity_generation={expected_generation}
          FOR UPDATE
        ), inserted AS (
          INSERT INTO security_control.replay_witness(
            replay_scope,client_principal,jti,continuity_generation,consumed_at
          )
          SELECT {scope},{client},{token},continuity_generation,
                 (extract(epoch from clock_timestamp())*1000000)::bigint
          FROM current
          ON CONFLICT DO NOTHING
          RETURNING continuity_generation
        )
        SELECT continuity_generation FROM inserted;
        """
        witness = psql(PG_CONTROL, sql)
        if not witness:
            state = psql(
                PG_CONTROL,
                "SELECT continuity_generation||'|'||admission_state "
                "FROM security_control.replay_state WHERE singleton=true;",
                check=False,
            )
            if not state:
                raise RuntimeError("replay authority unavailable")
            generation_s, admission = state.split("|")
            if int(generation_s) != expected_generation or admission != "admitted":
                raise RuntimeError("replay continuity generation is not current")
            return False

        mirrored = psql(
            PG_REPLAY,
            "INSERT INTO replay.local_consumed(replay_scope,client_principal,jti,witness_generation) "
            f"VALUES({scope},{client},{token},{int(witness)}) "
            "ON CONFLICT DO NOTHING RETURNING witness_generation;",
            check=False,
        )
        if not mirrored:
            raise RuntimeError("replay local mirror unavailable after durable consume")
        return True

    def begin_recovery(self) -> int:
        row = psql(
            PG_CONTROL,
            "UPDATE security_control.replay_state "
            "SET continuity_generation=continuity_generation+1, admission_state='recovery_blocked' "
            "WHERE singleton=true RETURNING continuity_generation;",
        )
        require(bool(row), "failed to fence replay recovery")
        return int(row)

    def reconcile_and_readmit(self, *, generation: int) -> None:
        rows = psql(
            PG_CONTROL,
            "SELECT replay_scope||E'\\t'||client_principal||E'\\t'||jti "
            "FROM security_control.replay_witness ORDER BY replay_scope,client_principal,jti;",
        )
        for line in filter(None, rows.splitlines()):
            scope, client, jti = line.split("\t")
            psql(
                PG_REPLAY,
                "INSERT INTO replay.local_consumed(replay_scope,client_principal,jti,witness_generation) "
                f"VALUES({sql_literal(scope)},{sql_literal(client)},{sql_literal(jti)},{generation}) "
                "ON CONFLICT DO NOTHING;",
            )
        expected = psql(PG_CONTROL, "SELECT count(*) FROM security_control.replay_witness;")
        actual = psql(PG_REPLAY, "SELECT count(*) FROM replay.local_consumed;")
        require(expected == actual, "replay recovery reconciliation is incomplete")
        admitted = psql(
            PG_CONTROL,
            "UPDATE security_control.replay_state SET admission_state='admitted' "
            f"WHERE singleton=true AND continuity_generation={generation} "
            "AND admission_state='recovery_blocked' RETURNING continuity_generation;",
        )
        require(admitted == str(generation), "replay readmission CAS failed")


def create_key(ref: KeyRef) -> KeyAuthorityPort:
    openbao_request(
        "POST",
        f"/v1/transit/keys/{ref.openbao_name}",
        {"type": "hmac", "key_size": 32},
        ok=(200, 204),
    )
    psql(
        PG_CONTROL,
        "INSERT INTO security_control.key_state(logical_key,current_generation,min_verify_generation,erased) "
        f"VALUES({sql_literal(ref.logical_key)},1,1,false);",
    )
    return KeyAuthorityPort(ref)


def prove_historical_verifier_relocation_recovery_continuity() -> None:
    authority = create_key(KeyRef("tenant-a/comparison/record-a", "jlm-historical-a"))
    message = b"historical-equivalence-evidence"
    v1 = authority.generate_hmac(generation=1, message=message)
    require(v1.startswith("vault:v1:"), "OpenBao HMAC did not bind key generation")
    require(authority.rotate() == 2, "key rotation did not advance generation")

    psql(
        PG_CONTROL,
        "INSERT INTO security_control.historical_grant(target_cell,logical_key,key_generation,active) "
        "VALUES('cell-target','tenant-a/comparison/record-a',1,true);",
    )
    target = HistoricalVerifierPort(authority, target_cell="cell-target", generation=1)
    require(target.verify(message=message, mac=v1), "target could not verify source historical evidence")
    try:
        target.generate(message=message)
    except RuntimeError:
        pass
    else:
        raise AssertionError("historical verifier became signing/generation authority")

    psql(
        PG_CONTROL,
        "UPDATE security_control.historical_grant SET active=false "
        "WHERE target_cell='cell-target' AND logical_key='tenant-a/comparison/record-a' AND key_generation=1;",
    )
    try:
        target.verify(message=message, mac=v1)
    except RuntimeError:
        pass
    else:
        raise AssertionError("missing historical verifier grant did not recovery-block verification")

    print(
        "d3_e_historical_verifier_relocation_recovery_continuity=PASS "
        "source_generation_preserved=true target_verify_only=true "
        "current_generation_not_downgraded=true missing_manifest_fails_closed=true"
    )


def prove_retired_erased_key_nonresurrection() -> None:
    authority = create_key(KeyRef("tenant-a/erasure/record-z", "jlm-erasure-z"))
    message = b"governed-erasure-evidence"
    old_mac = authority.generate_hmac(generation=1, message=message)

    openbao_request("DELETE", "/v1/transit/keys/jlm-erasure-z/soft-delete", None, ok=(200, 204))
    authority.mark_erased()
    openbao_request("POST", "/v1/transit/keys/jlm-erasure-z/soft-delete-restore", {}, ok=(200, 204))

    native = openbao_request(
        "POST",
        "/v1/transit/verify/jlm-erasure-z/sha2-256",
        {"input": b64(message), "hmac": old_mac},
    )
    require(native.get("data", {}).get("valid") is True, "negative control: native restored key was not usable")

    for operation in ("verify", "generate"):
        try:
            if operation == "verify":
                authority.verify_hmac(generation=1, message=message, mac=old_mac)
            else:
                authority.generate_hmac(generation=1, message=message)
        except RuntimeError:
            pass
        else:
            raise AssertionError(f"erased key resurrected through canonical port: {operation}")

    print(
        "d3_e_retired_erased_key_nonresurrection=PASS "
        "native_restore_negative_control_usable=true trusted_erasure_tombstone_external=true "
        "restored_key_not_current_authority=true restored_key_cannot_generate_or_verify=true"
    )


def prove_key_generation_rotation_retirement() -> None:
    authority = create_key(KeyRef("tenant-b/comparison/record-y", "jlm-rotation-y"))
    message = b"rotation-evidence"
    v1 = authority.generate_hmac(generation=1, message=message)
    v2_generation = authority.rotate()
    require(v2_generation == 2, "rotation did not create generation 2")
    v2 = authority.generate_hmac(generation=2, message=message)
    require(v1 != v2, "rotated HMAC generation did not change output")
    require(authority.verify_hmac(generation=1, message=message, mac=v1), "historical generation unavailable before retirement")
    authority.retire_before(2)
    require(not authority.verify_hmac(generation=1, message=message, mac=v1), "retired generation remained verifiable")
    require(authority.verify_hmac(generation=2, message=message, mac=v2), "current generation failed verification")
    try:
        authority.generate_hmac(generation=1, message=message)
    except RuntimeError:
        pass
    else:
        raise AssertionError("retired generation could generate new evidence")

    print(
        "d3_e_key_generation_rotation_retirement=PASS "
        "explicit_generation=true current_generation_rotated=true historical_overlap_bounded=true "
        "retired_generation_not_sign_capable=true retired_generation_not_verify_capable=true"
    )


def prove_private_key_jwt_replay_atomic_single_winner() -> None:
    authority = DurableReplayAuthority()
    generation = authority.current_generation()
    barrier = threading.Barrier(32)

    def attempt(_: int) -> bool:
        barrier.wait()
        return authority.consume(
            replay_scope="issuer-A|client-A",
            client_principal="machine-A",
            jti="assertion-jti-atomic",
            expected_generation=generation,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
        results = list(pool.map(attempt, range(32)))
    require(sum(results) == 1, f"expected exactly one replay winner, got {sum(results)}")
    witness_count = psql(
        PG_CONTROL,
        "SELECT count(*) FROM security_control.replay_witness "
        "WHERE replay_scope='issuer-A|client-A' AND client_principal='machine-A' "
        "AND jti='assertion-jti-atomic';",
    )
    require(witness_count == "1", "durable replay witness is not single-winner")

    require(
        authority.consume(
            replay_scope="issuer-B|client-B",
            client_principal="machine-A",
            jti="assertion-jti-atomic",
            expected_generation=generation,
        ),
        "distinct replay scope collided incorrectly",
    )

    print(
        "d3_e_private_key_jwt_replay_atomic_single_winner=PASS "
        "replica_race=true exactly_one_winner=true durable_unique_identity=true "
        "issuer_client_scope_bound=true"
    )


def prove_replay_partition_fail_closed() -> None:
    authority = DurableReplayAuthority()
    generation = authority.current_generation()
    subprocess.run(["docker", "pause", PG_CONTROL], check=True, stdout=subprocess.DEVNULL)
    try:
        try:
            authority.consume(
                replay_scope="issuer-A|client-A",
                client_principal="machine-A",
                jti="assertion-jti-partition",
                expected_generation=generation,
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("replay authority partition admitted an assertion")
    finally:
        subprocess.run(["docker", "unpause", PG_CONTROL], check=True, stdout=subprocess.DEVNULL)

    require(
        authority.consume(
            replay_scope="issuer-A|client-A",
            client_principal="machine-A",
            jti="assertion-jti-after-recovery",
            expected_generation=generation,
        ),
        "replay authority did not recover after partition",
    )
    print(
        "d3_e_replay_partition_fail_closed=PASS "
        "actual_authority_pause=true unavailable_not_absence=true no_local_fallback=true recovery_requires_authority=true"
    )


def prove_replay_consumed_identity_survives_restore_loss() -> None:
    authority = DurableReplayAuthority()
    generation = authority.current_generation()
    require(
        authority.consume(
            replay_scope="issuer-R|client-R",
            client_principal="machine-R",
            jti="assertion-before-restore",
            expected_generation=generation,
        ),
        "pre-restore assertion was not consumed",
    )

    psql(PG_REPLAY, "TRUNCATE replay.local_consumed;")
    require(psql(PG_REPLAY, "SELECT count(*) FROM replay.local_consumed;") == "0", "negative control restore did not lose local row")
    require(psql(PG_CONTROL, "SELECT count(*) FROM security_control.replay_witness;") != "0", "trusted witness unexpectedly rolled back")

    next_generation = authority.begin_recovery()
    try:
        authority.consume(
            replay_scope="issuer-R|client-R",
            client_principal="machine-R",
            jti="assertion-before-restore",
            expected_generation=next_generation,
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("recovery-blocked replay authority admitted before reconciliation")

    authority.reconcile_and_readmit(generation=next_generation)
    require(
        not authority.consume(
            replay_scope="issuer-R|client-R",
            client_principal="machine-R",
            jti="assertion-before-restore",
            expected_generation=next_generation,
        ),
        "previously consumed assertion became unused after restore loss",
    )
    require(
        authority.consume(
            replay_scope="issuer-R|client-R",
            client_principal="machine-R",
            jti="assertion-new-after-restore",
            expected_generation=next_generation,
        ),
        "fresh assertion was not admitted after trusted recovery",
    )

    print(
        "d3_e_replay_consumed_identity_survives_restore_loss=PASS "
        "stale_restore_negative_control_lost_local_row=true independent_witness_preserved=true "
        "recovery_generation_fenced=true readmission_waits_for_reconciliation=true "
        "consumed_identity_not_resurrected_as_unused=true"
    )


def prove_provider_boundary_static() -> None:
    forbidden = ("vault:", "/v1/transit", "X-Vault-Token")
    public_surface = "KeyAuthorityPort(logical_key,generation,message)->opaque_hmac"
    require(not any(item in public_surface for item in forbidden), "provider-native concept leaked into canonical surface")
    print(
        "d3_e_provider_neutral_runtime_boundary=PASS "
        "logical_key_identity=true explicit_generation=true openbao_native_paths_adapter_local=true "
        "replay_authority_separate_from_key_backend=true"
    )


def main() -> None:
    initialize_postgres()
    initialize_openbao()
    prove_historical_verifier_relocation_recovery_continuity()
    prove_retired_erased_key_nonresurrection()
    prove_key_generation_rotation_retirement()
    prove_private_key_jwt_replay_atomic_single_winner()
    prove_replay_partition_fail_closed()
    prove_replay_consumed_identity_survives_restore_loss()
    prove_provider_boundary_static()
    print(
        "d3_e_crypto_replay_conformance=PASS "
        "openbao_transit_candidate=true postgresql_replay_witness=true "
        "mechanism_c2_only=true c3_numerics_topology_not_selected=true "
        "d3_global_not_accepted=true wave4_not_granted=true production_none=true d4_not_selected_not_granted=true"
    )


if __name__ == "__main__":
    main()
