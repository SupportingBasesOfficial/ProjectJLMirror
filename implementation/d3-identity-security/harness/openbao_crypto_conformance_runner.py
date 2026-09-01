#!/usr/bin/env python3
from __future__ import annotations

import base64
import concurrent.futures
from dataclasses import dataclass, fields
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Protocol
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import quote

PG_CONTAINER = os.environ.get("PG_CONTAINER", "jlmirror-d3e-postgres")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "d3-postgres-password")
OPENBAO_IMAGE = os.environ["OPENBAO_IMAGE"]
D3_NETWORK = os.environ.get("D3_NETWORK", "jlmirror-d3e-conformance")
SOURCE_CONTAINER = "jlmirror-d3e-openbao-source"
TARGET_CONTAINER = "jlmirror-d3e-openbao-target"
SOURCE_VOLUME = "jlmirror-d3e-openbao-source-data"
TARGET_VOLUME = "jlmirror-d3e-openbao-target-data"
STALE_VOLUME = "jlmirror-d3e-openbao-stale-data"
SOURCE_ADDR = "http://127.0.0.1:18200"
TARGET_ADDR = "http://127.0.0.1:18201"
CONFIG_PATH = Path("/tmp/jlmirror-d3e-openbao.hcl")
CRYPTO_WITNESS_PATH = Path(os.environ.get("D3E_CRYPTO_WITNESS", "/tmp/jlmirror-d3e-crypto-witness.json"))


def sh(args: list[str], *, input_text: str | None = None, timeout: float = 45, check: bool = True):
    r = subprocess.run(args, input=input_text, text=True, capture_output=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(f"command failed rc={r.returncode}: {r.stderr.strip()[:900]}")
    return r


def lit(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def psql(sql: str) -> str:
    return sh([
        "docker", "exec", "-e", f"PGPASSWORD={PG_PASSWORD}", PG_CONTAINER,
        "psql", "-X", "-U", "postgres", "-d", "d3", "-v", "ON_ERROR_STOP=1", "-Atq", "-c", sql,
    ]).stdout.strip()


def psql_script(script: str) -> None:
    sh([
        "docker", "exec", "-i", "-e", f"PGPASSWORD={PG_PASSWORD}", PG_CONTAINER,
        "psql", "-X", "-U", "postgres", "-d", "d3", "-v", "ON_ERROR_STOP=1", "-q",
    ], input_text=script)


class BaoError(RuntimeError):
    def __init__(self, status: int, body: str = ""):
        super().__init__(f"OpenBao HTTP {status}: {body[:300]}")
        self.status = status


class BaoClient:
    def __init__(self, addr: str, token: str | None = None):
        self.addr = addr.rstrip("/")
        self.token = token

    def call(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        *,
        expect: set[int] = {200, 204},
        timeout: float = 6,
    ) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["X-Vault-Token"] = self.token
        req = urlrequest.Request(
            f"{self.addr}/v1/{path.lstrip('/')}",
            data=None if body is None else json.dumps(body, separators=(",", ":")).encode(),
            method=method,
            headers=headers,
        )
        try:
            with urlrequest.urlopen(req, timeout=timeout) as resp:
                status, raw = resp.status, resp.read()
        except urlerror.HTTPError as exc:
            status, raw = exc.code, exc.read()
            if status not in expect:
                raise BaoError(status, raw.decode("utf-8", "replace")) from exc
        except Exception as exc:
            raise RuntimeError("OpenBao authority unavailable") from exc
        if status not in expect:
            raise BaoError(status, raw.decode("utf-8", "replace"))
        return {} if not raw else json.loads(raw)


def wait_server_reachable(addr: str) -> None:
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            BaoClient(addr).call("GET", "sys/health", expect={200, 429, 472, 473, 501, 503})
            return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("OpenBao server did not become reachable")


def wait_unsealed(addr: str) -> None:
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            data = BaoClient(addr).call("GET", "sys/health", expect={200, 429, 472, 473, 501, 503})
            if data.get("sealed") is False and data.get("initialized") is True:
                return
        except Exception:
            pass
        time.sleep(0.2)
    raise RuntimeError("OpenBao server did not become unsealed")


def write_config() -> None:
    CONFIG_PATH.write_text(
        'storage "file" {\n'
        '  path = "/openbao/file"\n'
        '}\n'
        'listener "tcp" {\n'
        '  address = "0.0.0.0:8200"\n'
        '  tls_disable = true\n'
        '}\n'
        'disable_mlock = true\n'
        'api_addr = "http://127.0.0.1:8200"\n'
    )


def remove_container(name: str) -> None:
    sh(["docker", "rm", "-f", name], check=False)


def remove_volume(name: str) -> None:
    sh(["docker", "volume", "rm", "-f", name], check=False)


def create_volume(name: str) -> None:
    sh(["docker", "volume", "create", name])


def start_bao(name: str, volume: str, port: int) -> None:
    remove_container(name)
    sh([
        "docker", "run", "-d", "--rm", "--name", name, "--network", D3_NETWORK,
        "--cap-add=IPC_LOCK", "-p", f"127.0.0.1:{port}:8200",
        "-v", f"{volume}:/openbao/file",
        "-v", f"{CONFIG_PATH}:/openbao/config/d3e.hcl:ro",
        OPENBAO_IMAGE, "server", "-config=/openbao/config/d3e.hcl",
    ])
    wait_server_reachable(f"http://127.0.0.1:{port}")


def initialize_source() -> tuple[str, str]:
    r = sh([
        "docker", "exec", "-e", "BAO_ADDR=http://127.0.0.1:8200", "-e", "VAULT_ADDR=http://127.0.0.1:8200", SOURCE_CONTAINER,
        "bao", "operator", "init", "-key-shares=1", "-key-threshold=1", "-format=json",
    ])
    data = json.loads(r.stdout)
    unseal = data["unseal_keys_b64"][0]
    root = data["root_token"]
    if not unseal or not root:
        raise RuntimeError("OpenBao initialization did not return recovery material")
    unseal_server(SOURCE_ADDR, unseal)
    return unseal, root


def unseal_server(addr: str, unseal_key: str) -> None:
    data = BaoClient(addr).call("POST", "sys/unseal", {"key": unseal_key}, expect={200})
    if data.get("sealed") is not False:
        raise RuntimeError("OpenBao unseal did not complete")
    wait_unsealed(addr)


def copy_volume(src: str, dst: str) -> None:
    remove_volume(dst)
    create_volume(dst)
    sh([
        "docker", "run", "--rm", "--entrypoint", "/bin/sh",
        "-v", f"{src}:/from:ro", "-v", f"{dst}:/to",
        OPENBAO_IMAGE, "-ec", "cp -a /from/. /to/",
    ])


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


@dataclass(frozen=True)
class LogicalKeyHandle:
    logical_key_id: str
    generation: int
    tenant_id: str
    message_identity_scope: str
    erasure_unit: str


@dataclass(frozen=True)
class Evidence:
    logical_key_id: str
    generation: int
    handle_binding: str
    mac: str


def canonical_handle(handle: LogicalKeyHandle) -> bytes:
    return json.dumps([
        handle.logical_key_id,
        handle.generation,
        handle.tenant_id,
        handle.message_identity_scope,
        handle.erasure_unit,
    ], separators=(",", ":"), ensure_ascii=True).encode()


def handle_binding(handle: LogicalKeyHandle) -> str:
    return hashlib.sha256(b"jlmirror-d3e-logical-key-v2\x00" + canonical_handle(handle)).hexdigest()


def key_name(handle: LogicalKeyHandle) -> str:
    return "eq-" + handle_binding(handle)[:40]


class CryptoContinuityWitness:
    """Governed erasure continuity outside stale provider/storage snapshots."""

    def __init__(self, path: Path = CRYPTO_WITNESS_PATH):
        self.path = path
        self.state: dict[str, str] = {}
        self.persist()

    def key(self, handle: LogicalKeyHandle) -> str:
        return handle_binding(handle)

    def persist(self) -> None:
        self.path.write_text(json.dumps(self.state, sort_keys=True))

    def reserve_erasure(self, handle: LogicalKeyHandle) -> None:
        self.state[self.key(handle)] = "erasure_pending"
        self.persist()

    def finalize_erased(self, handle: LogicalKeyHandle) -> None:
        if self.state.get(self.key(handle)) != "erasure_pending":
            raise RuntimeError("erasure was not fenced before terminalization")
        self.state[self.key(handle)] = "erased"
        self.persist()

    def state_for(self, handle: LogicalKeyHandle) -> str | None:
        return self.state.get(self.key(handle))


class CurrentKeyAuthorityPort(Protocol):
    def issue(self, *, handle: LogicalKeyHandle, content: bytes) -> Evidence: ...


class HistoricalVerifierPort(Protocol):
    def verify(self, *, handle: LogicalKeyHandle, content: bytes, evidence: Evidence) -> bool: ...


class OpenBaoTransitAdapter:
    def __init__(self, addr: str, token: str, refs: dict[LogicalKeyHandle, str]):
        self.client = BaoClient(addr, token)
        self.refs = dict(refs)

    def ref(self, handle: LogicalKeyHandle) -> str:
        try:
            return self.refs[handle]
        except KeyError as exc:
            raise RuntimeError("logical key handle is not provisioned for this adapter") from exc

    def issue_hmac(self, handle: LogicalKeyHandle, content: bytes) -> str:
        data = self.client.call(
            "POST", f"transit/hmac/{quote(self.ref(handle), safe='')}/sha2-256",
            {"input": b64(content)}, expect={200},
        )
        value = data.get("data", {}).get("hmac")
        if not isinstance(value, str) or not value:
            raise RuntimeError("malformed OpenBao HMAC response")
        return value

    def verify_hmac(self, handle: LogicalKeyHandle, content: bytes, mac: str) -> bool:
        data = self.client.call(
            "POST", f"transit/verify/{quote(self.ref(handle), safe='')}/sha2-256",
            {"input": b64(content), "hmac": mac}, expect={200},
        )
        valid = data.get("data", {}).get("valid")
        if type(valid) is not bool:
            raise RuntimeError("malformed OpenBao verify response")
        return valid


def init_db() -> None:
    psql_script("""
DROP SCHEMA IF EXISTS d3e_crypto_control CASCADE;
CREATE SCHEMA d3e_crypto_control;
CREATE TABLE d3e_crypto_control.generation(
    logical_key_id TEXT NOT NULL,
    generation BIGINT NOT NULL CHECK(generation > 0),
    tenant_id TEXT NOT NULL,
    message_identity_scope TEXT NOT NULL,
    erasure_unit TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN('current','historical','erasure_pending','erased')),
    PRIMARY KEY(logical_key_id,generation)
);
""")


def set_control(handle: LogicalKeyHandle, state: str) -> None:
    value = psql(
        "INSERT INTO d3e_crypto_control.generation("
        "logical_key_id,generation,tenant_id,message_identity_scope,erasure_unit,state) "
        f"VALUES({lit(handle.logical_key_id)},{handle.generation},{lit(handle.tenant_id)},"
        f"{lit(handle.message_identity_scope)},{lit(handle.erasure_unit)},{lit(state)}) "
        "ON CONFLICT(logical_key_id,generation) DO UPDATE SET state=EXCLUDED.state "
        "WHERE d3e_crypto_control.generation.tenant_id=EXCLUDED.tenant_id "
        "AND d3e_crypto_control.generation.message_identity_scope=EXCLUDED.message_identity_scope "
        "AND d3e_crypto_control.generation.erasure_unit=EXCLUDED.erasure_unit "
        "RETURNING state;"
    )
    if value != state:
        raise RuntimeError("logical key generation cannot be rebound to another authority tuple")


def pg_control_state(handle: LogicalKeyHandle) -> str:
    value = psql(
        "SELECT state FROM d3e_crypto_control.generation "
        f"WHERE logical_key_id={lit(handle.logical_key_id)} AND generation={handle.generation} "
        f"AND tenant_id={lit(handle.tenant_id)} "
        f"AND message_identity_scope={lit(handle.message_identity_scope)} "
        f"AND erasure_unit={lit(handle.erasure_unit)};"
    )
    if value not in {"current", "historical", "erasure_pending", "erased"}:
        raise RuntimeError("crypto currentness unavailable")
    return value


class KeyAuthorityPort:
    def __init__(self, adapter: OpenBaoTransitAdapter, witness: CryptoContinuityWitness):
        self.adapter = adapter
        self.witness = witness

    def state(self, handle: LogicalKeyHandle) -> str:
        continuity = self.witness.state_for(handle)
        if continuity in {"erasure_pending", "erased"}:
            return continuity
        return pg_control_state(handle)

    def issue(self, *, handle: LogicalKeyHandle, content: bytes) -> Evidence:
        if self.state(handle) != "current":
            raise RuntimeError("not current issue authority")
        return Evidence(
            handle.logical_key_id,
            handle.generation,
            handle_binding(handle),
            self.adapter.issue_hmac(handle, content),
        )

    def verify_historical(
        self, *, handle: LogicalKeyHandle, content: bytes, evidence: Evidence
    ) -> bool:
        if self.state(handle) != "historical":
            raise RuntimeError("not historical verifier authority")
        if (
            evidence.logical_key_id != handle.logical_key_id
            or evidence.generation != handle.generation
            or evidence.handle_binding != handle_binding(handle)
        ):
            return False
        return self.adapter.verify_hmac(handle, content, evidence.mac)


class HistoricalVerifier:
    def __init__(self, port: KeyAuthorityPort, handle: LogicalKeyHandle):
        self.port = port
        self.handle = handle

    def verify(self, *, content: bytes, evidence: Evidence) -> bool:
        return self.port.verify_historical(handle=self.handle, content=content, evidence=evidence)

    def generate(self, *, content: bytes) -> Evidence:
        del content
        raise RuntimeError("historical verifier is verify-only")


def create_key(root: BaoClient, ref: str) -> None:
    root.call("POST", f"transit/keys/{ref}", {
        "type": "hmac",
        "key_size": 32,
        "exportable": False,
        "allow_plaintext_backup": False,
    }, expect={204})
    root.call("POST", f"transit/keys/{ref}/config", {"deletion_allowed": True}, expect={204})
    meta = root.call("GET", f"transit/keys/{ref}", expect={200})["data"]
    assert meta["type"] == "hmac"
    assert meta["exportable"] is False
    assert meta["allow_plaintext_backup"] is False


def token_for(root: BaoClient, label: str, rule: str) -> str:
    policy = f"d3e-{label}"
    root.call("PUT", f"sys/policies/acl/{policy}", {"policy": rule}, expect={204})
    data = root.call(
        "POST", "auth/token/create",
        {"policies": [policy], "ttl": "60m", "renewable": False},
        expect={200},
    )
    return data["auth"]["client_token"]


def issue_token(root: BaoClient, label: str, ref: str) -> str:
    return token_for(
        root, label,
        f'path "transit/hmac/{ref}/sha2-256" {{ capabilities=["update"] }}\n',
    )


def verify_token(root: BaoClient, label: str, ref: str) -> str:
    return token_for(
        root, label,
        f'path "transit/verify/{ref}/sha2-256" {{ capabilities=["update"] }}\n',
    )


def denied(fn) -> int:
    try:
        fn()
    except BaoError as exc:
        if exc.status not in {400, 403, 404}:
            raise
        return exc.status
    except RuntimeError:
        return 0
    raise AssertionError("provider/key-authority operation unexpectedly succeeded")


def handles() -> dict[str, LogicalKeyHandle]:
    return {
        "g1": LogicalKeyHandle("tenant-a.scope-a.record-1", 1, "tenant-a", "scope-a", "record-1"),
        "g2": LogicalKeyHandle("tenant-a.scope-a.record-1", 2, "tenant-a", "scope-a", "record-1"),
        "tenant": LogicalKeyHandle("tenant-b.scope-a.record-1", 1, "tenant-b", "scope-a", "record-1"),
        "scope": LogicalKeyHandle("tenant-a.scope-b.record-1", 1, "tenant-a", "scope-b", "record-1"),
        "erasure": LogicalKeyHandle("tenant-a.scope-a.record-2", 1, "tenant-a", "scope-a", "record-2"),
    }


def revoke_token(addr: str, token: str) -> None:
    BaoClient(addr, token).call("POST", "auth/token/revoke-self", {}, expect={204})


def prove_retirement_linearization(
    *, addr: str, handle: LogicalKeyHandle, token: str,
    refs: dict[LogicalKeyHandle, str], content: bytes,
) -> str:
    adapter = OpenBaoTransitAdapter(addr, token, refs)

    def issue_race() -> str:
        try:
            adapter.issue_hmac(handle, content)
            return "ISSUED_BEFORE_REVOKE"
        except BaoError as exc:
            if exc.status not in {400, 403}:
                raise
            return "DENIED_BY_REVOKE"

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        issue_future = pool.submit(issue_race)
        revoke_future = pool.submit(revoke_token, addr, token)
        issue_outcome = issue_future.result()
        revoke_future.result()

    denied(lambda: adapter.issue_hmac(handle, content))
    return issue_outcome


def raw_verify(addr: str, token: str, ref: str, content: bytes, mac: str) -> bool:
    data = BaoClient(addr, token).call(
        "POST", f"transit/verify/{ref}/sha2-256",
        {"input": b64(content), "hmac": mac}, expect={200},
    )
    return data.get("data", {}).get("valid") is True


def setup_persistent_source() -> tuple[str, str]:
    write_config()
    for name in (SOURCE_CONTAINER, TARGET_CONTAINER):
        remove_container(name)
    for volume in (SOURCE_VOLUME, TARGET_VOLUME, STALE_VOLUME):
        remove_volume(volume)
    create_volume(SOURCE_VOLUME)
    start_bao(SOURCE_CONTAINER, SOURCE_VOLUME, 18200)
    unseal_key, root_token = initialize_source()
    BaoClient(SOURCE_ADDR, root_token).call("POST", "sys/mounts/transit", {"type": "transit"}, expect={204})
    return unseal_key, root_token


def main() -> None:
    if CRYPTO_WITNESS_PATH.exists():
        CRYPTO_WITNESS_PATH.unlink()
    witness = CryptoContinuityWitness()
    init_db()

    unseal_key, root_token = setup_persistent_source()
    root = BaoClient(SOURCE_ADDR, root_token)
    hs = handles()
    refs = {h: key_name(h) for h in hs.values()}
    for ref in sorted(set(refs.values())):
        create_key(root, ref)

    tokens = {name: issue_token(root, "issue-" + name, refs[h]) for name, h in hs.items()}
    historical_token = verify_token(root, "historical-g1", refs[hs["g1"]])

    same = b"same-low-entropy-immutable-message"
    tags = []
    for name in ("g1", "tenant", "scope", "erasure"):
        handle = hs[name]
        set_control(handle, "current")
        port = KeyAuthorityPort(OpenBaoTransitAdapter(SOURCE_ADDR, tokens[name], refs), witness)
        tags.append(port.issue(handle=handle, content=same).mac)
    assert len(set(tags)) == 4

    forged = LogicalKeyHandle(
        hs["g1"].logical_key_id, hs["g1"].generation, "tenant-forged",
        hs["g1"].message_identity_scope, hs["g1"].erasure_unit,
    )
    denied(lambda: KeyAuthorityPort(
        OpenBaoTransitAdapter(SOURCE_ADDR, tokens["g1"], refs), witness
    ).issue(handle=forged, content=same))
    assert all("provider" not in f.name and "openbao" not in f.name for f in fields(LogicalKeyHandle))
    denied(lambda: root.call("GET", f"transit/export/hmac-key/{refs[hs['g1']]}/1", expect={200}))

    print(
        "d3_e_openbao_provider_neutral_custody=PASS "
        "persistent_storage=true non_exportable=true plaintext_backup_disabled=true "
        "provider_detail_hidden=true logical_handle_tuple_bound=true"
    )
    print(
        "d3_e_actual_domain_separation=PASS tenant=true scope=true erasure_unit=true "
        "shared_key_domain_input_only=false distinct_provider_key_material=true forged_tuple_rejected=true"
    )

    immutable = b'{"message_id":"m-1","immutable":"value"}'
    g1_port = KeyAuthorityPort(OpenBaoTransitAdapter(SOURCE_ADDR, tokens["g1"], refs), witness)
    old = g1_port.issue(handle=hs["g1"], content=immutable)

    set_control(hs["g2"], "current")
    g2_port = KeyAuthorityPort(OpenBaoTransitAdapter(SOURCE_ADDR, tokens["g2"], refs), witness)
    new = g2_port.issue(handle=hs["g2"], content=immutable)
    assert new.mac != old.mac

    race_outcome = prove_retirement_linearization(
        addr=SOURCE_ADDR, handle=hs["g1"], token=tokens["g1"], refs=refs, content=immutable,
    )
    set_control(hs["g1"], "historical")

    remove_container(SOURCE_CONTAINER)
    copy_volume(SOURCE_VOLUME, TARGET_VOLUME)
    start_bao(TARGET_CONTAINER, TARGET_VOLUME, 18201)
    unseal_server(TARGET_ADDR, unseal_key)

    relocated_port = KeyAuthorityPort(
        OpenBaoTransitAdapter(TARGET_ADDR, historical_token, refs), witness
    )
    verifier = HistoricalVerifier(relocated_port, hs["g1"])
    assert verifier.verify(content=immutable, evidence=old)
    denied(lambda: verifier.generate(content=immutable))
    denied(lambda: OpenBaoTransitAdapter(TARGET_ADDR, historical_token, refs).issue_hmac(hs["g1"], immutable))
    denied(lambda: BaoClient(TARGET_ADDR, historical_token).call(
        "POST", f"transit/verify/{refs[hs['g2']]}/sha2-256",
        {"input": b64(immutable), "hmac": new.mac}, expect={200},
    ))

    print(
        "d3_e_historical_verifier_relocation_recovery_continuity=PASS "
        "source_authority_stopped=true encrypted_storage_relocated_offline=true "
        "target_distinct_instance=true historical_verify_survives_recovery=true "
        "historical_verify_only=true current_generation_isolated=true exact_logical_generation_bound=true"
    )
    print(
        "d3_e_key_generation_rotation_retirement=PASS "
        "separate_provider_ref_per_logical_generation=true new_generation_current_before_retirement=true "
        "provider_credential_revocation_linearization=true "
        f"concurrent_issue_outcome={race_outcome.lower()} post_retirement_issue_denied=true "
        "old_generation_historical_only=true provider_native_rotation_drift_not_authority=true"
    )

    remove_container(TARGET_CONTAINER)
    copy_volume(TARGET_VOLUME, STALE_VOLUME)
    start_bao(TARGET_CONTAINER, TARGET_VOLUME, 18201)
    unseal_server(TARGET_ADDR, unseal_key)

    witness.reserve_erasure(hs["g1"])
    set_control(hs["g1"], "erasure_pending")
    denied(lambda: KeyAuthorityPort(
        OpenBaoTransitAdapter(TARGET_ADDR, historical_token, refs), witness
    ).verify_historical(handle=hs["g1"], content=immutable, evidence=old))
    assert raw_verify(TARGET_ADDR, root_token, refs[hs["g1"]], immutable, old.mac)

    BaoClient(TARGET_ADDR, root_token).call("DELETE", f"transit/keys/{refs[hs['g1']]}", expect={204})
    denied(lambda: raw_verify(TARGET_ADDR, root_token, refs[hs["g1"]], immutable, old.mac))
    witness.finalize_erased(hs["g1"])
    set_control(hs["g1"], "erased")

    remove_container(TARGET_CONTAINER)
    copy_volume(STALE_VOLUME, TARGET_VOLUME)
    start_bao(TARGET_CONTAINER, TARGET_VOLUME, 18201)
    unseal_server(TARGET_ADDR, unseal_key)
    assert raw_verify(TARGET_ADDR, root_token, refs[hs["g1"]], immutable, old.mac)

    set_control(hs["g1"], "historical")
    stale_port = KeyAuthorityPort(
        OpenBaoTransitAdapter(TARGET_ADDR, historical_token, refs), witness
    )
    denied(lambda: stale_port.verify_historical(handle=hs["g1"], content=immutable, evidence=old))
    denied(lambda: stale_port.issue(handle=hs["g1"], content=immutable))

    BaoClient(TARGET_ADDR, root_token).call("DELETE", f"transit/keys/{refs[hs['g1']]}", expect={204})
    set_control(hs["g1"], "erased")
    denied(lambda: raw_verify(TARGET_ADDR, root_token, refs[hs["g1"]], immutable, old.mac))

    target_g2 = KeyAuthorityPort(OpenBaoTransitAdapter(TARGET_ADDR, tokens["g2"], refs), witness)
    target_g2.issue(handle=hs["g2"], content=b"current-still-works")

    print(
        "d3_e_retired_erased_key_nonresurrection=PASS "
        "erasure_fence_before_provider_delete=true provider_key_destroyed_before_erased_terminal=true "
        "stale_encrypted_provider_storage_restored=true raw_provider_negative_control_revived=true "
        "stale_currentness_restored=true governed_erasure_witness_wins=true "
        "recovery_redeletes_resurrected_key=true unrelated_current_generation_works=true"
    )
    print(
        "d3_e_crypto_authority_conformance=PASS openbao_transit=true "
        "provider_neutral_handle=true persistent_relocation=true historical_continuity=true "
        "rotation_retirement=true erasure_nonresurrection=true "
        "c3_numerics_not_selected=true production_topology_not_selected=true"
    )


if __name__ == "__main__":
    try:
        main()
    finally:
        remove_container(SOURCE_CONTAINER)
        remove_container(TARGET_CONTAINER)
        for volume in (SOURCE_VOLUME, TARGET_VOLUME, STALE_VOLUME):
            remove_volume(volume)
