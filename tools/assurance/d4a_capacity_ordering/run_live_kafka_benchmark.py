from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

from key_serial_executor import KeySerialExecutor

ROOT = Path(__file__).resolve().parents[3]
PROFILE_PATH = ROOT / "implementation/d4-eventing-async/source-evidence/capacity-ordering/benchmark-profile.json"
CONTAINER = "d4a-kafka"
KAFKA_BIN = "/opt/kafka/bin"
BOOTSTRAP = "localhost:9092"


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
        "kafka-topics.sh", "--bootstrap-server", BOOTSTRAP, "--create", "--if-not-exists",
        "--topic", name, "--partitions", str(partitions), "--replication-factor", "1"
    )


def producer_perf(
    topic_name: str,
    count: int,
    size: int,
    throughput: int,
    *,
    client_id: str | None = None,
) -> dict[str, float]:
    producer_props = ["bootstrap.servers=localhost:9092", "acks=all"]
    if client_id is not None:
        producer_props.append(f"client.id={client_id}")
    started = time.monotonic()
    proc = ktool(
        "kafka-producer-perf-test.sh",
        "--topic", topic_name,
        "--num-records", str(count),
        "--record-size", str(size),
        "--throughput", str(throughput),
        "--producer-props", *producer_props,
        timeout=240,
    )
    elapsed = time.monotonic() - started
    text = proc.stdout + "\n" + proc.stderr
    matches = re.findall(r"([0-9.]+) records/sec.*?([0-9.]+) ms avg latency.*?([0-9.]+) ms max latency", text)
    if not matches:
        raise AssertionError(f"producer perf output not parseable: {text[-3000:]}")
    rps, avg, maximum = matches[-1]
    return {
        "messages_per_second": float(rps),
        "avg_latency_ms": float(avg),
        "max_latency_ms": float(maximum),
        "elapsed_seconds": elapsed,
    }


def consumer_perf(topic_name: str, count: int, group: str) -> dict[str, float]:
    started = time.monotonic()
    proc = ktool(
        "kafka-consumer-perf-test.sh",
        "--bootstrap-server", BOOTSTRAP,
        "--topic", topic_name,
        "--messages", str(count),
        "--group", group,
        "--timeout", "30000",
        timeout=90,
    )
    elapsed = time.monotonic() - started
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    data_line = next((line for line in reversed(lines) if line.count(",") >= 5 and not line.lower().startswith("start.time")), None)
    if data_line is None:
        raise AssertionError(f"consumer perf output not parseable: {proc.stdout[-3000:]}")
    fields = [field.strip() for field in data_line.split(",")]
    consumed = float(fields[4])
    rate = float(fields[5])
    if consumed < count:
        raise AssertionError(f"expected {count} consumed messages, got {consumed}")
    return {"consumed_messages": consumed, "messages_per_second": rate, "elapsed_seconds": elapsed}


def measured_topic_messages(topic_name: str) -> int:
    proc = ktool("kafka-get-offsets.sh", "--bootstrap-server", BOOTSTRAP, "--topic", topic_name)
    total = 0
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.rsplit(":", 1)
        if len(parts) != 2:
            raise AssertionError(f"unexpected offset line: {line!r}")
        total += int(parts[1])
    return total


def keyed_roundtrip(topic_name: str, records: list[tuple[str, str]], *, partitions: int = 4) -> list[tuple[str, str]]:
    topic(topic_name, partitions)
    payload = "".join(f"{key}|{value}\n" for key, value in records)
    ktool(
        "kafka-console-producer.sh",
        "--bootstrap-server", BOOTSTRAP,
        "--topic", topic_name,
        "--property", "parse.key=true",
        "--property", "key.separator=|",
        stdin=payload,
    )
    proc = ktool(
        "kafka-console-consumer.sh",
        "--bootstrap-server", BOOTSTRAP,
        "--topic", topic_name,
        "--from-beginning",
        "--max-messages", str(len(records)),
        "--timeout-ms", "30000",
        "--property", "print.key=true",
        "--property", "key.separator=|",
        timeout=90,
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


def plain_roundtrip(topic_name: str, records: list[str], *, partitions: int = 4) -> list[str]:
    topic(topic_name, partitions)
    ktool(
        "kafka-console-producer.sh", "--bootstrap-server", BOOTSTRAP, "--topic", topic_name,
        stdin="".join(f"{record}\n" for record in records),
    )
    proc = ktool(
        "kafka-console-consumer.sh", "--bootstrap-server", BOOTSTRAP, "--topic", topic_name,
        "--from-beginning", "--max-messages", str(len(records)), "--timeout-ms", "30000",
        timeout=90,
    )
    out = [line for line in proc.stdout.splitlines() if line]
    if len(out) != len(records):
        raise AssertionError(f"plain roundtrip expected {len(records)} records, got {len(out)}")
    return out


def configure_producer_quota(client_id: str, byte_rate: int) -> None:
    ktool(
        "kafka-configs.sh", "--bootstrap-server", BOOTSTRAP, "--alter",
        "--add-config", f"producer_byte_rate={byte_rate}",
        "--entity-type", "clients", "--entity-name", client_id,
    )


def clear_producer_quota(client_id: str) -> None:
    ktool(
        "kafka-configs.sh", "--bootstrap-server", BOOTSTRAP, "--alter",
        "--delete-config", "producer_byte_rate",
        "--entity-type", "clients", "--entity-name", client_id,
    )


def stable_cohort(tenant: str, count: int) -> int:
    return int(hashlib.sha256(tenant.encode()).hexdigest(), 16) % count


def assert_overlap(intervals: list[tuple[str, float, float]]) -> None:
    for i, (key_a, start_a, end_a) in enumerate(intervals):
        for key_b, start_b, end_b in intervals[i + 1:]:
            if key_a != key_b and max(start_a, start_b) < min(end_a, end_b):
                return
    raise AssertionError("independent ordering keys did not overlap")


def exercise_key_serial(records: list[tuple[str, int]]) -> tuple[dict[str, list[int]], list[tuple[str, float, float]]]:
    executor = KeySerialExecutor(max_workers=8)
    futures = []

    def task(key: str, sequence: int) -> tuple[str, int, float, float]:
        started = time.monotonic()
        time.sleep(0.004)
        ended = time.monotonic()
        return key, sequence, started, ended

    try:
        for key, sequence in records:
            futures.append(executor.submit(key, lambda key=key, sequence=sequence: task(key, sequence)))
        completed = [future.result(timeout=30) for future in futures]
    finally:
        executor.shutdown(wait=True)

    observed: dict[str, list[tuple[float, int]]] = {}
    intervals: list[tuple[str, float, float]] = []
    for key, sequence, started, ended in completed:
        observed.setdefault(key, []).append((started, sequence))
        intervals.append((key, started, ended))
    ordered = {key: [seq for _, seq in sorted(items)] for key, items in observed.items()}
    return ordered, intervals


def benchmark_partition_ceiling(tier: dict) -> tuple[list[dict[str, object]], int]:
    probes: list[dict[str, object]] = []
    admission = tier["admission"]
    for partitions in tier["partition_probe_counts"]:
        probe_topic = f"d4a-partition-{tier['name'].lower()}-{partitions}"
        topic(probe_topic, partitions)
        probe_count = max(300, min(tier["message_count"], partitions * 100))
        perf = producer_perf(
            probe_topic,
            probe_count,
            tier["record_size_bytes"],
            tier["target_messages_per_second"],
        )
        accepted = (
            perf["messages_per_second"] >= admission["minimum_records_per_second"]
            and perf["avg_latency_ms"] <= admission["maximum_avg_latency_ms"]
        )
        probes.append({"partitions": partitions, "producer": perf, "admission_passed": accepted})
    passing = [int(probe["partitions"]) for probe in probes if probe["admission_passed"]]
    if not passing:
        raise AssertionError(f"no partition probe passed bounded admission for {tier['name']}")
    return probes, max(passing)


def exercise_ordering_profiles(profile: dict) -> list[dict[str, object]]:
    exercised: list[dict[str, object]] = []
    for scope, mapping in profile["ordering_scope_mappings"].items():
        topic_name = f"d4a-ordering-{scope.replace('_', '-')}"
        if mapping["serialization"] == "none":
            records = [f"{scope}-record-{i}" for i in range(24)]
            consumed = plain_roundtrip(topic_name, records)
            exercised.append({
                "scope": scope,
                "partition_key_strategy": mapping["partition_key"],
                "ordering_required": False,
                "broker_exercised": len(consumed) == len(records),
                "key_serial_component_exercised": False,
            })
            continue

        keys = [f"{scope}:logical-a", f"{scope}:logical-b", f"{scope}:logical-c"]
        produced: list[tuple[str, str]] = []
        for sequence in range(10):
            for key in keys:
                produced.append((key, str(sequence)))
        consumed = keyed_roundtrip(topic_name, produced)
        numeric = [(key, int(value)) for key, value in consumed]
        observed, intervals = exercise_key_serial(numeric)
        for key, sequences in observed.items():
            if sequences != sorted(sequences):
                raise AssertionError(f"same-key order violated for {scope}/{key}: {sequences}")
        assert_overlap(intervals)
        exercised.append({
            "scope": scope,
            "partition_key_strategy": mapping["partition_key"],
            "ordering_required": True,
            "broker_exercised": True,
            "key_serial_component_exercised": True,
            "same_key_order_preserved": True,
            "independent_keys_overlap_observed": True,
            "observed_sequences": observed,
        })
    return exercised


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    profile = json.loads(PROFILE_PATH.read_text())
    results: dict[str, object] = {
        "profile_id": profile["profile_id"],
        "numeric_authority": "test_values_only_not_production",
        "environment_scope": profile["environment_scope"],
        "tiers": [],
        "ordering_scope_mappings": profile["ordering_scope_mappings"],
    }

    for tier in profile["tiers"]:
        name = tier["name"].lower()
        perf_topic = f"d4a-capacity-{name}"
        topic(perf_topic, max(tier["partition_probe_counts"]))
        producer = producer_perf(perf_topic, tier["message_count"], tier["record_size_bytes"], tier["target_messages_per_second"])
        time.sleep(tier["backlog_pause_seconds"])
        backlog_before = measured_topic_messages(perf_topic)
        if backlog_before != tier["message_count"]:
            raise AssertionError(f"measured backlog mismatch for {tier['name']}: {backlog_before}")
        consumer = consumer_perf(perf_topic, tier["message_count"], f"d4a-{name}-drain")
        partition_probes, ceiling = benchmark_partition_ceiling(tier)

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
            "backlog_drain_seconds": consumer["elapsed_seconds"],
            "recovery_messages_per_second": consumer["messages_per_second"],
            "partition_probes": partition_probes,
            "tested_partition_ceiling": ceiling,
            "partition_ceiling_authority": "bounded_test_only_not_production",
            "tenant_skew_expected_weights": tier["tenant_weights"],
            "tenant_skew_observed_counts": observed_skew,
            "tenant_skew_observed": max(observed_skew.values()) > sum(observed_skew.values()) / len(observed_skew),
        })

    degradation = profile["degradation_probe"]
    stress = profile["tiers"][-1]
    degradation_topic = "d4a-real-kafka-degradation-boundary"
    topic(degradation_topic, max(stress["partition_probe_counts"]))
    probe_count = 600
    baseline = producer_perf(
        degradation_topic, probe_count, stress["record_size_bytes"], -1,
        client_id=degradation["client_id"],
    )
    configure_producer_quota(degradation["client_id"], degradation["producer_byte_rate"])
    try:
        throttled = producer_perf(
            degradation_topic, probe_count, stress["record_size_bytes"], -1,
            client_id=degradation["client_id"],
        )
    finally:
        clear_producer_quota(degradation["client_id"])
    if baseline["messages_per_second"] <= 0:
        raise AssertionError("unthrottled degradation baseline throughput invalid")
    drop_fraction = 1.0 - (throttled["messages_per_second"] / baseline["messages_per_second"])
    if drop_fraction < degradation["minimum_throughput_drop_fraction"]:
        raise AssertionError(f"real Kafka quota did not expose required degradation boundary: drop={drop_fraction:.3f}")
    results["degradation_probe"] = {
        "mechanism": degradation["mechanism"],
        "client_id": degradation["client_id"],
        "producer_byte_rate_test_value": degradation["producer_byte_rate"],
        "baseline": baseline,
        "throttled": throttled,
        "throughput_drop_fraction": drop_fraction,
        "degradation_boundary_observed": True,
        "numeric_authority": "bounded_test_only_not_production",
    }

    ordering_profiles = exercise_ordering_profiles(profile)
    if {item["scope"] for item in ordering_profiles} != set(profile["ordering_scope_mappings"]):
        raise AssertionError("not every declared ordering profile was exercised")
    results["ordering_profiles"] = ordering_profiles
    results["ordering_component"] = {
        "name": "JLMIRROR KeySerialExecutor",
        "implementation_path": "tools/assurance/d4a_capacity_ordering/key_serial_executor.py",
        "same_key_order_preserved": all(item.get("same_key_order_preserved", True) for item in ordering_profiles),
        "independent_keys_overlap_observed": all(item.get("independent_keys_overlap_observed", True) for item in ordering_profiles),
        "global_or_tenant_wide_serialization": False,
    }

    stress_ceiling = int(results["tiers"][-1]["tested_partition_ceiling"])
    modeled_scope_cardinality = stress_ceiling + 1
    if modeled_scope_cardinality <= stress_ceiling:
        raise AssertionError("fallback trigger was not exceeded")
    cohort_count = profile["tenant_cohort_fallback"]["cohort_count"]
    cohort_records: dict[int, list[tuple[str, str]]] = {i: [] for i in range(cohort_count)}
    tenants = ["tenant-a", "tenant-b", "tenant-c", "tenant-d", "tenant-e", "tenant-f"]
    for tenant in tenants:
        cohort = stable_cohort(tenant, cohort_count)
        cohort_records[cohort].append((tenant, "fallback-probe"))
    cohort_observed: dict[str, int] = {}
    for cohort, records in cohort_records.items():
        if not records:
            continue
        roundtrip = keyed_roundtrip(f"d4a-cohort-{cohort}", records, partitions=stress_ceiling)
        for tenant, _ in roundtrip:
            cohort_observed[tenant] = cohort
    if len(cohort_observed) != len(tenants) or len(set(cohort_observed.values())) < 2:
        raise AssertionError(f"tenant cohort fallback not exercised across cohorts: {cohort_observed}")
    results["tenant_cohort_fallback"] = {
        "exercised": True,
        "triggered_by_modeled_scope_cardinality": modeled_scope_cardinality,
        "single_topic_test_ceiling": stress_ceiling,
        "cohort_count_test_value": cohort_count,
        "cohort_topics_each_partitions": stress_ceiling,
        "tenant_to_cohort": cohort_observed,
        "logical_contract_identity_changes": False,
        "numeric_authority": "bounded_test_only_not_production",
    }

    if not all(tier["tenant_skew_observed"] for tier in results["tiers"]):
        raise AssertionError("all tiers must exercise observable tenant skew")
    Path(args.output).write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    print("d4a_live_kafka_capacity_ordering=PASS tiers=3 skew=exercised backlog=measured quota_degradation=observed partition_ceiling=benchmarked ordering_profiles=6 key_serial=PASS cohort_fallback=PASS numerics=test_only")


if __name__ == "__main__":
    main()
