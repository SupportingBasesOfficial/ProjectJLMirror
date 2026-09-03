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
    elif isinstance(target, ast.Starred):
        names.update(_target_names(target.value))
    elif isinstance(target, (ast.Tuple, ast.List)):
        for item in target.elts:
            names.update(_target_names(item))
    return names


def _terminates(body: list[ast.stmt]) -> bool:
    if not body:
        return False
    last = body[-1]
    return isinstance(last, (ast.Raise, ast.Return))


@dataclass
class State:
    member_aliases: dict[str, str] = field(default_factory=lambda: {name: name for name in MEMBER_BUILTINS})
    mapping_aliases: dict[str, str] = field(default_factory=lambda: {name: name for name in MAPPING_BUILTINS})
    builtins_modules: set[str] = field(default_factory=lambda: {"builtins"})
    reflected_callables: set[str] = field(default_factory=set)
    mapping_values: set[str] = field(default_factory=set)
    authority_aliases: set[str] = field(default_factory=lambda: set(AUTHORITY_CLASSES))

    def copy(self) -> "State":
        return State(
            member_aliases=dict(self.member_aliases),
            mapping_aliases=dict(self.mapping_aliases),
            builtins_modules=set(self.builtins_modules),
            reflected_callables=set(self.reflected_callables),
            mapping_values=set(self.mapping_values),
            authority_aliases=set(self.authority_aliases),
        )

    def absorb_possible(self, other: "State") -> None:
        self.reflected_callables |= other.reflected_callables
        self.mapping_values |= other.mapping_values
        self.authority_aliases |= other.authority_aliases
        for name, value in other.member_aliases.items():
            if name not in self.member_aliases:
                self.member_aliases[name] = value
        for name, value in other.mapping_aliases.items():
            if name not in self.mapping_aliases:
                self.mapping_aliases[name] = value
        self.builtins_modules |= other.builtins_modules

    def clear_name(self, name: str) -> None:
        self.member_aliases.pop(name, None)
        self.mapping_aliases.pop(name, None)
        self.reflected_callables.discard(name)
        self.mapping_values.discard(name)
        self.builtins_modules.discard(name)
        if name not in AUTHORITY_CLASSES:
            self.authority_aliases.discard(name)


def _member_builtin(node: ast.AST, state: State) -> str | None:
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


def _mapping_builtin(node: ast.AST, state: State) -> str | None:
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


def _is_mapping(node: ast.AST, state: State) -> bool:
    if isinstance(node, ast.Name) and node.id in state.mapping_values:
        return True
    if isinstance(node, ast.Attribute) and node.attr == "__dict__":
        return True
    return isinstance(node, ast.Call) and _mapping_builtin(node.func, state) == "vars"


def _reflection_member(node: ast.AST, state: State) -> str | None | bool:
    if isinstance(node, ast.Call) and _member_builtin(node.func, state) in {"getattr", "hasattr"} and len(node.args) >= 2:
        value = _constant_string(node.args[1])
        return value if value is not None else False
    if isinstance(node, ast.Subscript) and _is_mapping(node.value, state):
        value = _constant_string(node.slice)
        return value if value is not None else False
    return None


def _authority_ref(node: ast.AST, state: State) -> bool:
    if isinstance(node, ast.Name):
        return node.id in state.authority_aliases
    if isinstance(node, ast.Attribute):
        return node.attr in AUTHORITY_CLASSES
    return False


def _type_mutation_owner(node: ast.AST, state: State) -> bool:
    if isinstance(node, ast.Name) and node.id == "type":
        return True
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "type"
        and len(node.args) == 1
        and _authority_ref(node.args[0], state)
    )


def _scan_expr(node: ast.AST, state: State, findings: set[str], *, called: bool = False) -> None:
    reflected = _reflection_member(node, state)
    if reflected is False and called:
        findings.add("reflection:unresolved_callable_member")
    elif isinstance(reflected, str):
        transaction = _normalized_transaction(reflected)
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
            and _type_mutation_owner(node.func.value, state)
            and len(node.args) >= 2
            and _authority_ref(node.args[0], state)
        ):
            name = _constant_string(node.args[1])
            if name is None or name in AUTHORITY_MUTATION_NAMES:
                findings.add("authority:type_namespace_mutation")
        _scan_expr(node.func, state, findings, called=True)
        for arg in node.args:
            _scan_expr(arg, state, findings)
        for keyword in node.keywords:
            _scan_expr(keyword.value, state, findings)
        return
    for child in ast.iter_child_nodes(node):
        _scan_expr(child, state, findings)


def _value_kind(value: ast.AST, state: State, findings: set[str]) -> tuple[str, str | None]:
    if isinstance(value, ast.Name):
        if value.id in state.member_aliases:
            return "member", state.member_aliases[value.id]
        if value.id in state.mapping_aliases:
            return "mapping_builtin", state.mapping_aliases[value.id]
        if value.id in state.reflected_callables:
            return "reflected", None
        if value.id in state.mapping_values:
            return "mapping_value", None
        if value.id in state.authority_aliases:
            return "authority", None
    if isinstance(value, ast.Attribute):
        member = _member_builtin(value, state)
        if member is not None:
            return "member", member
        mapping = _mapping_builtin(value, state)
        if mapping is not None:
            return "mapping_builtin", mapping
        if value.attr in AUTHORITY_CLASSES:
            return "authority", None
        if value.attr == "__dict__":
            return "mapping_value", None
    if isinstance(value, ast.Call) and _mapping_builtin(value.func, state) == "vars":
        return "mapping_value", None
    reflected = _reflection_member(value, state)
    if reflected is False:
        return "reflected", None
    if isinstance(reflected, str):
        transaction = _normalized_transaction(reflected)
        if transaction is not None:
            findings.add(f"reflection:transaction_member:{transaction}")
    return "other", None


def _bind(name: str, kind: str, detail: str | None, state: State) -> None:
    state.clear_name(name)
    if kind == "member" and detail is not None:
        state.member_aliases[name] = detail
    elif kind == "mapping_builtin" and detail is not None:
        state.mapping_aliases[name] = detail
    elif kind == "reflected":
        state.reflected_callables.add(name)
    elif kind == "mapping_value":
        state.mapping_values.add(name)
    elif kind == "authority":
        state.authority_aliases.add(name)


def _sequence_values(value: ast.AST) -> list[ast.AST] | None:
    if not isinstance(value, (ast.Tuple, ast.List)):
        return None
    result: list[ast.AST] = []
    for item in value.elts:
        if isinstance(item, ast.Starred):
            nested = _sequence_values(item.value)
            if nested is None:
                return None
            result.extend(nested)
        else:
            result.append(item)
    return result


def _bind_pattern(target: ast.AST, value: ast.AST, state: State, findings: set[str]) -> None:
    if isinstance(target, ast.Name):
        kind, detail = _value_kind(value, state, findings)
        _bind(target.id, kind, detail, state)
        return
    if isinstance(target, ast.Starred):
        for name in _target_names(target):
            _bind(name, "other", None, state)
        return
    if not isinstance(target, (ast.Tuple, ast.List)):
        return
    values = _sequence_values(value)
    if values is None:
        for name in _target_names(target):
            _bind(name, "other", None, state)
        return
    stars = [i for i, item in enumerate(target.elts) if isinstance(item, ast.Starred)]
    if len(stars) > 1:
        for name in _target_names(target):
            _bind(name, "other", None, state)
        return
    if not stars:
        if len(target.elts) != len(values):
            for name in _target_names(target):
                _bind(name, "other", None, state)
            return
        for t_item, v_item in zip(target.elts, values):
            _bind_pattern(t_item, v_item, state, findings)
        return
    star = stars[0]
    prefix = target.elts[:star]
    suffix = target.elts[star + 1:]
    if len(values) < len(prefix) + len(suffix):
        for name in _target_names(target):
            _bind(name, "other", None, state)
        return
    for t_item, v_item in zip(prefix, values[:len(prefix)]):
        _bind_pattern(t_item, v_item, state, findings)
    if suffix:
        for t_item, v_item in zip(suffix, values[-len(suffix):]):
            _bind_pattern(t_item, v_item, state, findings)
    starred = target.elts[star]
    if isinstance(starred, ast.Starred):
        for name in _target_names(starred):
            _bind(name, "other", None, state)


def _scan_statements(body: list[ast.stmt], state: State, findings: set[str]) -> None:
    for statement in body:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                bound = alias.asname or alias.name.split(".")[0]
                state.clear_name(bound)
                if alias.name == "builtins":
                    state.builtins_modules.add(bound)
            continue
        if isinstance(statement, ast.ImportFrom):
            for alias in statement.names:
                bound = alias.asname or alias.name
                if statement.module == "builtins" and alias.name in MEMBER_BUILTINS:
                    _bind(bound, "member", alias.name, state)
                elif statement.module == "builtins" and alias.name in MAPPING_BUILTINS:
                    _bind(bound, "mapping_builtin", alias.name, state)
                elif alias.name in AUTHORITY_CLASSES:
                    _bind(bound, "authority", None, state)
                else:
                    _bind(bound, "other", None, state)
            continue
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            value = statement.value
            if value is not None:
                _scan_expr(value, state, findings)
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            for target in targets:
                if isinstance(target, ast.Attribute) and target.attr in AUTHORITY_MUTATION_NAMES and _authority_ref(target.value, state):
                    findings.add("authority:direct_namespace_mutation")
                if value is not None:
                    _bind_pattern(target, value, state, findings)
                else:
                    for name in _target_names(target):
                        _bind(name, "other", None, state)
            continue
        if isinstance(statement, ast.Delete):
            for target in statement.targets:
                if isinstance(target, ast.Attribute) and target.attr in AUTHORITY_MUTATION_NAMES and _authority_ref(target.value, state):
                    findings.add("authority:direct_namespace_mutation")
                for name in _target_names(target):
                    state.clear_name(name)
            continue
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in statement.decorator_list:
                _scan_expr(decorator, state, findings)
            child = state.copy()
            for arg in [*statement.args.posonlyargs, *statement.args.args, *statement.args.kwonlyargs]:
                child.clear_name(arg.arg)
            if statement.args.vararg is not None:
                child.clear_name(statement.args.vararg.arg)
            if statement.args.kwarg is not None:
                child.clear_name(statement.args.kwarg.arg)
            _scan_statements(statement.body, child, findings)
            _bind(statement.name, "other", None, state)
            continue
        if isinstance(statement, ast.ClassDef):
            for base in statement.bases:
                _scan_expr(base, state, findings)
            child = state.copy()
            _scan_statements(statement.body, child, findings)
            _bind(statement.name, "authority" if statement.name in AUTHORITY_CLASSES else "other", None, state)
            continue
        if isinstance(statement, ast.If):
            _scan_expr(statement.test, state, findings)
            left = state.copy()
            right = state.copy()
            _scan_statements(statement.body, left, findings)
            _scan_statements(statement.orelse, right, findings)
            if _terminates(statement.orelse) and not _terminates(statement.body):
                state.__dict__.update(left.__dict__)
            elif _terminates(statement.body) and not _terminates(statement.orelse):
                state.__dict__.update(right.__dict__)
            else:
                state.absorb_possible(left)
                state.absorb_possible(right)
            continue
        if isinstance(statement, (ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try)):
            branches: list[list[ast.stmt]] = []
            if isinstance(statement, (ast.For, ast.AsyncFor, ast.While)):
                branches.extend([statement.body, statement.orelse])
            elif isinstance(statement, (ast.With, ast.AsyncWith)):
                branches.append(statement.body)
            else:
                branches.extend([statement.body, statement.orelse, statement.finalbody])
                branches.extend(handler.body for handler in statement.handlers)
            for branch_body in branches:
                branch = state.copy()
                _scan_statements(branch_body, branch, findings)
                state.absorb_possible(branch)
            continue
        for child in ast.iter_child_nodes(statement):
            if isinstance(child, ast.expr):
                _scan_expr(child, state, findings)


def reflection_and_authority_findings(raw: str) -> set[str]:
    tree = ast.parse(raw)
    findings: set[str] = set()
    _scan_statements(tree.body, State(), findings)
    return findings


def _leaf_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _resolve_alias(name: str, aliases: dict[str, str]) -> str:
    seen: set[str] = set()
    current = name
    while current in aliases and current not in seen:
        seen.add(current)
        current = aliases[current]
    return current


def _snapshot_sequence(value: ast.AST, aliases: dict[str, str], sequences: dict[str, tuple[str, ...]]) -> tuple[str, ...] | None:
    if isinstance(value, ast.Name):
        if value.id in sequences:
            return sequences[value.id]
        return (_resolve_alias(value.id, aliases),)
    if isinstance(value, ast.Attribute):
        return (_resolve_alias(value.attr, aliases),)
    if not isinstance(value, (ast.Tuple, ast.List)):
        return None
    result: list[str] = []
    for item in value.elts:
        if isinstance(item, ast.Starred):
            nested = _snapshot_sequence(item.value, aliases, sequences)
            if nested is None:
                return None
            result.extend(nested)
        else:
            snapshot = _snapshot_sequence(item, aliases, sequences)
            if snapshot is None or len(snapshot) != 1:
                return None
            result.extend(snapshot)
    return tuple(result)


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


def broker_path_declarations(raw: str, label: str) -> list[tuple[str, int, str, set[str]]]:
    tree = ast.parse(raw)
    declarations: list[tuple[str, int, str, set[str]]] = []

    def walk(body: list[ast.stmt], aliases: dict[str, str], sequences: dict[str, tuple[str, ...]]) -> None:
        for statement in body:
            if isinstance(statement, ast.ImportFrom):
                for imported in statement.names:
                    aliases[imported.asname or imported.name] = _resolve_alias(imported.name, aliases)
                continue
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                value = statement.value
                if value is None:
                    continue
                targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                snapshot = _snapshot_sequence(value, aliases, sequences)
                leaf = _leaf_name(value)
                resolved_leaf = _resolve_alias(leaf, aliases) if leaf is not None else None
                for target in targets:
                    for name in _target_names(target):
                        aliases.pop(name, None)
                        sequences.pop(name, None)
                    if isinstance(target, ast.Name) and resolved_leaf is not None:
                        aliases[target.id] = resolved_leaf
                    if snapshot is not None:
                        _bind_sequence_target(target, snapshot, sequences)
                continue
            if isinstance(statement, ast.ClassDef):
                bases: set[str] = set()
                for base in statement.bases:
                    if isinstance(base, ast.Starred):
                        snapshot = _snapshot_sequence(base.value, aliases, sequences)
                        if snapshot is None:
                            raise AssertionError(f"unresolved starred class base is forbidden: {label}:{statement.name}@L{statement.lineno}")
                        bases.update(snapshot)
                    elif isinstance(base, (ast.Name, ast.Attribute)):
                        name = _leaf_name(base)
                        assert name is not None
                        bases.add(_resolve_alias(name, aliases))
                    else:
                        raise AssertionError(f"unresolved ordinary class base is forbidden: {label}:{statement.name}@L{statement.lineno}")
                declarations.append((label, statement.lineno, statement.name, bases))
                walk(statement.body, dict(aliases), dict(sequences))
                aliases[statement.name] = statement.name
                sequences.pop(statement.name, None)
                continue
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                walk(statement.body, dict(aliases), dict(sequences))
                aliases.pop(statement.name, None)
                sequences.pop(statement.name, None)
                continue
            nested: list[list[ast.stmt]] = []
            if isinstance(statement, ast.If):
                nested.extend([statement.body, statement.orelse])
            elif isinstance(statement, (ast.For, ast.AsyncFor, ast.While)):
                nested.extend([statement.body, statement.orelse])
            elif isinstance(statement, (ast.With, ast.AsyncWith)):
                nested.append(statement.body)
            elif isinstance(statement, ast.Try):
                nested.extend([statement.body, statement.orelse, statement.finalbody])
                nested.extend(handler.body for handler in statement.handlers)
            for branch in nested:
                walk(branch, dict(aliases), dict(sequences))

    walk(tree.body, {}, {})
    return declarations


def _governed_sources(inventory: dict) -> list[Path]:
    paths = [BOUNDARY_SOURCE]
    for root_value in inventory["implementation_code_roots"]:
        root = ROOT / root_value
        if root.exists():
            paths.extend(sorted(root.rglob("*.py")))
    paths.extend(sorted(ASSURANCE_DIR.rglob("*.py")))
    return list(dict.fromkeys(paths))


def assert_broker_inventory(inventory: dict) -> None:
    declarations: list[tuple[str, int, str, set[str]]] = []
    for path in _governed_sources(inventory):
        declarations.extend(broker_path_declarations(path.read_text(encoding="utf-8"), path.relative_to(ROOT).as_posix()))
    descendants = {"BrokerFacingPath"}
    changed = True
    while changed:
        changed = False
        for _, _, class_name, bases in declarations:
            if class_name not in descendants and bases & descendants:
                descendants.add(class_name)
                changed = True
    discovered = [
        (label, line, class_name)
        for label, line, class_name, bases in declarations
        if class_name != "BrokerFacingPath" and class_name in descendants and bases & descendants
    ]
    names = [item[2] for item in discovered]
    if set(names) != EXPECTED_PATH_CLASSES or len(names) != len(EXPECTED_PATH_CLASSES):
        raise AssertionError(f"snapshot-aware broker-path inventory mismatch: {discovered}")


def run_negative_controls() -> None:
    reflection_cases = {
        "destructured_mapping": "(namespace,) = (vars(client),)\ntransaction = namespace[transaction_name]\ntransaction()",
        "branch_survivor": "if enabled:\n    namespace = vars(client)\nelse:\n    raise RuntimeError()\ntransaction = namespace[transaction_name]\ntransaction()",
        "dynamic_type_mutation": "class BrokerFacingPath: pass\nclass InboxAcknowledgePath(BrokerFacingPath): pass\ntype(InboxAcknowledgePath).__setattr__(InboxAcknowledgePath, '__bases__', (EvilBase,))",
    }
    for label, source in reflection_cases.items():
        findings = reflection_and_authority_findings(source)
        if not findings:
            raise AssertionError(f"{label} escaped v2 lexical/authority guard")

    shadowed_module = "builtins = Helper()\nbuiltins.vars(record)[field_name]()"
    if reflection_and_authority_findings(shadowed_module):
        raise AssertionError("shadowed builtins module alias produced a false reflective finding")

    captured_before_rebind = "Bases = (OutboxDispatchPath,)\nOutboxDispatchPath = object\nclass EscapingPath(*Bases):\n    pass"
    escaping = next(item for item in broker_path_declarations(captured_before_rebind, "negative-control") if item[2] == "EscapingPath")
    if "OutboxDispatchPath" not in escaping[3]:
        raise AssertionError("captured base identity was rewritten by later symbol rebinding")

    ordinary_expression = "class EscapingPath((OutboxDispatchPath,)[0]):\n    pass"
    try:
        broker_path_declarations(ordinary_expression, "negative-control")
    except AssertionError:
        pass
    else:
        raise AssertionError("unrecognized ordinary class base did not fail closed")


def main() -> int:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    findings: list[str] = []
    for path in _governed_sources(inventory):
        for finding in sorted(reflection_and_authority_findings(path.read_text(encoding="utf-8"))):
            findings.append(f"{path.relative_to(ROOT).as_posix()}:{finding}")
    if findings:
        raise AssertionError(f"v2 lexical reflection/authority guard findings: {findings}")
    assert_broker_inventory(inventory)
    run_negative_controls()
    print(
        "d4a_lexical_reflection_hierarchy_v2=PASS "
        "reflection=destructuring+branch_survivor+callable_mapping_alias+shadowed_builtins_order_aware "
        "authority=direct_reflective_and_dynamic_type_base_mutation_rejected "
        "broker_paths=capture_time_snapshots+symbol_rebinding_safe+ordinary_and_starred_unresolved_fail_closed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
