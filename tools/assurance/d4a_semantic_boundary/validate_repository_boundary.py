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
ASSURANCE_ENTRY_SOURCES = [BOUNDARY_SOURCE, EFFECT_PROTECTION_SOURCE, REGISTRATION_SOURCE]

EXPECTED_PATH_CLASSES = {"OutboxDispatchPath", "ConsumerReceivePath", "InboxAcknowledgePath", "ReplayDispatchPath"}
EXPECTED_PATH_IDS = {"outbox_dispatch", "consumer_receive", "inbox_acknowledge", "replay_dispatch"}
EXPECTED_IMPLEMENTATION_ROOTS = ["implementation", "src"]
EXPECTED_NATIVE_TRANSPORT_ALLOWLIST = ["KafkaCandidateAdapter"]
EXPECTED_CONSUMER_DISCOVERY_ROOT = "implementation"
EXPECTED_REGISTRATION_ENTRYPOINT = "tools/assurance/d4a_semantic_boundary/consumer_registration_gate.py"
EXPECTED_REGISTRATION_FUNCTION = "register_consumer"
EXPECTED_DEPENDENCY_CALLS = {
    "OutboxDispatchPath": {"_broker.publish"},
    "ConsumerReceivePath": {"_broker.receive"},
    "InboxAcknowledgePath": {"_verifier.assert_durable", "_broker.acknowledge"},
    "ReplayDispatchPath": {"_broker.publish"},
}
EXPECTED_DEPENDENCY_CALL_SEQUENCES = {
    "OutboxDispatchPath": ["_broker.publish"],
    "ConsumerReceivePath": ["_broker.receive"],
    "InboxAcknowledgePath": ["_verifier.assert_durable", "_broker.acknowledge"],
    "ReplayDispatchPath": ["_broker.publish"],
}
KAFKA_IMPORT_PREFIXES = ("kafka", "aiokafka", "confluent_kafka")
KAFKA_NATIVE_NAMES = {"offset", "partition", "consumer_group", "rebalance", "transactional_id"}
KAFKA_TRANSACTION_METHODS = {
    "init_transactions",
    "begin_transaction",
    "commit_transaction",
    "abort_transaction",
    "send_offsets_to_transaction",
}
KAFKA_TRANSACTION_IDENTIFIERS = {
    method: method.replace("_", "") for method in KAFKA_TRANSACTION_METHODS
}
CODE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".go", ".rs", ".java", ".kt", ".cs"}
KAFKA_TEXT_MARKERS = (
    "confluent_kafka", "confluent-kafka", "confluent.kafka", "aiokafka", "kafkajs",
    "node-rdkafka", "rdkafka", "librdkafka", "@confluentinc/kafka-javascript",
    "org.apache.kafka", "org.springframework.kafka", "segmentio/kafka-go", "shopify/sarama",
    "ibm/sarama", "twmb/franz-go", "rust-rdkafka",
)
GENERIC_BROKER_MARKERS = ("BrokerPort", "_broker.publish", "_broker.receive", "_broker.acknowledge")
REFLECTIVE_MEMBER_BUILTINS = {"getattr", "hasattr", "setattr", "delattr"}


def _call_target(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Attribute):
        owner = func.value
        if isinstance(owner.value, ast.Name) and owner.value.id == "self":
            return f"{owner.attr}.{func.attr}"
    if isinstance(func, ast.Name):
        return func.id
    return ast.unparse(func)


def dependency_call_sequence(source: str) -> list[str]:
    tree = ast.parse(textwrap.dedent(source))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    calls.sort(key=lambda node: (getattr(node, "lineno", -1), getattr(node, "col_offset", -1)))
    return [_call_target(node) for node in calls]


def dependency_calls(source: str) -> set[str]:
    return set(dependency_call_sequence(source))


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


def _expand_static_sequence(value: ast.AST) -> list[ast.AST] | None:
    if not isinstance(value, (ast.Tuple, ast.List)):
        return None
    expanded: list[ast.AST] = []
    for item in value.elts:
        if isinstance(item, ast.Starred):
            nested = _expand_static_sequence(item.value)
            if nested is None:
                return None
            expanded.extend(nested)
        else:
            expanded.append(item)
    return expanded


def _binding_pairs(target: ast.AST, value: ast.AST) -> list[tuple[str, str]]:
    if isinstance(target, ast.Name):
        source = _base_leaf_name(value)
        return [(target.id, source)] if source is not None else []
    if isinstance(target, ast.Starred):
        return []
    if isinstance(target, (ast.Tuple, ast.List)):
        values = _expand_static_sequence(value)
        if values is None:
            return []
        targets = target.elts
        starred_indexes = [i for i, item in enumerate(targets) if isinstance(item, ast.Starred)]
        if len(starred_indexes) > 1:
            return []
        pairs: list[tuple[str, str]] = []
        if not starred_indexes:
            if len(targets) != len(values):
                return []
            for target_item, value_item in zip(targets, values):
                pairs.extend(_binding_pairs(target_item, value_item))
            return pairs
        star = starred_indexes[0]
        prefix = targets[:star]
        suffix = targets[star + 1:]
        if len(values) < len(prefix) + len(suffix):
            return []
        for target_item, value_item in zip(prefix, values[:len(prefix)]):
            pairs.extend(_binding_pairs(target_item, value_item))
        if suffix:
            for target_item, value_item in zip(suffix, values[-len(suffix):]):
                pairs.extend(_binding_pairs(target_item, value_item))
        return pairs
    return []


def _assignment_aliases(node: ast.stmt) -> list[tuple[str, str]]:
    aliases: list[tuple[str, str]] = []
    if isinstance(node, ast.Assign):
        for target in node.targets:
            aliases.extend(_binding_pairs(target, node.value))
    elif isinstance(node, ast.AnnAssign) and node.value is not None:
        aliases.extend(_binding_pairs(node.target, node.value))
    return aliases


def _starred_sequence_aliases(node: ast.stmt) -> dict[str, tuple[str, ...]]:
    assignments: list[tuple[ast.AST, ast.AST]] = []
    if isinstance(node, ast.Assign):
        assignments.extend((target, node.value) for target in node.targets)
    elif isinstance(node, ast.AnnAssign) and node.value is not None:
        assignments.append((node.target, node.value))
    captured: dict[str, tuple[str, ...]] = {}
    for target, value in assignments:
        if not isinstance(target, (ast.Tuple, ast.List)):
            continue
        values = _expand_static_sequence(value)
        if values is None:
            continue
        stars = [i for i, item in enumerate(target.elts) if isinstance(item, ast.Starred)]
        if len(stars) != 1:
            continue
        star = stars[0]
        prefix_count = star
        suffix_count = len(target.elts) - star - 1
        if len(values) < prefix_count + suffix_count:
            continue
        starred_target = target.elts[star]
        if not isinstance(starred_target, ast.Starred) or not isinstance(starred_target.value, ast.Name):
            continue
        end = len(values) - suffix_count if suffix_count else len(values)
        names = tuple(name for item in values[prefix_count:end] if (name := _base_leaf_name(item)) is not None)
        if len(names) == end - prefix_count:
            captured[starred_target.value.id] = names
    return captured


def _class_base_names(node: ast.ClassDef, sequence_aliases: dict[str, tuple[str, ...]]) -> set[str]:
    bases: set[str] = set()
    for base in node.bases:
        if isinstance(base, ast.Starred) and isinstance(base.value, ast.Name):
            bases.update(sequence_aliases.get(base.value.id, ()))
            continue
        name = _base_leaf_name(base)
        if name is not None:
            bases.add(name)
    return bases


def discover_broker_path_declarations(paths: list[Path]) -> dict[str, str]:
    """Discover descendants without collapsing same-name declarations or starred sequence bases."""
    classes: list[tuple[Path, int, str, set[str]]] = []
    aliases: list[tuple[str, str]] = []
    for path in paths:
        if not path.exists() or path.suffix != ".py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        sequence_aliases: dict[str, tuple[str, ...]] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    aliases.append((alias.asname or alias.name, alias.name))
            if isinstance(node, ast.stmt):
                aliases.extend(_assignment_aliases(node))
                sequence_aliases.update(_starred_sequence_aliases(node))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append((path, node.lineno, node.name, _class_base_names(node, sequence_aliases)))

    descendant_symbols = {"BrokerFacingPath"}
    changed = True
    while changed:
        changed = False
        for local_name, source_name in aliases:
            if source_name in descendant_symbols and local_name not in descendant_symbols:
                descendant_symbols.add(local_name)
                changed = True
        for _, _, class_name, bases in classes:
            if class_name not in descendant_symbols and bases & descendant_symbols:
                descendant_symbols.add(class_name)
                changed = True

    discovered: dict[str, str] = {}
    for path, lineno, class_name, bases in classes:
        if class_name != "BrokerFacingPath" and class_name in descendant_symbols and bases & descendant_symbols:
            declaration_id = f"{_display_path(path)}:{class_name}@L{lineno}"
            discovered[declaration_id] = class_name
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
            for candidate in _candidate_local_modules(base, module):
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


def _normalized_transaction_method(identifier: str) -> str | None:
    normalized_identifier = identifier.lower().replace("_", "")
    for canonical_method, normalized_method in KAFKA_TRANSACTION_IDENTIFIERS.items():
        if normalized_identifier == normalized_method:
            return canonical_method
    return None


def _constant_string_value(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _constant_string_value(node.left)
        right = _constant_string_value(node.right)
        if left is not None and right is not None:
            return left + right
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                return None
            parts.append(value.value)
        return "".join(parts)
    return None


def _reflective_aliases(tree: ast.AST) -> tuple[set[str], set[str]]:
    call_aliases = set(REFLECTIVE_MEMBER_BUILTINS)
    module_aliases = {"builtins"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "builtins":
            for imported in node.names:
                if imported.name in REFLECTIVE_MEMBER_BUILTINS:
                    call_aliases.add(imported.asname or imported.name)
        elif isinstance(node, ast.Import):
            for imported in node.names:
                if imported.name == "builtins":
                    module_aliases.add(imported.asname or imported.name)
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            source: str | None = None
            if isinstance(value, ast.Name) and value.id in call_aliases:
                source = value.id
            elif (
                isinstance(value, ast.Attribute)
                and value.attr in REFLECTIVE_MEMBER_BUILTINS
                and isinstance(value.value, ast.Name)
                and value.value.id in module_aliases
            ):
                source = value.attr
            if source is None:
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in call_aliases:
                    call_aliases.add(target.id)
                    changed = True
    return call_aliases, module_aliases


def _reflective_callable(node: ast.AST, call_aliases: set[str], module_aliases: set[str]) -> str | None:
    if isinstance(node, ast.Name) and node.id in call_aliases:
        return node.id
    if (
        isinstance(node, ast.Attribute)
        and node.attr in REFLECTIVE_MEMBER_BUILTINS
        and isinstance(node.value, ast.Name)
        and node.value.id in module_aliases
    ):
        return node.attr
    return None


def _dynamic_transaction_method(node: ast.AST) -> str | None:
    value = _constant_string_value(node)
    return _normalized_transaction_method(value) if value is not None else None


def _is_reflective_mapping(node: ast.AST) -> bool:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "vars":
        return True
    return isinstance(node, ast.Attribute) and node.attr == "__dict__"


def _python_tree_findings(tree: ast.AST) -> set[str]:
    findings: set[str] = set()
    call_aliases, module_aliases = _reflective_aliases(tree)
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
            canonical_method = _normalized_transaction_method(node.attr)
            if canonical_method is not None:
                findings.add(f"transaction_api:{canonical_method}")
        elif isinstance(node, ast.Call):
            reflective = _reflective_callable(node.func, call_aliases, module_aliases)
            if reflective is not None and len(node.args) >= 2:
                canonical_method = _dynamic_transaction_method(node.args[1])
                if canonical_method is not None:
                    findings.add(f"dynamic_transaction_api:{canonical_method}")
                elif _constant_string_value(node.args[1]) is None:
                    findings.add("dynamic_transaction_api:unresolved_reflective_member")
        if isinstance(node, ast.Subscript) and _is_reflective_mapping(node.value):
            canonical_method = _dynamic_transaction_method(node.slice)
            if canonical_method is not None:
                findings.add(f"dynamic_transaction_api:{canonical_method}")
            elif _constant_string_value(node.slice) is None:
                findings.add("dynamic_transaction_api:unresolved_reflective_member")
    return findings


def scan_python_for_direct_kafka(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8")
    tree = ast.parse(raw, filename=str(path))
    findings = _python_tree_findings(tree)
    lowered = raw.lower()
    findings.update(f"marker:{marker}" for marker in KAFKA_TEXT_MARKERS if marker in lowered)
    return sorted(findings)


def scan_boundary_module_for_direct_kafka(path: Path, allowlisted_classes: set[str]) -> list[str]:
    """Scan the broker boundary and exempt only explicitly pinned native adapter class bodies."""
    raw = path.read_text(encoding="utf-8")
    tree = ast.parse(raw, filename=str(path))
    findings: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name in allowlisted_classes:
            continue
        findings.update(_python_tree_findings(node))
        segment = ast.get_source_segment(raw, node) or ""
        lowered = segment.lower()
        findings.update(f"marker:{marker}" for marker in KAFKA_TEXT_MARKERS if marker in lowered)
    return sorted(findings)


def scan_nonpython_for_direct_kafka(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    lowered = raw.lower()
    findings: set[str] = {f"marker:{marker}" for marker in KAFKA_TEXT_MARKERS if marker in lowered}
    for match in re.finditer(r"\.\s*([A-Za-z_][A-Za-z0-9_]*)", raw):
        canonical_method = _normalized_transaction_method(match.group(1))
        if canonical_method is not None:
            findings.add(f"transaction_api:{canonical_method}")
    return sorted(findings)


def scan_governed_implementation(inventory: dict) -> tuple[list[str], list[str]]:
    kafka_findings: list[str] = []
    broker_marker_findings: list[str] = []
    boundary_module = inventory["broker_boundary_module"]
    native_allowlist = set(inventory["native_transport_allowlist"])
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
        if path.resolve() == BOUNDARY_SOURCE.resolve():
            direct = scan_boundary_module_for_direct_kafka(path, native_allowlist)
        else:
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
    assert inventory["native_transport_allowlist"] == EXPECTED_NATIVE_TRANSPORT_ALLOWLIST
    assert inventory["consumer_manifest_discovery_root"] == EXPECTED_CONSUMER_DISCOVERY_ROOT
    assert inventory["consumer_registration_entrypoint"] == EXPECTED_REGISTRATION_ENTRYPOINT
    assert inventory["consumer_registration_function"] == EXPECTED_REGISTRATION_FUNCTION

    assurance_closure = discover_assurance_dependency_sources()
    assert BOUNDARY_SOURCE in assurance_closure
    assert EFFECT_PROTECTION_SOURCE in assurance_closure and REGISTRATION_SOURCE in assurance_closure

    runtime_discovered = discover_broker_facing_paths()
    assert set(runtime_discovered) == EXPECTED_PATH_CLASSES
    static_discovered = discover_broker_path_declarations(governed_python_sources(inventory))
    assert set(static_discovered.values()) == EXPECTED_PATH_CLASSES and len(static_discovered) == len(EXPECTED_PATH_CLASSES)
    for class_name, path_type in runtime_discovered.items():
        source = inspect.getsource(path_type)
        assert not forbidden_kafka_tokens(source)
        calls = dependency_calls(source)
        call_sequence = dependency_call_sequence(source)
        attrs = dependency_attributes(source)
        assert calls == EXPECTED_DEPENDENCY_CALLS[class_name]
        assert call_sequence == EXPECTED_DEPENDENCY_CALL_SEQUENCES[class_name]
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
        "consumer-registry",
    ):
        assert marker in source

    constructor_bypass = """class BadPath:\n    def __init__(self, broker):\n        helper(broker)\n        self._broker = broker\n    def run(self, message):\n        return self._broker.publish(message)\n"""
    assert dependency_calls(constructor_bypass) == {"helper", "_broker.publish"}
    assert dependency_call_sequence(constructor_bypass) == ["helper", "_broker.publish"]
    marker_fixture = "using Confluent.Kafka; import org.springframework.kafka.core.KafkaTemplate; // node-rdkafka rdkafka"
    lowered = marker_fixture.lower()
    assert all(marker in lowered for marker in ("confluent.kafka", "org.springframework.kafka", "node-rdkafka", "rdkafka"))
    assert all(marker in KAFKA_TEXT_MARKERS for marker in ("confluent.kafka", "org.springframework.kafka", "node-rdkafka", "rdkafka"))
    dynamic_tree = ast.parse("resolver = getattr\nresolver(client, 'commit' + 'Transaction')()\nvars(client)['commit_' + 'transaction']()")
    dynamic_findings = _python_tree_findings(dynamic_tree)
    assert "dynamic_transaction_api:commit_transaction" in dynamic_findings
    unresolved_tree = ast.parse("getattr(client, transaction_name)()")
    assert "dynamic_transaction_api:unresolved_reflective_member" in _python_tree_findings(unresolved_tree)
    imported_alias_tree = ast.parse("from builtins import getattr as resolve\nresolve(client, 'commitTransaction')()")
    assert "dynamic_transaction_api:commit_transaction" in _python_tree_findings(imported_alias_tree)
    starred_base_tree = ast.parse("*Bases, = (OutboxDispatchPath,)\nclass EscapingPath(*Bases):\n    pass")
    sequence_aliases: dict[str, tuple[str, ...]] = {}
    for statement in starred_base_tree.body:
        if isinstance(statement, ast.stmt):
            sequence_aliases.update(_starred_sequence_aliases(statement))
    escaping = next(node for node in starred_base_tree.body if isinstance(node, ast.ClassDef))
    assert "OutboxDispatchPath" in _class_base_names(escaping, sequence_aliases)

    print(
        f"d4a_repository_boundary=PASS broker_paths={len(runtime_discovered)} consumers={len(consumers)} "
        "direct_kafka_bypass=0 generic_broker_bypass=0 static_subclasses=distinct_nested_declarations+starred_sequence_base_transitive_exact "
        "call_graph=ordered_exact verifier_before_ack=true "
        f"roots=implementation+src assurance_dependency_closure={len(assurance_closure)} boundary_module=class_scoped_native_allowlist package_initializers=scanned "
        "transaction_apis=owner_independent+import_qualified_dynamic_reflection_fail_closed+polyglot_case_and_generic_syntax_normalized"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())