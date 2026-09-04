from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROFILE_PATH = ROOT / "implementation/d4-eventing-async/source-evidence/recovery/recovery-profile.json"
CONTAINER = "d4a-kafka"
KAFKA_BIN = "/opt/kafka/bin"
BOOTSTRAP = "localhost:9092"


def run(cmd: list[str], *, input_text: str | None = None, timeout: int = 120, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, input=input_text, text=True, capture_output=True, check=check, timeout=timeout)


def ktool(tool: str, *args: str, stdin: str | None = None, timeout: int = 120, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = ["docker", "exec"]
    if stdin is not None:
        cmd.append("-i")
    cmd += [CONTAINER, f"{KAFKA_BIN}/{tool}", *args]
    return run(cmd, input_text=stdin, timeout=timeout, check=check)


def wait_kafka_ready() -> None:
    for _ in range(60):
        probe = ktool("kafka-topics.sh", "--bootstrap-server", BOOTSTRAP, "--list", timeout=10, check=False)
        if probe.returncode == 0:
            return
        time.sleep(1)
    raise AssertionError("Kafka did not become ready after restart")


def topic(name: str, partitions: int) -> None:
    ktool(
        "kafka-topics.sh", "--bootstrap-server", BOOTSTRAP, "--create", "--if-not-exists",
        "--topic", name, "--partitions", str(partitions), "--replication-factor", "1"
    )


def broker_end_offset(topic_name: str) -> int:
    proc = ktool("kafka-get-offsets.sh", "--bootstrap-server", BOOTSTRAP, "--topic", topic_name)
    total = 0
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        _, offset = line.rsplit(":", 1)
        total += int(offset)
    return total


def publish(topic_name: str, message_id: str, payload: dict) -> None:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    ktool(
        "kafka-console-producer.sh",
        "--bootstrap-server", BOOTSTRAP,
        "--topic", topic_name,
        "--property", "parse.key=true",
        "--property", "key.separator=|",
        stdin=f"{message_id}|{encoded}\n",
        timeout=60,
    )


def assert_broker_unavailable(topic_name: str) -> None:
    probe = run(
        ["docker", "exec", CONTAINER, f"{KAFKA_BIN}/kafka-console-producer.sh", "--bootstrap-server", BOOTSTRAP,
         "--topic", topic_name, "--producer-property", "max.block.ms=1500", "--producer-property", "request.timeout.ms=1000"],
        input_text="must-not-publish\n",
        timeout=10,
        check=False,
    )
    if probe.returncode == 0:
        raise AssertionError("broker outage negative control unexpectedly published")


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS outbox (
          message_id TEXT PRIMARY KEY,
          priority INTEGER NOT NULL,
          workload TEXT NOT NULL,
          semantic_payload TEXT NOT NULL,
          committed_seq INTEGER NOT NULL UNIQUE,
          state TEXT NOT NULL CHECK(state IN ('pending','published')),
          attempts INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS dispatch_log (
          dispatch_seq INTEGER PRIMARY KEY AUTOINCREMENT,
          message_id TEXT NOT NULL,
          workload TEXT NOT NULL,
          priority INTEGER NOT NULL,
          attempt INTEGER NOT NULL,
          outcome TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS inbox (
          message_id TEXT PRIMARY KEY,
          content_sha256 TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS business_effects (
          message_id TEXT PRIMARY KEY,
          effect_value TEXT NOT NULL
        );
        """
    )
    return conn


def commit_outbox(conn: sqlite3.Connection, *, message_id: str, priority: int, workload: str, seq: int) -> None:
    payload = json.dumps({"message_id": message_id, "workload": workload, "committed_seq": seq}, sort_keys=True)
    with conn:
        conn.execute(
            "INSERT INTO outbox(message_id,priority,workload,semantic_payload,committed_seq,state) VALUES(?,?,?,?,?,'pending')",
            (message_id, priority, workload, payload, seq),
        )


def pending_count(conn: sqlite3.Connection, workload: str | None = None) -> int:
    if workload is None:
        return int(conn.execute("SELECT COUNT(*) FROM outbox WHERE state='pending'").fetchone()[0])
    return int(conn.execute("SELECT COUNT(*) FROM outbox WHERE state='pending' AND workload=?", (workload,)).fetchone()[0])


def next_pending(conn: sqlite3.Connection) -> tuple[str, int, str, str, int] | None:
    row = conn.execute(
        "SELECT message_id,priority,workload,semantic_payload,attempts FROM outbox WHERE state='pending' "
        "ORDER BY priority DESC, committed_seq ASC LIMIT 1"
    ).fetchone()
    return tuple(row) if row else None


def record_attempt(conn: sqlite3.Connection, row: tuple[str, int, str, str, int], outcome: str, *, mark_published: bool) -> None:
    message_id, priority, workload, _, attempts = row
    attempt = attempts + 1
    with conn:
        conn.execute("UPDATE outbox SET attempts=? WHERE message_id=?", (attempt, message_id))
        if mark_published:
            conn.execute("UPDATE outbox SET state='published' WHERE message_id=?", (message_id,))
        conn.execute(
            "INSERT INTO dispatch_log(message_id,workload,priority,attempt,outcome) VALUES(?,?,?,?,?)",
            (message_id, workload, priority, attempt, outcome),
        )


def consume(topic_name: str, expected_records: int) -> list[tuple[str, dict]]:
    proc = ktool(
        "kafka-console-consumer.sh",
        "--bootstrap-server", BOOTSTRAP,
        "--topic", topic_name,
        "--from-beginning",
        "--max-messages", str(expected_records),
        "--timeout-ms", "30000",
        "--property", "print.key=true",
        "--property", "key.separator=|",
        timeout=90,
    )
    records: list[tuple[str, dict]] = []
    for line in proc.stdout.splitlines():
        if "|" not in line:
            continue
        key, value = line.split("|", 1)
        records.append((key, json.loads(value)))
    if len(records) != expected_records:
        raise AssertionError(f"expected {expected_records} broker records, got {len(records)}")
    return records


def apply_consumer_effects(conn: sqlite3.Connection, records: list[tuple[str, dict]]) -> int:
    suppressed = 0
    for key, payload in records:
        message_id = payload["message_id"]
        if key != message_id:
            raise AssertionError("Kafka key and logical message_id diverged")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        content_hash = hashlib.sha256(canonical).hexdigest()
        prior = conn.execute("SELECT content_sha256 FROM inbox WHERE message_id=?", (message_id,)).fetchone()
        if prior:
            if prior[0] != content_hash:
                raise AssertionError("same logical message_id arrived with conflicting immutable content")
            suppressed += 1
            continue
        with conn:
            conn.execute("INSERT INTO inbox(message_id,content_sha256) VALUES(?,?)", (message_id, content_hash))
            conn.execute("INSERT INTO business_effects(message_id,effect_value) VALUES(?,?)", (message_id, payload["workload"]))
    return suppressed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    profile = json.loads(PROFILE_PATH.read_text())
    runtime = Path(args.output).parent
    runtime.mkdir(parents=True, exist_ok=True)
    db_path = runtime / "recovery-outbox.sqlite3"
    if db_path.exists():
        db_path.unlink()

    topic_name = profile["topic"]
    topic(topic_name, profile["partitions"])

    # Real broker outage. Business/outbox commits continue while Kafka is unavailable.
    run(["docker", "stop", CONTAINER], timeout=60)
    assert_broker_unavailable(topic_name)
    conn = connect(db_path)
    ambiguous_id = profile["ack_ambiguity"]["logical_message_id"]
    for index in range(profile["committed_backlog_messages"]):
        message_id = ambiguous_id if index == 0 else f"d4a-recovery-backlog-{index:04d}"
        commit_outbox(
            conn,
            message_id=message_id,
            priority=profile["normal_priority"],
            workload="recovery_backlog",
            seq=index + 1,
        )
    committed_during_outage = pending_count(conn, "recovery_backlog")
    conn.close()
    if committed_during_outage != profile["committed_backlog_messages"]:
        raise AssertionError("committed outage backlog count drift")

    # Reopen durable outbox independently of broker lifecycle, then recover Kafka.
    conn = connect(db_path)
    rows_after_reopen = pending_count(conn, "recovery_backlog")
    if rows_after_reopen != committed_during_outage:
        raise AssertionError("durable outbox backlog did not survive close/reopen")
    run(["docker", "start", CONTAINER], timeout=60)
    wait_kafka_ready()
    rows_after_broker_restart = pending_count(conn, "recovery_backlog")
    if rows_after_broker_restart != committed_during_outage:
        raise AssertionError("broker restart changed durable outbox truth")

    backlog_since_protected = 0
    protected_injected = 0
    protected_bounds: list[int] = []
    ambiguity_first_publish_done = False
    started = time.monotonic()
    seq = profile["committed_backlog_messages"]

    while pending_count(conn) > 0 or protected_injected < profile["protected_current_messages"]:
        if (
            protected_injected < profile["protected_current_messages"]
            and backlog_since_protected >= profile["max_backlog_dispatches_before_protected"]
            and pending_count(conn, "protected_current") == 0
        ):
            protected_injected += 1
            seq += 1
            commit_outbox(
                conn,
                message_id=f"d4a-recovery-protected-{protected_injected:04d}",
                priority=profile["protected_priority"],
                workload="protected_current",
                seq=seq,
            )

        row = next_pending(conn)
        if row is None:
            continue
        message_id, _, workload, payload_text, _ = row
        payload = json.loads(payload_text)
        publish(topic_name, message_id, payload)

        if message_id == ambiguous_id and not ambiguity_first_publish_done:
            ambiguity_first_publish_done = True
            record_attempt(conn, row, "broker_ack_intentionally_treated_as_ambiguous", mark_published=False)
            backlog_since_protected += 1
            continue

        record_attempt(conn, row, "published", mark_published=True)
        if workload == "protected_current":
            protected_bounds.append(backlog_since_protected)
            backlog_since_protected = 0
        else:
            backlog_since_protected += 1

    drain_seconds = time.monotonic() - started
    if pending_count(conn) != 0:
        raise AssertionError("recovery drain left pending outbox work")
    if len(protected_bounds) != profile["protected_current_messages"]:
        raise AssertionError("protected current work was not fully exercised")
    if max(protected_bounds, default=0) > profile["max_backlog_dispatches_before_protected"]:
        raise AssertionError("protected current work starved during backlog drain")

    ambiguous_attempts = int(conn.execute("SELECT attempts FROM outbox WHERE message_id=?", (ambiguous_id,)).fetchone()[0])
    if ambiguous_attempts != 2:
        raise AssertionError("ack ambiguity did not force exactly one same-identity retry")
    ambiguous_ids = {row[0] for row in conn.execute("SELECT message_id FROM dispatch_log WHERE message_id=?", (ambiguous_id,))}
    if ambiguous_ids != {ambiguous_id}:
        raise AssertionError("ack ambiguity invented a new semantic identity")

    expected_unique = profile["committed_backlog_messages"] + profile["protected_current_messages"]
    expected_broker_records = expected_unique + 1
    end_offset = broker_end_offset(topic_name)
    effects_before = int(conn.execute("SELECT COUNT(*) FROM business_effects").fetchone()[0])
    if end_offset != expected_broker_records:
        raise AssertionError(f"broker end offset drift: expected {expected_broker_records}, got {end_offset}")
    if effects_before != 0:
        raise AssertionError("broker publication progress incorrectly created business effects")

    records = consume(topic_name, expected_broker_records)
    suppressed = apply_consumer_effects(conn, records)
    effects_after = int(conn.execute("SELECT COUNT(*) FROM business_effects").fetchone()[0])
    inbox_count = int(conn.execute("SELECT COUNT(*) FROM inbox").fetchone()[0])
    if effects_after != expected_unique or inbox_count != expected_unique:
        raise AssertionError("consumer effect/inbox durable truth count drift")
    if suppressed != 1:
        raise AssertionError(f"expected one ambiguous duplicate suppression, got {suppressed}")

    dispatch_rows = conn.execute(
        "SELECT dispatch_seq,message_id,workload,priority,attempt,outcome FROM dispatch_log ORDER BY dispatch_seq"
    ).fetchall()
    conn.close()

    result = {
        "schema": "d4a-recovery-benchmark-results-v1",
        "profile_id": profile["profile_id"],
        "numeric_authority": profile["numeric_authority"],
        "environment_scope": profile["environment_scope"],
        "real_candidate_outage_exercised": True,
        "committed_outbox_backlog_survives_broker_outage": True,
        "outbox_rows_committed_while_broker_unavailable": committed_during_outage,
        "outbox_rows_after_database_reopen": rows_after_reopen,
        "outbox_rows_remaining_after_broker_restart": rows_after_broker_restart,
        "backlog_drain_seconds": drain_seconds,
        "backlog_fully_drained": True,
        "protected_current_messages_exercised": len(protected_bounds),
        "max_backlog_before_each_protected_delivery": max(protected_bounds, default=0),
        "protected_delivery_bounds": protected_bounds,
        "priority_preserving_anti_starvation": True,
        "ack_ambiguity": {
            "message_id": ambiguous_id,
            "publish_attempts": ambiguous_attempts,
            "distinct_logical_message_ids": len(ambiguous_ids),
            "same_logical_identity_reused": ambiguous_ids == {ambiguous_id},
        },
        "broker_progress_non_authority": {
            "broker_end_offset_before_business_effects": end_offset,
            "business_effect_count_before_consumer_admission": effects_before,
            "broker_progress_is_business_effect_truth": False,
        },
        "consumer_effect_safety": {
            "broker_records_observed": len(records),
            "unique_logical_messages": expected_unique,
            "business_effect_count_after_consumer_admission": effects_after,
            "duplicate_business_effects_suppressed": suppressed,
            "inbox_identity_is_logical_message_id": True,
        },
        "dispatch_log": [
            {"seq": r[0], "message_id": r[1], "workload": r[2], "priority": r[3], "attempt": r[4], "outcome": r[5]}
            for r in dispatch_rows
        ],
        "kafka_selection_state": "not_selected",
        "d4_transport_authority": "not_selected_not_granted",
        "production_authority": "none",
        "c3_numeric_topology_authority": "not_selected",
    }
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        "d4a_recovery_benchmark=PASS outage=real outbox=durable drain=complete "
        f"protected_max_backlog={result['max_backlog_before_each_protected_delivery']} "
        f"ambiguous_attempts={ambiguous_attempts} duplicate_effects_suppressed={suppressed} "
        "broker_progress_business_truth=false numerics=test_only"
    )


if __name__ == "__main__":
    main()
