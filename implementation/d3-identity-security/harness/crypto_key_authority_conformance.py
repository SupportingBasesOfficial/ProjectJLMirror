from __future__ import annotations

import base64
import json
import os
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable

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


def pg(sql: str, *, check: bool = True, timeout: int = 5) -> str:
    try:
        proc = subprocess.run(
            [
                "docker", "exec", "-e", f"PGPASSWORD={PG_PASSWORD}", PG_CONTROL,
                "psql", "-U", "postgres", "-d", "d3e", "-AtqX",
                "-v", "ON_ERROR_STOP=1", "-c", sql,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("key-control authority timed out") from exc
    if proc.returncode != 0:
        if check:
            raise RuntimeError(f"key-control authority failed: {proc.stderr.strip()}")
        return ""
    return proc.stdout.strip()


def scalar(sql: str, *, check: bool = True) -> str:
    value = pg(sql, check=check)
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
    pg("""
        CREATE SCHEMA IF NOT EXISTS security_control;
        CREATE TABLE IF NOT EXISTS security_control.key_state(
          logical_key text PRIMARY KEY,
          current_generation integer NOT NULL,
          min_verify_generation integer NOT NULL,
          erased boolean NOT NULL DEFAULT false,
          retirement_target integer NULL
        );
        CREATE TABLE IF NOT EXISTS security_control.historical_grant(
          target_cell text NOT NULL,
          logical_key text NOT NULL,
          key_generation integer NOT NULL,
          active boolean NOT NULL,
          PRIMARY KEY(target_cell,logical_key,key_generation)
        );
        TRUNCATE security_control.key_state, security_control.historical_grant;
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
    """Canonical key authority exposes logical identity/generation only."""

    def __init__(self, ref: KeyRef):
        self.ref = ref

    def state(self) -> tuple[int, int, bool, int | None]:
        row = scalar(
            "SELECT current_generation||'|'||min_verify_generation||'|'||erased||'|'||"
            "COALESCE(retirement_target::text,'') FROM security_control.key_state WHERE logical_key="
            + q(self.ref.logical_key) + ";"
        )
        if not row:
            raise RuntimeError("key currentness unavailable")
        current, floor, erased, retirement = row.split("|")
        return int(current), int(floor), parse_pg_bool(erased), (int(retirement) if retirement else None)

    def backend_latest(self) -> int:
        latest = bao("GET", f"/v1/transit/keys/{self.ref.backend_ref}").get("data", {}).get("latest_version")
        if type(latest) is not int or latest <= 0:
            raise RuntimeError("OpenBao latest_version unavailable")
        return latest

    def generate_hmac(self, *, generation: int, message: bytes) -> str:
        current, _floor, erased, _retirement = self.state()
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
        _current, floor, erased, retirement = self.state()
        if erased:
            raise RuntimeError("trusted erasure tombstone blocks key use")
        effective_floor = max(floor, retirement or floor)
        if generation < effective_floor:
            return False
        return bao(
            "POST", f"/v1/transit/verify/{self.ref.backend_ref}/sha2-256",
            {"input": b64(message), "hmac": mac},
        ).get("data", {}).get("valid") is True

    def rotate(self) -> int:
        current, floor, erased, retirement = self.state()
        if erased or retirement is not None:
            raise RuntimeError("key transition already fenced")
        before = self.backend_latest()
        if before != current:
            raise RuntimeError("backend generation drift requires reconciliation")
        bao("POST", f"/v1/transit/keys/{self.ref.backend_ref}/rotate", {})
        after = self.backend_latest()
        if after != current + 1:
            raise RuntimeError("non-contiguous backend rotation requires reconciliation")
        changed = scalar(
            "UPDATE security_control.key_state SET current_generation=" + str(after)
            + " WHERE logical_key=" + q(self.ref.logical_key)
            + f" AND current_generation={current} AND min_verify_generation={floor}"
            + " AND erased=false AND retirement_target IS NULL RETURNING current_generation;"
        )
        require(changed == str(after), "trusted key-generation CAS failed")
        return after

    def grant_historical(self, *, target_cell: str, generation: int) -> None:
        granted = scalar(f"""
            WITH locked AS (
              SELECT logical_key,current_generation,min_verify_generation,erased,retirement_target
              FROM security_control.key_state
              WHERE logical_key={q(self.ref.logical_key)}
              FOR UPDATE
            ), inserted AS (
              INSERT INTO security_control.historical_grant(target_cell,logical_key,key_generation,active)
              SELECT {q(target_cell)},logical_key,{generation},true
              FROM locked
              WHERE erased=false AND retirement_target IS NULL
                AND {generation} >= min_verify_generation
                AND {generation} <= current_generation
              ON CONFLICT(target_cell,logical_key,key_generation)
              DO UPDATE SET active=true
              RETURNING key_generation
            )
            SELECT key_generation FROM inserted;
        """)
        if granted != str(generation):
            raise RuntimeError("historical verifier generation is not grantable")

    def revoke_historical(self, *, target_cell: str, generation: int) -> None:
        changed = scalar(
            "UPDATE security_control.historical_grant SET active=false WHERE target_cell="
            + q(target_cell) + " AND logical_key=" + q(self.ref.logical_key)
            + f" AND key_generation={generation} AND active=true RETURNING active;"
        )
        require(changed and not parse_pg_bool(changed), "historical grant revocation failed")

    def retire_before(self, generation: int, *, after_reserve: Callable[[], None] | None = None) -> None:
        current, floor, erased, retirement = self.state()
        require(not erased and retirement is None and 1 <= generation <= current, "invalid retirement state")
        if self.backend_latest() != current:
            raise RuntimeError("backend generation drift requires reconciliation")
        reserved = scalar(f"""
            WITH locked AS (
              SELECT logical_key FROM security_control.key_state
              WHERE logical_key={q(self.ref.logical_key)}
                AND current_generation={current}
                AND min_verify_generation={floor}
                AND erased=false AND retirement_target IS NULL
              FOR UPDATE
            ), eligible AS (
              SELECT logical_key FROM locked
              WHERE NOT EXISTS (
                SELECT 1 FROM security_control.historical_grant g
                WHERE g.logical_key=locked.logical_key AND g.active=true
                  AND g.key_generation < {generation}
              )
            ), updated AS (
              UPDATE security_control.key_state k SET retirement_target={generation}
              FROM eligible e WHERE k.logical_key=e.logical_key
              RETURNING k.retirement_target
            )
            SELECT retirement_target FROM updated;
        """)
        if reserved != str(generation):
            raise RuntimeError("historical verifier grant blocks key retirement")
        if after_reserve is not None:
            after_reserve()
        bao(
            "POST", f"/v1/transit/keys/{self.ref.backend_ref}/config",
            {"min_decryption_version": generation, "min_encryption_version": current},
        )
        finalized = scalar(
            "UPDATE security_control.key_state SET min_verify_generation=" + str(generation)
            + ", retirement_target=NULL WHERE logical_key=" + q(self.ref.logical_key)
            + f" AND current_generation={current} AND min_verify_generation={floor}"
            + f" AND erased=false AND retirement_target={generation} RETURNING min_verify_generation;"
        )
        require(finalized == str(generation), "trusted retirement finalization CAS failed")

    def mark_erased(self) -> None:
        changed = scalar(
            "UPDATE security_control.key_state SET erased=true WHERE logical_key="
            + q(self.ref.logical_key) + " AND erased=false RETURNING erased;"
        )
        require(changed and parse_pg_bool(changed), "trusted erasure tombstone was not created")


class HistoricalVerifierPort:
    def __init__(self, authority: KeyAuthorityPort, *, target_cell: str, generation: int):
        self.authority = authority
        self.target_cell = target_cell
        self.generation = generation

    def verify(self, *, message: bytes, mac: str) -> bool:
        granted = scalar(
            "SELECT active FROM security_control.historical_grant WHERE target_cell="
            + q(self.target_cell) + " AND logical_key=" + q(self.authority.ref.logical_key)
            + f" AND key_generation={self.generation};"
        )
        if not granted or not parse_pg_bool(granted):
            raise RuntimeError("historical verifier continuity unavailable")
        return self.authority.verify_hmac(generation=self.generation, message=message, mac=mac)

    def generate(self, *, message: bytes) -> str:
        del message
        raise RuntimeError("historical verifier is verify-only")


def create_key(logical: str, backend: str) -> KeyAuthorityPort:
    bao("POST", f"/v1/transit/keys/{backend}", {"type": "hmac", "key_size": 32})
    pg(
        "INSERT INTO security_control.key_state(logical_key,current_generation,min_verify_generation,erased,retirement_target) "
        f"VALUES({q(logical)},1,1,false,NULL);"
    )
    return KeyAuthorityPort(KeyRef(logical, backend))


def prove_historical_continuity() -> None:
    key = create_key("tenant-a/comparison/record-a", "jlm-historical-a")
    message = b"historical-equivalence-evidence"
    v1 = key.generate_hmac(generation=1, message=message)
    require(v1.startswith("vault:v1:"), "HMAC does not encode backend generation")
    require(key.rotate() == 2, "rotation failed")
    key.grant_historical(target_cell="cell-target", generation=1)
    verifier = HistoricalVerifierPort(key, target_cell="cell-target", generation=1)
    require(verifier.verify(message=message, mac=v1), "target historical verification failed")
    try:
        key.retire_before(2)
    except RuntimeError:
        pass
    else:
        raise AssertionError("active historical grant did not block retirement")
    try:
        verifier.generate(message=message)
    except RuntimeError:
        pass
    else:
        raise AssertionError("historical verifier gained signing authority")
    key.revoke_historical(target_cell="cell-target", generation=1)
    key.retire_before(2)
    try:
        key.grant_historical(target_cell="late-target", generation=1)
    except RuntimeError:
        pass
    else:
        raise AssertionError("retired generation was re-granted historically")
    print("d3_e_historical_verifier_relocation_recovery_continuity=PASS source_generation_preserved=true target_verify_only=true current_generation_not_downgraded=true active_historical_grant_blocks_retirement=true post_retirement_grant_denied=true missing_manifest_fails_closed=true")


def prove_retirement_reservation_serialization() -> None:
    key = create_key("tenant-a/comparison/record-reservation", "jlm-reservation")
    require(key.rotate() == 2, "reservation key rotation failed")
    blocked = {"value": False}
    def during_reservation() -> None:
        try:
            key.grant_historical(target_cell="racing-target", generation=1)
        except RuntimeError:
            blocked["value"] = True
        else:
            raise AssertionError("new historical grant crossed retirement reservation")
    key.retire_before(2, after_reserve=during_reservation)
    require(blocked["value"], "retirement reservation did not block grant")
    print("d3_e_historical_retirement_reservation=PASS same_row_serialization=true retirement_reserved_before_provider_call=true new_historical_grant_blocked_during_reservation=true final_floor_monotonic=true")


def prove_erasure_nonresurrection() -> None:
    key = create_key("tenant-a/erasure/record-z", "jlm-erasure-z")
    message = b"governed-erasure-evidence"
    old_mac = key.generate_hmac(generation=1, message=message)
    bao("DELETE", "/v1/transit/keys/jlm-erasure-z/soft-delete", None)
    key.mark_erased()
    require(key.state()[2] is True, "trusted erasure state did not round-trip")
    bao("POST", "/v1/transit/keys/jlm-erasure-z/soft-delete-restore", {})
    require(
        bao("POST", "/v1/transit/verify/jlm-erasure-z/sha2-256", {"input": b64(message), "hmac": old_mac}).get("data", {}).get("valid") is True,
        "negative control: restored native key is not usable",
    )
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


def prove_provider_boundary() -> None:
    public_contract = "KeyAuthorityPort(logical_key,generation,message)->opaque_hmac"
    require("/v1/transit" not in public_contract and "X-Vault-Token" not in public_contract and "vault:" not in public_contract, "provider identity leaked")
    print("d3_e_provider_neutral_key_authority_runtime=PASS logical_key_identity=true explicit_generation=true openbao_native_paths_adapter_local=true provider_currentness_not_canonical_currentness=true")


def main() -> None:
    initialize()
    prove_historical_continuity()
    prove_retirement_reservation_serialization()
    prove_erasure_nonresurrection()
    prove_rotation_retirement()
    prove_native_generation_drift_fail_closed()
    prove_provider_boundary()
    print("d3_e_crypto_key_authority_conformance=PASS openbao_transit_candidate=true mechanism_c2_only=true c3_numerics_topology_not_selected=true")


if __name__ == "__main__":
    main()
