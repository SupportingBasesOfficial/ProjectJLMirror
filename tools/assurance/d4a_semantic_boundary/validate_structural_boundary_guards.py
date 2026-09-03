from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ASSURANCE_DIR = ROOT / "tools/assurance/d4a_semantic_boundary"
BOUNDARY_SOURCE = ASSURANCE_DIR / "broker_boundary.py"
INVENTORY = ROOT / "implementation/d4-eventing-async/source-evidence/semantic-boundary/boundary-inventory.json"

EXPECTED_PATH_CLASSES = {
    "OutboxDispatchPath",
    "ConsumerReceivePath",
    "InboxAcknowledgePath",
    "ReplayDispatchPath",
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
KAFKA_TEXT_MARKERS = (
    "confluent_kafka", "confluent-kafka", "confluent.kafka", "aiokafka", "kafkajs",
    "node-rdkafka", "rdkafka", "librdkafka", "@confluentinc/kafka-javascript",
    "org.apache.kafka", "org.springframework.kafka", "segmentio/kafka-go", "shopify/sarama",
    "ibm/sarama", "twmb/franz-go", "rust-rdkafka",
)
REPLACEMENT_SPECIALS = {
    "__getattribute__", "__getattr__", "__setattr__", "__get__", "__set__",
    "__init_subclass__", "__class_getitem__",
}


def _normalized_transaction_method(identifier: str) -> str | None:
    normalized = identifier.lower().replace("_", "")
    for canonical, expected in KAFKA_TRANSACTION_IDENTIFIERS.items():
        if normalized == expected:
            return canonical
    return None


def _dynamic_transaction_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return _normalized_transaction_method(node.value)
    return None


def _python_tree_findings(tree: ast.AST, raw: str) -> set[str]:
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
            transaction = _normalized_transaction_method(node.attr)
            if transaction is not None:
                findings.add(f"transaction_api:{transaction}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            # Builtin dynamic attribute resolution is executable authority too.  Detect the
            # prohibited transaction member when it is supplied as a literal name instead of
            # appearing as an Attribute node.
            if node.func.id in {"getattr", "hasattr", "setattr", "delattr"} and len(node.args) >= 2:
                transaction = _dynamic_transaction_name(node.args[1])
                if transaction is not None:
                    findings.add(f"dynamic_transaction_api:{transaction}")
        elif isinstance(node, ast.Subscript):
            # Common reflective maps such as vars(client)["commitTransaction"] or
            # obj.__dict__["commitTransaction"] must not evade construction-surface scanning.
            transaction = _dynamic_transaction_name(node.slice)
            if transaction is not None:
                findings.add(f"dynamic_transaction_api:{transaction}")
    segment = ast.get_source_segment(raw, tree) or raw
    lowered = segment.lower()
    findings.update(f"marker:{marker}" for marker in KAFKA_TEXT_MARKERS if marker in lowered)
    return findings


def _function_signature_nodes(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.AST]:
    """Nodes evaluated when the direct adapter method is defined, not when its body executes."""
    nodes: list[ast.AST] = list(node.decorator_list)
    nodes.extend(node.args.defaults)
    nodes.extend(default for default in node.args.kw_defaults if default is not None)
    args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    if node.args.vararg is not None:
        args.append(node.args.vararg)
    if node.args.kwarg is not None:
        args.append(node.args.kwarg)
    nodes.extend(arg.annotation for arg in args if arg.annotation is not None)
    if node.returns is not None:
        nodes.append(node.returns)
    for type_param in getattr(node, "type_params", []):
        nodes.append(type_param)
    return nodes


def _adapter_nonexempt_nodes(allowed: ast.ClassDef) -> list[ast.AST]:
    """Return everything except the direct executable bodies of the native adapter methods."""
    governed: list[ast.AST] = []
    governed.extend(allowed.decorator_list)
    governed.extend(allowed.bases)
    governed.extend(keyword.value for keyword in allowed.keywords)
    for type_param in getattr(allowed, "type_params", []):
        governed.append(type_param)

    for node in allowed.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            governed.extend(_function_signature_nodes(node))
            for descendant in ast.walk(node):
                if descendant is node:
                    continue
                if isinstance(descendant, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                    governed.append(descendant)
            continue
        governed.append(node)
    return governed


def boundary_non_allowlisted_findings(raw: str, allowlisted_class: str) -> list[str]:
    """Exempt exactly one adapter's direct method bodies; govern every other executable surface."""
    tree = ast.parse(raw)
    all_matching = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == allowlisted_class
    ]
    top_level_matching = [
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == allowlisted_class
    ]
    if len(all_matching) != 1 or len(top_level_matching) != 1 or all_matching[0] is not top_level_matching[0]:
        raise AssertionError(
            f"native adapter allowlist must bind to exactly one top-level lexical declaration: {allowlisted_class}"
        )
    allowed = top_level_matching[0]
    findings: set[str] = set()
    for node in tree.body:
        if node is not allowed:
            findings.update(_python_tree_findings(node, raw))
    for node in _adapter_nonexempt_nodes(allowed):
        findings.update(_python_tree_findings(node, raw))
    return sorted(findings)


def _call_target(statement: ast.stmt) -> str | None:
    if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
        return None
    func = statement.value.func
    if not isinstance(func, ast.Attribute) or not isinstance(func.value, ast.Attribute):
        return None
    owner = func.value
    if isinstance(owner.value, ast.Name) and owner.value.id == "self":
        return f"{owner.attr}.{func.attr}"
    return None


def _top_level_class(tree: ast.Module, name: str) -> ast.ClassDef:
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name]
    if len(classes) != 1:
        raise AssertionError(f"expected exactly one top-level {name} declaration")
    return classes[0]


def _assert_lookup_class_is_inert(path_class: ast.ClassDef, label: str, *, require_plain_object_base: bool) -> None:
    if path_class.decorator_list:
        raise AssertionError(f"{label} must not be decorated")
    if path_class.keywords:
        raise AssertionError(f"{label} must not use metaclass or class keyword replacement hooks")
    if require_plain_object_base and path_class.bases:
        raise AssertionError(f"{label} must remain a plain marker base with no inherited lookup hierarchy")
    for node in path_class.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            raise AssertionError(f"{label} class body must not rebind authority lookup")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in REPLACEMENT_SPECIALS:
            raise AssertionError(f"replacement-capable special method is forbidden on {label}: {node.name}")


def assert_ack_verification_dominates(raw: str) -> None:
    """Require a non-replaceable linear ack entrypoint across the complete governed lookup hierarchy."""
    tree = ast.parse(raw)
    base_class = _top_level_class(tree, "BrokerFacingPath")
    _assert_lookup_class_is_inert(base_class, "BrokerFacingPath", require_plain_object_base=True)

    path_class = _top_level_class(tree, "InboxAcknowledgePath")
    if len(path_class.bases) != 1 or not isinstance(path_class.bases[0], ast.Name) or path_class.bases[0].id != "BrokerFacingPath":
        raise AssertionError("InboxAcknowledgePath must inherit directly and only from BrokerFacingPath")
    _assert_lookup_class_is_inert(path_class, "InboxAcknowledgePath", require_plain_object_base=False)

    methods = [
        node for node in path_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "acknowledge_after_durable_responsibility"
    ]
    if len(methods) != 1:
        raise AssertionError("expected exactly one acknowledgement entrypoint")
    method = methods[0]
    if method.decorator_list:
        raise AssertionError("acknowledgement entrypoint must not be decorated or replaced by a wrapper")
    if isinstance(method, ast.AsyncFunctionDef):
        raise AssertionError("acknowledgement entrypoint must remain synchronous for this source-evidence shape")
    body = method.body
    if len(body) != 2:
        raise AssertionError("acknowledgement entrypoint must be a linear two-statement verify-then-ack path")
    targets = [_call_target(statement) for statement in body]
    if targets != ["_verifier.assert_durable", "_broker.acknowledge"]:
        raise AssertionError(
            "durable verification must unconditionally dominate broker acknowledgement with no branch/try/loop escape"
        )


def _leaf_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _binding_pairs(target: ast.AST, value: ast.AST) -> list[tuple[str, str]]:
    """Resolve Python assignment aliases, including variable-length starred unpacking."""
    if isinstance(target, ast.Name):
        source = _leaf_name(value)
        return [(target.id, source)] if source is not None else []
    if isinstance(target, ast.Starred):
        # A starred target receives a sequence, not one source symbol. Descendant propagation is
        # instead derived from the fixed-prefix/fixed-suffix bindings around it.
        return []
    if isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (ast.Tuple, ast.List)):
        targets = target.elts
        values = value.elts
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


def discover_broker_path_declarations(paths: list[Path]) -> dict[str, str]:
    """Independent descendant discovery including nested scopes and destructuring aliases."""
    classes: list[tuple[Path, int, str, set[str]]] = []
    aliases: list[tuple[str, str]] = []
    for path in paths:
        if not path.exists() or path.suffix != ".py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    aliases.append((alias.asname or alias.name, alias.name))
            if isinstance(node, ast.stmt):
                aliases.extend(_assignment_aliases(node))
            if isinstance(node, ast.ClassDef):
                bases = {name for base in node.bases if (name := _leaf_name(base)) is not None}
                classes.append((path, node.lineno, node.name, bases))

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
            declaration_id = f"{path.relative_to(ROOT).as_posix()}:{class_name}@L{lineno}"
            discovered[declaration_id] = class_name
    return discovered


def governed_python_sources(inventory: dict) -> list[Path]:
    paths = [BOUNDARY_SOURCE]
    for root_value in inventory["implementation_code_roots"]:
        root = ROOT / root_value
        if root.exists():
            paths.extend(sorted(root.rglob("*.py")))
    return list(dict.fromkeys(paths))


def assert_complete_broker_path_inventory(inventory: dict) -> None:
    discovered = discover_broker_path_declarations(governed_python_sources(inventory))
    names = list(discovered.values())
    if set(names) != EXPECTED_PATH_CLASSES or len(names) != len(EXPECTED_PATH_CLASSES):
        raise AssertionError(f"broker-facing path inventory mismatch under structural discovery: {discovered}")


def _must_fail_ack(source: str, label: str) -> None:
    try:
        assert_ack_verification_dominates(source)
    except AssertionError:
        return
    raise AssertionError(f"{label} escaped acknowledgement structural guard")


def run_negative_controls() -> None:
    duplicate = """
class KafkaCandidateAdapter:
    def run(self, client):
        client.commitTransaction()
class KafkaCandidateAdapter:
    pass
"""
    try:
        boundary_non_allowlisted_findings(duplicate, "KafkaCandidateAdapter")
    except AssertionError:
        pass
    else:
        raise AssertionError("duplicate allowlisted declaration escaped lexical uniqueness guard")

    adapter_cases = {
        "nested_class": """
class KafkaCandidateAdapter:
    class AlternateStubTransport:
        def run(self, client):
            client.commitTransaction()
""",
        "nested_def": """
class KafkaCandidateAdapter:
    def publish(self, client):
        def hidden_helper():
            client.commitTransaction()
        return hidden_helper()
""",
        "nested_async_def": """
class KafkaCandidateAdapter:
    async def publish(self, client):
        async def hidden_helper():
            client.commitTransaction()
        return await hidden_helper()
""",
        "nested_lambda": """
class KafkaCandidateAdapter:
    def publish(self, client):
        hidden = lambda: client.commitTransaction()
        return hidden()
""",
        "class_body": """
class KafkaCandidateAdapter:
    authority = client.commitTransaction()
""",
        "default_argument": """
class KafkaCandidateAdapter:
    def publish(self, authority=client.commitTransaction()):
        return authority
""",
        "decorator_expression": """
class KafkaCandidateAdapter:
    @client.commitTransaction()
    def publish(self):
        pass
""",
        "annotation_expression": """
class KafkaCandidateAdapter:
    def publish(self, value: client.commitTransaction()):
        return value
""",
        "dynamic_getattr": """
class KafkaCandidateAdapter:
    authority = getattr(client, 'commitTransaction')()
""",
        "dynamic_subscript": """
class KafkaCandidateAdapter:
    authority = vars(client)['commit_transaction']()
""",
    }
    for label, source in adapter_cases.items():
        findings = boundary_non_allowlisted_findings(source, "KafkaCandidateAdapter")
        if not any(item.endswith(":commit_transaction") for item in findings):
            raise AssertionError(f"{label} escaped adapter construction/lexical guard")

    inert_base = "class BrokerFacingPath:\n    pass\n"
    ack_cases = {
        "conditional": inert_base + """
class InboxAcknowledgePath(BrokerFacingPath):
    def acknowledge_after_durable_responsibility(self, receipt):
        if receipt.receipt_id != 'escape':
            self._verifier.assert_durable(receipt)
        self._broker.acknowledge(receipt)
""",
        "broker_first": inert_base + """
class InboxAcknowledgePath(BrokerFacingPath):
    def acknowledge_after_durable_responsibility(self, receipt):
        self._broker.acknowledge(receipt)
        self._verifier.assert_durable(receipt)
""",
        "decorated_method": inert_base + """
def bypass_wrapper(fn):
    return fn
class InboxAcknowledgePath(BrokerFacingPath):
    @bypass_wrapper
    def acknowledge_after_durable_responsibility(self, receipt):
        self._verifier.assert_durable(receipt)
        self._broker.acknowledge(receipt)
""",
        "decorated_class": inert_base + """
def replace_class(cls):
    return cls
@replace_class
class InboxAcknowledgePath(BrokerFacingPath):
    def acknowledge_after_durable_responsibility(self, receipt):
        self._verifier.assert_durable(receipt)
        self._broker.acknowledge(receipt)
""",
        "metaclass": inert_base + """
class InboxAcknowledgePath(BrokerFacingPath, metaclass=ReplaceAck):
    def acknowledge_after_durable_responsibility(self, receipt):
        self._verifier.assert_durable(receipt)
        self._broker.acknowledge(receipt)
""",
        "entrypoint_rebind": inert_base + """
class InboxAcknowledgePath(BrokerFacingPath):
    def acknowledge_after_durable_responsibility(self, receipt):
        self._verifier.assert_durable(receipt)
        self._broker.acknowledge(receipt)
    acknowledge_after_durable_responsibility = external_hook
""",
        "getattribute_override": inert_base + """
class InboxAcknowledgePath(BrokerFacingPath):
    def __getattribute__(self, name):
        return external_hook
    def acknowledge_after_durable_responsibility(self, receipt):
        self._verifier.assert_durable(receipt)
        self._broker.acknowledge(receipt)
""",
        "inherited_getattribute": """
class BrokerFacingPath:
    def __getattribute__(self, name):
        return external_hook
class InboxAcknowledgePath(BrokerFacingPath):
    def acknowledge_after_durable_responsibility(self, receipt):
        self._verifier.assert_durable(receipt)
        self._broker.acknowledge(receipt)
""",
        "base_metaclass": """
class BrokerFacingPath(metaclass=ReplaceAck):
    pass
class InboxAcknowledgePath(BrokerFacingPath):
    def acknowledge_after_durable_responsibility(self, receipt):
        self._verifier.assert_durable(receipt)
        self._broker.acknowledge(receipt)
""",
    }
    for label, source in ack_cases.items():
        _must_fail_ack(source, label)

    destructuring = ast.parse("(Base,) = (OutboxDispatchPath,)").body[0]
    if ("Base", "OutboxDispatchPath") not in _assignment_aliases(destructuring):
        raise AssertionError("destructuring broker-path alias escaped structural alias discovery")
    starred_prefix = ast.parse("(Base, *rest) = (OutboxDispatchPath,)").body[0]
    if ("Base", "OutboxDispatchPath") not in _assignment_aliases(starred_prefix):
        raise AssertionError("starred-prefix broker-path alias escaped structural alias discovery")
    starred_suffix = ast.parse("(*rest, Base) = (OutboxDispatchPath,)").body[0]
    if ("Base", "OutboxDispatchPath") not in _assignment_aliases(starred_suffix):
        raise AssertionError("starred-suffix broker-path alias escaped structural alias discovery")


def main() -> int:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    allowlist = inventory.get("native_transport_allowlist")
    if allowlist != ["KafkaCandidateAdapter"]:
        raise AssertionError("native transport allowlist must remain exactly KafkaCandidateAdapter")

    raw = BOUNDARY_SOURCE.read_text(encoding="utf-8")
    findings = boundary_non_allowlisted_findings(raw, allowlist[0])
    if findings:
        raise AssertionError(f"non-allowlisted boundary execution gained native Kafka authority: {findings}")
    assert_ack_verification_dominates(raw)
    assert_complete_broker_path_inventory(inventory)
    run_negative_controls()
    print(
        "d4a_structural_boundary_guards=PASS "
        "native_allowlist=direct_method_bodies_only construction_surfaces=dynamic_resolution_scanned "
        "ack_dominance=complete_inert_lookup_hierarchy+linear_unconditional_verify_then_ack "
        "broker_path_discovery=nested+assignment+destructuring+starred_alias_aware "
        "negative_controls=adapter_dynamic_resolution+lookup_hierarchy+starred_unpacking"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
