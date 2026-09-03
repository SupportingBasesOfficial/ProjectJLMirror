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
ACK_AUTHORITY_CLASSES = {"BrokerFacingPath", "InboxAcknowledgePath"}
ACK_AUTHORITY_NAMES = REPLACEMENT_SPECIALS | {"acknowledge_after_durable_responsibility"}
REFLECTIVE_MEMBER_BUILTINS = {"getattr", "hasattr", "setattr", "delattr"}


def _normalized_transaction_method(identifier: str) -> str | None:
    normalized = identifier.lower().replace("_", "")
    for canonical, expected in KAFKA_TRANSACTION_IDENTIFIERS.items():
        if normalized == expected:
            return canonical
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


def _dynamic_transaction_name(node: ast.AST) -> str | None:
    value = _constant_string_value(node)
    return _normalized_transaction_method(value) if value is not None else None


def _reflective_aliases(tree: ast.AST) -> set[str]:
    aliases = set(REFLECTIVE_MEMBER_BUILTINS)
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            if not isinstance(value, ast.Name) or value.id not in aliases:
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in aliases:
                    aliases.add(target.id)
                    changed = True
    return aliases


def _is_reflective_mapping(node: ast.AST) -> bool:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "vars":
        return True
    return isinstance(node, ast.Attribute) and node.attr == "__dict__"


def _python_tree_findings(tree: ast.AST, raw: str) -> set[str]:
    findings: set[str] = set()
    reflective_aliases = _reflective_aliases(tree)
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
            if node.func.id in reflective_aliases and len(node.args) >= 2:
                transaction = _dynamic_transaction_name(node.args[1])
                if transaction is not None:
                    findings.add(f"dynamic_transaction_api:{transaction}")
                elif _constant_string_value(node.args[1]) is None:
                    findings.add("dynamic_transaction_api:unresolved_reflective_member")
        elif isinstance(node, ast.Subscript) and _is_reflective_mapping(node.value):
            transaction = _dynamic_transaction_name(node.slice)
            if transaction is not None:
                findings.add(f"dynamic_transaction_api:{transaction}")
            elif _constant_string_value(node.slice) is None:
                findings.add("dynamic_transaction_api:unresolved_reflective_member")
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
    """Resolve Python assignment aliases, including target- and value-side starred unpacking."""
    if isinstance(target, ast.Name):
        source = _leaf_name(value)
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


def _authority_mutation_sources(inventory: dict) -> list[Path]:
    paths = governed_python_sources(inventory)
    paths.extend(sorted(ASSURANCE_DIR.rglob("*.py")))
    return list(dict.fromkeys(paths))


def _class_symbol_aliases(tree: ast.AST) -> set[str]:
    aliases = set(ACK_AUTHORITY_CLASSES)
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for imported in node.names:
                    if imported.name in ACK_AUTHORITY_CLASSES:
                        aliases.add(imported.asname or imported.name)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = node.value
                source = _leaf_name(value) if value is not None else None
                if source not in aliases:
                    continue
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name) and target.id not in aliases:
                        aliases.add(target.id)
                        changed = True
    return aliases


def _is_authority_class_ref(node: ast.AST, aliases: set[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in aliases
    if isinstance(node, ast.Attribute):
        return node.attr in ACK_AUTHORITY_CLASSES
    return False


def _attribute_mutates_authority(target: ast.AST, aliases: set[str]) -> bool:
    return (
        isinstance(target, ast.Attribute)
        and target.attr in ACK_AUTHORITY_NAMES
        and _is_authority_class_ref(target.value, aliases)
    )


def assert_no_post_declaration_ack_replacement(paths: list[Path]) -> None:
    """Reject monkey-patching/rebinding of the governed ack lookup classes after declaration."""
    for path in paths:
        if not path.exists() or path.suffix != ".py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        aliases = _class_symbol_aliases(tree)
        for node in ast.walk(tree):
            targets: list[ast.AST] = []
            if isinstance(node, ast.Assign):
                targets.extend(node.targets)
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                targets.append(node.target)
            elif isinstance(node, ast.Delete):
                targets.extend(node.targets)
            if any(_attribute_mutates_authority(target, aliases) for target in targets):
                raise AssertionError(f"post-declaration acknowledgement authority mutation is forbidden: {path}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"setattr", "delattr"}:
                if len(node.args) >= 2 and _is_authority_class_ref(node.args[0], aliases):
                    name = _constant_string_value(node.args[1])
                    if name is None or name in ACK_AUTHORITY_NAMES:
                        raise AssertionError(f"dynamic post-declaration acknowledgement authority mutation is forbidden: {path}")


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
        "computed_getattr": """
class KafkaCandidateAdapter:
    authority = getattr(client, 'commit' + 'Transaction')()
""",
        "aliased_getattr": """
resolver = getattr
class KafkaCandidateAdapter:
    authority = resolver(client, 'commit' + 'Transaction')()
""",
        "dynamic_subscript": """
class KafkaCandidateAdapter:
    authority = vars(client)['commit_' + 'transaction']()
""",
    }
    for label, source in adapter_cases.items():
        findings = boundary_non_allowlisted_findings(source, "KafkaCandidateAdapter")
        if not any(item.endswith(":commit_transaction") for item in findings):
            raise AssertionError(f"{label} escaped adapter construction/lexical guard")

    unresolved_reflection = """
class KafkaCandidateAdapter:
    authority = getattr(client, transaction_name)()
"""
    findings = boundary_non_allowlisted_findings(unresolved_reflection, "KafkaCandidateAdapter")
    if "dynamic_transaction_api:unresolved_reflective_member" not in findings:
        raise AssertionError("unresolved reflective member construction escaped fail-closed guard")

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
    starred_rhs = ast.parse("Base, *rest = *[OutboxDispatchPath],").body[0]
    if ("Base", "OutboxDispatchPath") not in _assignment_aliases(starred_rhs):
        raise AssertionError("starred-RHS broker-path alias escaped structural alias discovery")


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
    assert_no_post_declaration_ack_replacement(_authority_mutation_sources(inventory))
    assert_complete_broker_path_inventory(inventory)
    run_negative_controls()
    print(
        "d4a_structural_boundary_guards=PASS "
        "native_allowlist=direct_method_bodies_only construction_surfaces=computed_dynamic_resolution_fail_closed "
        "ack_dominance=complete_inert_lookup_hierarchy+post_declaration_mutation_rejected+linear_unconditional_verify_then_ack "
        "broker_path_discovery=nested+assignment+destructuring+target_and_rhs_starred_alias_aware "
        "negative_controls=computed_reflection+lookup_hierarchy+namespace_mutation+starred_rhs_unpacking"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())