from __future__ import annotations

import ast
import json
from pathlib import Path

from broker_boundary import (
    BrokerFacingPath,
    discover_broker_facing_paths,
    forbidden_kafka_tokens,
)
from consumer_registration_gate import discover_consumer_manifests

ROOT = Path(__file__).resolve().parents[3]
INVENTORY = ROOT / "implementation/d4-eventing-async/source-evidence/semantic-boundary/boundary-inventory.json"

EXPECTED_PATH_CLASSES = {
    "OutboxDispatchPath",
    "ConsumerReceivePath",
    "InboxAcknowledgePath",
    "ReplayDispatchPath",
}
EXPECTED_PATH_IDS = {
    "outbox_dispatch",
    "consumer_receive",
    "inbox_acknowledge",
    "replay_dispatch",
}
EXPECTED_IMPLEMENTATION_ROOTS = ["implementation/d4-eventing-async"]
EXPECTED_CONSUMER_DISCOVERY_ROOT = "implementation/d4-eventing-async"
EXPECTED_REGISTRATION_ENTRYPOINT = "tools/assurance/d4a_semantic_boundary/consumer_registration_gate.py"
EXPECTED_REGISTRATION_FUNCTION = "register_consumer"
KAFKA_IMPORT_PREFIXES = ("kafka", "aiokafka", "confluent_kafka")
KAFKA_NATIVE_NAMES = {"offset", "partition", "consumer_group", "rebalance", "transactional_id"}
CODE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".go", ".rs", ".java", ".kt", ".cs"}


def scan_python_for_direct_kafka(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    findings: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(KAFKA_IMPORT_PREFIXES):
                    findings.add(f"import:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith(KAFKA_IMPORT_PREFIXES):
                findings.add(f"import:{module}")
        elif isinstance(node, ast.Attribute) and node.attr in KAFKA_NATIVE_NAMES:
            findings.add(f"attribute:{node.attr}")
    return sorted(findings)


def scan_nonpython_for_direct_kafka(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    markers = (
        "confluent_kafka",
        "confluent-kafka",
        "aiokafka",
        "kafkajs",
        "org.apache.kafka",
        "segmentio/kafka-go",
        "sarama",
    )
    return sorted(marker for marker in markers if marker in text)


def scan_governed_implementation(inventory: dict) -> list[str]:
    findings: list[str] = []
    for root_value in inventory["implementation_code_roots"]:
        root = ROOT / root_value
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in CODE_SUFFIXES:
                continue
            rel = path.relative_to(ROOT).as_posix()
            direct = scan_python_for_direct_kafka(path) if path.suffix == ".py" else scan_nonpython_for_direct_kafka(path)
            for item in direct:
                findings.append(f"{rel}:{item}")
    return sorted(findings)


def main() -> int:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    inventory_paths = inventory["broker_facing_paths"]
    assert {item["class_name"] for item in inventory_paths} == EXPECTED_PATH_CLASSES
    assert {item["path_id"] for item in inventory_paths} == EXPECTED_PATH_IDS
    assert len(inventory_paths) == 4
    assert inventory["implementation_code_roots"] == EXPECTED_IMPLEMENTATION_ROOTS
    assert inventory["consumer_manifest_discovery_root"] == EXPECTED_CONSUMER_DISCOVERY_ROOT
    assert inventory["consumer_registration_entrypoint"] == EXPECTED_REGISTRATION_ENTRYPOINT
    assert inventory["consumer_registration_function"] == EXPECTED_REGISTRATION_FUNCTION

    discovered = discover_broker_facing_paths()
    assert set(discovered) == EXPECTED_PATH_CLASSES, (
        f"broker-facing discovery/inventory mismatch: discovered={sorted(discovered)} expected={sorted(EXPECTED_PATH_CLASSES)}"
    )
    for class_name, path_type in discovered.items():
        assert issubclass(path_type, BrokerFacingPath)
        source = __import__("inspect").getsource(path_type)
        leaks = forbidden_kafka_tokens(source)
        assert not leaks, f"{class_name} leaks physical Kafka primitives: {leaks}"

    direct_kafka = scan_governed_implementation(inventory)
    assert direct_kafka == [], f"governed D4 implementation contains direct Kafka bypass: {direct_kafka}"

    implementation_root = ROOT / EXPECTED_CONSUMER_DISCOVERY_ROOT
    consumers = discover_consumer_manifests(implementation_root)
    assert consumers, "no consumer manifests discovered"
    assert len(consumers) == len(set(consumers)), "consumer manifest discovery contains duplicates"

    entrypoint = ROOT / EXPECTED_REGISTRATION_ENTRYPOINT
    assert entrypoint.exists(), "canonical consumer registration entrypoint missing"
    source = entrypoint.read_text(encoding="utf-8")
    assert f"def {EXPECTED_REGISTRATION_FUNCTION}(" in source
    assert "issue_registration_permit(manifest)" in source
    assert "register_validated" in source

    print(
        "d4a_repository_boundary=PASS "
        f"broker_paths={len(discovered)} consumers={len(consumers)} direct_kafka_bypass=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
