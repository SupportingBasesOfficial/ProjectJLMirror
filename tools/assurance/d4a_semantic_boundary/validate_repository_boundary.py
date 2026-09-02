from __future__ import annotations

import ast
import inspect
import json
import textwrap
from pathlib import Path

from broker_boundary import BrokerFacingPath, discover_broker_facing_paths, forbidden_kafka_tokens
from consumer_registration_gate import discover_consumer_manifests

ROOT = Path(__file__).resolve().parents[3]
INVENTORY = ROOT / "implementation/d4-eventing-async/source-evidence/semantic-boundary/boundary-inventory.json"

EXPECTED_PATH_CLASSES = {"OutboxDispatchPath", "ConsumerReceivePath", "InboxAcknowledgePath", "ReplayDispatchPath"}
EXPECTED_PATH_IDS = {"outbox_dispatch", "consumer_receive", "inbox_acknowledge", "replay_dispatch"}
EXPECTED_IMPLEMENTATION_ROOTS = ["implementation", "src"]
EXPECTED_CONSUMER_DISCOVERY_ROOT = "implementation"
EXPECTED_REGISTRATION_ENTRYPOINT = "tools/assurance/d4a_semantic_boundary/consumer_registration_gate.py"
EXPECTED_REGISTRATION_FUNCTION = "register_consumer"
EXPECTED_DEPENDENCY_CALLS = {
    "OutboxDispatchPath": {"_broker.publish"},
    "ConsumerReceivePath": {"_broker.receive"},
    "InboxAcknowledgePath": {"_verifier.assert_durable", "_broker.acknowledge"},
    "ReplayDispatchPath": {"_broker.publish"},
}
KAFKA_IMPORT_PREFIXES = ("kafka", "aiokafka", "confluent_kafka")
KAFKA_NATIVE_NAMES = {"offset", "partition", "consumer_group", "rebalance", "transactional_id"}
CODE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".go", ".rs", ".java", ".kt", ".cs"}
GENERIC_BROKER_MARKERS = ("BrokerPort", "_broker.publish", "_broker.receive", "_broker.acknowledge")


def _call_target(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Attribute):
        owner = func.value
        if isinstance(owner.value, ast.Name) and owner.value.id == "self":
            return f"{owner.attr}.{func.attr}"
    if isinstance(func, ast.Name):
        return func.id
    return ast.unparse(func)


def dependency_calls(source: str) -> set[str]:
    tree = ast.parse(textwrap.dedent(source))
    return {_call_target(node) for node in ast.walk(tree) if isinstance(node, ast.Call)}


def dependency_attributes(source: str) -> set[str]:
    tree = ast.parse(textwrap.dedent(source))
    accesses: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute):
            owner = node.value
            if isinstance(owner.value, ast.Name) and owner.value.id == "self" and owner.attr in {"_broker", "_verifier"}:
                accesses.add(f"{owner.attr}.{node.attr}")
    return accesses


def scan_python_for_direct_kafka(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
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
    markers = ("confluent_kafka", "confluent-kafka", "aiokafka", "kafkajs", "org.apache.kafka", "segmentio/kafka-go", "sarama")
    return sorted(marker for marker in markers if marker in text)


def scan_governed_implementation(inventory: dict) -> tuple[list[str], list[str]]:
    kafka_findings: list[str] = []
    broker_marker_findings: list[str] = []
    boundary_module = inventory["broker_boundary_module"]
    for root_value in inventory["implementation_code_roots"]:
        root = ROOT / root_value
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in CODE_SUFFIXES:
                continue
            rel = path.relative_to(ROOT).as_posix()
            direct = scan_python_for_direct_kafka(path) if path.suffix == ".py" else scan_nonpython_for_direct_kafka(path)
            kafka_findings.extend(f"{rel}:{item}" for item in direct)
            text = path.read_text(encoding="utf-8", errors="ignore")
            for marker in GENERIC_BROKER_MARKERS:
                if marker in text and rel != boundary_module:
                    broker_marker_findings.append(f"{rel}:{marker}")
    return sorted(kafka_findings), sorted(broker_marker_findings)


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
    assert set(discovered) == EXPECTED_PATH_CLASSES
    for class_name, path_type in discovered.items():
        assert issubclass(path_type, BrokerFacingPath)
        source = inspect.getsource(path_type)
        leaks = forbidden_kafka_tokens(source)
        assert not leaks, f"{class_name} leaks physical Kafka primitives: {leaks}"
        calls = dependency_calls(source)
        attrs = dependency_attributes(source)
        assert calls == EXPECTED_DEPENDENCY_CALLS[class_name], f"{class_name} call-graph drift: {sorted(calls)}"
        assert attrs <= EXPECTED_DEPENDENCY_CALLS[class_name], f"{class_name} dependency attribute bypass: {sorted(attrs)}"

    direct_kafka, generic_broker_bypass = scan_governed_implementation(inventory)
    assert direct_kafka == [], f"repository implementation contains direct Kafka bypass: {direct_kafka}"
    assert generic_broker_bypass == [], f"repository implementation contains broker path outside shared boundary: {generic_broker_bypass}"

    consumers = discover_consumer_manifests(ROOT / EXPECTED_CONSUMER_DISCOVERY_ROOT)
    assert consumers and len(consumers) == len(set(consumers))

    entrypoint = ROOT / EXPECTED_REGISTRATION_ENTRYPOINT
    source = entrypoint.read_text(encoding="utf-8")
    assert f"def {EXPECTED_REGISTRATION_FUNCTION}(" in source
    assert "issue_registration_permit(manifest)" in source
    assert "register_validated" in source
    assert "SUPPORTED_EFFECT_BINDINGS" in source

    helper_source = """
class BadPath:
    def run(self, message):
        return helper(self._broker)
"""
    constructor_bypass = """
class BadPath:
    def __init__(self, broker):
        helper(broker)
        self._broker = broker
    def run(self, message):
        return self._broker.publish(message)
"""
    alias_source = """
class BadPath:
    def run(self):
        return self._broker.record_position
"""
    assert dependency_calls(helper_source) == {"helper"}
    assert dependency_calls(constructor_bypass) == {"helper", "_broker.publish"}
    assert dependency_attributes(alias_source) == {"_broker.record_position"}

    print(
        f"d4a_repository_boundary=PASS broker_paths={len(discovered)} consumers={len(consumers)} "
        "direct_kafka_bypass=0 generic_broker_bypass=0 call_graph=exact roots=implementation+src"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
