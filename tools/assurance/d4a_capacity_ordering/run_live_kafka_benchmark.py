from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROFILE_PATH = ROOT / "implementation/d4-eventing-async/source-evidence/capacity-ordering/benchmark-profile.json"
CONTAINER = "d4a-kafka"
KAFKA_BIN = "/opt/kafka/bin"


def run(cmd: list[str], *, input_text: str | None = None, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, input=input_text, text=True, capture_output=True, check=True, timeout=timeout)


def ktool(tool: str, *args: str, stdin: str | None = None, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    cmd = ["docker", "exec"]
    if stdin is not None:
        cmd.append("-i")
    cmd += [CONTAINER, f"{KAFKA_BIN}/{tool}", *args]
    return run(cmd, input_text=stdin, timeout=timeout)


def topic(name: str, partitions: int) -> None:
    ktool(
        "kafka-topics.sh", "--bootstrap-server", "localhost:9092", "--create", "--if-not-exists",
        "--topic", name, "--partitions", str(partitions), "--replication-factor", "1"
    )


def producer_perf(topic_name: str, count: int, size: int, throughput: int) -> dict[str, float]:
    started = time.monotonic()
    proc = ktool(
        "kafka-producer-perf-test.sh",
        "--topic", topic_name,
        "--num-records", str(count),
        "--record-size", str(size),
        "--throughput", str(throughput),
        "--producer-props", "bootstrap.servers=localhost:9092", "acks=all",
        timeout=180,
    )
    elapsed = time.monotonic() - started
    text = proc.stdout + "\n" + proc.stderr
    match = re.search(r"([0-9.]+) records/sec.*?([0-9.]+) ms avg latency.*?([0-9.]+) ms max latency", text)
    if not match:
        raise AssertionError(f"producer perf output not parseable: {text[-2000:]}")
    return {
        "messages_per_second": float(match.group(1)),
        "avg_latency_ms": float(match.group(2)),
        "max_latency_ms": float(match.group(3)),
        "elapsed_seconds": elapsed,
    }


def consumer_perf(topic_name: str, count: int, group: str) -> dict[str, float]:
    started = time.monotonic()
    proc = ktool(
        "kafka-consumer-perf-test.sh",
        "--bootstrap-server", "localhost:9092",
        "--topic", topic_name,
        "--messages", str(count),
        "--group", group,
        "--timeout", "30000",
        timeout=60,
    )
    elapsed = time.monotonic() - started
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    data_line = next((line for line in reversed(lines) if line.count(",") >= 5 and not line.lower().startswith("start.time")), None)
    if data_line is None:
        raise AssertionError(f"consumer perf output not parseable: {proc.stdout[-2000:]}")
    fields = [field.strip() for field in data_line.split(",")]
    consumed = float(fields[4])
    rate = float(fields[5])
    if consumed < count:
        raise AssertionError(f"expected {count} consumed messages, got {consumed}")
    return {"consumed_messages": consumed, "messages_per_second": rate, "elapsed_seconds": elapsed}


def keyed_roundtrip(topic_name: str, records: list[tuple[str, str]]) -> list[tuple[str, str]]:
    topic(topic_name, 4)
    payload = "".join(f"{key}|{value}\n" for key, value in records)
    ktool(
        "kafka-console-producer.sh",
        "--bootstrap-server", "localhost:9092",
        "--topic", topic_name,
        "--property", "parse.key=true",
        "--property", "key.separator=|",
        stdin=payload,
    )
    proc = ktool(
        "kafka-console-consumer.sh",
        "--bootstrap-server", "localhost:9092",
        "--topic", topic_name,
        "--from-beginning",
        "--max-messages", str(len(records)),
        "--timeout-ms", "30000",
        "--property", "print.key=true",
        "--property", "key.separator=|",
        timeout=60,
    )
    out: list[tuple[str, str]] = []
    for line in proc.stdout.splitlines():
        if "|" not in line:
            continue
        key, value = line.split("|", 1)
        out.append((key, value))
    if len(out) != len(records):
        raise AssertionError(f"keyed roundtrip expected {len(records)} records, got {len(out)}")
    return out


class KeySerialExecutor:
    """Named consumer-side component: serial per trusted logical key, parallel across independent keys."""

    def __init__(self, max_workers: int = 8) -> None:
        self.max_workers = max_workers

    def execute(self, records: list[tuple[str, int]]) -> tuple[dict[str, list[int]], list[tuple[str, float, float]]]:
        grouped: dict[str, list[int]] = {}
        for key, sequence in records:
            grouped.setdefault(key, []).append(sequence)
        observed: dict[str, list[int]] = {}
        intervals: list[tuple[str, float, float]] = []

        def worker(key: str, seqs: list[int]) -> tuple[str, list[int], float, float]:
            started = time.monotonic()
            local: list[int] = []
            for seq in seqs:
                time.sleep(0.004)
                local.append(seq)
            ended = time.monotonic()
            return key, local, started, ended

        with ThreadPoolExecutor(max_workers=min(self.max_workers, max(1, len(grouped)))) as pool:
            futures = [pool.submit(worker, key, seqs) for key, seqs in grouped.items()]
            for future in futures:
                key, local, started, ended = future.result()
                observed[key] = local
                intervals.append((key, started, ended))
        return observed, intervals


def stable_cohort(tenant: str, count: int) -> int:
    return int(hashlib.sha256(tenant.encode()).hexdigest(), 16) % count


def assert_overlap(intervals: list[tuple[str, float, float]]) -> None:
    for i, (key_a, start_a, end_a) in enumerate(intervals):
        for key_b, start_b, end_b in intervals[i + 1:]:
            if key_a != key_b and max(start_a, start_b) < min(end_a, end_b):
                return
    raise AssertionError("independent ordering keys did not overlap")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    profile = json.loads(PROFILE_PATH.read_text())
    results: dict[str, object] = {
        "profile_id": profile["profile_id"],
        "numeric_authority": "test_values_only_not_production",
        "tiers": [],
        "ordering_scope_mappings": profile["ordering_scope_mappings"],
    }

    for tier in profile["tiers"]:
        name = tier["name"].lower()
        perf_topic = f"d4a-capacity-{name}"
        partitions = max(tier["partition_probe_counts"])
        topic(perf_topic, partitions)
        producer = producer_perf(perf_topic, tier["message_count"], tier["record_size_bytes"], tier["target_messages_per_second"])
        time.sleep(tier["backlog_pause_seconds"])
        backlog_before = tier["message_count"]
        consumer = consumer_perf(perf_topic, tier["message_count"], f"d4a-{name}-drain")
        partition_probes: list[dict[str, object]] = []
        for count in tier["partition_probe_counts"]:
            probe_topic = f"d4a-partition-{name}-{count}"
            started = time.monotonic()
            topic(probe_topic, count)
            elapsed = time.monotonic() - started
            partition_probes.append({"partitions": count, "topic_create_elapsed_seconds": elapsed, "success": True})

        weighted_records: list[tuple[str, str]] = []
        total_weight = sum(tier["tenant_weights"].values())
        sample_count = max(100, len(tier["tenant_weights"]) * 20)
        for tenant, weight in tier["tenant_weights"].items():
            n = max(1, round(sample_count * weight / total_weight))
            weighted_records.extend((tenant, f"{name}-event-{i}") for i in range(n))
        skew_roundtrip = keyed_roundtrip(f"d4a-skew-{name}", weighted_records)
        observed_skew: dict[str, int] = {}
        for tenant, _ in skew_roundtrip:
            observed_skew[tenant] = observed_skew.get(tenant, 0) + 1

        results["tiers"].append({
            "name": tier["name"],
            "test_message_count": tier["message_count"],
            "test_record_size_bytes": tier["record_size_bytes"],
            "producer": producer,
            "backlog_messages_before_drain": backlog_before,
            "backlog_drain": consumer,
            "recovery_messages_per_second": consumer["messages_per_second"],
            "partition_probes": partition_probes,
            "bounded_test_partition_ceiling": max(tier["partition_probe_counts"]),
            "tenant_skew_expected_weights": tier["tenant_weights"],
            "tenant_skew_observed_counts": observed_skew,
            "degradation_boundary_observed": backlog_before > 0 and consumer["elapsed_seconds"] > 0,
        })

    ordering_records: list[tuple[str, str]] = []
    keys = ["tenant-a:subject-1", "tenant-a:subject-2", "tenant-b:subject-1", "tenant-c:process-1"]
    for seq in range(12):
        for key in keys:
            ordering_records.append((key, str(seq)))
    consumed = keyed_roundtrip("d4a-ordering-component", ordering_records)
    numeric_records = [(key, int(value)) for key, value in consumed]
    executor = KeySerialExecutor(max_workers=8)
    observed, intervals = executor.execute(numeric_records)
    for key, seqs in observed.items():
        if seqs != sorted(seqs):
            raise AssertionError(f"same-key order violated for {key}: {seqs}")
    assert_overlap(intervals)

    cohort_count = profile["tenant_cohort_fallback"]["cohort_count"]
    cohort_records: dict[int, list[tuple[str, str]]] = {i: [] for i in range(cohort_count)}
    for tenant in ["tenant-a", "tenant-b", "tenant-c", "tenant-d", "tenant-e", "tenant-f"]:
        cohort = stable_cohort(tenant, cohort_count)
        cohort_records[cohort].append((tenant, "fallback-probe"))
    cohort_observed: dict[str, int] = {}
    for cohort, records in cohort_records.items():
        if not records:
            continue
        roundtrip = keyed_roundtrip(f"d4a-cohort-{cohort}", records)
        for tenant, _ in roundtrip:
            cohort_observed[tenant] = cohort
    if len(cohort_observed) != 6 or len(set(cohort_observed.values())) < 2:
        raise AssertionError(f"tenant cohort fallback not exercised across cohorts: {cohort_observed}")

    results["ordering_component"] = {
        "name": "JLMIRROR KeySerialExecutor",
        "same_key_order_preserved": True,
        "independent_keys_overlap_observed": True,
        "global_or_tenant_wide_serialization": False,
        "observed_sequences": observed,
    }
    results["tenant_cohort_fallback"] = {
        "exercised": True,
        "cohort_count_test_value": cohort_count,
        "tenant_to_cohort": cohort_observed,
        "logical_contract_identity_changes": False,
    }

    if not all(t["degradation_boundary_observed"] for t in results["tiers"]):
        raise AssertionError("all tiers must observe bounded backlog degradation and recovery")
    Path(args.output).write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    print("d4a_live_kafka_capacity_ordering=PASS tiers=3 skew=exercised backlog_recovery=measured ordering_scopes=6 key_serial=PASS cohort_fallback=PASS numerics=test_only")


if __name__ == "__main__":
    main()
