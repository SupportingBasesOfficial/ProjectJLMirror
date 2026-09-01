#!/usr/bin/env python3
from __future__ import annotations

import concurrent.futures
import hashlib
import hmac
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PG_CONTAINER = os.environ.get("PG_CONTAINER", "jlmirror-d3e-postgres")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "d3-postgres-password")
PG_IMAGE = os.environ["POSTGRES_IMAGE"]
D3_NETWORK = os.environ.get("D3_NETWORK", "jlmirror-d3e-conformance")
WITNESS_PATH = Path(os.environ.get("D3E_RECOVERY_WITNESS", "/tmp/jlmirror-d3e-recovery-witness.json"))
WITNESS_KEY = os.environ.get("D3E_RECOVERY_WITNESS_KEY", "d3e-test-recovery-witness-key").encode()
PROVIDER_PORT = int(os.environ.get("D3E_EFFECT_PROVIDER_PORT", "18081"))
PROVIDER_STATE = Path(os.environ.get("D3E_EFFECT_PROVIDER_STATE", "/tmp/jlmirror-d3e-provider-state.json"))


def sh(args: list[str], *, input_text: str | None = None, timeout: float = 30, check: bool = True):
    r = subprocess.run(args, input=input_text, text=True, capture_output=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(f"command failed rc={r.returncode}: {r.stderr.strip()[:900]}")
    return r


def lit(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def psql(sql: str, *, db: str = "d3", check: bool = True) -> str:
    r = sh([
        "docker", "exec", "-e", f"PGPASSWORD={PG_PASSWORD}", PG_CONTAINER,
        "psql", "-X", "-U", "postgres", "-d", db, "-v", "ON_ERROR_STOP=1", "-Atq", "-c", sql,
    ], check=check)
    return r.stdout.strip()


def psql_script(script: str, *, db: str = "d3") -> None:
    sh([
        "docker", "exec", "-i", "-e", f"PGPASSWORD={PG_PASSWORD}", PG_CONTAINER,
        "psql", "-X", "-U", "postgres", "-d", db, "-v", "ON_ERROR_STOP=1", "-q",
    ], input_text=script)


def network_psql(sql: str, *, check: bool = True, timeout: float = 12):
    return sh([
        "docker", "run", "--rm", "--network", D3_NETWORK, "-e", f"PGPASSWORD={PG_PASSWORD}", PG_IMAGE,
        "psql", "-X", "-h", PG_CONTAINER, "-U", "postgres", "-d", "d3",
        "-v", "ON_ERROR_STOP=1", "-Atq", "-c", sql,
    ], check=check, timeout=timeout)


def whole_database_dump() -> str:
    r = sh([
        "docker", "exec", "-e", f"PGPASSWORD={PG_PASSWORD}", PG_CONTAINER,
        "pg_dump", "-U", "postgres", "-d", "d3", "--no-owner", "--no-privileges",
    ])
    if "CREATE SCHEMA d3e_replay" not in r.stdout:
        raise AssertionError("whole PostgreSQL database dump did not contain replay authority")
    if "-- Name: d3e_replay" not in r.stdout and "d3e_replay.replay_identity" not in r.stdout:
        raise AssertionError("whole database snapshot is malformed")
    return r.stdout


def restore_whole_database(stale_dump: str) -> None:
    psql("DROP SCHEMA IF EXISTS d3e_replay CASCADE;")
    psql_script(stale_dump)


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


class RecoveryWitnessPort:
    """Recovery-only continuity witness outside the rollback subject snapshot."""

    def __init__(self, path: Path = WITNESS_PATH):
        self.path = path

    def _seal(self, payload: dict) -> dict:
        mac = hmac.new(WITNESS_KEY, canonical_json(payload), hashlib.sha256).hexdigest()
        return {"payload": payload, "mac": mac}

    def write(self, payload: dict) -> None:
        envelope = self._seal(payload)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(envelope, sort_keys=True))
        os.replace(tmp, self.path)

    def read(self) -> dict:
        if not self.path.exists():
            raise RuntimeError("recovery continuity witness unavailable")
        envelope = json.loads(self.path.read_text())
        payload = envelope.get("payload")
        supplied = envelope.get("mac")
        if not isinstance(payload, dict) or not isinstance(supplied, str):
            raise RuntimeError("malformed recovery continuity witness")
        expected = self._seal(payload)["mac"]
        if not hmac.compare_digest(supplied, expected):
            raise RuntimeError("recovery continuity witness integrity failure")
        return payload

    def initialize(self) -> None:
        self.write({
            "epoch": 1,
            "admission_open": True,
            "boundary": "initial",
            "consumed": [],
            "provider_outcomes": {},
        })

    def require_admission(self, expected_epoch: int) -> None:
        payload = self.read()
        if payload["epoch"] != expected_epoch or payload["admission_open"] is not True:
            raise RuntimeError("recovery continuity currentness unavailable")

    def capture_boundary(self, *, next_epoch: int, provider_outcomes: dict[str, dict]) -> None:
        consumed_rows = psql(
            "SELECT client_principal||'|'||jti||'|'||assertion_fingerprint||'|'||effect_id||'|'||result_ref "
            "FROM d3e_replay.replay_identity WHERE state='consumed' ORDER BY client_principal,jti;"
        )
        consumed = []
        for row in filter(None, consumed_rows.splitlines()):
            client, jti, fingerprint, effect_id, result_ref = row.split("|", 4)
            consumed.append({
                "client": client,
                "jti": jti,
                "fingerprint": fingerprint,
                "effect_id": effect_id,
                "result_ref": result_ref,
            })
        self.write({
            "epoch": next_epoch,
            "admission_open": False,
            "boundary": f"F-{next_epoch}",
            "consumed": consumed,
            "provider_outcomes": provider_outcomes,
        })

    def open_after_reconciliation(self) -> None:
        payload = self.read()
        payload["admission_open"] = True
        self.write(payload)


class ReplayAuthorityPort:
    def __init__(self, witness: RecoveryWitnessPort):
        self.witness = witness

    def consume(
        self,
        client: str,
        jti: str,
        fingerprint: str,
        effect_id: str,
        result_ref: str,
        expected_epoch: int,
    ) -> str:
        try:
            self.witness.require_admission(expected_epoch)
        except RuntimeError:
            return "BLOCKED"
        return consume_sql(client, jti, fingerprint, effect_id, result_ref, expected_epoch)


def init_db() -> None:
    psql_script(r"""
DROP SCHEMA IF EXISTS d3e_replay CASCADE;
CREATE SCHEMA d3e_replay;

CREATE TABLE d3e_replay.recovery_fence(
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK(singleton),
    epoch BIGINT NOT NULL CHECK(epoch > 0),
    reconciled BOOLEAN NOT NULL
);
INSERT INTO d3e_replay.recovery_fence(singleton,epoch,reconciled) VALUES(TRUE,1,TRUE);

CREATE TABLE d3e_replay.replay_identity(
    client_principal TEXT NOT NULL,
    jti TEXT NOT NULL,
    assertion_fingerprint TEXT NOT NULL,
    recovery_epoch BIGINT NOT NULL CHECK(recovery_epoch > 0),
    state TEXT NOT NULL CHECK(state IN('consumed')),
    effect_id TEXT NOT NULL,
    result_ref TEXT NOT NULL,
    PRIMARY KEY(client_principal,jti),
    UNIQUE(effect_id)
);

CREATE TABLE d3e_replay.effect_ledger(
    effect_id TEXT PRIMARY KEY,
    client_principal TEXT NOT NULL,
    jti TEXT NOT NULL,
    result_ref TEXT NOT NULL,
    UNIQUE(client_principal,jti)
);

CREATE TABLE d3e_replay.redrive(
    operation_id TEXT PRIMARY KEY,
    recovery_epoch BIGINT NOT NULL CHECK(recovery_epoch > 0),
    state TEXT NOT NULL CHECK(state IN('prepared','attempting','reconciliation_required','completed')),
    attempt_generation BIGINT NOT NULL DEFAULT 0 CHECK(attempt_generation >= 0),
    worker_id TEXT NULL,
    attempt_token TEXT NULL,
    ambiguity_reason TEXT NULL,
    provider_revision TEXT NULL,
    result_ref TEXT NULL,
    CHECK(
      (state='attempting' AND worker_id IS NOT NULL AND attempt_token IS NOT NULL)
      OR (state<>'attempting' AND worker_id IS NULL AND attempt_token IS NULL)
    ),
    CHECK(state<>'reconciliation_required' OR ambiguity_reason IS NOT NULL),
    CHECK(state<>'completed' OR result_ref IS NOT NULL)
);

CREATE FUNCTION d3e_replay.consume_private_jwt(
    p_client TEXT,
    p_jti TEXT,
    p_fingerprint TEXT,
    p_effect_id TEXT,
    p_result_ref TEXT,
    p_expected_epoch BIGINT
) RETURNS TEXT
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog,d3e_replay
AS $$
DECLARE
    prior d3e_replay.replay_identity%ROWTYPE;
    gate_ok BOOLEAN;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('jwt:' || p_client || E'\x1f' || p_jti,0));

    SELECT TRUE INTO gate_ok
      FROM d3e_replay.recovery_fence
     WHERE singleton=TRUE AND epoch=p_expected_epoch AND reconciled=TRUE;
    IF gate_ok IS DISTINCT FROM TRUE THEN
        RETURN 'BLOCKED';
    END IF;

    SELECT * INTO prior
      FROM d3e_replay.replay_identity
     WHERE client_principal=p_client AND jti=p_jti
     FOR UPDATE;

    IF FOUND THEN
        IF prior.recovery_epoch<>p_expected_epoch THEN
            RETURN 'BLOCKED';
        END IF;
        IF prior.assertion_fingerprint=p_fingerprint
           AND prior.effect_id=p_effect_id
           AND prior.result_ref=p_result_ref THEN
            RETURN 'OBSERVE';
        END IF;
        RETURN 'CONFLICT';
    END IF;

    INSERT INTO d3e_replay.replay_identity(
        client_principal,jti,assertion_fingerprint,recovery_epoch,state,effect_id,result_ref
    ) VALUES(p_client,p_jti,p_fingerprint,p_expected_epoch,'consumed',p_effect_id,p_result_ref);

    INSERT INTO d3e_replay.effect_ledger(effect_id,client_principal,jti,result_ref)
    VALUES(p_effect_id,p_client,p_jti,p_result_ref);

    RETURN 'WIN';
END;
$$;

CREATE FUNCTION d3e_replay.claim_redrive(
    p_operation_id TEXT,p_worker_id TEXT,p_attempt_token TEXT,p_expected_epoch BIGINT
) RETURNS BIGINT
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog,d3e_replay
AS $$
DECLARE
    item d3e_replay.redrive%ROWTYPE;
    gate_ok BOOLEAN;
    next_generation BIGINT;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('redrive:' || p_operation_id,0));
    SELECT TRUE INTO gate_ok FROM d3e_replay.recovery_fence
     WHERE singleton=TRUE AND epoch=p_expected_epoch AND reconciled=TRUE;
    IF gate_ok IS DISTINCT FROM TRUE THEN RETURN NULL; END IF;

    SELECT * INTO item FROM d3e_replay.redrive
     WHERE operation_id=p_operation_id FOR UPDATE;
    IF NOT FOUND OR item.state<>'prepared' OR item.recovery_epoch<>p_expected_epoch THEN
        RETURN NULL;
    END IF;
    next_generation := item.attempt_generation + 1;
    UPDATE d3e_replay.redrive
       SET state='attempting',attempt_generation=next_generation,
           worker_id=p_worker_id,attempt_token=p_attempt_token,
           ambiguity_reason=NULL,provider_revision=NULL,result_ref=NULL
     WHERE operation_id=p_operation_id;
    RETURN next_generation;
END;
$$;

CREATE FUNCTION d3e_replay.mark_ambiguous(
    p_operation_id TEXT,p_attempt_generation BIGINT,p_reason TEXT
) RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog,d3e_replay
AS $$
BEGIN
    UPDATE d3e_replay.redrive
       SET state='reconciliation_required',worker_id=NULL,attempt_token=NULL,
           ambiguity_reason=p_reason
     WHERE operation_id=p_operation_id AND state='attempting'
       AND attempt_generation=p_attempt_generation;
    RETURN FOUND;
END;
$$;

CREATE FUNCTION d3e_replay.complete_after_provider(
    p_operation_id TEXT,p_attempt_generation BIGINT,p_result_ref TEXT,p_revision TEXT
) RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog,d3e_replay
AS $$
BEGIN
    UPDATE d3e_replay.redrive
       SET state='completed',worker_id=NULL,attempt_token=NULL,
           ambiguity_reason=NULL,provider_revision=p_revision,result_ref=p_result_ref
     WHERE operation_id=p_operation_id AND state='attempting'
       AND attempt_generation=p_attempt_generation;
    RETURN FOUND;
END;
$$;

CREATE FUNCTION d3e_replay.reconcile_provider_outcome(
    p_operation_id TEXT,p_attempt_generation BIGINT,p_outcome TEXT,
    p_revision TEXT,p_result_ref TEXT
) RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog,d3e_replay
AS $$
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('redrive:' || p_operation_id,0));
    IF p_outcome='CONFIRMED' THEN
        UPDATE d3e_replay.redrive
           SET state='completed',worker_id=NULL,attempt_token=NULL,
               ambiguity_reason=NULL,provider_revision=p_revision,result_ref=p_result_ref
         WHERE operation_id=p_operation_id AND state='reconciliation_required'
           AND attempt_generation=p_attempt_generation;
        RETURN FOUND;
    ELSIF p_outcome='ABSENT' THEN
        UPDATE d3e_replay.redrive
           SET state='prepared',worker_id=NULL,attempt_token=NULL,
               ambiguity_reason=NULL,provider_revision=p_revision,result_ref=NULL
         WHERE operation_id=p_operation_id AND state='reconciliation_required'
           AND attempt_generation=p_attempt_generation;
        RETURN FOUND;
    END IF;
    RETURN FALSE;
END;
$$;
""")


def consume_sql(client: str, jti: str, fp: str, effect: str, result: str, epoch: int) -> str:
    return psql(
        "SELECT d3e_replay.consume_private_jwt("
        f"{lit(client)},{lit(jti)},{lit(fp)},{lit(effect)},{lit(result)},{epoch});"
    )


def prepare_redrive(op: str, epoch: int) -> None:
    psql(
        "INSERT INTO d3e_replay.redrive(operation_id,recovery_epoch,state) "
        f"VALUES({lit(op)},{epoch},'prepared');"
    )


def claim(op: str, worker: str, token: str, epoch: int) -> str:
    out = psql(
        "SELECT COALESCE(d3e_replay.claim_redrive("
        f"{lit(op)},{lit(worker)},{lit(token)},{epoch})::text,'BLOCKED');"
    )
    return out or "BLOCKED"


def mark_ambiguous(op: str, gen: int, reason: str) -> None:
    assert psql(
        f"SELECT d3e_replay.mark_ambiguous({lit(op)},{gen},{lit(reason)});"
    ) == "t"


def complete_provider(op: str, gen: int, result_ref: str, revision: str) -> bool:
    return psql(
        "SELECT d3e_replay.complete_after_provider("
        f"{lit(op)},{gen},{lit(result_ref)},{lit(revision)});"
    ) == "t"


def reconcile_provider(op: str, gen: int, outcome: dict) -> bool:
    result = outcome.get("result_ref") or ""
    return psql(
        "SELECT d3e_replay.reconcile_provider_outcome("
        f"{lit(op)},{gen},{lit(outcome['outcome'])},{lit(outcome['revision'])},{lit(result)});"
    ) == "t"


class ProviderState:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        self.effects: dict[str, dict] = {}
        self.fences: dict[str, dict] = {}
        self.revision = 0
        self.persist()

    def next_revision(self) -> str:
        self.revision += 1
        return f"provider-r{self.revision}"

    def persist(self) -> None:
        self.path.write_text(json.dumps(
            {"effects": self.effects, "fences": self.fences, "revision": self.revision},
            sort_keys=True,
        ))


class ProviderHandler(BaseHTTPRequestHandler):
    server_version = "JLMirrorD3EProvider/1"

    def log_message(self, fmt, *args):
        return

    @property
    def state(self) -> ProviderState:
        return self.server.provider_state

    def read_json(self) -> dict:
        length = int(self.headers.get("content-length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self.send_json(200, {"ok": True})
            return
        if self.path.startswith("/status/"):
            op = self.path.split("/", 2)[2]
            with self.state.lock:
                effect = self.state.effects.get(op)
                fence = self.state.fences.get(op)
                self.send_json(200, {"effect": effect, "fence": fence})
            return
        self.send_json(404, {"error": "not_found"})

    def do_POST(self):
        payload = self.read_json()
        if self.path == "/send":
            op = payload["operation_id"]
            generation = int(payload["attempt_generation"])
            token = payload["attempt_token"]
            with self.state.lock:
                fence = self.state.fences.get(op)
                if fence and fence["attempt_generation"] == generation and fence["attempt_token"] == token:
                    self.send_json(409, {"outcome": "BLOCKED", "revision": fence["revision"]})
                    return
                existing = self.state.effects.get(op)
                if existing:
                    same = (
                        existing["effect_id"] == payload["effect_id"]
                        and existing["result_ref"] == payload["result_ref"]
                    )
                    self.send_json(200 if same else 409, {
                        "outcome": "OBSERVE" if same else "CONFLICT",
                        **existing,
                    })
                    return
                revision = self.state.next_revision()
                effect = {
                    "attempt_generation": generation,
                    "attempt_token": token,
                    "effect_id": payload["effect_id"],
                    "result_ref": payload["result_ref"],
                    "revision": revision,
                }
                self.state.effects[op] = effect
                self.state.persist()
                if payload.get("drop_response"):
                    self.close_connection = True
                    return
                self.send_json(200, {"outcome": "WIN", **effect})
            return

        if self.path == "/probe":
            op = payload["operation_id"]
            generation = int(payload["attempt_generation"])
            token = payload["attempt_token"]
            with self.state.lock:
                existing = self.state.effects.get(op)
                if existing:
                    self.send_json(200, {"outcome": "CONFIRMED", **existing})
                    return
                prior_fence = self.state.fences.get(op)
                if prior_fence:
                    same = (
                        prior_fence["attempt_generation"] == generation
                        and prior_fence["attempt_token"] == token
                    )
                    self.send_json(200 if same else 409, {
                        "outcome": "ABSENT" if same else "CONFLICT",
                        **prior_fence,
                    })
                    return
                revision = self.state.next_revision()
                fence = {
                    "attempt_generation": generation,
                    "attempt_token": token,
                    "revision": revision,
                }
                self.state.fences[op] = fence
                self.state.persist()
                self.send_json(200, {"outcome": "ABSENT", **fence})
            return

        self.send_json(404, {"error": "not_found"})


def provider_server() -> None:
    state = ProviderState(PROVIDER_STATE)
    server = ThreadingHTTPServer(("127.0.0.1", PROVIDER_PORT), ProviderHandler)
    server.provider_state = state
    server.serve_forever()


def provider_call(method: str, path: str, payload: dict | None = None, *, tolerate_drop: bool = False) -> dict:
    conn = http.client.HTTPConnection("127.0.0.1", PROVIDER_PORT, timeout=5)
    try:
        body = None if payload is None else json.dumps(payload, separators=(",", ":"))
        conn.request(method, path, body=body, headers={"content-type": "application/json"})
        response = conn.getresponse()
        raw = response.read()
        data = json.loads(raw or b"{}")
        if response.status >= 400 and data.get("outcome") not in {"BLOCKED", "CONFLICT"}:
            raise RuntimeError(f"provider HTTP {response.status}")
        return data
    except (http.client.RemoteDisconnected, ConnectionResetError, socket.timeout):
        if tolerate_drop:
            return {"outcome": "AMBIGUOUS"}
        raise
    finally:
        conn.close()


def provider_send(op: str, gen: int, token: str, effect: str, result: str, *, drop: bool = False) -> dict:
    return provider_call("POST", "/send", {
        "operation_id": op,
        "attempt_generation": gen,
        "attempt_token": token,
        "effect_id": effect,
        "result_ref": result,
        "drop_response": drop,
    }, tolerate_drop=drop)


def provider_probe(op: str, gen: int, token: str) -> dict:
    return provider_call("POST", "/probe", {
        "operation_id": op,
        "attempt_generation": gen,
        "attempt_token": token,
    })


def provider_status(op: str) -> dict:
    return provider_call("GET", f"/status/{op}")


def wait_provider() -> None:
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            if provider_call("GET", "/health").get("ok") is True:
                return
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("external effect provider did not start")


def prove_single_winner(port: ReplayAuthorityPort) -> None:
    args = ("client-a", "jti-a", "fp-a", "session-effect-a", "session-result-a", 1)
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        outcomes = list(pool.map(lambda _: port.consume(*args), range(48)))
    assert outcomes.count("WIN") == 1
    assert outcomes.count("OBSERVE") == 47
    assert port.consume("client-a", "jti-a", "fp-conflict", "session-effect-a", "session-result-a", 1) == "CONFLICT"
    assert psql("SELECT count(*) FROM d3e_replay.effect_ledger WHERE effect_id='session-effect-a';") == "1"
    assert port.consume("client-b", "jti-a", "fp-b", "session-effect-b", "session-result-b", 1) == "WIN"
    print(
        "d3_e_private_key_jwt_replay_atomic_single_winner=PASS "
        "postgres_create_or_observe=true concurrent_workers=48 exactly_one_effect=true "
        "duplicates_observe=true assertion_fingerprint_conflict_rejected=true client_principal_scope=true"
    )


def prove_duplicate_recovery_gate_order(port: ReplayAuthorityPort) -> None:
    assert port.consume("gate-client", "gate-jti", "gate-fp", "gate-effect", "gate-result", 1) == "WIN"
    psql("UPDATE d3e_replay.recovery_fence SET reconciled=FALSE WHERE singleton=TRUE;")
    assert consume_sql("gate-client", "gate-jti", "gate-fp", "gate-effect", "gate-result", 1) == "BLOCKED"
    psql("UPDATE d3e_replay.recovery_fence SET epoch=2,reconciled=FALSE WHERE singleton=TRUE;")
    assert consume_sql("gate-client", "gate-jti", "gate-fp", "gate-effect", "gate-result", 1) == "BLOCKED"
    assert consume_sql("gate-client", "gate-jti", "gate-fp", "gate-effect", "gate-result", 2) == "BLOCKED"
    psql("UPDATE d3e_replay.recovery_fence SET epoch=1,reconciled=TRUE WHERE singleton=TRUE;")
    print(
        "d3_e_replay_duplicate_recovery_gate_order=PASS "
        "recovery_gate_before_duplicate_observe=true prior_epoch_must_match=true quarantine_observe_blocked=true"
    )


def prove_partition() -> None:
    assert network_psql("SELECT 1;").stdout.strip() == "1"
    sh(["docker", "network", "disconnect", D3_NETWORK, PG_CONTAINER])
    try:
        attempt = network_psql(
            "SELECT d3e_replay.consume_private_jwt("
            "'partition-client','partition-jti','partition-fp','partition-effect','partition-result',1);",
            check=False, timeout=8,
        )
        assert attempt.returncode != 0
    finally:
        sh(["docker", "network", "connect", D3_NETWORK, PG_CONTAINER])
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            if network_psql("SELECT 1;", timeout=4).stdout.strip() == "1":
                break
        except Exception:
            time.sleep(0.2)
    else:
        raise RuntimeError("PostgreSQL replay authority did not recover")
    assert psql("SELECT count(*) FROM d3e_replay.replay_identity WHERE jti='partition-jti';") == "0"
    print(
        "d3_e_replay_partition_fail_closed=PASS actual_network_partition=true "
        "replay_authority_unreachable=true no_consumed_identity=true no_effect=true"
    )


def prove_redrive_external_boundary() -> None:
    op = "redrive-worker-died-before-effect"
    prepare_redrive(op, 1)
    assert claim(op, "worker-a", "token-a", 1) == "1"
    mark_ambiguous(op, 1, "worker_died")
    assert claim(op, "worker-b", "token-b", 1) == "BLOCKED"
    absence = provider_probe(op, 1, "token-a")
    assert absence["outcome"] == "ABSENT"
    assert reconcile_provider(op, 1, absence)
    assert claim(op, "worker-b", "token-b", 1) == "2"
    assert provider_send(op, 1, "token-a", "late-effect", "late-result")["outcome"] == "BLOCKED"
    sent = provider_send(op, 2, "token-b", "effect-a", "result-a")
    assert sent["outcome"] == "WIN"
    assert complete_provider(op, 2, "result-a", sent["revision"])
    assert provider_status(op)["effect"]["effect_id"] == "effect-a"

    op2 = "redrive-lost-response"
    prepare_redrive(op2, 1)
    assert claim(op2, "worker-c", "token-c", 1) == "1"
    ambiguous_send = provider_send(op2, 1, "token-c", "effect-b", "result-b", drop=True)
    assert ambiguous_send["outcome"] == "AMBIGUOUS"
    mark_ambiguous(op2, 1, "response_lost")
    assert claim(op2, "worker-d", "token-d", 1) == "BLOCKED"
    confirmed = provider_probe(op2, 1, "token-c")
    assert confirmed["outcome"] == "CONFIRMED"
    assert reconcile_provider(op2, 1, confirmed)
    assert psql(f"SELECT state||'|'||attempt_generation FROM d3e_replay.redrive WHERE operation_id={lit(op2)};") == "completed|1"

    print(
        "d3_e_redrive_crash_retry_single_effect=PASS "
        "external_provider_process=true worker_death_not_absence=true "
        "absence_fences_exact_attempt=true delayed_old_effect_blocked=true "
        "lost_response_external_effect_survives=true provider_probe_reconciles=true"
    )


def prove_absence_effect_race() -> None:
    op = "redrive-absence-effect-race"
    prepare_redrive(op, 1)
    assert claim(op, "race-worker", "race-token", 1) == "1"
    mark_ambiguous(op, 1, "race_ambiguity")

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        send_future = pool.submit(provider_send, op, 1, "race-token", "race-effect", "race-result")
        probe_future = pool.submit(provider_probe, op, 1, "race-token")
        send = send_future.result()
        probe = probe_future.result()

    if probe["outcome"] == "CONFIRMED":
        assert send["outcome"] in {"WIN", "OBSERVE"}
        assert reconcile_provider(op, 1, probe)
        final_gen = 1
    else:
        assert probe["outcome"] == "ABSENT"
        assert send["outcome"] == "BLOCKED"
        assert reconcile_provider(op, 1, probe)
        assert claim(op, "race-worker-2", "race-token-2", 1) == "2"
        sent = provider_send(op, 2, "race-token-2", "race-effect", "race-result")
        assert sent["outcome"] == "WIN"
        assert complete_provider(op, 2, "race-result", sent["revision"])
        final_gen = 2

    status = provider_status(op)
    assert status["effect"]["effect_id"] == "race-effect"
    assert psql(f"SELECT state||'|'||attempt_generation FROM d3e_replay.redrive WHERE operation_id={lit(op)};") == f"completed|{final_gen}"
    print(
        "d3_e_redrive_absence_effect_race_single_winner=PASS "
        "real_network_effect_boundary=true provider_side_serialization=true "
        "absence_and_effect_mutually_exclusive=true absence_fences_old_capability=true exactly_one_external_effect=true"
    )


def _redrive_row(op: str) -> tuple[str, int, str] | None:
    raw = psql(
        "SELECT state||'|'||attempt_generation||'|'||COALESCE(attempt_token,'') "
        f"FROM d3e_replay.redrive WHERE operation_id={lit(op)};"
    )
    if not raw:
        return None
    state, gen_text, token = raw.split("|", 2)
    return state, int(gen_text), token


def _resolve_provider_capability(op: str) -> dict:
    row = _redrive_row(op)
    if row is None:
        return provider_status(op)
    state, generation, token = row

    if state == "attempting":
        if not token:
            raise RuntimeError("attempting redrive lost provider capability")
        outcome = provider_probe(op, generation, token)
        mark_ambiguous(op, generation, "recovery_provider_serialization")
        if not reconcile_provider(op, generation, outcome):
            raise RuntimeError("attempting provider capability could not be reconciled")
    elif state == "reconciliation_required":
        status = provider_status(op)
        capability = status.get("effect") or status.get("fence")
        if not capability:
            raise RuntimeError("ambiguous provider capability has no effect or authoritative absence fence")
        if int(capability["attempt_generation"]) != generation:
            raise RuntimeError("provider capability generation mismatch")
        outcome = provider_probe(op, generation, capability["attempt_token"])
        if not reconcile_provider(op, generation, outcome):
            raise RuntimeError("ambiguous provider capability could not be reconciled")

    final = _redrive_row(op)
    if final and final[0] in {"attempting", "reconciliation_required"}:
        raise RuntimeError("provider capability remained unresolved")
    return provider_status(op)


def capture_recovery_boundary(witness: RecoveryWitnessPort, *, next_epoch: int, ops: list[str]) -> None:
    psql("UPDATE d3e_replay.recovery_fence SET reconciled=FALSE WHERE singleton=TRUE;")
    outstanding_raw = psql(
        "SELECT COALESCE(json_agg(operation_id ORDER BY operation_id)::text,'[]') "
        "FROM d3e_replay.redrive WHERE state IN('attempting','reconciliation_required');"
    )
    outstanding = json.loads(outstanding_raw or "[]")
    all_ops = sorted(set(ops) | set(outstanding))
    outcomes = {op: _resolve_provider_capability(op) for op in all_ops}
    unresolved = psql(
        "SELECT count(*) FROM d3e_replay.redrive "
        "WHERE state IN('attempting','reconciliation_required');"
    )
    if unresolved != "0":
        raise RuntimeError("recovery witness cannot capture unresolved provider capabilities")
    witness.capture_boundary(next_epoch=next_epoch, provider_outcomes=outcomes)


def recover_from_witness(witness: RecoveryWitnessPort) -> None:
    payload = witness.read()
    epoch = int(payload["epoch"])
    if payload["admission_open"] is not False:
        raise RuntimeError("recovery witness must be closed during reconciliation")

    psql(f"UPDATE d3e_replay.recovery_fence SET epoch={epoch},reconciled=FALSE WHERE singleton=TRUE;")
    for item in payload["consumed"]:
        prior = psql(
            "SELECT assertion_fingerprint||'|'||effect_id||'|'||result_ref FROM d3e_replay.replay_identity "
            f"WHERE client_principal={lit(item['client'])} AND jti={lit(item['jti'])};"
        )
        expected = f"{item['fingerprint']}|{item['effect_id']}|{item['result_ref']}"
        if prior and prior != expected:
            raise RuntimeError("recovery continuity conflicts with restored replay identity")
        psql(
            "INSERT INTO d3e_replay.replay_identity("
            "client_principal,jti,assertion_fingerprint,recovery_epoch,state,effect_id,result_ref) "
            f"VALUES({lit(item['client'])},{lit(item['jti'])},{lit(item['fingerprint'])},{epoch},'consumed',"
            f"{lit(item['effect_id'])},{lit(item['result_ref'])}) "
            "ON CONFLICT(client_principal,jti) DO UPDATE SET "
            "assertion_fingerprint=EXCLUDED.assertion_fingerprint,recovery_epoch=EXCLUDED.recovery_epoch,"
            "state='consumed',effect_id=EXCLUDED.effect_id,result_ref=EXCLUDED.result_ref;"
        )
        psql(
            "INSERT INTO d3e_replay.effect_ledger(effect_id,client_principal,jti,result_ref) "
            f"VALUES({lit(item['effect_id'])},{lit(item['client'])},{lit(item['jti'])},{lit(item['result_ref'])}) "
            "ON CONFLICT(effect_id) DO NOTHING;"
        )

    for op, witnessed_status in payload["provider_outcomes"].items():
        row = _redrive_row(op)
        if row is None:
            effect = witnessed_status.get("effect")
            if effect:
                raise RuntimeError("surviving provider effect has no local redrive row; recovery rehydration required")
            continue

        state, generation, token = row
        effect = witnessed_status.get("effect")
        fence = witnessed_status.get("fence")

        if state == "attempting":
            if not token:
                raise RuntimeError("restored attempting row lost provider capability token")
            probe = provider_probe(op, generation, token)
            mark_ambiguous(op, generation, "restore_requires_provider_reconciliation")
            expected_outcome = "CONFIRMED" if probe.get("outcome") == "CONFIRMED" else "ABSENT"
            if probe.get("outcome") not in {"CONFIRMED", "ABSENT"}:
                raise RuntimeError("restored attempting capability did not produce authoritative outcome")
            if not reconcile_provider(op, generation, probe):
                raise RuntimeError("restored attempting provider outcome could not be reconciled")
            state = "completed" if expected_outcome == "CONFIRMED" else "prepared"
        elif state == "reconciliation_required":
            capability = effect or fence
            if not capability:
                raise RuntimeError("restored ambiguous attempt lacks captured provider continuity")
            if int(capability["attempt_generation"]) != generation:
                raise RuntimeError("restored provider capability generation mismatch")
            probe = provider_probe(op, generation, capability["attempt_token"])
            expected_outcome = "CONFIRMED" if effect else "ABSENT"
            if probe.get("outcome") != expected_outcome:
                raise RuntimeError("provider state diverged from captured recovery continuity")
            if not reconcile_provider(op, generation, probe):
                raise RuntimeError("restored provider outcome could not be reconciled")
            state = "completed" if expected_outcome == "CONFIRMED" else "prepared"
        elif state == "completed":
            if not effect:
                raise RuntimeError("completed restored attempt lacks captured provider effect")
            probe = provider_probe(op, int(effect["attempt_generation"]), effect["attempt_token"])
            if probe.get("outcome") != "CONFIRMED":
                raise RuntimeError("completed provider effect was not durable across recovery")
        elif state == "prepared":
            if effect:
                raise RuntimeError("prepared restored attempt has an unaccounted provider effect")
            if fence:
                probe = provider_probe(op, int(fence["attempt_generation"]), fence["attempt_token"])
                if probe.get("outcome") != "ABSENT":
                    raise RuntimeError("captured provider absence fence was not durable")

        psql(
            f"UPDATE d3e_replay.redrive SET recovery_epoch={epoch} "
            f"WHERE operation_id={lit(op)};"
        )

    unresolved = psql(
        "SELECT count(*) FROM d3e_replay.redrive "
        "WHERE state IN('attempting','reconciliation_required');"
    )
    if unresolved != "0":
        raise RuntimeError("recovery remains ambiguous or has an in-flight provider capability")
    psql(f"UPDATE d3e_replay.recovery_fence SET reconciled=TRUE WHERE singleton=TRUE AND epoch={epoch};")
    witness.open_after_reconciliation()


def prove_whole_restore(port: ReplayAuthorityPort, witness: RecoveryWitnessPort) -> None:
    op = "restore-post-r-effect"
    prepare_redrive(op, 1)
    assert claim(op, "restore-worker", "restore-token", 1) == "1"

    stale_dump = whole_database_dump()

    assert port.consume(
        "restore-client", "restore-jti", "restore-fp",
        "restore-session-effect", "restore-session-result", 1,
    ) == "WIN"
    provider_effect = provider_send(op, 1, "restore-token", "restore-provider-effect", "restore-provider-result")
    assert provider_effect["outcome"] == "WIN"
    assert complete_provider(op, 1, "restore-provider-result", provider_effect["revision"])

    capture_recovery_boundary(witness, next_epoch=2, ops=[op])
    assert port.consume("post-f-client", "post-f-jti", "post-f-fp", "post-f-effect", "post-f-result", 1) == "BLOCKED"

    restore_whole_database(stale_dump)

    assert psql("SELECT count(*) FROM d3e_replay.replay_identity WHERE jti='restore-jti';") == "0"
    assert psql("SELECT epoch||'|'||reconciled FROM d3e_replay.recovery_fence WHERE singleton=TRUE;") == "1|t"
    assert port.consume("restore-client", "restore-jti", "restore-fp", "restore-session-effect", "restore-session-result", 1) == "BLOCKED"
    assert port.consume("restore-client", "restore-jti", "restore-fp", "restore-session-effect", "restore-session-result", 2) == "BLOCKED"

    saved = witness.path.with_suffix(".saved")
    os.replace(witness.path, saved)
    try:
        assert port.consume("missing-witness", "mw-jti", "mw-fp", "mw-effect", "mw-result", 2) == "BLOCKED"
        try:
            recover_from_witness(witness)
        except RuntimeError:
            pass
        else:
            raise AssertionError("recovery opened without surviving continuity witness")
    finally:
        os.replace(saved, witness.path)

    recover_from_witness(witness)
    assert port.consume(
        "restore-client", "restore-jti", "restore-fp",
        "restore-session-effect", "restore-session-result", 2,
    ) == "OBSERVE"
    assert port.consume(
        "restore-client", "restore-jti", "restore-fp",
        "restore-session-effect", "restore-session-result", 1,
    ) == "BLOCKED"
    assert psql(
        f"SELECT state||'|'||attempt_generation FROM d3e_replay.redrive WHERE operation_id={lit(op)};"
    ) == "completed|1"
    assert provider_status(op)["effect"]["effect_id"] == "restore-provider-effect"

    print(
        "d3_e_replay_consumed_identity_survives_restore_loss=PASS "
        "whole_database_restore=true rollback_includes_local_control=true "
        "surviving_recovery_witness_external_to_snapshot=true stale_epoch_callers_fenced=true "
        "missing_witness_fail_closed=true consumed_identity_rehydrated=true "
        "ambiguous_external_effect_reconciled=true confirmed_effect_not_repeated=true"
    )


def main() -> None:
    if WITNESS_PATH.exists():
        WITNESS_PATH.unlink()
    if PROVIDER_STATE.exists():
        PROVIDER_STATE.unlink()

    provider_proc = subprocess.Popen(
        [sys.executable, __file__, "--provider-server"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_provider()
        init_db()
        witness = RecoveryWitnessPort()
        witness.initialize()
        port = ReplayAuthorityPort(witness)

        prove_single_winner(port)
        prove_duplicate_recovery_gate_order(port)
        prove_partition()
        prove_redrive_external_boundary()
        prove_absence_effect_race()
        prove_whole_restore(port, witness)

        print(
            "d3_e_replay_redrive_conformance=PASS postgres_replay_truth=true "
            "recovery_witness_recovery_only=true single_winner=true partition_fail_closed=true "
            "external_effect_network_boundary=true whole_restore_nonresurrection=true "
            "c3_numerics_not_selected=true topology_not_selected=true"
        )
    finally:
        provider_proc.terminate()
        try:
            provider_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            provider_proc.kill()


if __name__ == "__main__":
    if "--provider-server" in sys.argv:
        provider_server()
    else:
        main()
