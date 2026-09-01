#!/usr/bin/env python3
"""D3-E bounded candidate conformance against OpenBao Transit + PostgreSQL replay authority.

Evidence-only C2 mechanism validation. It intentionally does not select production
rotation intervals, RPO/RTO, topology, capacity or retention numerics. No key or
backup material is printed or persisted as ordinary evidence.
"""
from __future__ import annotations

import base64
import concurrent.futures
from dataclasses import dataclass
import json
import os
import subprocess
import threading
import urllib.error
import urllib.request
from typing import Protocol

OPENBAO_ADDR = os.environ.get("OPENBAO_ADDR", "http://127.0.0.1:18200").rstrip("/")
OPENBAO_ROOT_TOKEN = os.environ["OPENBAO_ROOT_TOKEN"]
PG_CONTAINER = os.environ["PG_CONTAINER"]
PG_PASSWORD = os.environ["PG_PASSWORD"]

SOURCE_KEY = "d3-e-relocation-source"
TARGET_KEY = "d3-e-target-current"
ROTATION_KEY = "d3-e-rotation"
ERASURE_KEY = "d3-e-erasure-negative"
STALE_RESTORED_KEY = "d3-e-stale-restored"
REPLAY_SCOPE = "token-endpoint/private-key-jwt"


class ApiError(RuntimeError):
    def __init__(self, status: int, path: str, body: str):
        super().__init__(f"OpenBao API {status} at {path}")
        self.status = status
        self.path = path
        self.body = body


class ReplayUnavailable(RuntimeError):
    pass


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def canonical_message(*, tenant: str, scope: str, erasure_unit: str, payload: bytes) -> bytes:
    parts = (tenant, scope, erasure_unit)
    if any(not p or p != p.strip() or "\x00" in p for p in parts):
        raise ValueError("non-canonical comparison context")
    return (
        b"jlmirror-d3-eq-v1\x00"
        + tenant.encode()
        + b"\x00"
        + scope.encode()
        + b"\x00"
        + erasure_unit.encode()
        + b"\x00"
        + payload
    )


class OpenBaoHttp:
    def __init__(self, token: str):
        self.token = token
        self.calls: list[tuple[str, str]] = []
        self._lock = threading.Lock()

    def request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        *,
        expected: tuple[int, ...] = (200, 204),
    ) -> dict:
        body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        req = urllib.request.Request(
            OPENBAO_ADDR + "/v1/" + path.lstrip("/"),
            data=body,
            method=method,
            headers={"X-Vault-Token": self.token, "Content-Type": "application/json"},
        )
        with self._lock:
            self.calls.append((method, path))
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                raw, status = response.read(), response.status
        except urllib.error.HTTPError as exc:
            raw, status = exc.read(), exc.code
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ApiError(599, path, type(exc).__name__) from exc
        text = raw.decode("utf-8", errors="replace")
        if status not in expected:
            raise ApiError(status, path, text)
        if not text:
            return {}
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ApiError(status, path, "non-object response")
        return parsed


class KeyAuthorityPort(Protocol):
    def hmac_sha256(self, *, version: int, message: bytes) -> str:
        ...

    def verify_hmac_sha256(self, *, version: int, message: bytes, mac: str) -> bool:
        ...


@dataclass
class OpenBaoKeyAuthorityAdapter:
    """Provider-neutral port adapter; callers never consume OpenBao response shapes."""

    api: OpenBaoHttp
    physical_key: str

    def hmac_sha256(self, *, version: int, message: bytes) -> str:
        response = self.api.request(
            "POST",
            f"transit/hmac/{self.physical_key}/sha2-256",
            {"input": b64(message), "key_version": version},
        )
        mac = response.get("data", {}).get("hmac")
        if not isinstance(mac, str) or not mac:
            raise RuntimeError("candidate did not return a canonical HMAC")
        return mac

    def verify_hmac_sha256(self, *, version: int, message: bytes, mac: str) -> bool:
        response = self.api.request(
            "POST",
            f"transit/verify/{self.physical_key}/sha2-256",
            {"input": b64(message), "hmac": mac},
        )
        valid = response.get("data", {}).get("valid")
        if type(valid) is not bool:
            raise RuntimeError("candidate did not return a boolean verification result")
        return valid


class HistoricalVerifierPort(Protocol):
    def verify(self, *, version: int, message: bytes, mac: str) -> bool:
        ...


@dataclass
class HistoricalOpenBaoVerifier:
    """Narrow historical verifier: verification only, no current issuance methods."""

    adapter: OpenBaoKeyAuthorityAdapter

    def verify(self, *, version: int, message: bytes, mac: str) -> bool:
        return self.adapter.verify_hmac_sha256(version=version, message=message, mac=mac)


def root_api() -> OpenBaoHttp:
    return OpenBaoHttp(OPENBAO_ROOT_TOKEN)


def create_policy_and_token(root: OpenBaoHttp, *, policy_name: str, policy: str) -> str:
    root.request("PUT", f"sys/policies/acl/{policy_name}", {"policy": policy})
    response = root.request(
        "POST",
        "auth/token/create",
        {"policies": [policy_name], "ttl": "10m", "renewable": False, "no_default_policy": True},
    )
    token = response.get("auth", {}).get("client_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("failed to create bounded OpenBao token")
    return token


def expect_api_denied(fn) -> None:
    try:
        fn()
    except ApiError as exc:
        if exc.status not in (400, 403, 404):
            raise
    else:
        raise AssertionError("operation unexpectedly authorized")


def pg(sql: str, *, timeout: float = 10.0, unavailable_ok: bool = False) -> str:
    cmd = [
        "docker",
        "exec",
        "-e",
        f"PGPASSWORD={PG_PASSWORD}",
        PG_CONTAINER,
        "psql",
        "-X",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        "postgres",
        "-d",
        "d3",
        "-At",
        "-c",
        sql,
    ]
    try:
        result = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise ReplayUnavailable("replay authority timed out") from exc
    if result.returncode != 0:
        if unavailable_ok:
            raise ReplayUnavailable("replay authority unavailable")
        raise RuntimeError("PostgreSQL command failed without exposing credentials")
    return result.stdout.strip()


def sql_literal(value: str) -> str:
    if "\x00" in value:
        raise ValueError("NUL not allowed")
    return "'" + value.replace("'", "''") + "'"


def setup_postgres() -> None:
    pg(
        r"""
        DROP SCHEMA IF EXISTS d3e CASCADE;
        CREATE SCHEMA d3e;
        CREATE TABLE d3e.key_authority_state (
            logical_key text PRIMARY KEY,
            current_version integer NOT NULL CHECK (current_version > 0),
            minimum_verify_version integer NOT NULL CHECK (minimum_verify_version > 0),
            state text NOT NULL CHECK (state IN ('current','retired','erased'))
        );
        CREATE TABLE d3e.replay_continuity (
            scope text PRIMARY KEY,
            epoch bigint NOT NULL CHECK (epoch > 0),
            state text NOT NULL CHECK (state IN ('current','recovery_blocked'))
        );
        CREATE TABLE d3e.replay_claim (
            scope text NOT NULL,
            client_principal text NOT NULL,
            jti text NOT NULL,
            claimed_epoch bigint NOT NULL CHECK (claimed_epoch > 0),
            PRIMARY KEY (scope, client_principal, jti)
        );
        INSERT INTO d3e.replay_continuity(scope, epoch, state)
        VALUES ('token-endpoint/private-key-jwt', 1, 'current');
        CREATE OR REPLACE FUNCTION d3e.claim_replay(
            p_scope text, p_client text, p_jti text, p_expected_epoch bigint
        ) RETURNS boolean LANGUAGE plpgsql AS $$
        DECLARE v_epoch bigint; v_state text; v_inserted integer;
        BEGIN
            SELECT epoch, state INTO v_epoch, v_state
            FROM d3e.replay_continuity WHERE scope = p_scope FOR SHARE;
            IF NOT FOUND OR v_state <> 'current' OR v_epoch <> p_expected_epoch THEN
                RAISE EXCEPTION 'replay continuity not current';
            END IF;
            INSERT INTO d3e.replay_claim(scope, client_principal, jti, claimed_epoch)
            VALUES (p_scope, p_client, p_jti, v_epoch) ON CONFLICT DO NOTHING;
            GET DIAGNOSTICS v_inserted = ROW_COUNT;
            RETURN v_inserted = 1;
        END; $$;
        """
    )


def replay_claim(*, client: str, jti: str, epoch: int, timeout: float = 10.0) -> bool:
    for label, value in (("client", client), ("jti", jti)):
        if not value or value != value.strip() or len(value) > 256:
            raise ValueError(f"invalid {label}")
    sql = (
        "SELECT d3e.claim_replay("
        + sql_literal(REPLAY_SCOPE)
        + ","
        + sql_literal(client)
        + ","
        + sql_literal(jti)
        + f",{int(epoch)});"
    )
    try:
        output = pg(sql, timeout=timeout, unavailable_ok=True)
    except (RuntimeError, ReplayUnavailable) as exc:
        raise ReplayUnavailable("replay authority unavailable") from exc
    if output == "t":
        return True
    if output == "f":
        return False
    raise ReplayUnavailable("replay authority returned no trusted decision")


def block_replay_after_restore_loss() -> int:
    output = pg(
        "WITH advanced AS ("
        "UPDATE d3e.replay_continuity SET state='recovery_blocked', epoch=epoch+1 "
        f"WHERE scope={sql_literal(REPLAY_SCOPE)} RETURNING epoch"
        ") SELECT epoch FROM advanced;"
    )
    if not output.isdigit():
        raise AssertionError("continuity fence did not advance")
    return int(output)


def set_key_state(logical_key: str, *, current_version: int, minimum_verify_version: int, state: str) -> None:
    pg(
        "INSERT INTO d3e.key_authority_state(logical_key,current_version,minimum_verify_version,state) VALUES ("
        f"{sql_literal(logical_key)},{current_version},{minimum_verify_version},{sql_literal(state)}) "
        "ON CONFLICT (logical_key) DO UPDATE SET current_version=EXCLUDED.current_version,"
        "minimum_verify_version=EXCLUDED.minimum_verify_version,state=EXCLUDED.state;"
    )


def registry_allows_verify(logical_key: str, version: int) -> bool:
    out = pg(
        "SELECT CASE WHEN state <> 'erased' AND "
        + str(int(version))
        + " >= minimum_verify_version THEN 1 ELSE 0 END FROM d3e.key_authority_state "
        f"WHERE logical_key={sql_literal(logical_key)};"
    )
    return out == "1"


@dataclass
class RegistryGuardedHistoricalVerifier:
    logical_key: str
    versioned_verifier: HistoricalVerifierPort

    def verify(self, *, version: int, message: bytes, mac: str) -> bool:
        if not registry_allows_verify(self.logical_key, version):
            return False
        return self.versioned_verifier.verify(version=version, message=message, mac=mac)


def create_hmac_key(root: OpenBaoHttp, name: str, *, backup: bool = False) -> None:
    root.request(
        "POST",
        f"transit/keys/{name}",
        {
            "type": "hmac",
            "key_size": 32,
            # Only the deliberately stale-restore negative-control fixture sets
            # backup=True. Authority-candidate keys keep the default non-exportable.
            "exportable": backup,
            "allow_plaintext_backup": backup,
        },
    )


def configure_key(root: OpenBaoHttp, name: str, *, min_verify: int, min_generate: int) -> None:
    root.request(
        "POST",
        f"transit/keys/{name}/config",
        {"min_decryption_version": min_verify, "min_encryption_version": min_generate},
    )


def rotate_key(root: OpenBaoHttp, name: str) -> None:
    root.request("POST", f"transit/keys/{name}/rotate", {})


def prove_historical_verifier_relocation(root: OpenBaoHttp) -> None:
    create_hmac_key(root, SOURCE_KEY)
    create_hmac_key(root, TARGET_KEY)
    historical_policy = (
        f'path "transit/verify/{SOURCE_KEY}" {{ capabilities = ["update"] }}\n'
        f'path "transit/verify/{SOURCE_KEY}/sha2-256" {{ capabilities = ["update"] }}\n'
    )
    target_policy = (
        f'path "transit/hmac/{TARGET_KEY}" {{ capabilities = ["update"] }}\n'
        f'path "transit/hmac/{TARGET_KEY}/sha2-256" {{ capabilities = ["update"] }}\n'
        f'path "transit/verify/{TARGET_KEY}" {{ capabilities = ["update"] }}\n'
        f'path "transit/verify/{TARGET_KEY}/sha2-256" {{ capabilities = ["update"] }}\n'
    )
    historical_token = create_policy_and_token(root, policy_name="d3e-historical-source", policy=historical_policy)
    target_token = create_policy_and_token(root, policy_name="d3e-target-current", policy=target_policy)
    source_admin = OpenBaoKeyAuthorityAdapter(root, SOURCE_KEY)
    historical_api = OpenBaoHttp(historical_token)
    historical = HistoricalOpenBaoVerifier(OpenBaoKeyAuthorityAdapter(historical_api, SOURCE_KEY))
    target = OpenBaoKeyAuthorityAdapter(OpenBaoHttp(target_token), TARGET_KEY)
    message = canonical_message(
        tenant="tenant-A",
        scope="consumer/orders",
        erasure_unit="record-42",
        payload=b"immutable-body",
    )
    source_mac = source_admin.hmac_sha256(version=1, message=message)
    assert historical.verify(version=1, message=message, mac=source_mac)
    assert not target.verify_hmac_sha256(version=1, message=message, mac=source_mac)
    target_mac = target.hmac_sha256(version=1, message=message)
    assert target_mac != source_mac
    expect_api_denied(
        lambda: historical_api.request(
            "POST",
            f"transit/hmac/{SOURCE_KEY}/sha2-256",
            {"input": b64(message), "key_version": 1},
        )
    )
    expect_api_denied(lambda: historical_api.request("POST", f"transit/keys/{SOURCE_KEY}/rotate", {}))
    expect_api_denied(
        lambda: historical_api.request(
            "POST",
            f"transit/verify/{TARGET_KEY}/sha2-256",
            {"input": b64(message), "hmac": target_mac},
        )
    )
    print(
        "d3_e_historical_verifier_relocation_recovery_continuity=PASS "
        "source_historical_evidence_verified=true target_current_key_independent=true "
        "historical_token_verify_only=true historical_verifier_not_current_authority=true"
    )


def prove_key_rotation_retirement(root: OpenBaoHttp) -> None:
    create_hmac_key(root, ROTATION_KEY)
    adapter = OpenBaoKeyAuthorityAdapter(root, ROTATION_KEY)
    message = canonical_message(
        tenant="tenant-B",
        scope="consumer/billing",
        erasure_unit="record-7",
        payload=b"rotation-body",
    )
    old_mac = adapter.hmac_sha256(version=1, message=message)
    rotate_key(root, ROTATION_KEY)
    configure_key(root, ROTATION_KEY, min_verify=1, min_generate=2)
    expect_api_denied(lambda: adapter.hmac_sha256(version=1, message=message))
    assert adapter.verify_hmac_sha256(version=1, message=message, mac=old_mac)
    new_mac = adapter.hmac_sha256(version=2, message=message)
    assert adapter.verify_hmac_sha256(version=2, message=message, mac=new_mac)
    configure_key(root, ROTATION_KEY, min_verify=2, min_generate=2)
    try:
        retired_valid = adapter.verify_hmac_sha256(version=1, message=message, mac=old_mac)
    except ApiError as exc:
        if exc.status not in (400, 403, 404):
            raise
        retired_valid = False
    assert not retired_valid
    root.request("POST", f"transit/keys/{ROTATION_KEY}/trim", {"min_available_version": 2})
    metadata = root.request("GET", f"transit/keys/{ROTATION_KEY}")
    key_data = metadata.get("data", {})
    assert key_data.get("min_available_version") == 2
    assert key_data.get("latest_version") == 2
    print(
        "d3_e_key_generation_rotation_retirement=PASS "
        "new_generation_issues=true previous_generation_verify_only_overlap=true "
        "previous_generation_generation_disabled=true retired_generation_verify_denied=true "
        "trim_min_available_version=2 latest_version=2"
    )


def prove_erased_nonresurrection(root: OpenBaoHttp) -> None:
    create_hmac_key(root, ERASURE_KEY, backup=True)
    adapter = OpenBaoKeyAuthorityAdapter(root, ERASURE_KEY)
    message = canonical_message(
        tenant="tenant-C",
        scope="consumer/support",
        erasure_unit="subject-99",
        payload=b"erasure-body",
    )
    old_mac = adapter.hmac_sha256(version=1, message=message)
    backup_response = root.request("GET", f"transit/backup/{ERASURE_KEY}")
    backup = backup_response.get("data", {}).get("backup")
    if not isinstance(backup, str) or not backup:
        raise AssertionError("negative-control backup unavailable")
    set_key_state(ERASURE_KEY, current_version=1, minimum_verify_version=1, state="current")
    rotate_key(root, ERASURE_KEY)
    # Governed currentness wins before provider destruction. Even if destruction
    # is delayed or a stale backup later reappears, application authority is fenced.
    set_key_state(ERASURE_KEY, current_version=2, minimum_verify_version=2, state="erased")
    configure_key(root, ERASURE_KEY, min_verify=2, min_generate=2)
    root.request("POST", f"transit/keys/{ERASURE_KEY}/trim", {"min_available_version": 2})
    expect_api_denied(lambda: adapter.verify_hmac_sha256(version=1, message=message, mac=old_mac))
    # Restore stale candidate bytes deliberately as a negative control. The backup
    # remains only in process memory and is never printed or persisted as evidence.
    root.request("POST", f"transit/restore/{STALE_RESTORED_KEY}", {"backup": backup})
    stale_raw = HistoricalOpenBaoVerifier(OpenBaoKeyAuthorityAdapter(root, STALE_RESTORED_KEY))
    assert stale_raw.verify(version=1, message=message, mac=old_mac)
    guarded = RegistryGuardedHistoricalVerifier(
        ERASURE_KEY,
        HistoricalOpenBaoVerifier(OpenBaoKeyAuthorityAdapter(root, STALE_RESTORED_KEY)),
    )
    before = len(root.calls)
    assert not guarded.verify(version=1, message=message, mac=old_mac)
    after = len(root.calls)
    assert after == before
    print(
        "d3_e_retired_erased_key_nonresurrection=PASS "
        "governed_erasure_precedes_provider_destroy=true provider_trim_irreversible=true "
        "stale_restored_provider_negative_control_verifies=true external_currentness_blocks_restore=true "
        "erased_generation_denied_before_provider_call=true negative_control_backup_fixture_only=true "
        "backup_material_not_logged=true"
    )


def prove_replay_atomic_single_winner() -> None:
    def attempt(_: int) -> bool:
        return replay_claim(client="machine-A", jti="assertion-jti-race", epoch=1)

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        outcomes = list(pool.map(attempt, range(32)))
    assert sum(outcomes) == 1 and outcomes.count(False) == 31
    print(
        "d3_e_private_key_jwt_replay_atomic_single_winner=PASS "
        "shared_postgresql_authority=true create_or_observe_atomic=true "
        "parallel_token_boundary_replicas=32 exactly_one_winner=true local_check_then_insert=false"
    )


def prove_replay_partition_fail_closed() -> None:
    subprocess.run(["docker", "pause", PG_CONTAINER], check=True, capture_output=True, text=True)
    denied = False
    try:
        try:
            replay_claim(client="machine-A", jti="assertion-jti-partition", epoch=1, timeout=2.0)
        except (ReplayUnavailable, RuntimeError):
            denied = True
    finally:
        subprocess.run(["docker", "unpause", PG_CONTAINER], check=True, capture_output=True, text=True)
    assert denied
    count = pg(
        "SELECT count(*) FROM d3e.replay_claim "
        + f"WHERE scope={sql_literal(REPLAY_SCOPE)} AND jti='assertion-jti-partition';"
    )
    assert count == "0"
    print(
        "d3_e_replay_partition_fail_closed=PASS "
        "actual_replay_authority_partition=true no_replica_local_fallback=true "
        "no_access_token_eligibility_on_uncertainty=true partition_attempt_not_recorded_as_success=true"
    )


def prove_replay_restore_loss() -> None:
    assert replay_claim(client="machine-A", jti="assertion-jti-current-snapshot", epoch=1)
    pg(
        "DROP TABLE IF EXISTS d3e.snapshot_current; "
        "CREATE TABLE d3e.snapshot_current AS TABLE d3e.replay_claim;"
    )
    pg(
        "DELETE FROM d3e.replay_claim; "
        "INSERT INTO d3e.replay_claim SELECT * FROM d3e.snapshot_current;"
    )
    assert not replay_claim(client="machine-A", jti="assertion-jti-current-snapshot", epoch=1)
    pg(
        "DROP TABLE IF EXISTS d3e.snapshot_old; "
        "CREATE TABLE d3e.snapshot_old AS TABLE d3e.replay_claim;"
    )
    assert replay_claim(client="machine-A", jti="assertion-jti-lost-after-R", epoch=1)
    # Recovery admission is fenced *before* rollback-subject replay rows are restored.
    # Restored bytes cannot serve until security-authority continuity is reconciled.
    new_epoch = block_replay_after_restore_loss()
    pg(
        "DELETE FROM d3e.replay_claim; "
        "INSERT INTO d3e.replay_claim SELECT * FROM d3e.snapshot_old;"
    )
    assert new_epoch == 2
    denied_old_epoch = False
    denied_new_epoch = False
    for epoch, marker in ((1, "old"), (2, "new")):
        try:
            replay_claim(client="machine-A", jti="assertion-jti-lost-after-R", epoch=epoch)
        except ReplayUnavailable:
            if marker == "old":
                denied_old_epoch = True
            else:
                denied_new_epoch = True
    assert denied_old_epoch and denied_new_epoch
    state = pg(
        "SELECT state || ':' || epoch::text FROM d3e.replay_continuity "
        + f"WHERE scope={sql_literal(REPLAY_SCOPE)};"
    )
    assert state == "recovery_blocked:2"
    print(
        "d3_e_replay_consumed_identity_survives_restore_loss=PASS "
        "current_snapshot_preserves_consumed_identity=true rollback_missing_row_not_unused=true "
        "trusted_recovery_fence_precedes_rollback_restore=true old_epoch_rejected=true "
        "new_epoch_blocked_until_reconciliation=true recovery_blocked_fail_closed=true"
    )


def main() -> None:
    setup_postgres()
    root = root_api()
    root.request("POST", "sys/mounts/transit", {"type": "transit"})
    prove_historical_verifier_relocation(root)
    prove_key_rotation_retirement(root)
    prove_erased_nonresurrection(root)
    prove_replay_atomic_single_winner()
    prove_replay_partition_fail_closed()
    prove_replay_restore_loss()
    print(
        "d3_e_key_authority_conformance=PASS_PINNED_CANDIDATE "
        "openbao_transit_real=true postgresql_replay_real=true provider_neutral_boundary=true "
        "evidence_credited=false c3_numerics=not_selected d3_global=not_accepted "
        "wave4=not_granted production=none d4=not_selected_not_granted"
    )


if __name__ == "__main__":
    main()
