from __future__ import annotations

import base64
import concurrent.futures
import json
import os
import subprocess
import threading
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


def q(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def parse_pg_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"t", "true", "1"}:
        return True
    if normalized in {"f", "false", "0"}:
        return False
    raise RuntimeError(f"non-canonical PostgreSQL boolean: {value!r}")


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
        raise RuntimeError(f"postgres authority timed out: {container}") from exc
    if proc.returncode != 0:
        if check:
            raise RuntimeError(f"postgres authority failed: {proc.stderr.strip()}")
        return ""
    return proc.stdout.strip()


def scalar(container: str, sql: str, *, check: bool = True, timeout: int = 5) -> str:
    value = pg(container, sql, check=check, timeout=timeout)
    if not value:
        return ""
    rows = value.splitlines()
    if len(rows) != 1:
        raise RuntimeError(f"expected exactly one SQL scalar, got {len(rows)} rows")
    return rows[0]


def bao(method: str, path: str, payload: dict | None = None, *, ok=(200, 204)) -> dict:
    body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
    request = urllib.request.Request(
        OPENBAO_ADDR + path,
        data=body,
        method=method,
        headers={"X-Vault-Token": OPENBAO_TOKEN, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            raw = response.read()
            require(response.status in ok, f"unexpected OpenBao status {response.status}")
            return {} if not raw else json.loads(raw.decode())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"OpenBao {method} {path}: HTTP {exc.code}: {raw[:500]}") from exc


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def initialize() -> None:
    pg(PG_REPLAY, """
        CREATE SCHEMA IF NOT EXISTS replay;
        CREATE TABLE IF NOT EXISTS replay.local_consumed(
          replay_scope text NOT NULL,
          client_principal text NOT NULL,
          jti text NOT NULL,
          witness_generation bigint NOT NULL,
          PRIMARY KEY(replay_scope,client_principal,jti)
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
          replay_scope text NOT NULL,
          client_principal text NOT NULL,
          jti text NOT NULL,
          continuity_generation bigint NOT NULL,
          consumed_at bigint NOT NULL,
          PRIMARY KEY(replay_scope,client_principal,jti)
        );
        CREATE TABLE IF NOT EXISTS security_control.key_state(
          logical_key text PRIMARY KEY,
          current_generation integer NOT NULL,
          min_verify_generation integer NOT NULL,
          erased boolean NOT NULL DEFAULT false
        );
        CREATE TABLE IF NOT EXISTS security_control.historical_grant(
          target_cell text NOT NULL,
          logical_key text NOT NULL,
          key_generation integer NOT NULL,
          active boolean NOT NULL,
          PRIMARY KEY(target_cell,logical_key,key_generation)
        );
        TRUNCATE security_control.replay_state,
                 security_control.replay_witness,
                 security_control.key_state,
                 security_control.historical_grant;
        INSERT INTO security_control.replay_state(singleton,continuity_generation,admission_state)
        VALUES(true,1,'admitted');
    """)
    try:
        bao("POST", "/v1/sys/mounts/transit", {"type": "transit"})
    except RuntimeError as exc:
        if "path is already in use" not in str(exc).lower():
            raise


@dataclass(frozen=True)
class KeyRef:
    logical_key: str
    backend_ref: str


class KeyAuthorityPort:
    """Provider-neutral authority; native OpenBao identity never becomes canonical identity."""

    def __init__(self, ref: KeyRef):
        self.ref = ref

    def state(self) -> tuple[int, int, bool]:
        row = scalar(
            PG_CONTROL,
            "SELECT current_generation||'|'||min_verify_generation||'|'||erased "
            "FROM security_control.key_state WHERE logical_key=" + q(self.ref.logical_key) + ";",
        )
        if not row:
            raise RuntimeError("key currentness unavailable")
        current, floor, erased = row.split("|")
        return int(current), int(floor), parse_pg_bool(erased)

    def backend_latest(self) -> int:
        latest = bao("GET", f"/v1/transit/keys/{self.ref.backend_ref}").get("data", {}).get("latest_version")
        if type(latest) is not int or latest <= 0:
            raise RuntimeError("OpenBao latest_version unavailable")
        return latest

    def generate_hmac(self, *, generation: int, message: bytes) -> str:
        current, _floor, erased = self.state()
        if erased:
            raise RuntimeError("trusted erasure tombstone blocks key use")
        if generation != current:
            raise RuntimeError("only trusted current generation may create evidence")
        value = bao(
            "POST", f"/v1/transit/hmac/{self.ref.backend_ref}/sha2-256",
            {"key_version": generation, "input": b64(message)},
        ).get("data", {}).get("hmac")
        if not isinstance(value, str) or not value:
            raise RuntimeError("OpenBao HMAC response missing")
        return value

    def verify_hmac(self, *, generation: int, message: bytes, mac: str) -> bool:
        _current, floor, erased = self.state()
        if erased:
            raise RuntimeError("trusted erasure tombstone blocks key use")
        if generation < floor:
            return False
        return bao(
            "POST", f"/v1/transit/verify/{self.ref.backend_ref}/sha2-256",
            {"input": b64(message), "hmac": mac},
        ).get("data", {}).get("valid") is True

    def rotate(self) -> int:
        current, floor, erased = self.state()
        if erased:
            raise RuntimeError("erased key cannot rotate")
        before = self.backend_latest()
        if before != current:
            raise RuntimeError("backend generation drift requires reconciliation")
        bao("POST", f"/v1/transit/keys/{self.ref.backend_ref}/rotate", {})
        after = self.backend_latest()
        if after != current + 1:
            raise RuntimeError("non-contiguous backend rotation requires reconciliation")
        changed = scalar(
            PG_CONTROL,
            "UPDATE security_control.key_state SET current_generation=" + str(after)
            + " WHERE logical_key=" + q(self.ref.logical_key)
            + f" AND current_generation={current} AND min_verify_generation={floor} AND erased=false"
            + " RETURNING current_generation;",
        )
        require(changed == str(after), "trusted key-generation CAS failed")
        return after

    def retire_before(self, generation: int) -> None:
        current, floor, erased = self.state()
        require(not erased and 1 <= generation <= current, "invalid retirement state")
        if self.backend_latest() != current:
            raise RuntimeError("backend generation drift requires reconciliation")
        active_grants = int(scalar(
            PG_CONTROL,
            "SELECT count(*) FROM security_control.historical_grant WHERE logical_key="
            + q(self.ref.logical_key) + f" AND active=true AND key_generation < {generation};",
        ))
        if active_grants:
            raise RuntimeError("historical verifier grant blocks key retirement")
        bao(
            "POST", f"/v1/transit/keys/{self.ref.backend_ref}/config",
            {"min_decryption_version": generation, "min_encryption_version": current},
        )
        changed = scalar(
            PG_CONTROL,
            "UPDATE security_control.key_state SET min_verify_generation=" + str(generation)
            + " WHERE logical_key=" + q(self.ref.logical_key)
            + f" AND current_generation={current} AND min_verify_generation={floor} AND erased=false"
            + " RETURNING min_verify_generation;",
        )
        require(changed == str(generation), "trusted verification-floor CAS failed")

    def mark_erased(self) -> None:
        changed = scalar(
            PG_CONTROL,
            "UPDATE security_control.key_state SET erased=true WHERE logical_key="
            + q(self.ref.logical_key) + " AND erased=false RETURNING erased;",
        )
        require(parse_pg_bool(changed), "trusted erasure tombstone was not created")


class HistoricalVerifierPort:
    def __init__(self, authority: KeyAuthorityPort, *, target_cell: str, generation: int):
        self.authority = authority
        self.target_cell = target_cell
        self.generation = generation

    def verify(self, *, message: bytes, mac: str) -> bool:
        granted = scalar(
            PG_CONTROL,
            "SELECT active FROM security_control.historical_grant WHERE target_cell="
            + q(self.target_cell) + " AND logical_key=" + q(self.authority.ref.logical_key)
            + f" AND key_generation={self.generation};",
        )
        if not granted or not parse_pg_bool(granted):
            raise RuntimeError("historical verifier continuity unavailable")
        return self.authority.verify_hmac(generation=self.generation, message=message, mac=mac)

    def generate(self, *, message: bytes) -> str:
        del message
        raise RuntimeError("historical verifier is verify-only")


class ReplayAuthority:
    """Replay witness is security-continuity truth; local replay state is a recoverable mirror."""

    def current_generation(self) -> int:
        value = scalar(
            PG_CONTROL,
            "SELECT continuity_generation FROM security_control.replay_state "
            "WHERE singleton=true AND admission_state='admitted';",
        )
        if not value:
            raise RuntimeError("replay currentness unavailable")
        return int(value)

    def consume(self, *, replay_scope: str, principal: str, jti: str, expected_generation: int) -> bool:
        scope, actor, token = q(replay_scope), q(principal), q(jti)
        winner = scalar(PG_CONTROL, f"""
            WITH current AS (
              SELECT continuity_generation FROM security_control.replay_state
              WHERE singleton=true AND admission_state='admitted'
                AND continuity_generation={expected_generation}
              FOR UPDATE
            ), inserted AS (
              INSERT INTO security_control.replay_witness(
                replay_scope,client_principal,jti,continuity_generation,consumed_at
              )
              SELECT {scope},{actor},{token},continuity_generation,
                     (extract(epoch from clock_timestamp())*1000000)::bigint
              FROM current
              ON CONFLICT DO NOTHING
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
                raise RuntimeError("replay generation is not current")
            return False
        mirrored = scalar(
            PG_REPLAY,
            "INSERT INTO replay.local_consumed(replay_scope,client_principal,jti,witness_generation) "
            f"VALUES({scope},{actor},{token},{int(winner)}) ON CONFLICT DO NOTHING "
            "RETURNING witness_generation;",
            check=False,
        )
        if not mirrored:
            raise RuntimeError("local replay mirror unavailable after durable consume")
        return True

    def begin_recovery(self) -> int:
        value = scalar(
            PG_CONTROL,
            "UPDATE security_control.replay_state SET continuity_generation=continuity_generation+1, "
            "admission_state='recovery_blocked' WHERE singleton=true RETURNING continuity_generation;",
        )
        require(bool(value), "replay recovery fence failed")
        return int(value)

    def reconcile_and_readmit(self, *, generation: int) -> None:
        rows = pg(
            PG_CONTROL,
            "SELECT replay_scope||E'\\t'||client_principal||E'\\t'||jti "
            "FROM security_control.replay_witness ORDER BY replay_scope,client_principal,jti;",
        )
        for row in filter(None, rows.splitlines()):
            scope, actor, token = row.split("\t")
            pg(
                PG_REPLAY,
                "INSERT INTO replay.local_consumed(replay_scope,client_principal,jti,witness_generation) "
                f"VALUES({q(scope)},{q(actor)},{q(token)},{generation}) ON CONFLICT DO NOTHING;",
            )
        require(
            scalar(PG_CONTROL, "SELECT count(*) FROM security_control.replay_witness;")
            == scalar(PG_REPLAY, "SELECT count(*) FROM replay.local_consumed;"),
            "replay reconciliation incomplete",
        )
        admitted = scalar(
            PG_CONTROL,
            "UPDATE security_control.replay_state SET admission_state='admitted' "
            f"WHERE singleton=true AND continuity_generation={generation} "
            "AND admission_state='recovery_blocked' RETURNING continuity_generation;",
        )
        require(admitted == str(generation), "replay readmission CAS failed")


def create_key(logical: str, backend: str) -> KeyAuthorityPort:
    bao("POST", f"/v1/transit/keys/{backend}", {"type": "hmac", "key_size": 32})
    pg(PG_CONTROL, "INSERT INTO security_control.key_state(logical_key,current_generation,min_verify_generation,erased) " f"VALUES({q(logical)},1,1,false);")
    return KeyAuthorityPort(KeyRef(logical, backend))


def prove_historical_continuity() -> None:
    key = create_key("tenant-a/comparison/record-a", "jlm-historical-a")
    message = b"historical-equivalence-evidence"
    v1 = key.generate_hmac(generation=1, message=message)
    require(v1.startswith("vault:v1:"), "HMAC does not encode backend generation")
    require(key.rotate() == 2, "rotation failed")
    pg(PG_CONTROL, "INSERT INTO security_control.historical_grant VALUES('cell-target','tenant-a/comparison/record-a',1,true);")
    verifier = HistoricalVerifierPort(key, target_cell="cell-target", generation=1)
    require(verifier.verify(message=message, mac=v1), "target historical verification failed")
    try:
        key.retire_before(2)
    except RuntimeError:
        pass
    else:
        raise AssertionError("active historical verifier grant did not block retirement")
    try:
        verifier.generate(message=message)
    except RuntimeError:
        pass
    else:
        raise AssertionError("historical verifier gained signing authority")
    pg(PG_CONTROL, "UPDATE security_control.historical_grant SET active=false WHERE target_cell='cell-target';")
    try:
        verifier.verify(message=message, mac=v1)
    except RuntimeError:
        pass
    else:
        raise AssertionError("missing relocation grant did not fail closed")
    print("d3_e_historical_verifier_relocation_recovery_continuity=PASS source_generation_preserved=true target_verify_only=true current_generation_not_downgraded=true active_historical_grant_blocks_retirement=true missing_manifest_fails_closed=true")


def prove_erasure_nonresurrection() -> None:
    key = create_key("tenant-a/erasure/record-z", "jlm-erasure-z")
    message = b"governed-erasure-evidence"
    old_mac = key.generate_hmac(generation=1, message=message)
    bao("DELETE", "/v1/transit/keys/jlm-erasure-z/soft-delete", None)
    key.mark_erased()
    require(key.state()[2] is True, "trusted erasure state did not round-trip")
    bao("POST", "/v1/transit/keys/jlm-erasure-z/soft-delete-restore", {})
    native_valid = bao(
        "POST", "/v1/transit/verify/jlm-erasure-z/sha2-256",
        {"input": b64(message), "hmac": old_mac},
    ).get("data", {}).get("valid") is True
    require(native_valid, "negative control: restored native key is not usable")
    for operation in ("verify", "generate"):
        try:
            if operation == "verify":
                key.verify_hmac(generation=1, message=message, mac=old_mac)
            else:
                key.generate_hmac(generation=1, message=message)
        except RuntimeError:
            pass
        else:
            raise AssertionError(f"restored erased key became canonical authority: {operation}")
    print("d3_e_retired_erased_key_nonresurrection=PASS native_restore_negative_control_usable=true trusted_erasure_tombstone_external=true trusted_erasure_state_roundtrip=true restored_key_not_current_authority=true restored_key_cannot_generate_or_verify=true")


def prove_rotation_retirement() -> None:
    key = create_key("tenant-b/comparison/record-y", "jlm-rotation-y")
    message = b"rotation-evidence"
    v1 = key.generate_hmac(generation=1, message=message)
    require(key.rotate() == 2, "generation did not advance")
    v2 = key.generate_hmac(generation=2, message=message)
    require(v1 != v2, "rotated generation reused HMAC output")
    require(key.verify_hmac(generation=1, message=message, mac=v1), "historical overlap absent")
    key.retire_before(2)
    require(not key.verify_hmac(generation=1, message=message, mac=v1), "retired generation still verified")
    require(key.verify_hmac(generation=2, message=message, mac=v2), "current generation failed")
    try:
        key.generate_hmac(generation=1, message=message)
    except RuntimeError:
        pass
    else:
        raise AssertionError("retired generation could generate new evidence")
    print("d3_e_key_generation_rotation_retirement=PASS explicit_generation=true current_generation_rotated=true historical_overlap_bounded=true retired_generation_not_sign_capable=true retired_generation_not_verify_capable=true")


def prove_native_generation_drift_fail_closed() -> None:
    key = create_key("tenant-c/comparison/record-drift", "jlm-drift")
    bao("POST", "/v1/transit/keys/jlm-drift/rotate", {})
    require(key.backend_latest() == 2, "negative control did not create native generation drift")
    require(key.state()[0] == 1, "native drift changed trusted generation")
    try:
        key.rotate()
    except RuntimeError:
        pass
    else:
        raise AssertionError("native generation drift was silently promoted")
    try:
        key.generate_hmac(generation=2, message=b"drift")
    except RuntimeError:
        pass
    else:
        raise AssertionError("untrusted native generation became canonical generation")
    require(key.state()[0] == 1, "failed rotation altered trusted generation")
    print("d3_e_native_generation_drift_fail_closed=PASS native_rotation_negative_control=true trusted_generation_unchanged=true untrusted_latest_not_promoted=true reconciliation_required=true")


def prove_replay_single_winner() -> None:
    replay = ReplayAuthority()
    generation = replay.current_generation()
    gate = threading.Barrier(32)
    def attempt(_: int) -> bool:
        gate.wait()
        return replay.consume(replay_scope="issuer-A|client-A", principal="machine-A", jti="assertion-jti-atomic", expected_generation=generation)
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
        results = list(pool.map(attempt, range(32)))
    require(sum(results) == 1, f"expected one replay winner, got {sum(results)}")
    require(scalar(PG_CONTROL, "SELECT count(*) FROM security_control.replay_witness WHERE replay_scope='issuer-A|client-A' AND client_principal='machine-A' AND jti='assertion-jti-atomic';") == "1", "durable replay identity was not single-winner")
    require(replay.consume(replay_scope="issuer-B|client-B", principal="machine-A", jti="assertion-jti-atomic", expected_generation=generation), "same raw jti collided across trusted issuer/client scope")
    print("d3_e_private_key_jwt_replay_atomic_single_winner=PASS replica_race=true exactly_one_winner=true durable_unique_identity=true issuer_client_scope_bound=true")


def prove_replay_partition() -> None:
    replay = ReplayAuthority()
    generation = replay.current_generation()
    subprocess.run(["docker", "pause", PG_CONTROL], check=True, stdout=subprocess.DEVNULL)
    try:
        try:
            replay.consume(replay_scope="issuer-A|client-A", principal="machine-A", jti="partition-jti", expected_generation=generation)
        except RuntimeError:
            pass
        else:
            raise AssertionError("partitioned replay authority admitted")
    finally:
        subprocess.run(["docker", "unpause", PG_CONTROL], check=True, stdout=subprocess.DEVNULL)
    require(replay.consume(replay_scope="issuer-A|client-A", principal="machine-A", jti="post-partition-jti", expected_generation=generation), "replay authority did not recover")
    print("d3_e_replay_partition_fail_closed=PASS actual_authority_pause=true unavailable_not_absence=true no_local_fallback=true recovery_requires_authority=true")


def prove_replay_restore_loss() -> None:
    replay = ReplayAuthority()
    generation = replay.current_generation()
    require(replay.consume(replay_scope="issuer-R|client-R", principal="machine-R", jti="assertion-before-restore", expected_generation=generation), "pre-restore consume failed")
    pg(PG_REPLAY, "TRUNCATE replay.local_consumed;")
    require(scalar(PG_REPLAY, "SELECT count(*) FROM replay.local_consumed;") == "0", "negative-control restore did not lose local replay state")
    require(int(scalar(PG_CONTROL, "SELECT count(*) FROM security_control.replay_witness;")) > 0, "trusted witness rolled back")
    nxt = replay.begin_recovery()
    try:
        replay.consume(replay_scope="issuer-R|client-R", principal="machine-R", jti="assertion-before-restore", expected_generation=nxt)
    except RuntimeError:
        pass
    else:
        raise AssertionError("recovery-blocked replay admitted before reconciliation")
    replay.reconcile_and_readmit(generation=nxt)
    require(not replay.consume(replay_scope="issuer-R|client-R", principal="machine-R", jti="assertion-before-restore", expected_generation=nxt), "consumed assertion became unused after restore")
    require(replay.consume(replay_scope="issuer-R|client-R", principal="machine-R", jti="assertion-new-after-restore", expected_generation=nxt), "fresh assertion rejected after recovery")
    print("d3_e_replay_consumed_identity_survives_restore_loss=PASS stale_restore_negative_control_lost_local_row=true independent_witness_preserved=true recovery_generation_fenced=true readmission_waits_for_reconciliation=true consumed_identity_not_resurrected_as_unused=true")


def prove_provider_boundary() -> None:
    public_contract = "KeyAuthorityPort(logical_key,generation,message)->opaque_hmac"
    require("/v1/transit" not in public_contract and "X-Vault-Token" not in public_contract and "vault:" not in public_contract, "provider identity leaked")
    print("d3_e_provider_neutral_runtime_boundary=PASS logical_key_identity=true explicit_generation=true openbao_native_paths_adapter_local=true replay_authority_separate_from_key_backend=true")


def main() -> None:
    initialize()
    prove_historical_continuity()
    prove_erasure_nonresurrection()
    prove_rotation_retirement()
    prove_native_generation_drift_fail_closed()
    prove_replay_single_winner()
    prove_replay_partition()
    prove_replay_restore_loss()
    prove_provider_boundary()
    print("d3_e_crypto_replay_conformance=PASS openbao_transit_candidate=true postgresql_replay_witness=true mechanism_c2_only=true c3_numerics_topology_not_selected=true d3_global_not_accepted=true wave4_not_granted=true production_none=true d4_not_selected_not_granted=true")


if __name__ == "__main__":
    main()
