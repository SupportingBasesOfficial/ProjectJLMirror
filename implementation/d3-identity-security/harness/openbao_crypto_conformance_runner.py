#!/usr/bin/env python3
from __future__ import annotations

import base64
import concurrent.futures
from dataclasses import dataclass, fields
import hashlib
import json
import os
import subprocess
import time
from typing import Protocol
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import quote

PG_CONTAINER = os.environ.get("PG_CONTAINER", "jlmirror-d3e-postgres")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "d3-postgres-password")
OPENBAO_ADDR = os.environ.get("OPENBAO_ADDR", "http://127.0.0.1:18200").rstrip("/")
OPENBAO_ROOT_TOKEN = os.environ.get("OPENBAO_ROOT_TOKEN", "d3-root-token")


def sh(args: list[str], *, input_text: str | None = None, timeout: float = 30, check: bool = True):
    r = subprocess.run(args, input=input_text, text=True, capture_output=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(f"command failed rc={r.returncode}: {r.stderr.strip()[:600]}")
    return r


def lit(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def psql(sql: str, *, db: str = "d3") -> str:
    return sh([
        "docker", "exec", "-e", f"PGPASSWORD={PG_PASSWORD}", PG_CONTAINER,
        "psql", "-X", "-U", "postgres", "-d", db, "-v", "ON_ERROR_STOP=1", "-Atq", "-c", sql
    ]).stdout.strip()


def psql_script(script: str, *, db: str = "d3") -> None:
    sh([
        "docker", "exec", "-i", "-e", f"PGPASSWORD={PG_PASSWORD}", PG_CONTAINER,
        "psql", "-X", "-U", "postgres", "-d", db, "-v", "ON_ERROR_STOP=1", "-q"
    ], input_text=script)


def dump_app_schema() -> str:
    r = sh([
        "docker", "exec", "-e", f"PGPASSWORD={PG_PASSWORD}", PG_CONTAINER,
        "pg_dump", "-U", "postgres", "-d", "d3", "--schema", "d3e_crypto",
        "--no-owner", "--no-privileges"
    ])
    if "CREATE SCHEMA d3e_crypto" not in r.stdout:
        raise AssertionError("real PostgreSQL crypto app-schema dump was not captured")
    if "d3e_crypto_control" in r.stdout:
        raise AssertionError("fresh crypto currentness authority leaked into stale app snapshot")
    return r.stdout


class BaoError(RuntimeError):
    def __init__(self, status: int):
        super().__init__(f"OpenBao HTTP {status}")
        self.status = status


class Bao:
    def __init__(self, token: str):
        self.token = token

    def call(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        *,
        expect: set[int] = {200, 204},
    ) -> dict:
        req = urlrequest.Request(
            f"{OPENBAO_ADDR}/v1/{path.lstrip('/')}",
            data=None if body is None else json.dumps(body, separators=(",", ":")).encode(),
            method=method,
            headers={"X-Vault-Token": self.token, "Content-Type": "application/json"},
        )
        try:
            with urlrequest.urlopen(req, timeout=5) as resp:
                status, raw = resp.status, resp.read()
        except urlerror.HTTPError as exc:
            status, raw = exc.code, exc.read()
            if status not in expect:
                raise BaoError(status) from exc
        except Exception as exc:
            raise RuntimeError("OpenBao authority unavailable") from exc
        if status not in expect:
            raise BaoError(status)
        if not raw:
            return {}
        return json.loads(raw)


ROOT = Bao(OPENBAO_ROOT_TOKEN)


def wait_bao() -> None:
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            with urlrequest.urlopen(f"{OPENBAO_ADDR}/v1/sys/health", timeout=2) as r:
                if r.status == 200:
                    return
        except Exception:
            time.sleep(0.25)
    raise RuntimeError("OpenBao did not become ready")


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


class CurrentKeyAuthorityPort(Protocol):
    def issue(self, *, handle: LogicalKeyHandle, content: bytes) -> Evidence: ...


class HistoricalVerifierPort(Protocol):
    def verify(self, *, handle: LogicalKeyHandle, content: bytes, evidence: Evidence) -> bool: ...


def canonical_handle(handle: LogicalKeyHandle) -> bytes:
    return json.dumps(
        [
            handle.logical_key_id,
            handle.generation,
            handle.tenant_id,
            handle.message_identity_scope,
            handle.erasure_unit,
        ],
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()


def handle_binding(handle: LogicalKeyHandle) -> str:
    return hashlib.sha256(b"jlmirror-d3e-logical-key-v1\x00" + canonical_handle(handle)).hexdigest()


def key_name(handle: LogicalKeyHandle) -> str:
    return "eq-" + handle_binding(handle)[:32]


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


class OpenBaoTransitAdapter:
    """Provider-specific implementation hidden behind complete logical handles."""

    def __init__(self, token: str, refs: dict[LogicalKeyHandle, str]):
        self._bao = Bao(token)
        self._refs = dict(refs)

    def _ref(self, handle: LogicalKeyHandle) -> str:
        try:
            return self._refs[handle]
        except KeyError as exc:
            raise RuntimeError("logical key handle is not provisioned for this adapter") from exc

    def issue_hmac(self, handle: LogicalKeyHandle, content: bytes) -> str:
        data = self._bao.call(
            "POST",
            f"transit/hmac/{quote(self._ref(handle), safe='')}/sha2-256",
            {"input": b64(content)},
            expect={200},
        )
        mac = data.get("data", {}).get("hmac")
        if not isinstance(mac, str) or not mac:
            raise RuntimeError("malformed HMAC evidence")
        return mac

    def verify_hmac(self, handle: LogicalKeyHandle, content: bytes, mac: str) -> bool:
        data = self._bao.call(
            "POST",
            f"transit/verify/{quote(self._ref(handle), safe='')}/sha2-256",
            {"input": b64(content), "hmac": mac},
            expect={200},
        )
        valid = data.get("data", {}).get("valid")
        if type(valid) is not bool:
            raise RuntimeError("malformed verify response")
        return valid


def control_state(handle: LogicalKeyHandle) -> str:
    value = psql(
        "SELECT state FROM d3e_crypto_control.generation "
        f"WHERE logical_key_id={lit(handle.logical_key_id)} "
        f"AND generation={handle.generation} "
        f"AND tenant_id={lit(handle.tenant_id)} "
        f"AND message_identity_scope={lit(handle.message_identity_scope)} "
        f"AND erasure_unit={lit(handle.erasure_unit)};"
    )
    if value not in {"current", "historical", "erased"}:
        raise RuntimeError("crypto currentness or exact logical-handle binding unavailable")
    return value


class CurrentAuthority:
    def __init__(self, adapter: OpenBaoTransitAdapter):
        self.adapter = adapter

    def issue(self, *, handle: LogicalKeyHandle, content: bytes) -> Evidence:
        if control_state(handle) != "current":
            raise RuntimeError("not current issue authority")
        return Evidence(
            handle.logical_key_id,
            handle.generation,
            handle_binding(handle),
            self.adapter.issue_hmac(handle, content),
        )


class HistoricalVerifier:
    def __init__(self, adapter: OpenBaoTransitAdapter):
        self.adapter = adapter

    def verify(self, *, handle: LogicalKeyHandle, content: bytes, evidence: Evidence) -> bool:
        if control_state(handle) != "historical":
            raise RuntimeError("not historical verifier authority")
        if (
            evidence.logical_key_id != handle.logical_key_id
            or evidence.generation != handle.generation
            or evidence.handle_binding != handle_binding(handle)
        ):
            return False
        return self.adapter.verify_hmac(handle, content, evidence.mac)


def set_control(handle: LogicalKeyHandle, state: str) -> None:
    value = psql(
        "INSERT INTO d3e_crypto_control.generation("
        "logical_key_id,generation,tenant_id,message_identity_scope,erasure_unit,state"
        f") VALUES({lit(handle.logical_key_id)},{handle.generation},{lit(handle.tenant_id)},"
        f"{lit(handle.message_identity_scope)},{lit(handle.erasure_unit)},{lit(state)}) "
        "ON CONFLICT(logical_key_id,generation) DO UPDATE SET state=EXCLUDED.state "
        "WHERE d3e_crypto_control.generation.tenant_id=EXCLUDED.tenant_id "
        "AND d3e_crypto_control.generation.message_identity_scope=EXCLUDED.message_identity_scope "
        "AND d3e_crypto_control.generation.erasure_unit=EXCLUDED.erasure_unit "
        "RETURNING state;"
    )
    if value != state:
        raise RuntimeError("logical key generation cannot be rebound to another authority tuple")


def set_catalog(handle: LogicalKeyHandle, state: str) -> None:
    value = psql(
        "INSERT INTO d3e_crypto.catalog("
        "logical_key_id,generation,tenant_id,message_identity_scope,erasure_unit,state"
        f") VALUES({lit(handle.logical_key_id)},{handle.generation},{lit(handle.tenant_id)},"
        f"{lit(handle.message_identity_scope)},{lit(handle.erasure_unit)},{lit(state)}) "
        "ON CONFLICT(logical_key_id,generation) DO UPDATE SET state=EXCLUDED.state "
        "WHERE d3e_crypto.catalog.tenant_id=EXCLUDED.tenant_id "
        "AND d3e_crypto.catalog.message_identity_scope=EXCLUDED.message_identity_scope "
        "AND d3e_crypto.catalog.erasure_unit=EXCLUDED.erasure_unit "
        "RETURNING state;"
    )
    if value != state:
        raise RuntimeError("application crypto catalog cannot rebind logical key tuple")


def init_db() -> None:
    psql_script("""
DROP SCHEMA IF EXISTS d3e_crypto CASCADE;
DROP SCHEMA IF EXISTS d3e_crypto_control CASCADE;

CREATE SCHEMA d3e_crypto_control;
CREATE TABLE d3e_crypto_control.generation(
    logical_key_id TEXT NOT NULL,
    generation BIGINT NOT NULL CHECK(generation > 0),
    tenant_id TEXT NOT NULL,
    message_identity_scope TEXT NOT NULL,
    erasure_unit TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN('current','historical','erased')),
    PRIMARY KEY(logical_key_id,generation)
);

CREATE SCHEMA d3e_crypto;
CREATE TABLE d3e_crypto.catalog(
    logical_key_id TEXT NOT NULL,
    generation BIGINT NOT NULL CHECK(generation > 0),
    tenant_id TEXT NOT NULL,
    message_identity_scope TEXT NOT NULL,
    erasure_unit TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN('current','historical','erased')),
    PRIMARY KEY(logical_key_id,generation)
);
""")


def create_key(ref: str) -> None:
    ROOT.call(
        "POST",
        f"transit/keys/{ref}",
        {
            "type": "hmac",
            "key_size": 32,
            "exportable": False,
            "allow_plaintext_backup": False,
        },
        expect={204},
    )
    ROOT.call(
        "POST",
        f"transit/keys/{ref}/config",
        {"deletion_allowed": True},
        expect={204},
    )
    meta = ROOT.call("GET", f"transit/keys/{ref}", expect={200})["data"]
    assert meta["type"] == "hmac"
    assert meta["exportable"] is False
    assert meta["allow_plaintext_backup"] is False


def token_for(label: str, rule: str) -> str:
    policy = f"d3e-{label}"
    ROOT.call("PUT", f"sys/policies/acl/{policy}", {"policy": rule}, expect={204})
    data = ROOT.call(
        "POST",
        "auth/token/create",
        {"policies": [policy], "ttl": "30m", "renewable": False},
        expect={200},
    )
    return data["auth"]["client_token"]


def issue_token(label: str, ref: str) -> str:
    return token_for(
        label,
        f'path "transit/hmac/{ref}/sha2-256" {{ capabilities=["update"] }}\n',
    )


def verify_token(label: str, ref: str) -> str:
    return token_for(
        label,
        f'path "transit/verify/{ref}/sha2-256" {{ capabilities=["update"] }}\n',
    )


def denied(fn) -> int:
    try:
        fn()
    except BaoError as exc:
        if exc.status not in {400, 403, 404}:
            raise
        return exc.status
    raise AssertionError("provider operation unexpectedly succeeded")


def handles() -> dict[str, LogicalKeyHandle]:
    return {
        "g1": LogicalKeyHandle(
            "tenant-a.scope-a.record-1", 1, "tenant-a", "scope-a", "record-1"
        ),
        "g2": LogicalKeyHandle(
            "tenant-a.scope-a.record-1", 2, "tenant-a", "scope-a", "record-1"
        ),
        "tenant": LogicalKeyHandle(
            "tenant-b.scope-a.record-1", 1, "tenant-b", "scope-a", "record-1"
        ),
        "scope": LogicalKeyHandle(
            "tenant-a.scope-b.record-1", 1, "tenant-a", "scope-b", "record-1"
        ),
        "erasure": LogicalKeyHandle(
            "tenant-a.scope-a.record-2", 1, "tenant-a", "scope-a", "record-2"
        ),
    }


def prove_retirement_linearization(
    *,
    handle: LogicalKeyHandle,
    token: str,
    refs: dict[LogicalKeyHandle, str],
    content: bytes,
) -> str:
    adapter = OpenBaoTransitAdapter(token, refs)

    def issue_race() -> str:
        try:
            adapter.issue_hmac(handle, content)
            return "ISSUED_BEFORE_REVOKE"
        except BaoError as exc:
            if exc.status not in {400, 403}:
                raise
            return "DENIED_BY_REVOKE"

    def revoke() -> str:
        Bao(token).call("POST", "auth/token/revoke-self", {}, expect={204})
        return "REVOKED"

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        issue_future = pool.submit(issue_race)
        revoke_future = pool.submit(revoke)
        issue_outcome = issue_future.result()
        assert revoke_future.result() == "REVOKED"

    denied(lambda: adapter.issue_hmac(handle, content))
    return issue_outcome


def restore_stale_catalog(stale_dump: str) -> None:
    psql("DROP SCHEMA d3e_crypto CASCADE;")
    psql_script(stale_dump)


def main() -> None:
    wait_bao()
    ROOT.call("POST", "sys/mounts/transit", {"type": "transit"}, expect={204})
    init_db()

    hs = handles()
    refs = {h: key_name(h) for h in hs.values()}
    for ref in set(refs.values()):
        create_key(ref)

    tokens = {
        name: issue_token("issue-" + name, refs[h])
        for name, h in hs.items()
    }
    historical_token = verify_token("verify-g1", refs[hs["g1"]])

    same = b"same-low-entropy-immutable-message"
    tags = []
    for name in ("g1", "tenant", "scope", "erasure"):
        handle = hs[name]
        set_control(handle, "current")
        set_catalog(handle, "current")
        tags.append(
            CurrentAuthority(
                OpenBaoTransitAdapter(tokens[name], refs)
            ).issue(handle=handle, content=same).mac
        )
    assert len(set(tags)) == 4

    forged = LogicalKeyHandle(
        hs["g1"].logical_key_id,
        hs["g1"].generation,
        "tenant-forged",
        hs["g1"].message_identity_scope,
        hs["g1"].erasure_unit,
    )
    try:
        CurrentAuthority(OpenBaoTransitAdapter(tokens["g1"], refs)).issue(
            handle=forged, content=same
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("same logical id/generation was rebound to another tenant tuple")

    ref1 = refs[hs["g1"]]
    meta = ROOT.call("GET", f"transit/keys/{ref1}", expect={200})["data"]
    assert meta["exportable"] is False
    assert meta["allow_plaintext_backup"] is False
    denied(lambda: ROOT.call("GET", f"transit/export/hmac-key/{ref1}/1", expect={200}))
    denied(
        lambda: Bao(tokens["g1"]).call(
            "GET", f"transit/export/hmac-key/{ref1}/1", expect={200}
        )
    )
    assert all(
        "provider" not in f.name and "openbao" not in f.name
        for f in fields(LogicalKeyHandle)
    )

    print(
        "d3_e_openbao_provider_neutral_custody=PASS "
        "non_exportable=true plaintext_backup_disabled=true app_export_denied=true "
        "provider_detail_hidden=true logical_handle_tuple_bound=true"
    )
    print(
        "d3_e_actual_domain_separation=PASS tenant=true scope=true erasure_unit=true "
        "shared_key_domain_input_only=false distinct_provider_key_material=true "
        "forged_tuple_rejected=true"
    )

    immutable = b'{"message_id":"m-1","immutable":"value"}'
    source = CurrentAuthority(OpenBaoTransitAdapter(tokens["g1"], refs))
    old = source.issue(handle=hs["g1"], content=immutable)
    stale_dump = dump_app_schema()

    # Provision the new current generation before retiring the old issuer.
    set_control(hs["g2"], "current")
    set_catalog(hs["g2"], "current")
    new = CurrentAuthority(
        OpenBaoTransitAdapter(tokens["g2"], refs)
    ).issue(handle=hs["g2"], content=immutable)
    assert new.mac != old.mac

    # The provider credential revocation is the retirement linearization point.
    # Control changes to historical only after revocation completes.
    race_outcome = prove_retirement_linearization(
        handle=hs["g1"],
        token=tokens["g1"],
        refs=refs,
        content=immutable,
    )
    set_control(hs["g1"], "historical")
    set_catalog(hs["g1"], "historical")

    verifier = HistoricalVerifier(
        OpenBaoTransitAdapter(historical_token, refs)
    )
    assert verifier.verify(handle=hs["g1"], content=immutable, evidence=old)
    denied(
        lambda: OpenBaoTransitAdapter(historical_token, refs).issue_hmac(
            hs["g1"], immutable
        )
    )
    denied(
        lambda: Bao(historical_token).call(
            "POST",
            f"transit/verify/{refs[hs['g2']]}/sha2-256",
            {"input": b64(immutable), "hmac": new.mac},
            expect={200},
        )
    )
    denied(
        lambda: OpenBaoTransitAdapter(tokens["g1"], refs).issue_hmac(
            hs["g1"], immutable
        )
    )

    print(
        "d3_e_historical_verifier_relocation_recovery_continuity=PASS "
        "target_historical_verify=true historical_verify_only=true "
        "current_generation_isolated=true source_credential_revoked=true "
        "historical_handle_exact_tuple_bound=true"
    )
    print(
        "d3_e_key_generation_rotation_retirement=PASS "
        "new_generation_current_before_retirement=true "
        "provider_revocation_is_retirement_linearization=true "
        f"concurrent_issue_outcome={race_outcome.lower()} "
        "post_retirement_issue_denied=true old_generation_historical_only=true"
    )

    # Provider destruction completes before the external control plane marks the
    # generation erased, preventing an in-flight verification from crossing a
    # declared erasure boundary.
    ROOT.call("DELETE", f"transit/keys/{ref1}", expect={204})
    try:
        OpenBaoTransitAdapter(historical_token, refs).verify_hmac(
            hs["g1"], immutable, old.mac
        )
    except BaoError as exc:
        if exc.status not in {400, 403, 404}:
            raise
    else:
        raise AssertionError("destroyed provider key still verified historical evidence")

    set_control(hs["g1"], "erased")
    set_catalog(hs["g1"], "erased")
    CurrentAuthority(
        OpenBaoTransitAdapter(tokens["g2"], refs)
    ).issue(handle=hs["g2"], content=b"current-still-works")

    restore_stale_catalog(stale_dump)
    restored = psql(
        "SELECT state FROM d3e_crypto.catalog "
        "WHERE logical_key_id='tenant-a.scope-a.record-1' AND generation=1;"
    )
    assert restored == "current"

    try:
        verifier.verify(handle=hs["g1"], content=immutable, evidence=old)
    except RuntimeError:
        pass
    else:
        raise AssertionError("stale restored catalog resurrected erased verifier")

    denied(
        lambda: OpenBaoTransitAdapter(historical_token, refs).verify_hmac(
            hs["g1"], immutable, old.mac
        )
    )

    print(
        "d3_e_retired_erased_key_nonresurrection=PASS "
        "actual_pg_restore_stale_catalog=true fresh_control_excluded_from_snapshot=true "
        "provider_key_destroyed_before_erasure_commit=true external_erasure_tombstone_wins=true "
        "stale_catalog_current_not_authority=true unrelated_current_generation_works=true"
    )
    print(
        "d3_e_crypto_authority_conformance=PASS openbao_transit=true "
        "provider_neutral_handle=true exact_authority_tuple_binding=true "
        "historical_continuity=true rotation_retirement=true "
        "erasure_nonresurrection=true c3_numerics_not_selected=true "
        "topology_not_selected=true"
    )


if __name__ == "__main__":
    main()
