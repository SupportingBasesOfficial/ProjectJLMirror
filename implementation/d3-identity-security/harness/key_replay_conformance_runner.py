#!/usr/bin/env python3
from __future__ import annotations

import base64
import concurrent.futures
import dataclasses
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from typing import Protocol


OPENBAO_BIN = os.environ["OPENBAO_BIN"]
PG_CONTAINER = os.environ["PG_CONTAINER"]
PG_PASSWORD = os.environ.get("PG_PASSWORD", "d3-postgres-password")
PG_DATABASE = os.environ.get("PG_DATABASE", "d3")
PG_USER = os.environ.get("PG_USER", "postgres")
KEY_NAME = "jlmirror-d3e-receipt-hmac"
CONTEXT_ID = "jlmirror:d3-e:receipt:v1"
ALGORITHM = "sha2-256"
WORK_ROOT = pathlib.Path(os.environ.get("D3E_WORK_ROOT", tempfile.mkdtemp(prefix="jlmirror-d3e-"))).resolve()
WORK_ROOT.mkdir(parents=True, exist_ok=True)


def fail(message: str) -> None:
    raise AssertionError(message)


def run(cmd: list[str], *, check: bool = True, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"command failed rc={result.returncode}: {' '.join(cmd)}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return result


def pg_psql(sql: str, *, timeout: float = 15.0, check: bool = True) -> str:
    cmd = [
        "docker", "exec", "-e", f"PGPASSWORD={PG_PASSWORD}", PG_CONTAINER,
        "psql", "-X", "-v", "ON_ERROR_STOP=1", "-U", PG_USER, "-d", PG_DATABASE,
        "-At", "-F", "\t", "-c", sql,
    ]
    result = run(cmd, timeout=timeout, check=check)
    return result.stdout.strip()


def pg_setup() -> None:
    sql = r"""
CREATE SCHEMA IF NOT EXISTS crypto_control;

CREATE TABLE IF NOT EXISTS crypto_control.key_policy (
    key_name text PRIMARY KEY,
    min_verify_version integer NOT NULL CHECK (min_verify_version >= 1),
    current_write_version integer NOT NULL CHECK (current_write_version >= min_verify_version),
    policy_epoch bigint NOT NULL CHECK (policy_epoch >= 1)
);

CREATE TABLE IF NOT EXISTS crypto_control.replay_claim (
    issuer text NOT NULL,
    jti text NOT NULL,
    fingerprint text NOT NULL,
    tenant_context text NOT NULL,
    durable_owner_token text NOT NULL,
    outcome text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (issuer, jti)
);

CREATE OR REPLACE FUNCTION crypto_control.claim_replay(
    p_issuer text,
    p_jti text,
    p_fingerprint text,
    p_tenant_context text,
    p_owner_token text,
    p_outcome text
)
RETURNS TABLE (
    is_owner boolean,
    durable_owner_token text,
    durable_fingerprint text,
    durable_tenant_context text,
    durable_outcome text
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_owner text;
    v_fingerprint text;
    v_tenant text;
    v_outcome text;
BEGIN
    IF p_issuer IS NULL OR p_issuer = '' OR p_jti IS NULL OR p_jti = '' THEN
        RAISE EXCEPTION 'issuer and jti are required';
    END IF;

    PERFORM pg_advisory_xact_lock(hashtext(p_issuer), hashtext(p_jti));

    INSERT INTO crypto_control.replay_claim(
        issuer, jti, fingerprint, tenant_context, durable_owner_token, outcome
    )
    VALUES (
        p_issuer, p_jti, p_fingerprint, p_tenant_context, p_owner_token, p_outcome
    )
    ON CONFLICT (issuer, jti) DO NOTHING;

    SELECT r.durable_owner_token, r.fingerprint, r.tenant_context, r.outcome
      INTO STRICT v_owner, v_fingerprint, v_tenant, v_outcome
      FROM crypto_control.replay_claim AS r
     WHERE r.issuer = p_issuer AND r.jti = p_jti;

    RETURN QUERY
    SELECT
        (v_owner = p_owner_token),
        v_owner,
        v_fingerprint,
        v_tenant,
        v_outcome;
END;
$$;
"""
    pg_psql(sql)
    pg_psql(
        "DELETE FROM crypto_control.replay_claim;"
        "DELETE FROM crypto_control.key_policy;"
        f"INSERT INTO crypto_control.key_policy(key_name,min_verify_version,current_write_version,policy_epoch)"
        f" VALUES ('{KEY_NAME}',1,1,1);"
    )


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


@dataclasses.dataclass(frozen=True)
class KeyPolicy:
    min_verify_version: int
    current_write_version: int
    policy_epoch: int


class KeyPolicyStore:
    def read(self) -> KeyPolicy:
        out = pg_psql(
            f"SELECT min_verify_version,current_write_version,policy_epoch "
            f"FROM crypto_control.key_policy WHERE key_name={sql_literal(KEY_NAME)};"
        )
        parts = out.split("\t")
        if len(parts) != 3:
            fail(f"unexpected key policy row: {out!r}")
        return KeyPolicy(*(int(x) for x in parts))

    def rotate_write_version(self, expected: int, new: int) -> KeyPolicy:
        out = pg_psql(
            "UPDATE crypto_control.key_policy "
            f"SET current_write_version={new}, policy_epoch=policy_epoch+1 "
            f"WHERE key_name={sql_literal(KEY_NAME)} AND current_write_version={expected} "
            "RETURNING min_verify_version,current_write_version,policy_epoch;"
        )
        if not out:
            fail("write-version CAS lost")
        return self.read()

    def retire_before(self, expected_floor: int, new_floor: int) -> KeyPolicy:
        out = pg_psql(
            "UPDATE crypto_control.key_policy "
            f"SET min_verify_version={new_floor}, policy_epoch=policy_epoch+1 "
            f"WHERE key_name={sql_literal(KEY_NAME)} AND min_verify_version={expected_floor} "
            f"AND current_write_version >= {new_floor} "
            "RETURNING min_verify_version,current_write_version,policy_epoch;"
        )
        if not out:
            fail("retirement-floor CAS lost")
        return self.read()


class VersionedHmacProvider(Protocol):
    verify_calls: int
    hmac_calls: int
    def generate(self, key_name: str, payload: bytes, key_version: int) -> str: ...
    def verify(self, key_name: str, payload: bytes, hmac_value: str) -> bool: ...
    def rotate(self, key_name: str) -> int: ...
    def versions(self, key_name: str) -> set[int]: ...
    def configure_min_versions(self, key_name: str, minimum: int) -> None: ...


def api_request(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    token: str | None = None,
    body: dict | None = None,
    timeout: float = 5.0,
    allow_status: set[int] | None = None,
) -> tuple[int, dict]:
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Vault-Token"] = token
    if body is not None:
        data = json.dumps(body, separators=(",", ":")).encode()
    request = urllib.request.Request(base_url + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            parsed = json.loads(raw) if raw else {}
            return response.status, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        parsed = json.loads(raw) if raw else {}
        if allow_status and exc.code in allow_status:
            return exc.code, parsed
        raise RuntimeError(f"OpenBao HTTP {exc.code} {path}: {parsed}") from exc


class OpenBaoServer:
    def __init__(self, storage_dir: pathlib.Path, port: int, name: str) -> None:
        self.storage_dir = storage_dir.resolve()
        self.port = port
        self.name = name
        self.base_url = f"http://127.0.0.1:{port}"
        self.config_path = WORK_ROOT / f"{name}.hcl"
        self.log_path = WORK_ROOT / f"{name}.log"
        self.process: subprocess.Popen[str] | None = None
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _write_config(self) -> None:
        self.config_path.write_text(
            f"""ui = false
disable_mlock = true
api_addr = "{self.base_url}"

storage "file" {{
  path = "{self.storage_dir}"
}}

listener "tcp" {{
  address = "127.0.0.1:{self.port}"
  tls_disable = true
}}
""",
            encoding="utf-8",
        )

    def start(self) -> None:
        self._write_config()
        log = self.log_path.open("a", encoding="utf-8")
        self.process = subprocess.Popen(
            [OPENBAO_BIN, "server", f"-config={self.config_path}", "-log-level=warn"],
            stdout=log, stderr=subprocess.STDOUT, text=True,
        )
        deadline = time.time() + 20
        while time.time() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"OpenBao {self.name} exited early; log={self.log_path.read_text(errors='replace')}")
            try:
                status, _ = api_request(
                    self.base_url, "/v1/sys/health", timeout=0.5,
                    allow_status={429, 472, 473, 501, 503},
                )
                if status in {200, 429, 472, 473, 501, 503}:
                    return
            except Exception:
                pass
            time.sleep(0.2)
        raise RuntimeError(f"OpenBao {self.name} readiness deadline exceeded")

    def stop(self) -> None:
        if not self.process:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=3)
        self.process = None

    def init(self) -> tuple[str, str]:
        _, payload = api_request(
            self.base_url, "/v1/sys/init", method="POST",
            body={"secret_shares": 1, "secret_threshold": 1},
        )
        keys = payload.get("keys_base64") or payload.get("keys") or []
        if len(keys) != 1 or not payload.get("root_token"):
            fail(f"unexpected OpenBao init response keys/root token: {payload.keys()}")
        return str(keys[0]), str(payload["root_token"])

    def unseal(self, unseal_key: str) -> None:
        _, payload = api_request(
            self.base_url, "/v1/sys/unseal", method="POST", body={"key": unseal_key},
        )
        if payload.get("sealed") is not False:
            fail(f"OpenBao {self.name} did not unseal")


class OpenBaoTransitProvider:
    def __init__(self, server: OpenBaoServer, token: str) -> None:
        self.server = server
        self.token = token
        self.verify_calls = 0
        self.hmac_calls = 0

    @property
    def base_url(self) -> str:
        return self.server.base_url

    def enable_transit(self) -> None:
        api_request(
            self.base_url, "/v1/sys/mounts/transit", method="POST", token=self.token,
            body={"type": "transit", "description": "JLMirror D3-E candidate evidence"},
        )

    def create_hmac_key(self, key_name: str) -> None:
        api_request(
            self.base_url, f"/v1/transit/keys/{key_name}", method="POST", token=self.token,
            body={"type": "hmac"},
        )

    def generate(self, key_name: str, payload: bytes, key_version: int) -> str:
        self.hmac_calls += 1
        _, body = api_request(
            self.base_url, f"/v1/transit/hmac/{key_name}/{ALGORITHM}",
            method="POST", token=self.token,
            body={"input": base64.b64encode(payload).decode(), "key_version": key_version},
        )
        value = str(body.get("data", {}).get("hmac", ""))
        expected_prefix = f"vault:v{key_version}:"
        if not value.startswith(expected_prefix):
            fail(f"provider returned unexpected HMAC version: {value!r}")
        return value

    def verify(self, key_name: str, payload: bytes, hmac_value: str) -> bool:
        self.verify_calls += 1
        status, body = api_request(
            self.base_url, f"/v1/transit/verify/{key_name}/{ALGORITHM}",
            method="POST", token=self.token,
            body={"input": base64.b64encode(payload).decode(), "hmac": hmac_value},
            allow_status={400},
        )
        if status == 400:
            return False
        return body.get("data", {}).get("valid") is True

    def rotate(self, key_name: str) -> int:
        api_request(
            self.base_url, f"/v1/transit/keys/{key_name}/rotate",
            method="POST", token=self.token, body={},
        )
        return max(self.versions(key_name))

    def versions(self, key_name: str) -> set[int]:
        _, body = api_request(self.base_url, f"/v1/transit/keys/{key_name}", token=self.token)
        keys = body.get("data", {}).get("keys", {})
        versions = {int(v) for v in keys.keys()}
        if not versions:
            fail("OpenBao returned no key versions")
        return versions

    def configure_min_versions(self, key_name: str, minimum: int) -> None:
        api_request(
            self.base_url, f"/v1/transit/keys/{key_name}/config",
            method="POST", token=self.token,
            body={"min_decryption_version": minimum, "min_encryption_version": minimum},
        )


@dataclasses.dataclass(frozen=True)
class VerifierRecord:
    key_name: str
    key_version: int
    algorithm: str
    context_id: str
    hmac: str


class ProviderNeutralKeyAuthority:
    def __init__(self, provider: VersionedHmacProvider, policy: KeyPolicyStore) -> None:
        self.provider = provider
        self.policy = policy

    @staticmethod
    def canonical_input(context_id: str, payload: bytes) -> bytes:
        context = context_id.encode("utf-8")
        return (
            b"JLMIRROR-D3E-HMAC-V1\0"
            + len(context).to_bytes(4, "big") + context
            + len(payload).to_bytes(8, "big") + payload
        )

    def issue(self, payload: bytes, *, context_id: str = CONTEXT_ID) -> VerifierRecord:
        policy = self.policy.read()
        message = self.canonical_input(context_id, payload)
        hmac_value = self.provider.generate(KEY_NAME, message, policy.current_write_version)
        version = parse_hmac_version(hmac_value)
        if version != policy.current_write_version:
            fail("provider violated current write-version authority")
        return VerifierRecord(KEY_NAME, version, ALGORITHM, context_id, hmac_value)

    def verify(self, record: VerifierRecord, payload: bytes) -> bool:
        if record.key_name != KEY_NAME or record.algorithm != ALGORITHM or record.context_id != CONTEXT_ID:
            return False
        policy = self.policy.read()
        if record.key_version < policy.min_verify_version:
            return False
        if record.key_version > policy.current_write_version:
            return False
        if parse_hmac_version(record.hmac) != record.key_version:
            return False
        return self.provider.verify(KEY_NAME, self.canonical_input(record.context_id, payload), record.hmac)

    def backfill(self, historical_record: VerifierRecord, historical_payload: bytes, new_payload: bytes) -> VerifierRecord:
        if not self.verify(historical_record, historical_payload):
            raise PermissionError("historical verifier not currently trusted")
        return self.issue(new_payload)


def parse_hmac_version(value: str) -> int:
    parts = value.split(":", 2)
    if len(parts) != 3 or parts[0] != "vault" or not parts[1].startswith("v"):
        fail(f"unversioned or malformed HMAC: {value!r}")
    return int(parts[1][1:])


@dataclasses.dataclass(frozen=True)
class ReplayResult:
    is_owner: bool
    durable_owner_token: str
    durable_fingerprint: str
    durable_tenant_context: str
    durable_outcome: str


class DurableReplayStore:
    def claim(
        self, *, issuer: str, jti: str, fingerprint: str, tenant_context: str,
        owner_token: str, outcome: str, timeout: float = 15.0,
    ) -> ReplayResult:
        sql = (
            "SELECT is_owner,durable_owner_token,durable_fingerprint,durable_tenant_context,durable_outcome "
            "FROM crypto_control.claim_replay("
            + ",".join(sql_literal(v) for v in (issuer, jti, fingerprint, tenant_context, owner_token, outcome))
            + ");"
        )
        out = pg_psql(sql, timeout=timeout)
        parts = out.split("\t")
        if len(parts) != 5:
            fail(f"unexpected replay result: {out!r}")
        result = ReplayResult(parts[0] == "t", parts[1], parts[2], parts[3], parts[4])
        if result.durable_fingerprint != fingerprint:
            raise ValueError("replay fingerprint conflict")
        return result


def copy_storage(src: pathlib.Path, dst: pathlib.Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def prove_historical_relocation_and_rotation(
    primary: OpenBaoServer, unseal_key: str, root_token: str, policy_store: KeyPolicyStore,
) -> tuple[OpenBaoServer, OpenBaoTransitProvider, ProviderNeutralKeyAuthority, VerifierRecord, VerifierRecord, pathlib.Path]:
    primary_provider = OpenBaoTransitProvider(primary, root_token)
    primary_provider.enable_transit()
    primary_provider.create_hmac_key(KEY_NAME)
    if primary_provider.versions(KEY_NAME) != {1}:
        fail("initial OpenBao HMAC key was not v1")

    authority = ProviderNeutralKeyAuthority(primary_provider, policy_store)
    payload_v1 = b"receipt-before-relocation"
    receipt_v1 = authority.issue(payload_v1)
    if receipt_v1.key_version != 1 or not authority.verify(receipt_v1, payload_v1):
        fail("v1 receipt did not verify before relocation")

    primary.stop()
    relocated_dir = WORK_ROOT / "openbao-relocated-data"
    copy_storage(primary.storage_dir, relocated_dir)
    relocated = OpenBaoServer(relocated_dir, 18201, "relocated")
    relocated.start()
    relocated.unseal(unseal_key)
    relocated_provider = OpenBaoTransitProvider(relocated, root_token)
    relocated_authority = ProviderNeutralKeyAuthority(relocated_provider, policy_store)

    if not relocated_authority.verify(receipt_v1, payload_v1):
        fail("historical verifier failed after physical storage relocation")

    print(
        "d3_e_historical_verifier_relocation_recovery_continuity=PASS "
        "persistent_file_storage=true physical_storage_relocation=true same_unseal_recovery=true "
        "historical_v1_verified_after_relocation=true"
    )

    new_version = relocated_provider.rotate(KEY_NAME)
    if new_version != 2 or relocated_provider.versions(KEY_NAME) != {1, 2}:
        fail("OpenBao rotation did not establish v2 while retaining v1")
    policy = policy_store.rotate_write_version(1, 2)
    if policy.current_write_version != 2 or policy.min_verify_version != 1:
        fail("write-version authority did not cut over to v2 with dual-read retained")

    payload_v2 = b"receipt-after-current-key-rotation"
    receipt_v2 = relocated_authority.issue(payload_v2)
    if receipt_v2.key_version != 2:
        fail("new write did not use current v2")
    if not relocated_authority.verify(receipt_v1, payload_v1):
        fail("historical v1 stopped verifying before retirement")
    if not relocated_authority.verify(receipt_v2, payload_v2):
        fail("current v2 did not verify")

    old_hmac_calls = relocated_provider.hmac_calls
    backfill = relocated_authority.backfill(receipt_v1, payload_v1, b"late-backfill-output")
    if backfill.key_version != 2 or relocated_provider.hmac_calls != old_hmac_calls + 1:
        fail("late backfill did not verify historical input then single-write current v2")

    print(
        "d3_e_late_backfill_after_current_key_rotation=PASS "
        "historical_v1_read_after_rotation=true backfill_write_version_v2=true single_write_current=true"
    )

    stale_snapshot = WORK_ROOT / "openbao-stale-pre-retirement"
    relocated.stop()
    copy_storage(relocated.storage_dir, stale_snapshot)
    relocated.start()
    relocated.unseal(unseal_key)

    if not relocated_authority.verify(receipt_v1, payload_v1):
        fail("v1 continuity failed after same-storage recovery restart")

    print(
        "d3_e_key_rotation_retirement_dual_read_single_write=PASS "
        "post_rotation_dual_read_v1_v2=true new_write_only_v2=true "
        "versioned_verifier_record=true external_write_version_authority=true"
    )
    return relocated, relocated_provider, relocated_authority, receipt_v1, receipt_v2, stale_snapshot


def prove_retirement_nonresurrection(
    active: OpenBaoServer, active_provider: OpenBaoTransitProvider,
    authority: ProviderNeutralKeyAuthority, policy_store: KeyPolicyStore,
    unseal_key: str, root_token: str, receipt_v1: VerifierRecord,
    receipt_v2: VerifierRecord, stale_snapshot: pathlib.Path,
) -> None:
    payload_v1 = b"receipt-before-relocation"
    payload_v2 = b"receipt-after-current-key-rotation"

    policy = policy_store.retire_before(1, 2)
    if policy.min_verify_version != 2 or policy.current_write_version != 2:
        fail("trusted retirement floor did not advance to v2")
    active_provider.configure_min_versions(KEY_NAME, 2)

    verify_calls_before = active_provider.verify_calls
    if authority.verify(receipt_v1, payload_v1):
        fail("retired v1 was accepted by provider-neutral authority")
    if active_provider.verify_calls != verify_calls_before:
        fail("retired version reached provider despite trusted external floor")
    if not authority.verify(receipt_v2, payload_v2):
        fail("v2 stopped verifying after v1 retirement")

    if active_provider.verify(KEY_NAME, authority.canonical_input(CONTEXT_ID, payload_v1), receipt_v1.hmac):
        fail("current OpenBao config still verifies retired v1")

    hmac_calls_before = active_provider.hmac_calls
    try:
        authority.backfill(receipt_v1, payload_v1, b"backfill-after-retirement")
    except PermissionError:
        pass
    else:
        fail("backfill from retired historical verifier did not fail closed")
    if active_provider.hmac_calls != hmac_calls_before:
        fail("retired historical input caused a new HMAC write")

    active.stop()
    restored_dir = WORK_ROOT / "openbao-restored-stale"
    copy_storage(stale_snapshot, restored_dir)
    stale = OpenBaoServer(restored_dir, 18202, "stale-restore")
    stale.start()
    stale.unseal(unseal_key)
    stale_provider = OpenBaoTransitProvider(stale, root_token)
    stale_authority = ProviderNeutralKeyAuthority(stale_provider, policy_store)

    if not stale_provider.verify(
        KEY_NAME, stale_authority.canonical_input(CONTEXT_ID, payload_v1), receipt_v1.hmac,
    ):
        fail("stale provider snapshot is not a genuine resurrected-v1 negative control")

    calls_before = stale_provider.verify_calls
    if stale_authority.verify(receipt_v1, payload_v1):
        fail("stale provider self-certified retired v1 authority")
    if stale_provider.verify_calls != calls_before:
        fail("trusted external floor did not reject v1 before stale provider verification")
    if not stale_authority.verify(receipt_v2, payload_v2):
        fail("allowed v2 failed through stale pre-retirement snapshot")

    print(
        "d3_e_retired_key_nonresurrection=PASS "
        "trusted_pg_retirement_floor=true current_provider_v1_disabled=true "
        "stale_snapshot_genuine_v1_negative_control=true stale_provider_cannot_self_certify=true "
        "v2_remains_verifiable=true"
    )
    stale.stop()


def prove_replay_single_winner() -> None:
    replay = DurableReplayStore()
    issuer = "https://issuer.example.test"
    jti = "same-jti-global-replay"
    fingerprint = hashlib.sha256(b"assertion-canonical-bytes").hexdigest()

    def contender(index: int) -> ReplayResult:
        return replay.claim(
            issuer=issuer, jti=jti, fingerprint=fingerprint,
            tenant_context=f"tenant-{index % 4}",
            owner_token=f"owner-{index}-{uuid.uuid4()}", outcome="accepted",
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(contender, range(16)))

    owners = [r for r in results if r.is_owner]
    durable_owners = {r.durable_owner_token for r in results}
    if (
        len(owners) != 1
        or len(durable_owners) != 1
        or {r.durable_fingerprint for r in results} != {fingerprint}
        or {r.durable_outcome for r in results} != {"accepted"}
    ):
        fail(f"replay create-or-observe not single-winner: owners={len(owners)} durable_owners={durable_owners}")

    tenant_observer = replay.claim(
        issuer=issuer, jti=jti, fingerprint=fingerprint,
        tenant_context="tenant-completely-different",
        owner_token=f"observer-{uuid.uuid4()}", outcome="accepted",
    )
    if tenant_observer.is_owner or tenant_observer.durable_owner_token not in durable_owners:
        fail("tenant context improperly changed global replay uniqueness")

    try:
        replay.claim(
            issuer=issuer, jti=jti,
            fingerprint=hashlib.sha256(b"different-assertion").hexdigest(),
            tenant_context="tenant-conflict", owner_token=f"conflict-{uuid.uuid4()}",
            outcome="accepted",
        )
    except ValueError:
        pass
    else:
        fail("same replay identity with mismatched fingerprint was not rejected")

    row_count = pg_psql(
        f"SELECT count(*) FROM crypto_control.replay_claim "
        f"WHERE issuer={sql_literal(issuer)} AND jti={sql_literal(jti)};"
    )
    if row_count != "1":
        fail(f"replay identity produced {row_count} durable rows")

    print(
        "d3_e_replay_create_or_observe_exactly_one_owner=PASS "
        "unique_issuer_jti=true advisory_serialized_create_or_observe=true "
        "sixteen_contenders_one_owner=true all_duplicates_observe_winner=true "
        "tenant_not_in_uniqueness=true fingerprint_conflict_rejected=true"
    )


def prove_replay_store_unavailable_fail_closed() -> None:
    replay = DurableReplayStore()
    issuer = "https://issuer.example.test"
    jti = "outage-probe"
    fingerprint = hashlib.sha256(b"outage-probe").hexdigest()

    run(["docker", "pause", PG_CONTAINER])
    start = time.monotonic()
    denied = False
    try:
        replay.claim(
            issuer=issuer, jti=jti, fingerprint=fingerprint,
            tenant_context="tenant-outage", owner_token=f"outage-{uuid.uuid4()}",
            outcome="accepted", timeout=1.5,
        )
    except (subprocess.TimeoutExpired, RuntimeError):
        denied = True
    finally:
        run(["docker", "unpause", PG_CONTAINER], check=False)
    elapsed = time.monotonic() - start
    if not denied:
        fail("replay store outage did not fail closed")

    out = pg_psql(
        f"SELECT count(*) FROM crypto_control.replay_claim "
        f"WHERE issuer={sql_literal(issuer)} AND jti={sql_literal(jti)};"
    )
    if out != "0":
        fail("outage path created replay state outside durable store")

    recovery = replay.claim(
        issuer=issuer, jti=jti, fingerprint=fingerprint,
        tenant_context="tenant-outage", owner_token=f"recovery-{uuid.uuid4()}",
        outcome="accepted",
    )
    if not recovery.is_owner:
        fail("first post-recovery durable claim was not owner")

    print(
        "d3_e_replay_store_unavailable_fail_closed=PASS "
        f"actual_postgres_pause=true bounded_client_timeout=true no_memory_fallback=true "
        f"no_phantom_claim=true recovery_first_durable_claim_owner=true elapsed_lt_5s={elapsed < 5.0}"
    )


def main() -> None:
    print(f"d3_e_work_root={WORK_ROOT}")
    pg_setup()
    policy_store = KeyPolicyStore()

    primary = OpenBaoServer(WORK_ROOT / "openbao-primary-data", 18200, "primary")
    primary.start()
    unseal_key, root_token = primary.init()
    primary.unseal(unseal_key)

    active = None
    try:
        active, provider, authority, receipt_v1, receipt_v2, stale_snapshot = (
            prove_historical_relocation_and_rotation(primary, unseal_key, root_token, policy_store)
        )
        prove_retirement_nonresurrection(
            active, provider, authority, policy_store, unseal_key, root_token,
            receipt_v1, receipt_v2, stale_snapshot,
        )
        active = None

        prove_replay_single_winner()
        prove_replay_store_unavailable_fail_closed()

        print(
            "d3_e_key_replay_candidate_conformance=PASS_PINNED_OPENBAO "
            "openbao_transit_real=true postgres_replay_real=true provider_neutral_port=true "
            "production_numerics_not_selected=true"
        )
    finally:
        primary.stop()
        if active is not None:
            active.stop()


if __name__ == "__main__":
    main()
