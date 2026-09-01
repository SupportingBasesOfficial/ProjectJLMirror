from __future__ import annotations

from dataclasses import dataclass
import base64
import concurrent.futures
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
from typing import Protocol
import urllib.error
import urllib.request


OPENBAO_IMAGE = os.environ.get(
    "OPENBAO_IMAGE",
    "openbao/openbao@sha256:49e2d3586463aeef5447db400e7842ae7f76ceb0f8bc7d9a81ce3509a923decc",
)
CONTAINER_NAME = os.environ.get("OPENBAO_CONTAINER", "jlmirror-d3e-openbao")
PORT = int(os.environ.get("OPENBAO_PORT", "18200"))
POSTGRES_IMAGE = os.environ.get(
    "POSTGRES_IMAGE",
    "postgres@sha256:4ef4dbc939d61acea57712655ddb4b4ab27419c913f94cca0cd57cb3ea3c2280",
)
PG_CONTAINER_NAME = os.environ.get("D3E_POSTGRES_CONTAINER", "jlmirror-d3e-postgres")
PG_DATABASE = "d3e"
PG_PASSWORD = "d3e-postgres-password"


class ConformanceError(RuntimeError):
    pass


class LifecycleRejected(ConformanceError):
    pass


class ReplayUnavailable(ConformanceError):
    pass


class ReplayContinuityMismatch(ConformanceError):
    pass


def _canon(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{label} must be a non-empty canonical string")
    raw = value.encode("utf-8")
    if len(raw) > 512 or any(b < 0x20 or b == 0x7F for b in raw):
        raise ValueError(f"{label} outside bounded canonical envelope")
    return value


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    if not isinstance(value, str):
        raise ValueError("base64url value must be a string")
    padding = "=" * ((4 - len(value) % 4) % 4)
    raw = base64.urlsafe_b64decode((value + padding).encode("ascii"))
    if _b64url(raw) != value:
        raise ValueError("non-canonical base64url")
    return raw


def _stable_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@dataclass(frozen=True)
class KeyDomain:
    tenant_id: str
    scope: str
    erasure_unit: str

    def canonical_bytes(self) -> bytes:
        parts = (
            _canon(self.tenant_id, "tenant_id").encode(),
            _canon(self.scope, "scope").encode(),
            _canon(self.erasure_unit, "erasure_unit").encode(),
        )
        out = bytearray(b"jlmirror-key-domain-v1")
        for part in parts:
            out.extend(len(part).to_bytes(4, "big"))
            out.extend(part)
        return bytes(out)

    @property
    def domain_id(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    @property
    def provider_ref(self) -> str:
        return f"jlm-eq-{self.domain_id}"


def client_binding_id(client_principal: str) -> str:
    client = _canon(client_principal, "client_principal")
    return "client:" + hashlib.sha256(client.encode()).hexdigest()


def signing_logical_id_for_client(client_principal: str) -> str:
    return "signing:" + client_binding_id(client_principal)


@dataclass(frozen=True)
class LifecycleState:
    logical_id: str
    binding_id: str
    provider_ref: str
    current_generation: int
    previous_generation: int | None
    previous_mode: str
    state: str
    lifecycle_epoch: int


class SourceAuthority:
    """Durable JLMirror source lifecycle authority, deliberately outside provider storage."""

    def __init__(self, path: Path):
        self.path = path
        with self._connect() as db:
            db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS key_lifecycle (
                    logical_id TEXT PRIMARY KEY,
                    binding_id TEXT NOT NULL UNIQUE,
                    provider_ref TEXT NOT NULL UNIQUE,
                    current_generation INTEGER NOT NULL CHECK(current_generation > 0),
                    previous_generation INTEGER,
                    previous_mode TEXT NOT NULL CHECK(previous_mode IN ('none','verify_only','retired')),
                    state TEXT NOT NULL CHECK(state IN ('active','revoked')),
                    lifecycle_epoch INTEGER NOT NULL CHECK(lifecycle_epoch > 0)
                );
                CREATE TABLE IF NOT EXISTS replay_policy (
                    client_principal TEXT PRIMARY KEY,
                    current_epoch INTEGER NOT NULL CHECK(current_epoch > 0),
                    minimum_credential_generation INTEGER NOT NULL CHECK(minimum_credential_generation > 0)
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        db.execute("PRAGMA busy_timeout=30000")
        return db

    def register_key(self, *, logical_id: str, binding_id: str, provider_ref: str, generation: int = 1) -> None:
        logical_id = _canon(logical_id, "logical_id")
        binding_id = _canon(binding_id, "binding_id")
        provider_ref = _canon(provider_ref, "provider_ref")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO key_lifecycle(logical_id,binding_id,provider_ref,current_generation,previous_generation,previous_mode,state,lifecycle_epoch) VALUES(?,?,?,?,?,?,?,?)",
                (logical_id, binding_id, provider_ref, generation, None, "none", "active", 1),
            )
            db.execute("COMMIT")

    def read_key(self, logical_id: str) -> LifecycleState:
        logical_id = _canon(logical_id, "logical_id")
        with self._connect() as db:
            row = db.execute(
                "SELECT logical_id,binding_id,provider_ref,current_generation,previous_generation,previous_mode,state,lifecycle_epoch FROM key_lifecycle WHERE logical_id=?",
                (logical_id,),
            ).fetchone()
        if row is None:
            raise LifecycleRejected("unknown logical key")
        return LifecycleState(*row)

    def promote_rotation(self, *, logical_id: str, expected_generation: int, new_generation: int) -> None:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT current_generation,state,lifecycle_epoch FROM key_lifecycle WHERE logical_id=?",
                (logical_id,),
            ).fetchone()
            if row is None or row[1] != "active" or row[0] != expected_generation:
                db.execute("ROLLBACK")
                raise LifecycleRejected("rotation predecessor is not current")
            if new_generation <= expected_generation:
                db.execute("ROLLBACK")
                raise LifecycleRejected("rotation generation must advance")
            db.execute(
                "UPDATE key_lifecycle SET previous_generation=current_generation, previous_mode='verify_only', current_generation=?, lifecycle_epoch=lifecycle_epoch+1 WHERE logical_id=?",
                (new_generation, logical_id),
            )
            db.execute("COMMIT")

    def retire_previous(self, *, logical_id: str, expected_previous: int) -> None:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT previous_generation,previous_mode FROM key_lifecycle WHERE logical_id=?",
                (logical_id,),
            ).fetchone()
            if row is None or row[0] != expected_previous or row[1] != "verify_only":
                db.execute("ROLLBACK")
                raise LifecycleRejected("previous generation is not in verification overlap")
            db.execute(
                "UPDATE key_lifecycle SET previous_mode='retired', lifecycle_epoch=lifecycle_epoch+1 WHERE logical_id=?",
                (logical_id,),
            )
            db.execute("COMMIT")

    def revoke(self, *, logical_id: str) -> None:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute(
                "UPDATE key_lifecycle SET state='revoked', lifecycle_epoch=lifecycle_epoch+1 WHERE logical_id=? AND state='active'",
                (logical_id,),
            ).rowcount != 1:
                db.execute("ROLLBACK")
                raise LifecycleRejected("key is not active")
            db.execute("COMMIT")

    def require_issue(self, *, logical_id: str) -> LifecycleState:
        state = self.read_key(logical_id)
        if state.state != "active":
            raise LifecycleRejected("logical key is revoked")
        return state

    def require_verify(self, *, logical_id: str, generation: int) -> LifecycleState:
        state = self.read_key(logical_id)
        if state.state != "active":
            raise LifecycleRejected("logical key is revoked")
        if generation == state.current_generation:
            return state
        if generation == state.previous_generation and state.previous_mode == "verify_only":
            return state
        raise LifecycleRejected("key generation is not current or allowed historical verifier")

    def require_current_generation(self, *, logical_id: str, generation: int) -> LifecycleState:
        state = self.require_issue(logical_id=logical_id)
        if generation != state.current_generation:
            raise LifecycleRejected("credential generation is not current")
        return state

    def initialize_replay_policy(self, *, client_principal: str, epoch: int, minimum_credential_generation: int) -> None:
        client = _canon(client_principal, "client_principal")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO replay_policy(client_principal,current_epoch,minimum_credential_generation) VALUES(?,?,?)",
                (client, epoch, minimum_credential_generation),
            )
            db.execute("COMMIT")

    def read_replay_policy(self, client_principal: str) -> tuple[int, int]:
        client = _canon(client_principal, "client_principal")
        with self._connect() as db:
            row = db.execute(
                "SELECT current_epoch,minimum_credential_generation FROM replay_policy WHERE client_principal=?",
                (client,),
            ).fetchone()
        if row is None:
            raise LifecycleRejected("missing replay policy")
        return int(row[0]), int(row[1])

    def commit_replay_fence_and_credential_rotation(
        self,
        *,
        client_principal: str,
        expected_epoch: int,
        new_epoch: int,
        expected_generation: int,
        new_generation: int,
    ) -> None:
        """Source commit performed only after replay authority has already fenced to new_epoch."""
        client = _canon(client_principal, "client_principal")
        signing_logical_id = signing_logical_id_for_client(client)
        expected_binding = client_binding_id(client)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            replay = db.execute(
                "SELECT current_epoch,minimum_credential_generation FROM replay_policy WHERE client_principal=?",
                (client,),
            ).fetchone()
            key = db.execute(
                "SELECT current_generation,state,binding_id FROM key_lifecycle WHERE logical_id=?",
                (signing_logical_id,),
            ).fetchone()
            if (
                replay is None
                or replay[0] != expected_epoch
                or key is None
                or key[0] != expected_generation
                or key[1] != "active"
                or key[2] != expected_binding
            ):
                db.execute("ROLLBACK")
                raise LifecycleRejected("source predecessor changed during replay/key rotation")
            if new_epoch <= expected_epoch or new_generation <= expected_generation:
                db.execute("ROLLBACK")
                raise LifecycleRejected("replay/key generations must advance")
            db.execute(
                "UPDATE replay_policy SET current_epoch=?, minimum_credential_generation=? WHERE client_principal=?",
                (new_epoch, new_generation, client),
            )
            db.execute(
                "UPDATE key_lifecycle SET previous_generation=current_generation, previous_mode='retired', current_generation=?, lifecycle_epoch=lifecycle_epoch+1 WHERE logical_id=?",
                (new_generation, signing_logical_id),
            )
            db.execute("COMMIT")


class DerivedKeyReadModel:
    def __init__(self) -> None:
        self._rows: dict[str, dict[str, object]] = {}

    def publish(self, logical_id: str, *, generation: int, state: str) -> None:
        self._rows[logical_id] = {"generation": generation, "state": state}

    def read(self, logical_id: str) -> dict[str, object] | None:
        row = self._rows.get(logical_id)
        return None if row is None else dict(row)


class PostgresController:
    """Pinned PostgreSQL replay authority exercised through independent psql processes."""

    def __init__(self):
        self.container = PG_CONTAINER_NAME

    def _docker(self, *args: str, check: bool = True, input_bytes: bytes | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["docker", *args],
            check=check,
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
        )

    def start(self) -> None:
        self._docker("rm", "-f", self.container, check=False)
        result = self._docker(
            "run", "-d", "--rm", "--name", self.container,
            "-e", f"POSTGRES_PASSWORD={PG_PASSWORD}",
            "-e", f"POSTGRES_DB={PG_DATABASE}",
            POSTGRES_IMAGE,
        )
        if not result.stdout.strip():
            raise ConformanceError("PostgreSQL replay container did not start")
        deadline = time.time() + 45
        while time.time() < deadline:
            probe = self._docker(
                "exec", "-e", f"PGPASSWORD={PG_PASSWORD}", self.container,
                "psql", "-U", "postgres", "-d", PG_DATABASE, "-Atqc", "SELECT 1",
                check=False,
            )
            if probe.returncode == 0 and probe.stdout.strip() == b"1":
                return
            time.sleep(0.25)
        logs = self._docker("logs", self.container, check=False)
        raise ConformanceError("PostgreSQL replay authority not ready: " + logs.stderr.decode("utf-8", "replace")[-1000:])

    def stop(self) -> None:
        self._docker("rm", "-f", self.container, check=False)

    def pause(self) -> None:
        self._docker("pause", self.container)

    def unpause(self) -> None:
        self._docker("unpause", self.container, check=False)

    def sql(self, sql: str, *, check: bool = True) -> subprocess.CompletedProcess:
        return self._docker(
            "exec", "-e", f"PGPASSWORD={PG_PASSWORD}", self.container,
            "psql", "-X", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", PG_DATABASE,
            "-Atqc", sql,
            check=check,
        )

    def dump_database(self, destination: Path) -> None:
        result = self._docker(
            "exec", "-e", f"PGPASSWORD={PG_PASSWORD}", self.container,
            "pg_dump", "-U", "postgres", "-d", PG_DATABASE, "-Fc",
        )
        destination.write_bytes(result.stdout)
        if not destination.read_bytes():
            raise ConformanceError("PostgreSQL replay dump was empty")

    def restore_database(self, snapshot: Path) -> None:
        if not snapshot.exists() or snapshot.stat().st_size == 0:
            raise ConformanceError("missing replay snapshot")
        self._docker("exec", "-e", f"PGPASSWORD={PG_PASSWORD}", self.container, "dropdb", "-U", "postgres", "--if-exists", PG_DATABASE)
        self._docker("exec", "-e", f"PGPASSWORD={PG_PASSWORD}", self.container, "createdb", "-U", "postgres", PG_DATABASE)
        restored = self._docker(
            "exec", "-i", "-e", f"PGPASSWORD={PG_PASSWORD}", self.container,
            "pg_restore", "-U", "postgres", "-d", PG_DATABASE, "--exit-on-error",
            input_bytes=snapshot.read_bytes(),
            check=False,
        )
        if restored.returncode != 0:
            raise ConformanceError("PostgreSQL replay restore failed: " + restored.stderr.decode("utf-8", "replace")[-1200:])
        probe = self.sql("SELECT count(*) FROM replay_meta", check=False)
        if probe.returncode != 0:
            raise ConformanceError("restored replay authority is unreadable")


def _sql_literal(value: str) -> str:
    value = _canon(value, "sql_value")
    return "'" + value.replace("'", "''") + "'"


class PostgresReplayLedger:
    """Durable replay authority shared by independent token-boundary processes/connections."""

    def __init__(self, controller: PostgresController, *, initialize: bool = False):
        self.controller = controller
        if initialize:
            self._initialize()

    def _initialize(self) -> None:
        self.controller.sql(
            r"""
            CREATE TABLE replay_meta (
                client_principal TEXT PRIMARY KEY,
                current_epoch BIGINT NOT NULL CHECK(current_epoch > 0)
            );
            CREATE TABLE consumed (
                client_principal TEXT NOT NULL,
                jti TEXT NOT NULL,
                assertion_fingerprint TEXT NOT NULL,
                consumed_epoch BIGINT NOT NULL CHECK(consumed_epoch > 0),
                PRIMARY KEY(client_principal,jti)
            );
            CREATE OR REPLACE FUNCTION d3e_claim_replay(p_client TEXT,p_jti TEXT,p_epoch BIGINT,p_fingerprint TEXT)
            RETURNS TEXT LANGUAGE plpgsql AS $$
            DECLARE v_epoch BIGINT; v_existing TEXT; v_inserted INTEGER;
            BEGIN
                SELECT current_epoch INTO v_epoch FROM replay_meta WHERE client_principal=p_client FOR UPDATE;
                IF v_epoch IS NULL OR v_epoch <> p_epoch THEN
                    RAISE EXCEPTION 'D3_REPLAY_CONTINUITY_MISMATCH';
                END IF;
                WITH ins AS (
                    INSERT INTO consumed(client_principal,jti,assertion_fingerprint,consumed_epoch)
                    VALUES(p_client,p_jti,p_fingerprint,p_epoch)
                    ON CONFLICT DO NOTHING RETURNING 1
                ) SELECT count(*)::INTEGER INTO v_inserted FROM ins;
                IF v_inserted = 1 THEN RETURN 'accepted'; END IF;
                SELECT assertion_fingerprint INTO v_existing FROM consumed WHERE client_principal=p_client AND jti=p_jti;
                IF v_existing IS DISTINCT FROM p_fingerprint THEN
                    RAISE EXCEPTION 'D3_REPLAY_IDENTITY_CONFLICT';
                END IF;
                RETURN 'duplicate';
            END $$;
            """
        )

    def initialize_scope(self, *, client_principal: str, epoch: int) -> None:
        client = _sql_literal(client_principal)
        self.controller.sql(f"INSERT INTO replay_meta(client_principal,current_epoch) VALUES({client},{int(epoch)})")

    def fence_epoch(self, *, client_principal: str, expected_epoch: int, new_epoch: int) -> None:
        if new_epoch <= expected_epoch:
            raise ReplayContinuityMismatch("replay epoch must advance")
        client = _sql_literal(client_principal)
        sql = f"""
        DO $$ DECLARE n INTEGER; BEGIN
          UPDATE replay_meta SET current_epoch={int(new_epoch)}
          WHERE client_principal={client} AND current_epoch={int(expected_epoch)};
          GET DIAGNOSTICS n = ROW_COUNT;
          IF n <> 1 THEN RAISE EXCEPTION 'D3_REPLAY_CONTINUITY_MISMATCH'; END IF;
        END $$;
        """
        result = self.controller.sql(sql, check=False)
        if result.returncode != 0:
            raise ReplayContinuityMismatch("replay fence predecessor mismatch")

    def fence_recovered_epoch(self, *, client_principal: str, maximum_restored_epoch: int, new_epoch: int) -> None:
        """Jump restored replay state directly past source currentness; never momentarily equal it."""
        if new_epoch <= maximum_restored_epoch:
            raise ReplayContinuityMismatch("recovery epoch must advance beyond trusted source")
        client = _sql_literal(client_principal)
        sql = f"""
        DO $$ DECLARE v BIGINT; BEGIN
          SELECT current_epoch INTO v FROM replay_meta WHERE client_principal={client} FOR UPDATE;
          IF v IS NULL OR v > {int(maximum_restored_epoch)} THEN
            RAISE EXCEPTION 'D3_REPLAY_CONTINUITY_MISMATCH';
          END IF;
          UPDATE replay_meta SET current_epoch={int(new_epoch)} WHERE client_principal={client};
        END $$;
        """
        result = self.controller.sql(sql, check=False)
        if result.returncode != 0:
            raise ReplayContinuityMismatch("restored replay epoch cannot be safely fenced forward")

    def snapshot_to(self, destination: Path) -> None:
        self.controller.dump_database(destination)

    def restore_from(self, snapshot: Path) -> None:
        self.controller.restore_database(snapshot)

    def claim(self, *, client_principal: str, jti: str, expected_epoch: int, assertion_fingerprint: str) -> bool:
        client = _sql_literal(client_principal)
        token_id = _sql_literal(jti)
        fingerprint = _sql_literal(assertion_fingerprint)
        result = self.controller.sql(
            f"SELECT d3e_claim_replay({client},{token_id},{int(expected_epoch)},{fingerprint})",
            check=False,
        )
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", "replace")
            if "D3_REPLAY_CONTINUITY_MISMATCH" in err:
                raise ReplayContinuityMismatch("replay store cannot prove trusted current epoch")
            if "D3_REPLAY_IDENTITY_CONFLICT" in err:
                raise ConformanceError("same replay identity presented with different immutable assertion")
            raise ReplayUnavailable("replay authority unavailable or unprovable: " + err[-300:])
        outcome = result.stdout.decode("utf-8", "replace").strip()
        if outcome == "accepted": return True
        if outcome == "duplicate": return False
        raise ConformanceError("unexpected replay authority result")


class MacBackend(Protocol):
    """Runtime-only provider-neutral cryptographic port; lifecycle/admin is intentionally absent."""

    def binds_domain(self, *, provider_ref: str, domain: KeyDomain) -> bool: ...
    def latest_generation(self, provider_ref: str) -> int: ...
    def hmac(self, *, provider_ref: str, generation: int, message: bytes) -> str: ...
    def verify_hmac(self, *, provider_ref: str, generation: int, message: bytes, mac_value: str) -> bool: ...


class ReferenceMacBackend:
    """Deterministic substitution control; derived keys never leave this backend object."""

    def __init__(self, master: bytes):
        if len(master) < 32:
            raise ValueError("reference master too short")
        self.master = master
        self._domains: dict[str, tuple[str, int]] = {}

    def provision_domain(self, domain: KeyDomain) -> str:
        ref = f"ref-{domain.domain_id}"
        self._domains[ref] = (domain.domain_id, 1)
        return ref

    def binds_domain(self, *, provider_ref: str, domain: KeyDomain) -> bool:
        row = self._domains.get(provider_ref)
        return row is not None and row[0] == domain.domain_id

    def rotate_domain(self, provider_ref: str) -> int:
        domain_id, current = self._domains[provider_ref]
        self._domains[provider_ref] = (domain_id, current + 1)
        return current + 1

    def latest_generation(self, provider_ref: str) -> int:
        return self._domains[provider_ref][1]

    def _key(self, provider_ref: str, generation: int) -> bytes:
        domain_id, latest = self._domains[provider_ref]
        if generation <= 0 or generation > latest:
            raise ConformanceError("reference generation unavailable")
        prk = hmac.new(b"jlmirror-d3e-hkdf-salt-v1", self.master, hashlib.sha256).digest()
        info = b"jlmirror-domain-key-v1\x00" + domain_id.encode() + b"\x00" + str(generation).encode()
        return hmac.new(prk, info + b"\x01", hashlib.sha256).digest()

    def hmac(self, *, provider_ref: str, generation: int, message: bytes) -> str:
        digest = hmac.new(self._key(provider_ref, generation), message, hashlib.sha256).digest()
        return f"ref:v{generation}:{_b64url(digest)}"

    def verify_hmac(self, *, provider_ref: str, generation: int, message: bytes, mac_value: str) -> bool:
        expected = self.hmac(provider_ref=provider_ref, generation=generation, message=message)
        return hmac.compare_digest(expected, mac_value)
