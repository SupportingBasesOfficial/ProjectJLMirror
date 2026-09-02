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
BOUNDARY_SOURCE = ROOT / "tools/assurance/d4a_semantic_boundary/broker_boundary.py"

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
KAFKA_TEXT_MARKERS = (
    "confluent_kafka", "confluent-kafka", "confluent.kafka", "aiokafka", "kafkajs",
    "node-rdkafka", "rdkafka", "librdkafka", "@confluentinc/kafka-javascript",
    "org.apache.kafka", "org.springframework.kafka", "segmentio/kafka-go", "shopify/sarama",
    "ibm/sarama", "twmb/franz-go", "rust-rdkafka",
)
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


def _broker_base_aliases(tree: ast.AST) -> set[str]:
    aliases = {"BrokerFacingPath"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "BrokerFacingPath": aliases.add(alias.asname or alias.name)
    return aliases


def _display_path(path: Path) -> str:
    try: return path.relative_to(ROOT).as_posix()
    except ValueError: return path.as_posix()


def discover_broker_path_declarations(paths: list[Path]) -> dict[str, str]:
    discovered: dict[str, str] = {}
    for path in paths:
        if not path.exists() or path.suffix != ".py": continue
        try: tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError): continue
        aliases = _broker_base_aliases(tree)
        for node in tree.body:
            if not isinstance(node, ast.ClassDef): continue
            base_names = {base.id if isinstance(base, ast.Name) else base.attr for base in node.bases if isinstance(base, (ast.Name, ast.Attribute))}
            if base_names & aliases: discovered[f"{_display_path(path)}:{node.name}"] = node.name
    return discovered


def governed_python_sources(inventory: dict) -> list[Path]:
    paths = [BOUNDARY_SOURCE]
    for root_value in inventory["implementation_code_roots"]:
        root = ROOT / root_value
        if root.exists(): paths.extend(sorted(root.rglob("*.py")))
    return list(dict.fromkeys(paths))


def scan_python_for_direct_kafka(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    findings: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(KAFKA_IMPORT_PREFIXES): findings.add(f"import:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith(KAFKA_IMPORT_PREFIXES): findings.add(f"import:{module}")
        elif isinstance(node, ast.Attribute) and node.attr in KAFKA_NATIVE_NAMES:
            findings.add(f"attribute:{node.attr}")
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    findings.update(f"marker:{marker}" for marker in KAFKA_TEXT_MARKERS if marker in text)
    return sorted(findings)


def scan_nonpython_for_direct_kafka(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    return sorted(marker for marker in KAFKA_TEXT_MARKERS if marker in text)


def scan_governed_implementation(inventory: dict) -> tuple[list[str], list[str]]:
    kafka_findings, broker_marker_findings = [], []
    boundary_module = inventory["broker_boundary_module"]
    for root_value in inventory["implementation_code_roots"]:
        root = ROOT / root_value
        if not root.exists(): continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in CODE_SUFFIXES: continue
            rel = path.relative_to(ROOT).as_posix()
            direct = scan_python_for_direct_kafka(path) if path.suffix == ".py" else scan_nonpython_for_direct_kafka(path)
            kafka_findings.extend(f"{rel}:{item}" for item in direct)
            text = path.read_text(encoding="utf-8", errors="ignore")
            for marker in GENERIC_BROKER_MARKERS:
                if marker in text and rel != boundary_module: broker_marker_findings.append(f"{rel}:{marker}")
    return sorted(kafka_findings), sorted(broker_marker_findings)


def main() -> int:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8")); inventory_paths = inventory["broker_facing_paths"]
    assert {i["class_name"] for i in inventory_paths} == EXPECTED_PATH_CLASSES
    assert {i["path_id"] for i in inventory_paths} == EXPECTED_PATH_IDS and len(inventory_paths) == 4
    assert inventory["implementation_code_roots"] == EXPECTED_IMPLEMENTATION_ROOTS
    assert inventory["consumer_manifest_discovery_root"] == EXPECTED_CONSUMER_DISCOVERY_ROOT
    assert inventory["consumer_registration_entrypoint"] == EXPECTED_REGISTRATION_ENTRYPOINT
    assert inventory["consumer_registration_function"] == EXPECTED_REGISTRATION_FUNCTION
    runtime_discovered = discover_broker_facing_paths(); assert set(runtime_discovered) == EXPECTED_PATH_CLASSES
    static_discovered = discover_broker_path_declarations(governed_python_sources(inventory))
    assert set(static_discovered.values()) == EXPECTED_PATH_CLASSES and len(static_discovered) == len(EXPECTED_PATH_CLASSES)
    for class_name, path_type in runtime_discovered.items():
        source = inspect.getsource(path_type); assert not forbidden_kafka_tokens(source)
        calls = dependency_calls(source); attrs = dependency_attributes(source)
        assert calls == EXPECTED_DEPENDENCY_CALLS[class_name]; assert attrs <= EXPECTED_DEPENDENCY_CALLS[class_name]
    direct_kafka, generic_broker_bypass = scan_governed_implementation(inventory)
    assert direct_kafka == [], f"repository implementation contains direct Kafka bypass: {direct_kafka}"
    assert generic_broker_bypass == [], f"repository implementation contains broker path outside shared boundary: {generic_broker_bypass}"
    consumers = discover_consumer_manifests(ROOT / EXPECTED_CONSUMER_DISCOVERY_ROOT); assert consumers and len(consumers) == len(set(consumers))
    entrypoint = ROOT / EXPECTED_REGISTRATION_ENTRYPOINT; source = entrypoint.read_text(encoding="utf-8")
    for marker in (f"def {EXPECTED_REGISTRATION_FUNCTION}(", "issue_registration_permit(manifest)", "register_validated", "SUPPORTED_EFFECT_BINDINGS", "_ISSUED_PERMITS"):
        assert marker in source
    constructor_bypass = """class BadPath:\n    def __init__(self, broker):\n        helper(broker)\n        self._broker = broker\n    def run(self, message):\n        return self._broker.publish(message)\n"""
    assert dependency_calls(constructor_bypass) == {"helper", "_broker.publish"}
    marker_fixture = "using Confluent.Kafka; import org.springframework.kafka.core.KafkaTemplate; // node-rdkafka rdkafka"
    lowered = marker_fixture.lower()
    assert all(marker in lowered for marker in ("confluent.kafka", "org.springframework.kafka", "node-rdkafka", "rdkafka"))
    assert all(marker in KAFKA_TEXT_MARKERS for marker in ("confluent.kafka", "org.springframework.kafka", "node-rdkafka", "rdkafka"))
    print(f"d4a_repository_boundary=PASS broker_paths={len(runtime_discovered)} consumers={len(consumers)} direct_kafka_bypass=0 generic_broker_bypass=0 static_subclasses=exact call_graph=exact roots=implementation+src")
    return 0


if __name__ == "__main__": raise SystemExit(main())
