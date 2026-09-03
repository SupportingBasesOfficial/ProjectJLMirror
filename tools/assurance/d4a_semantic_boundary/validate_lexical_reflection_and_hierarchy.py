from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
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
TRANSACTION_METHODS = {
    "inittransactions",
    "begintransaction",
    "committransaction",
    "aborttransaction",
    "sendoffsetstotransaction",
}
MEMBER_BUILTINS = {"getattr", "hasattr", "setattr", "delattr"}
MAPPING_BUILTINS = {"vars"}
AUTHORITY_CLASSES = {"BrokerFacingPath", "InboxAcknowledgePath"}
AUTHORITY_MUTATION_NAMES = {
    "acknowledge_after_durable_responsibility",
    "__getattribute__",
    "__getattr__",
    "__setattr__",
    "__get__",
    "__set__",
    "__init_subclass__",
    "__class_getitem__",
    "__bases__",
}


def _normalized_transaction(name: str) -> str | None:
    normalized = name.lower().replace("_", "")
    return normalized if normalized in TRANSACTION_METHODS else None


def _constant_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _constant_string(node.left)
        right = _constant_string(node.right)
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


def _target_names(target: ast.AST) -> set[str]:
    names: set[str] = set()
    if isinstance(target, ast.Name):
        names.add(target.id)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for item in target.elts:
            names.update(_target_names(item))
    elif isinstance(target, ast.Starred):
        names.update(_target_names(target.value))
    return names


def _scope_local_bindings(body: list[ast.stmt], args: ast.arguments | None = None) -> set[str]:
    names: set[str] = set()
    if args is not None:
        for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
            names.add(arg.arg)
        if args.vararg is not None:
            names.add(args.vararg.arg)
        if args.kwarg is not None:
            names.add(args.kwarg.arg)
    for statement in body:
        for node in ast.walk(statement):
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                names.add(node.id)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.asname or alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    names.add(alias.asname or alias.name)
    return names


@dataclass
class ReflectionState:
    member_aliases: dict[str, str] = field(default_factory=lambda: {name: name for name in MEMBER_BUILTINS})
    mapping_aliases: dict[str, str] = field(default_factory=lambda: {name: name for name in MAPPING_BUILTINS})
    builtins_modules: set[str] = field(default_factory=lambda: {"builtins"})
    reflected_callables: set[str] = field(default_factory=set)
    mapping_values: set[str] = field(default_factory=set)
    authority_aliases: set[str] = field(default_factory=lambda: set(AUTHORITY_CLASSES))

    def child_for_function(self, body: list[ast.stmt], args: ast.arguments) -> "ReflectionState":
        child = ReflectionState(
            member_aliases=dict(self.member_aliases),
            mapping_aliases=dict(self.mapping_aliases),
            builtins_modules=set(self.builtins_modules),
            reflected_callables=set(self.reflected_callables),
            mapping_values=set(self.mapping_values),
            authority_aliases=set(self.authority_aliases),
        )
        local = _scope_local_bindings(body, args)
        for name in local:
            child.member_aliases.pop(name, None)
            child.mapping_aliases.pop(name, None)
            child.reflected_callables.discard(name)
            child.mapping_values.discard(name)
        return child

    def branch(self) -> "ReflectionState":
        return ReflectionState(
            member_aliases=dict(self.member_aliases),
            mapping_aliases=dict(self.mapping_aliases),
            builtins_modules=set(self.builtins_modules),
            reflected_callables=set(self.reflected_callables),
            mapping_values=set(self.mapping_values),
            authority_aliases=set(self.authority_aliases),
        )


def _member_builtin(node: ast.AST, state: ReflectionState) -> str | None:
    if isinstance(node, ast.Name):
        return state.member_aliases.get(node.id)
    if (
        isinstance(node, ast.Attribute)
        and node.attr in MEMBER_BUILTINS
        and isinstance(node.value, ast.Name)
        and node.value.id in state.builtins_modules
    ):
        return node.attr
    return None


def _mapping_builtin(node: ast.AST, state: ReflectionState) -> str | None:
    if isinstance(node, ast.Name):
        return state.mapping_aliases.get(node.id)
    if (
        isinstance(node, ast.Attribute)
        and node.attr in MAPPING_BUILTINS
        and isinstance(node.value, ast.Name)
        and node.value.id in state.builtins_modules
    ):
        return node.attr
    return None


def _is_mapping_expr(node: ast.AST, state: ReflectionState) -> bool:
    if isinstance(node, ast.Name) and node.id in state.mapping_values:
        return True
    if isinstance(node, ast.Attribute) and node.attr == "__dict__":
        return True
    return isinstance(node, ast.Call) and _mapping_builtin(node.func, state) == "vars"


def _reflection_member_name(node: ast.AST, state: ReflectionState) -> str | None | bool:
    if isinstance(node, ast.Call) and _member_builtin(node.func, state) in {"getattr", "hasattr"} and len(node.args) >= 2:
        value = _constant_string(node.args[1])
        return value if value is not None else False
    if isinstance(node, ast.Subscript) and _is_mapping_expr(node.value, state):
        value = _constant_string(node.slice)
        return value if value is not None else False
    return None


def _authority_ref(node: ast.AST, state: ReflectionState) -> bool:
    if isinstance(node, ast.Name):
        return node.id in state.authority_aliases
    if isinstance(node, ast.Attribute):
        return node.attr in AUTHORITY_CLASSES
    return False


def _scan_expression(node: ast.AST, state: ReflectionState, findings: set[str], *, called: bool = False) -> None:
    reflected_name = _reflection_member_name(node, state)
    if reflected_name is False and called:
        findings.add("reflection:unresolved_callable_member")
    elif isinstance(reflected_name, str):
        transaction = _normalized_transaction(reflected_name)
        if transaction is not None:
            findings.add(f"reflection:transaction_member:{transaction}")

    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in state.reflected_callables:
            findings.add("reflection:aliased_unresolved_callable_member")
        mutation = _member_builtin(node.func, state)
        if mutation in {"setattr", "delattr"} and len(node.args) >= 2 and _authority_ref(node.args[0], state):
            name = _constant_string(node.args[1])
            if name is None or name in AUTHORITY_MUTATION_NAMES:
                findings.add("authority:reflective_namespace_mutation")
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in {"__setattr__", "__delattr__"}
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "type"
            and len(node.args) >= 2
            and _authority_ref(node.args[0], state)
        ):
            name = _constant_string(node.args[1])
            if name is None or name in AUTHORITY_MUTATION_NAMES:
                findings.add("authority:type_namespace_mutation")
        _scan_expression(node.func, state, findings, called=True)
        for arg in node.args:
            _scan_expression(arg, state, findings)
        for kw in node.keywords:
            _scan_expression(kw.value, state, findings)
        return

    if isinstance(node, ast.Attribute):
        if node.attr in AUTHORITY_MUTATION_NAMES and _authority_ref(node.value, state):
            # Mere reads are handled by assignment/delete context in statement scanning.
            pass
        _scan_expression(node.value, state, findings)
        return
    if isinstance(node, ast.Subscript):
        _scan_expression(node.value, state, findings)
        _scan_expression(node.slice, state, findings)
        return
    for child in ast.iter_child_nodes(node):
        _scan_expression(child, state, findings)


def _assignment_value_kind(value: ast.AST, state: ReflectionState, findings: set[str]) -> tuple[str, str | None]:
    if isinstance(value, ast.Name):
        if value.id in state.member_aliases:
            return "member_builtin", state.member_aliases[value.id]
        if value.id in state.mapping_aliases:
            return "mapping_builtin", state.mapping_aliases[value.id]
        if value.id in state.reflected_callables:
            return "reflected_callable", None
        if value.id in state.mapping_values:
            return "mapping_value", None
        if value.id in state.authority_aliases:
            return "authority", None
    if isinstance(value, ast.Attribute):
        member = _member_builtin(value, state)
        if member is not None:
            return "member_builtin", member
        mapping = _mapping_builtin(value, state)
        if mapping is not None:
            return "mapping_builtin", mapping
        if value.attr in AUTHORITY_CLASSES:
            return "authority", None
    if isinstance(value, ast.Call) and _mapping_builtin(value.func, state) == "vars":
        return "mapping_value", None
    if isinstance(value, ast.Attribute) and value.attr == "__dict__":
        return "mapping_value", None
    reflected = _reflection_member_name(value, state)
    if reflected is False:
        return "reflected_callable", None
    if isinstance(reflected, str):
        transaction = _normalized_transaction(reflected)
        if transaction is not None:
            findings.add(f"reflection:transaction_member:{transaction}")
    return "other", None


def _bind_name(name: str, kind: str, detail: str | None, state: ReflectionState) -> None:
    state.member_aliases.pop(name, None)
    state.mapping_aliases.pop(name, None)
    state.reflected_callables.discard(name)
    state.mapping_values.discard(name)
    if name not in AUTHORITY_CLASSES:
        state.authority_aliases.discard(name)
    if kind == "member_builtin" and detail is not None:
        state.member_aliases[name] = detail
    elif kind == "mapping_builtin" and detail is not None:
        state.mapping_aliases[name] = detail
    elif kind == "reflected_callable":
        state.reflected_callables.add(name)
    elif kind == "mapping_value":
        state.mapping_values.add(name)
    elif kind == "authority":
        state.authority_aliases.add(name)


def _scan_statements(body: list[ast.stmt], state: ReflectionState, findings: set[str]) -> None:
    for statement in body:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                bound = alias.asname or alias.name.split(".")[0]
                _bind_name(bound, "other", None, state)
                if alias.name == "builtins":
                    state.builtins_modules.add(bound)
            continue
        if isinstance(statement, ast.ImportFrom):
            for alias in statement.names:
                bound = alias.asname or alias.name
                if statement.module == "builtins" and alias.name in MEMBER_BUILTINS:
                    _bind_name(bound, "member_builtin", alias.name, state)
                elif statement.module == "builtins" and alias.name in MAPPING_BUILTINS:
                    _bind_name(bound, "mapping_builtin", alias.name, state)
                elif alias.name in AUTHORITY_CLASSES:
                    _bind_name(bound, "authority", None, state)
                else:
                    _bind_name(bound, "other", None, state)
            continue
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            value = statement.value
            if value is not None:
                _scan_expression(value, state, findings)
                kind, detail = _assignment_value_kind(value, state, findings)
            else:
                kind, detail = "other", None
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            for target in targets:
                if isinstance(target, ast.Attribute) and target.attr in AUTHORITY_MUTATION_NAMES and _authority_ref(target.value, state):
                    findings.add("authority:direct_namespace_mutation")
                for name in _target_names(target):
                    _bind_name(name, kind, detail, state)
            continue
        if isinstance(statement, ast.AugAssign):
            _scan_expression(statement.value, state, findings)
            if isinstance(statement.target, ast.Attribute) and statement.target.attr in AUTHORITY_MUTATION_NAMES and _authority_ref(statement.target.value, state):
                findings.add("authority:direct_namespace_mutation")
            continue
        if isinstance(statement, ast.Delete):
            for target in statement.targets:
                if isinstance(target, ast.Attribute) and target.attr in AUTHORITY_MUTATION_NAMES and _authority_ref(target.value, state):
                    findings.add("authority:direct_namespace_mutation")
                for name in _target_names(target):
                    _bind_name(name, "other", None, state)
            continue
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in statement.decorator_list:
                _scan_expression(decorator, state, findings)
            for default in [*statement.args.defaults, *[d for d in statement.args.kw_defaults if d is not None]]:
                _scan_expression(default, state, findings)
            child = state.child_for_function(statement.body, statement.args)
            _scan_statements(statement.body, child, findings)
            _bind_name(statement.name, "other", None, state)
            continue
        if isinstance(statement, ast.ClassDef):
            for base in statement.bases:
                _scan_expression(base, state, findings)
            for decorator in statement.decorator_list:
                _scan_expression(decorator, state, findings)
            child = state.branch()
            _scan_statements(statement.body, child, findings)
            _bind_name(statement.name, "authority" if statement.name in AUTHORITY_CLASSES else "other", None, state)
            continue
        if isinstance(statement, ast.If):
            _scan_expression(statement.test, state, findings)
            _scan_statements(statement.body, state.branch(), findings)
            _scan_statements(statement.orelse, state.branch(), findings)
            continue
        if isinstance(statement, (ast.For, ast.AsyncFor)):
            _scan_expression(statement.iter, state, findings)
            branch = state.branch()
            for name in _target_names(statement.target):
                _bind_name(name, "other", None, branch)
            _scan_statements(statement.body, branch, findings)
            _scan_statements(statement.orelse, state.branch(), findings)
            continue
        if isinstance(statement, (ast.With, ast.AsyncWith)):
            branch = state.branch()
            for item in statement.items:
                _scan_expression(item.context_expr, state, findings)
                if item.optional_vars is not None:
                    for name in _target_names(item.optional_vars):
                        _bind_name(name, "other", None, branch)
            _scan_statements(statement.body, branch, findings)
            continue
        if isinstance(statement, ast.Try):
            _scan_statements(statement.body, state.branch(), findings)
            for handler in statement.handlers:
                branch = state.branch()
                if handler.name:
                    _bind_name(handler.name, "other", None, branch)
                _scan_statements(handler.body, branch, findings)
            _scan_statements(statement.orelse, state.branch(), findings)
            _scan_statements(statement.finalbody, state.branch(), findings)
            continue
        for child in ast.iter_child_nodes(statement):
            if isinstance(child, ast.expr):
                _scan_expression(child, state, findings)


def reflection_and_authority_findings(raw: str) -> set[str]:
    tree = ast.parse(raw)
    findings: set[str] = set()
    _scan_statements(tree.body, ReflectionState(), findings)
    return findings


def _leaf_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _static_sequence(value: ast.AST, sequences: dict[str, tuple[str, ...]]) -> tuple[str, ...] | None:
    if isinstance(value, ast.Name):
        return sequences.get(value.id)
    if not isinstance(value, (ast.Tuple, ast.List)):
        return None
    result: list[str] = []
    for item in value.elts:
        if isinstance(item, ast.Starred):
            nested = _static_sequence(item.value, sequences)
            if nested is None:
                return None
            result.extend(nested)
        else:
            name = _leaf_name(item)
            if name is None:
                return None
            result.append(name)
    return tuple(result)


def _resolve_alias(name: str, aliases: dict[str, str]) -> str:
    seen: set[str] = set()
    current = name
    while current in aliases and current not in seen:
        seen.add(current)
        current = aliases[current]
    return current


def _bind_sequence_target(target: ast.AST, values: tuple[str, ...], sequences: dict[str, tuple[str, ...]]) -> None:
    if isinstance(target, ast.Name):
        sequences[target.id] = values
        return
    if not isinstance(target, (ast.Tuple, ast.List)):
        return
    stars = [i for i, item in enumerate(target.elts) if isinstance(item, ast.Starred)]
    if len(stars) > 1:
        return
    if not stars:
        if len(target.elts) != len(values):
            return
        for item, value in zip(target.elts, values):
            if isinstance(item, ast.Name):
                sequences[item.id] = (value,)
        return
    star = stars[0]
    prefix = target.elts[:star]
    suffix = target.elts[star + 1:]
    if len(values) < len(prefix) + len(suffix):
        return
    for item, value in zip(prefix, values[:len(prefix)]):
        if isinstance(item, ast.Name):
            sequences[item.id] = (value,)
    end = len(values) - len(suffix) if suffix else len(values)
    starred = target.elts[star]
    if isinstance(starred, ast.Starred) and isinstance(starred.value, ast.Name):
        sequences[starred.value.id] = values[len(prefix):end]
    if suffix:
        for item, value in zip(suffix, values[-len(suffix):]):
            if isinstance(item, ast.Name):
                sequences[item.id] = (value,)


def broker_path_declarations_ordered(raw: str, label: str) -> list[tuple[str, int, str, set[str]]]:
    tree = ast.parse(raw)
    declarations: list[tuple[str, int, str, set[str]]] = []

    def walk(body: list[ast.stmt], aliases: dict[str, str], sequences: dict[str, tuple[str, ...]]) -> None:
        for statement in body:
            if isinstance(statement, ast.ImportFrom):
                for imported in statement.names:
                    aliases[imported.asname or imported.name] = imported.name
                continue
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                value = statement.value
                if value is None:
                    continue
                targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                source = _leaf_name(value)
                seq = _static_sequence(value, sequences)
                for target in targets:
                    for name in _target_names(target):
                        aliases.pop(name, None)
                        sequences.pop(name, None)
                    if isinstance(target, ast.Name) and source is not None:
                        aliases[target.id] = _resolve_alias(source, aliases)
                    if seq is not None:
                        _bind_sequence_target(target, tuple(_resolve_alias(item, aliases) for item in seq), sequences)
                continue
            if isinstance(statement, ast.ClassDef):
                bases: set[str] = set()
                for base in statement.bases:
                    if isinstance(base, ast.Starred):
                        seq = _static_sequence(base.value, sequences)
                        if seq is None:
                            raise AssertionError(f"unresolved starred class base is forbidden: {label}:{statement.name}@L{statement.lineno}")
                        bases.update(_resolve_alias(item, aliases) for item in seq)
                    else:
                        name = _leaf_name(base)
                        if name is not None:
                            bases.add(_resolve_alias(name, aliases))
                declarations.append((label, statement.lineno, statement.name, bases))
                child_aliases = dict(aliases)
                child_sequences = dict(sequences)
                walk(statement.body, child_aliases, child_sequences)
                aliases[statement.name] = statement.name
                sequences.pop(statement.name, None)
                continue
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                walk(statement.body, dict(aliases), dict(sequences))
                aliases.pop(statement.name, None)
                sequences.pop(statement.name, None)
                continue
            nested_bodies: list[list[ast.stmt]] = []
            if isinstance(statement, ast.If):
                nested_bodies.extend([statement.body, statement.orelse])
            elif isinstance(statement, (ast.For, ast.AsyncFor, ast.While)):
                nested_bodies.extend([statement.body, statement.orelse])
            elif isinstance(statement, (ast.With, ast.AsyncWith)):
                nested_bodies.append(statement.body)
            elif isinstance(statement, ast.Try):
                nested_bodies.extend([statement.body, statement.orelse, statement.finalbody])
                nested_bodies.extend(handler.body for handler in statement.handlers)
            for nested in nested_bodies:
                walk(nested, dict(aliases), dict(sequences))

    walk(tree.body, {}, {})
    return declarations


def _governed_python_sources(inventory: dict) -> list[Path]:
    paths = [BOUNDARY_SOURCE]
    for root_value in inventory["implementation_code_roots"]:
        root = ROOT / root_value
        if root.exists():
            paths.extend(sorted(root.rglob("*.py")))
    paths.extend(sorted(ASSURANCE_DIR.rglob("*.py")))
    return list(dict.fromkeys(paths))


def assert_ordered_broker_path_inventory(inventory: dict) -> None:
    declarations: list[tuple[str, int, str, set[str]]] = []
    for path in _governed_python_sources(inventory):
        declarations.extend(broker_path_declarations_ordered(path.read_text(encoding="utf-8"), path.relative_to(ROOT).as_posix()))
    descendant_symbols = {"BrokerFacingPath"}
    changed = True
    while changed:
        changed = False
        for _, _, class_name, bases in declarations:
            if class_name not in descendant_symbols and bases & descendant_symbols:
                descendant_symbols.add(class_name)
                changed = True
    discovered = [
        (label, line, class_name)
        for label, line, class_name, bases in declarations
        if class_name != "BrokerFacingPath" and class_name in descendant_symbols and bases & descendant_symbols
    ]
    names = [item[2] for item in discovered]
    if set(names) != EXPECTED_PATH_CLASSES or len(names) != len(EXPECTED_PATH_CLASSES):
        raise AssertionError(f"ordered broker-path inventory mismatch: {discovered}")


def run_negative_controls() -> None:
    cases = {
        "callable_alias": "transaction = getattr(client, transaction_name)\ntransaction()",
        "qualified_vars": "import builtins\nbuiltins.vars(client)[transaction_name]()",
        "imported_vars": "from builtins import vars as namespace\nnamespace(client)[transaction_name]()",
        "assigned_mapping": "namespace = vars(client)\nnamespace[transaction_name]()",
    }
    for label, source in cases.items():
        findings = reflection_and_authority_findings(source)
        if not any(item.startswith("reflection:") for item in findings):
            raise AssertionError(f"{label} escaped lexical reflection guard")

    shadowed = """
def test(record, field_name):
    def getattr(obj, name):
        return lambda: None
    getattr(record, field_name)()
"""
    if reflection_and_authority_findings(shadowed):
        raise AssertionError("lexically shadowed getattr produced a false reflective finding")

    base_mutation = """
class BrokerFacingPath: pass
class InboxAcknowledgePath(BrokerFacingPath): pass
InboxAcknowledgePath.__bases__ = (EvilBase,)
"""
    if "authority:direct_namespace_mutation" not in reflection_and_authority_findings(base_mutation):
        raise AssertionError("direct __bases__ replacement escaped authority guard")

    reflective_base_mutation = """
class BrokerFacingPath: pass
class InboxAcknowledgePath(BrokerFacingPath): pass
mutate = setattr
mutate(InboxAcknowledgePath, '__bases__', (EvilBase,))
"""
    if "authority:reflective_namespace_mutation" not in reflection_and_authority_findings(reflective_base_mutation):
        raise AssertionError("reflective __bases__ replacement escaped authority guard")

    ordered = """
*Bases, = (OutboxDispatchPath,)
class EscapingPath(*Bases):
    pass
*Bases, = (object,)
"""
    declarations = broker_path_declarations_ordered(ordered, "negative-control")
    escaping = next(item for item in declarations if item[2] == "EscapingPath")
    if "OutboxDispatchPath" not in escaping[3]:
        raise AssertionError("later sequence rebinding rewrote an earlier class declaration")

    copied = """
Bases = (OutboxDispatchPath,)
Alias = Bases
class EscapingPath(*Alias):
    pass
"""
    declarations = broker_path_declarations_ordered(copied, "negative-control")
    escaping = next(item for item in declarations if item[2] == "EscapingPath")
    if "OutboxDispatchPath" not in escaping[3]:
        raise AssertionError("ordinary/copied sequence alias escaped starred-base discovery")

    unresolved = """
Bases = choose_bases()
class EscapingPath(*Bases):
    pass
"""
    try:
        broker_path_declarations_ordered(unresolved, "negative-control")
    except AssertionError:
        pass
    else:
        raise AssertionError("unresolved starred class base did not fail closed")


def main() -> int:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    findings: list[str] = []
    for path in _governed_python_sources(inventory):
        raw = path.read_text(encoding="utf-8")
        for finding in sorted(reflection_and_authority_findings(raw)):
            findings.append(f"{path.relative_to(ROOT).as_posix()}:{finding}")
    if findings:
        raise AssertionError(f"lexical reflection/authority guard findings: {findings}")
    assert_ordered_broker_path_inventory(inventory)
    run_negative_controls()
    print(
        "d4a_lexical_reflection_hierarchy=PASS "
        "reflection=callable_alias+qualified_imported_vars+mapping_alias+lexical_shadowing_aware "
        "authority=base_replacement_rejected "
        "broker_paths=order_scoped_sequence_aliases+ordinary_copy+unresolved_starred_fail_closed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())