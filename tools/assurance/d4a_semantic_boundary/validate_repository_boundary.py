from __future__ import annotations

import ast
import inspect
import json
import re
import textwrap
from pathlib import Path

from broker_boundary import BrokerFacingPath, discover_broker_facing_paths, forbidden_kafka_tokens
from consumer_registration_gate import discover_consumer_manifests

ROOT = Path(__file__).resolve().parents[3]
INVENTORY = ROOT / "implementation/d4-eventing-async/source-evidence/semantic-boundary/boundary-inventory.json"
ASSURANCE_DIR = ROOT / "tools/assurance/d4a_semantic_boundary"
BOUNDARY_SOURCE = ASSURANCE_DIR / "broker_boundary.py"
EFFECT_PROTECTION_SOURCE = ASSURANCE_DIR / "effect_protection.py"
REGISTRATION_SOURCE = ASSURANCE_DIR / "consumer_registration_gate.py"
ASSURANCE_ENTRY_SOURCES = [EFFECT_PROTECTION_SOURCE, REGISTRATION_SOURCE]

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
KAFKA_TRANSACTION_METHODS = {
    "begin_transaction",
    "commit_transaction",
    "abort_transaction",
    "send_offsets_to_transaction",
}
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


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _base_leaf_name(base: ast.expr) -> str | None:
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    return None


def discover_broker_path_declarations(paths: list[Path]) -> dict[str, str]:
    """Discover descendants through inheritance and imported aliases across governed sources."""
    classes: list[tuple[Path, str, set[str]]] = []
    imported_aliases: list[tuple[str, str]] = []
    for path in paths:
        if not path.exists() or path.suffix != ".py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported_aliases.append((alias.asname or alias.name, alias.name))
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                bases = {name for base in node.bases if (name := _base_leaf_name(base)) is not None}
                classes.append((path, node.name, bases))

    descendant_symbols = {"BrokerFacingPath"}
    changed = True
    while changed:
        changed = False
        for local_name, imported_name in imported_aliases:
            if imported_name in descendant_symbols and local_name not in descendant_symbols:
                descendant_symbols.add(local_name)
                changed = True
        for _, class_name, bases in classes:
            if class_name not in descendant_symbols and bases & descendant_symbols:
                descendant_symbols.add(class_name)
                changed = True

    discovered: dict[str, str] = {}
    for path, class_name, bases in classes:
        if class_name != "BrokerFacingPath" and class_name in descendant_symbols and bases:
            discovered[f"{_display_path(path)}:{class_name}"] = class_name
    return discovered


def governed_python_sources(inventory: dict) -> list[Path]:
    paths = [BOUNDARY_SOURCE]
    for root_value in inventory["implementation_code_roots"]:
        root = ROOT / root_value
        if root.exists():
            paths.extend(sorted(root.rglob("*.py")))
    return list(dict.fromkeys(paths))


def _candidate_local_modules(base: Path, module: str) -> list[Path]:
    module_path = Path(*module.split(".")) if module else Path()
    target = base / module_path
    return [target.with_suffix(".py"), target / "__init__.py"]


def _package_initializers(candidate: Path, assurance_root: Path) -> list[Path]:
    """Return existing package initializers Python executes before a nested local module."""
    initializers: list[Path] = []
    current = candidate.parent
    root = assurance_root.resolve()
    while True:
        try:
            current.resolve().relative_to(root)
        except ValueError:
            break
        init = current / "__init__.py"
        if init.exists() and init.is_file() and init != candidate:
            initializers.append(init)
        if current.resolve() == root:
            break
        current = current.parent
    return initializers


def _local_import_targets(path: Path, assurance_dir: Path) -> list[Path]:
    """Resolve nested/relative modules and every executable parent-package initializer."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    targets: list[Path] = []
    assurance_root = assurance_dir.resolve()

    def add_candidate(candidate: Path) -> None:
        try:
            candidate.resolve().relative_to(assurance_root)
        except ValueError:
            return
        if candidate.exists() and candidate.is_file() and candidate.suffix == ".py" and candidate != path:
            targets.extend(_package_initializers(candidate, assurance_dir))
            targets.append(candidate)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for candidate in _candidate_local_modules(assurance_dir, alias.name):
                    add_candidate(candidate)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = path.parent
                for _ in range(node.level - 1):
                    base = base.parent
            else:
                base = assurance_dir
            module = node.module or ""
            module_candidates = _candidate_local_modules(base, module)
            for candidate in module_candidates:
                add_candidate(candidate)
            module_dir = base / Path(*module.split(".")) if module else base
            for alias in node.names:
                if alias.name == "*":
                    continue
                for candidate in _candidate_local_modules(module_dir, alias.name):
                    add_candidate(candidate)

    return list(dict.fromkeys(targets))


def discover_assurance_dependency_sources(
    entry_sources: list[Path] | None = None,
    assurance_dir: Path = ASSURANCE_DIR,
) -> list[Path]:
    """Walk executable local assurance import closure transitively, including package initializers."""
    pending = list(entry_sources or ASSURANCE_ENTRY_SOURCES)
    discovered: list[Path] = []
    seen: set[Path] = set()
    while pending:
        path = pending.pop()
        resolved = path.resolve()
        if resolved in seen:
            continue
        if not path.exists() or path.suffix != ".py":
            raise AssertionError(f"assurance dependency is missing or non-Python: {path}")
        seen.add(resolved)
        discovered.append(path)
        pending.extend(_local_import_targets(path, assurance_dir))
    return sorted(discovered)


def _transaction_api_finding(node: ast.Attribute) -> str | None:
    if node.attr in KAFKA_TRANSACTION_METHODS:
        return f"transaction_api:{node.attr}"
    return None


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
        elif isinstance(node, ast.Attribute):
            if node.attr in KAFKA_NATIVE_NAMES:
                findings.add(f"attribute:{node.attr}")
            transaction_finding = _transaction_api_finding(node)
            if transaction_finding:
                findings.add(transaction_finding)
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    findings.update(f"marker:{marker}" for marker in KAFKA_TEXT_MARKERS if marker in text)
    return sorted(findings)


def scan_nonpython_for_direct_kafka(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    findings: set[str] = {f"marker:{marker}" for marker in KAFKA_TEXT_MARKERS if marker in text}
    for method in KAFKA_TRANSACTION_METHODS:
        if re.search(rf"\.\s*{re.escape(method)}\s*\(", text):
            findings.add(f"transaction_api:{method}")
    return sorted(findings)


def scan_governed_implementation(inventory: dict) -> tuple[list[str], list[str]]:
    kafka_findings: list[str] = []
    broker_marker_findings: list[str] = []
    boundary_module = inventory["broker_boundary_module"]
    scanned_paths: list[Path] = []
    for root_value in inventory["implementation_code_roots"]:
        root = ROOT / root_value
        if not root.exists():
            continue
        scanned_paths.extend(
            path for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() in CODE_SUFFIXES
        )
    scanned_paths.extend(discover_assurance_dependency_sources())

    for path in dict.fromkeys(scanned_paths):
        rel = _display_path(path)
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
    assert {i["class_name"] for i in inventory_paths} == EXPECTED_PATH_CLASSES
    assert {i["path_id"] for i in inventory_paths} == EXPECTED_PATH_IDS and len(inventory_paths) == 4
    assert inventory["implementation_code_roots"] == EXPECTED_IMPLEMENTATION_ROOTS
    assert inventory["consumer_manifest_discovery_root"] == EXPECTED_CONSUMER_DISCOVERY_ROOT
    assert inventory["consumer_registration_entrypoint"] == EXPECTED_REGISTRATION_ENTRYPOINT
    assert inventory["consumer_registration_function"] == EXPECTED_REGISTRATION_FUNCTION

    assurance_closure = discover_assurance_dependency_sources()
    assert EFFECT_PROTECTION_SOURCE in assurance_closure and REGISTRATION_SOURCE in assurance_closure

    runtime_discovered = discover_broker_facing_paths()
    assert set(runtime_discovered) == EXPECTED_PATH_CLASSES
    static_discovered = discover_broker_path_declarations(governed_python_sources(inventory))
    assert set(static_discovered.values()) == EXPECTED_PATH_CLASSES and len(static_discovered) == len(EXPECTED_PATH_CLASSES)
    for class_name, path_type in runtime_discovered.items():
        source = inspect.getsource(path_type)
        assert not forbidden_kafka_tokens(source)
        calls = dependency_calls(source)
        attrs = dependency_attributes(source)
        assert calls == EXPECTED_DEPENDENCY_CALLS[class_name]
        assert attrs <= EXPECTED_DEPENDENCY_CALLS[class_name]

    direct_kafka, generic_broker_bypass = scan_governed_implementation(inventory)
    assert direct_kafka == [], f"repository implementation/dependency closure contains direct Kafka bypass: {direct_kafka}"
    assert generic_broker_bypass == [], f"repository implementation contains broker path outside shared boundary: {generic_broker_bypass}"

    consumers = discover_consumer_manifests(ROOT / EXPECTED_CONSUMER_DISCOVERY_ROOT)
    assert consumers and len(consumers) == len(set(consumers))
    entrypoint = ROOT / EXPECTED_REGISTRATION_ENTRYPOINT
    source = entrypoint.read_text(encoding="utf-8")
    for marker in (
        f"def {EXPECTED_REGISTRATION_FUNCTION}(",
        "issue_registration_permit(manifest)",
        "register_validated",
        "SUPPORTED_EFFECT_BINDINGS",
        "_ISSUED_PERMITS",
        "governed JSON is malformed",
    ):
        assert marker in source

    constructor_bypass = """class BadPath:\n    def __init__(self, broker):\n        helper(broker)\n        self._broker = broker\n    def run(self, message):\n        return self._broker.publish(message)\n"""
    assert dependency_calls(constructor_bypass) == {"helper", "_broker.publish"}
    marker_fixture = "using Confluent.Kafka; import org.springframework.kafka.core.KafkaTemplate; // node-rdkafka rdkafka"
    lowered = marker_fixture.lower()
    assert all(marker in lowered for marker in ("confluent.kafka", "org.springframework.kafka", "node-rdkafka", "rdkafka"))
    assert all(marker in KAFKA_TEXT_MARKERS for marker in ("confluent.kafka", "org.springframework.kafka", "node-rdkafka", "rdkafka"))

    print(
        f"d4a_repository_boundary=PASS broker_paths={len(runtime_discovered)} consumers={len(consumers)} "
        "direct_kafka_bypass=0 generic_broker_bypass=0 static_subclasses=alias_transitive_exact call_graph=exact "
        f"roots=implementation+src assurance_dependency_closure={len(assurance_closure)} package_initializers=scanned "
        "transaction_apis=owner_independent_polyglot"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())