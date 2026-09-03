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


def _constant_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _constant_string(node.left)
        right = _constant_string(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _normalized_transaction(value: str) -> str | None:
    value = value.lower().replace("_", "")
    return value if value in TRANSACTION_METHODS else None


def _target_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, ast.Starred):
        return _target_names(node.value)
    if isinstance(node, (ast.Tuple, ast.List)):
        out: set[str] = set()
        for item in node.elts:
            out |= _target_names(item)
        return out
    return set()


def _terminates(body: list[ast.stmt]) -> bool:
    return bool(body) and isinstance(body[-1], (ast.Raise, ast.Return))


@dataclass
class FlowState:
    member_aliases: dict[str, str] = field(default_factory=lambda: {
        "getattr": "getattr", "hasattr": "hasattr", "setattr": "setattr", "delattr": "delattr"
    })
    mapping_aliases: set[str] = field(default_factory=lambda: {"vars"})
    builtins_modules: set[str] = field(default_factory=lambda: {"builtins"})
    type_aliases: set[str] = field(default_factory=lambda: {"type"})
    reflected_callables: set[str] = field(default_factory=set)
    mapping_values: set[str] = field(default_factory=set)
    mapping_sequences: set[str] = field(default_factory=set)
    authority_aliases: set[str] = field(default_factory=lambda: set(AUTHORITY_CLASSES))

    def copy(self) -> "FlowState":
        return FlowState(
            member_aliases=dict(self.member_aliases),
            mapping_aliases=set(self.mapping_aliases),
            builtins_modules=set(self.builtins_modules),
            type_aliases=set(self.type_aliases),
            reflected_callables=set(self.reflected_callables),
            mapping_values=set(self.mapping_values),
            mapping_sequences=set(self.mapping_sequences),
            authority_aliases=set(self.authority_aliases),
        )

    def clear(self, name: str) -> None:
        self.member_aliases.pop(name, None)
        self.mapping_aliases.discard(name)
        self.builtins_modules.discard(name)
        self.type_aliases.discard(name)
        self.reflected_callables.discard(name)
        self.mapping_values.discard(name)
        self.mapping_sequences.discard(name)
        if name not in AUTHORITY_CLASSES:
            self.authority_aliases.discard(name)


def _member_builtin(node: ast.AST, state: FlowState) -> str | None:
    if isinstance(node, ast.Name):
        return state.member_aliases.get(node.id)
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in state.builtins_modules:
        if node.attr in {"getattr", "hasattr", "setattr", "delattr"}:
            return node.attr
    return None


def _is_vars_callable(node: ast.AST, state: FlowState) -> bool:
    if isinstance(node, ast.Name):
        return node.id in state.mapping_aliases
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "vars"
        and isinstance(node.value, ast.Name)
        and node.value.id in state.builtins_modules
    )


def _authority_ref(node: ast.AST, state: FlowState) -> bool:
    if isinstance(node, ast.Name):
        return node.id in state.authority_aliases
    return isinstance(node, ast.Attribute) and node.attr in AUTHORITY_CLASSES


def _mapping_expr(node: ast.AST, state: FlowState) -> bool:
    if isinstance(node, ast.Name) and node.id in state.mapping_values:
        return True
    if isinstance(node, ast.Attribute) and node.attr == "__dict__":
        return True
    if isinstance(node, ast.Call) and _is_vars_callable(node.func, state):
        return True
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id in state.mapping_sequences
    ):
        return True
    return False


def _reflection_member(node: ast.AST, state: FlowState) -> str | None | bool:
    if isinstance(node, ast.Call) and _member_builtin(node.func, state) in {"getattr", "hasattr"} and len(node.args) >= 2:
        value = _constant_string(node.args[1])
        return value if value is not None else False
    if isinstance(node, ast.Subscript) and _mapping_expr(node.value, state):
        value = _constant_string(node.slice)
        return value if value is not None else False
    return None


def _type_owner(node: ast.AST, state: FlowState) -> bool:
    if isinstance(node, ast.Name):
        return node.id in state.type_aliases
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in state.type_aliases:
        return len(node.args) == 1 and _authority_ref(node.args[0], state)
    return False


def _scan_expr(node: ast.AST, state: FlowState, findings: set[str], *, called: bool = False) -> None:
    reflected = _reflection_member(node, state)
    if reflected is False and called:
        findings.add("reflection:unresolved_callable_member")
    elif isinstance(reflected, str):
        transaction = _normalized_transaction(reflected)
        if transaction:
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
            and _type_owner(node.func.value, state)
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


def _kind(value: ast.AST, state: FlowState, findings: set[str]) -> str:
    if isinstance(value, ast.Name):
        if value.id in state.member_aliases:
            return f"member:{state.member_aliases[value.id]}"
        if value.id in state.mapping_aliases:
            return "mapping_builtin"
        if value.id in state.type_aliases:
            return "type"
        if value.id in state.reflected_callables:
            return "reflected"
        if value.id in state.mapping_values:
            return "mapping_value"
        if value.id in state.mapping_sequences:
            return "mapping_sequence"
        if value.id in state.authority_aliases:
            return "authority"
    if isinstance(value, ast.Attribute):
        member = _member_builtin(value, state)
        if member:
            return f"member:{member}"
        if _is_vars_callable(value, state):
            return "mapping_builtin"
        if isinstance(value.value, ast.Name) and value.value.id in state.builtins_modules and value.attr == "type":
            return "type"
        if value.attr in AUTHORITY_CLASSES:
            return "authority"
        if value.attr == "__dict__":
            return "mapping_value"
    if isinstance(value, ast.Call) and _is_vars_callable(value.func, state):
        return "mapping_value"
    reflected = _reflection_member(value, state)
    if reflected is False:
        return "reflected"
    if isinstance(reflected, str) and _normalized_transaction(reflected):
        findings.add(f"reflection:transaction_member:{_normalized_transaction(reflected)}")
    return "other"


def _bind(name: str, kind: str, state: FlowState) -> None:
    state.clear(name)
    if kind.startswith("member:"):
        state.member_aliases[name] = kind.split(":", 1)[1]
    elif kind == "mapping_builtin":
        state.mapping_aliases.add(name)
    elif kind == "type":
        state.type_aliases.add(name)
    elif kind == "reflected":
        state.reflected_callables.add(name)
    elif kind == "mapping_value":
        state.mapping_values.add(name)
    elif kind == "mapping_sequence":
        state.mapping_sequences.add(name)
    elif kind == "authority":
        state.authority_aliases.add(name)


def _sequence_nodes(value: ast.AST) -> list[ast.AST] | None:
    if not isinstance(value, (ast.Tuple, ast.List)):
        return None
    out: list[ast.AST] = []
    for item in value.elts:
        if isinstance(item, ast.Starred):
            nested = _sequence_nodes(item.value)
            if nested is None:
                return None
            out.extend(nested)
        else:
            out.append(item)
    return out


def _bind_pattern(target: ast.AST, value: ast.AST, state: FlowState, findings: set[str]) -> None:
    if isinstance(target, ast.Name):
        _bind(target.id, _kind(value, state, findings), state)
        return
    if isinstance(target, ast.Starred):
        names = _target_names(target)
        nodes = _sequence_nodes(value)
        if nodes is not None and nodes and all(_kind(item, state, findings) == "mapping_value" for item in nodes):
            for name in names:
                _bind(name, "mapping_sequence", state)
        else:
            for name in names:
                _bind(name, "other", state)
        return
    if not isinstance(target, (ast.Tuple, ast.List)):
        return
    values = _sequence_nodes(value)
    if values is None:
        for name in _target_names(target):
            _bind(name, "other", state)
        return
    stars = [i for i, item in enumerate(target.elts) if isinstance(item, ast.Starred)]
    if len(stars) > 1:
        for name in _target_names(target):
            _bind(name, "other", state)
        return
    if not stars:
        if len(target.elts) != len(values):
            for name in _target_names(target):
                _bind(name, "other", state)
            return
        for t_item, v_item in zip(target.elts, values):
            _bind_pattern(t_item, v_item, state, findings)
        return
    star = stars[0]
    prefix = target.elts[:star]
    suffix = target.elts[star + 1:]
    if len(values) < len(prefix) + len(suffix):
        for name in _target_names(target):
            _bind(name, "other", state)
        return
    for t_item, v_item in zip(prefix, values[:len(prefix)]):
        _bind_pattern(t_item, v_item, state, findings)
    if suffix:
        for t_item, v_item in zip(suffix, values[-len(suffix):]):
            _bind_pattern(t_item, v_item, state, findings)
    captured = values[len(prefix): len(values) - len(suffix) if suffix else len(values)]
    _bind_pattern(target.elts[star], ast.List(elts=captured, ctx=ast.Load()), state, findings)


def _merge_states(states: list[FlowState]) -> FlowState:
    assert states
    out = states[0].copy()
    # Aliases that are identity-sensitive survive only when every feasible branch agrees.
    for name in set(out.member_aliases):
        values = {state.member_aliases.get(name) for state in states}
        if len(values) != 1 or None in values:
            out.member_aliases.pop(name, None)
    out.mapping_aliases &= set.intersection(*(state.mapping_aliases for state in states[1:])) if len(states) > 1 else out.mapping_aliases
    out.builtins_modules &= set.intersection(*(state.builtins_modules for state in states[1:])) if len(states) > 1 else out.builtins_modules
    out.type_aliases &= set.intersection(*(state.type_aliases for state in states[1:])) if len(states) > 1 else out.type_aliases
    # Potential authority/reflection values are conservative unions: if any feasible path carries them, scan subsequent uses as risky.
    for state in states[1:]:
        out.reflected_callables |= state.reflected_callables
        out.mapping_values |= state.mapping_values
        out.mapping_sequences |= state.mapping_sequences
        out.authority_aliases |= state.authority_aliases
    return out


def _apply_default_bindings(statement: ast.FunctionDef | ast.AsyncFunctionDef, parent: FlowState, child: FlowState, findings: set[str]) -> None:
    positional = [*statement.args.posonlyargs, *statement.args.args]
    defaults = list(statement.args.defaults)
    if defaults:
        for arg, default in zip(positional[-len(defaults):], defaults):
            _scan_expr(default, parent, findings)
            _bind(arg.arg, _kind(default, parent, findings), child)
    for arg, default in zip(statement.args.kwonlyargs, statement.args.kw_defaults):
        if default is not None:
            _scan_expr(default, parent, findings)
            _bind(arg.arg, _kind(default, parent, findings), child)


def _scan_statements(body: list[ast.stmt], state: FlowState, findings: set[str]) -> None:
    for statement in body:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                name = alias.asname or alias.name.split(".")[0]
                state.clear(name)
                if alias.name == "builtins":
                    state.builtins_modules.add(name)
            continue
        if isinstance(statement, ast.ImportFrom):
            for alias in statement.names:
                name = alias.asname or alias.name
                if statement.module == "builtins" and alias.name in {"getattr", "hasattr", "setattr", "delattr"}:
                    _bind(name, f"member:{alias.name}", state)
                elif statement.module == "builtins" and alias.name == "vars":
                    _bind(name, "mapping_builtin", state)
                elif statement.module == "builtins" and alias.name == "type":
                    _bind(name, "type", state)
                elif alias.name in AUTHORITY_CLASSES:
                    _bind(name, "authority", state)
                else:
                    _bind(name, "other", state)
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
                        state.clear(name)
            continue
        if isinstance(statement, ast.Delete):
            for target in statement.targets:
                for name in _target_names(target):
                    state.clear(name)
            continue
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in statement.decorator_list:
                _scan_expr(decorator, state, findings)
            child = state.copy()
            for arg in [*statement.args.posonlyargs, *statement.args.args, *statement.args.kwonlyargs]:
                child.clear(arg.arg)
            if statement.args.vararg:
                child.clear(statement.args.vararg.arg)
            if statement.args.kwarg:
                child.clear(statement.args.kwarg.arg)
            _apply_default_bindings(statement, state, child, findings)
            _scan_statements(statement.body, child, findings)
            _bind(statement.name, "other", state)
            continue
        if isinstance(statement, ast.ClassDef):
            for base in statement.bases:
                _scan_expr(base, state, findings)
            child = state.copy()
            _scan_statements(statement.body, child, findings)
            _bind(statement.name, "authority" if statement.name in AUTHORITY_CLASSES else "other", state)
            continue
        if isinstance(statement, ast.If):
            _scan_expr(statement.test, state, findings)
            left = state.copy(); right = state.copy()
            _scan_statements(statement.body, left, findings)
            _scan_statements(statement.orelse, right, findings)
            feasible: list[FlowState] = []
            if not _terminates(statement.body): feasible.append(left)
            if not _terminates(statement.orelse): feasible.append(right)
            if feasible:
                merged = _merge_states(feasible)
                state.__dict__.update(merged.__dict__)
            continue
        if isinstance(statement, (ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try)):
            # Analyze every nested body for findings; keep the incoming state after uncertain loop/exception execution.
            bodies: list[list[ast.stmt]] = []
            if isinstance(statement, (ast.For, ast.AsyncFor, ast.While)):
                bodies += [statement.body, statement.orelse]
            elif isinstance(statement, (ast.With, ast.AsyncWith)):
                bodies += [statement.body]
            else:
                bodies += [statement.body, statement.orelse, statement.finalbody]
                bodies += [handler.body for handler in statement.handlers]
            for nested in bodies:
                _scan_statements(nested, state.copy(), findings)
            continue
        for child in ast.iter_child_nodes(statement):
            if isinstance(child, ast.expr):
                _scan_expr(child, state, findings)


def reflection_and_authority_findings(raw: str) -> set[str]:
    findings: set[str] = set()
    _scan_statements(ast.parse(raw).body, FlowState(), findings)
    return findings


@dataclass(frozen=True)
class BaseToken:
    name: str


def _leaf(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name): return node.id
    if isinstance(node, ast.Attribute): return node.attr
    return None


def _resolve(name: str, aliases: dict[str, BaseToken]) -> BaseToken:
    return aliases.get(name, BaseToken(name))


def _static_base_sequence(value: ast.AST, aliases: dict[str, BaseToken], sequences: dict[str, tuple[BaseToken, ...]]) -> tuple[BaseToken, ...] | None:
    if isinstance(value, ast.Name):
        # A name is a sequence only if it was previously proven to hold a static sequence.
        return sequences.get(value.id)
    if isinstance(value, ast.Attribute):
        return (BaseToken(value.attr),)
    if not isinstance(value, (ast.Tuple, ast.List)):
        return None
    out: list[BaseToken] = []
    for item in value.elts:
        if isinstance(item, ast.Starred):
            nested = _static_base_sequence(item.value, aliases, sequences)
            if nested is None: return None
            out.extend(nested)
        else:
            leaf = _leaf(item)
            if leaf is None: return None
            out.append(_resolve(leaf, aliases))
    return tuple(out)


def _bind_static_target(target: ast.AST, values: tuple[BaseToken, ...], sequences: dict[str, tuple[BaseToken, ...]]) -> None:
    if isinstance(target, ast.Name):
        sequences[target.id] = values
        return
    if not isinstance(target, (ast.Tuple, ast.List)): return
    stars = [i for i, item in enumerate(target.elts) if isinstance(item, ast.Starred)]
    if len(stars) > 1: return
    if not stars:
        if len(target.elts) != len(values): return
        for item, value in zip(target.elts, values):
            if isinstance(item, ast.Name): sequences[item.id] = (value,)
        return
    star = stars[0]; prefix = target.elts[:star]; suffix = target.elts[star + 1:]
    if len(values) < len(prefix) + len(suffix): return
    for item, value in zip(prefix, values[:len(prefix)]):
        if isinstance(item, ast.Name): sequences[item.id] = (value,)
    end = len(values) - len(suffix) if suffix else len(values)
    starred = target.elts[star]
    if isinstance(starred, ast.Starred) and isinstance(starred.value, ast.Name):
        sequences[starred.value.id] = values[len(prefix):end]
    if suffix:
        for item, value in zip(suffix, values[-len(suffix):]):
            if isinstance(item, ast.Name): sequences[item.id] = (value,)


def broker_path_declarations(raw: str, label: str) -> list[tuple[str, int, str, set[str]]]:
    declarations: list[tuple[str, int, str, set[str]]] = []

    def walk(body: list[ast.stmt], aliases: dict[str, BaseToken], sequences: dict[str, tuple[BaseToken, ...]]) -> None:
        for statement in body:
            if isinstance(statement, ast.ImportFrom):
                for imported in statement.names:
                    aliases[imported.asname or imported.name] = BaseToken(imported.name)
                continue
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                value = statement.value
                if value is None: continue
                targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                snapshot = _static_base_sequence(value, aliases, sequences)
                leaf = _leaf(value)
                token = _resolve(leaf, aliases) if leaf else None
                for target in targets:
                    for name in _target_names(target):
                        aliases.pop(name, None); sequences.pop(name, None)
                    if isinstance(target, ast.Name) and token is not None:
                        aliases[target.id] = token
                    if snapshot is not None:
                        _bind_static_target(target, snapshot, sequences)
                continue
            if isinstance(statement, ast.ClassDef):
                bases: set[str] = set()
                for base in statement.bases:
                    if isinstance(base, ast.Starred):
                        snapshot = _static_base_sequence(base.value, aliases, sequences)
                        if snapshot is None:
                            raise AssertionError(f"unresolved starred class base is forbidden: {label}:{statement.name}@L{statement.lineno}")
                        bases |= {token.name for token in snapshot}
                    elif isinstance(base, (ast.Name, ast.Attribute)):
                        leaf = _leaf(base); assert leaf
                        bases.add(_resolve(leaf, aliases).name)
                    else:
                        raise AssertionError(f"unresolved ordinary class base is forbidden: {label}:{statement.name}@L{statement.lineno}")
                declarations.append((label, statement.lineno, statement.name, bases))
                walk(statement.body, dict(aliases), dict(sequences))
                aliases[statement.name] = BaseToken(statement.name)
                sequences.pop(statement.name, None)
                continue
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                walk(statement.body, dict(aliases), dict(sequences)); continue
            nested: list[list[ast.stmt]] = []
            if isinstance(statement, ast.If): nested += [statement.body, statement.orelse]
            elif isinstance(statement, (ast.For, ast.AsyncFor, ast.While)): nested += [statement.body, statement.orelse]
            elif isinstance(statement, (ast.With, ast.AsyncWith)): nested += [statement.body]
            elif isinstance(statement, ast.Try):
                nested += [statement.body, statement.orelse, statement.finalbody]
                nested += [handler.body for handler in statement.handlers]
            for branch in nested:
                walk(branch, dict(aliases), dict(sequences))

    walk(ast.parse(raw).body, {}, {})
    return declarations


def _governed_sources(inventory: dict) -> list[Path]:
    paths = [BOUNDARY_SOURCE]
    for root_value in inventory["implementation_code_roots"]:
        root = ROOT / root_value
        if root.exists(): paths.extend(sorted(root.rglob("*.py")))
    paths.extend(sorted(ASSURANCE_DIR.rglob("*.py")))
    return list(dict.fromkeys(paths))


def assert_broker_inventory(inventory: dict) -> None:
    declarations: list[tuple[str, int, str, set[str]]] = []
    for path in _governed_sources(inventory):
        declarations += broker_path_declarations(path.read_text(encoding="utf-8"), path.relative_to(ROOT).as_posix())
    descendants = {"BrokerFacingPath"}
    changed = True
    while changed:
        changed = False
        for _, _, name, bases in declarations:
            if name not in descendants and bases & descendants:
                descendants.add(name); changed = True
    discovered = [(label, line, name) for label, line, name, bases in declarations if name != "BrokerFacingPath" and name in descendants and bases & descendants]
    names = [item[2] for item in discovered]
    if set(names) != EXPECTED_PATH_CLASSES or len(names) != len(EXPECTED_PATH_CLASSES):
        raise AssertionError(f"v3 broker-path inventory mismatch: {discovered}")


def run_negative_controls() -> None:
    risky = {
        "starred_mapping": "[*namespaces] = [vars(client)]\ntransaction = namespaces[0][transaction_name]\ntransaction()",
        "default_capture": "def run(resolve=getattr):\n    transaction = resolve(client, transaction_name)\n    transaction()",
        "type_alias": "class BrokerFacingPath: pass\nclass InboxAcknowledgePath(BrokerFacingPath): pass\nkind = type\nkind.__setattr__(InboxAcknowledgePath, '__bases__', (EvilBase,))",
    }
    for label, source in risky.items():
        if not reflection_and_authority_findings(source):
            raise AssertionError(f"{label} escaped v3 guard")

    shadowed = "if flag:\n    vars = fields_a\nelse:\n    vars = fields_b\nvars(record)[field_name]()"
    if reflection_and_authority_findings(shadowed):
        raise AssertionError("builtin alias removed on every branch still produced a false finding")

    unresolved = "Bases = choose_bases()\nclass EscapingPath(*Bases):\n    pass"
    try:
        broker_path_declarations(unresolved, "negative-control")
    except AssertionError:
        pass
    else:
        raise AssertionError("computed named base sequence did not fail closed")

    captured = "Bases = (OutboxDispatchPath,)\nOutboxDispatchPath = object\nclass EscapingPath(*Bases):\n    pass"
    escaping = next(item for item in broker_path_declarations(captured, "negative-control") if item[2] == "EscapingPath")
    if "OutboxDispatchPath" not in escaping[3]:
        raise AssertionError("capture-time base snapshot was rewritten")


def main() -> int:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    findings: list[str] = []
    for path in _governed_sources(inventory):
        for finding in sorted(reflection_and_authority_findings(path.read_text(encoding="utf-8"))):
            findings.append(f"{path.relative_to(ROOT).as_posix()}:{finding}")
    if findings:
        raise AssertionError(f"v3 lexical reflection/authority findings: {findings}")
    assert_broker_inventory(inventory)
    run_negative_controls()
    print(
        "d4a_lexical_reflection_hierarchy_v3=PASS "
        "reflection=starred_mapping+default_capture+feasible_branch_identity "
        "authority=type_alias_mutation_rejected "
        "broker_paths=static_sequence_only+capture_snapshot+computed_fail_closed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
