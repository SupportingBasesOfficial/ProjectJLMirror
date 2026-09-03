from __future__ import annotations

import ast
import json
import re
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
AUTHORITY_CLASS_NAMES = {"BrokerFacingPath", "InboxAcknowledgePath"}
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
TRANSACTION_METHODS = {
    "inittransactions",
    "begintransaction",
    "committransaction",
    "aborttransaction",
    "sendoffsetstotransaction",
}
MEMBER_NAMES = {"getattr", "hasattr", "setattr", "delattr"}

TOK_BUILTINS = "builtins_module"
TOK_TYPE = "builtin:type"
TOK_MAPPING = "mapping_value"
TOK_MAPPING_CONTAINER = "mapping_container"
TOK_REFLECTED = "reflected_callable"
TOK_AUTHORITY = "protected_authority"


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
        for item in node.values:
            if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
                return None
            parts.append(item.value)
        return "".join(parts)
    return None


def _target_names(target: ast.AST) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, ast.Starred):
        return _target_names(target.value)
    if isinstance(target, (ast.Tuple, ast.List)):
        result: set[str] = set()
        for item in target.elts:
            result |= _target_names(item)
        return result
    return set()


@dataclass
class FlowState:
    bindings: dict[str, set[str]] = field(default_factory=dict)

    @classmethod
    def initial(cls) -> "FlowState":
        state = cls()
        for name in MEMBER_NAMES:
            state.bindings[name] = {f"builtin:{name}"}
        state.bindings["vars"] = {"builtin:vars"}
        state.bindings["type"] = {TOK_TYPE}
        state.bindings["builtins"] = {TOK_BUILTINS}
        for name in AUTHORITY_CLASS_NAMES:
            state.bindings[name] = {TOK_AUTHORITY}
        return state

    def copy(self) -> "FlowState":
        return FlowState({name: set(tokens) for name, tokens in self.bindings.items()})

    def bind(self, name: str, tokens: set[str]) -> None:
        if tokens:
            self.bindings[name] = set(tokens)
        else:
            self.bindings.pop(name, None)

    def tokens(self, name: str) -> set[str]:
        return set(self.bindings.get(name, set()))

    @staticmethod
    def merge(states: list["FlowState"]) -> "FlowState":
        merged = FlowState()
        for state in states:
            for name, tokens in state.bindings.items():
                merged.bindings.setdefault(name, set()).update(tokens)
        return merged


def _callee_tokens(node: ast.AST, state: FlowState) -> set[str]:
    if isinstance(node, ast.Name):
        return state.tokens(node.id)
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and TOK_BUILTINS in state.tokens(node.value.id):
        if node.attr in MEMBER_NAMES or node.attr == "vars":
            return {f"builtin:{node.attr}"}
        if node.attr == "type":
            return {TOK_TYPE}
    return set()


def _authority_expr(node: ast.AST, state: FlowState) -> bool:
    if isinstance(node, ast.Name):
        return TOK_AUTHORITY in state.tokens(node.id)
    if isinstance(node, ast.Attribute):
        return node.attr in AUTHORITY_CLASS_NAMES
    return False


def _is_type_object(node: ast.AST, state: FlowState) -> bool:
    if TOK_TYPE in _callee_tokens(node, state):
        return True
    if isinstance(node, ast.Call) and TOK_TYPE in _callee_tokens(node.func, state) and len(node.args) == 1:
        return _authority_expr(node.args[0], state)
    return False


def _expr_tokens(node: ast.AST, state: FlowState, findings: set[str]) -> set[str]:
    if isinstance(node, ast.Name):
        return state.tokens(node.id)
    if isinstance(node, ast.NamedExpr):
        tokens = _expr_tokens(node.value, state, findings)
        if isinstance(node.target, ast.Name):
            state.bind(node.target.id, tokens)
        return tokens
    if isinstance(node, ast.Attribute):
        tokens = _callee_tokens(node, state)
        if tokens:
            return tokens
        if node.attr in AUTHORITY_CLASS_NAMES:
            return {TOK_AUTHORITY}
        if node.attr == "__dict__":
            return {TOK_MAPPING}
        return set()
    if isinstance(node, (ast.Tuple, ast.List)):
        element_tokens = [_expr_tokens(item.value if isinstance(item, ast.Starred) else item, state, findings) for item in node.elts]
        if any(TOK_MAPPING in tokens or TOK_MAPPING_CONTAINER in tokens for tokens in element_tokens):
            return {TOK_MAPPING_CONTAINER}
        return set()
    if isinstance(node, ast.Call):
        callee = _callee_tokens(node.func, state)
        if "builtin:vars" in callee:
            return {TOK_MAPPING}
        if callee & {"builtin:getattr", "builtin:hasattr"} and len(node.args) >= 2:
            member = _constant_string(node.args[1])
            if member is None:
                return {TOK_REFLECTED}
            transaction = _normalized_transaction(member)
            if transaction is not None:
                findings.add(f"reflection:transaction_member:{transaction}")
            return set()
        return set()
    if isinstance(node, ast.Subscript):
        owner_tokens = _expr_tokens(node.value, state, findings)
        if TOK_MAPPING_CONTAINER in owner_tokens:
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, int):
                return {TOK_MAPPING}
            return {TOK_MAPPING}
        if TOK_MAPPING in owner_tokens:
            member = _constant_string(node.slice)
            if member is None:
                return {TOK_REFLECTED}
            transaction = _normalized_transaction(member)
            if transaction is not None:
                findings.add(f"reflection:transaction_member:{transaction}")
        return set()
    return set()


def _bind_pattern(target: ast.AST, value: ast.AST, state: FlowState, findings: set[str]) -> None:
    if isinstance(target, ast.Name):
        state.bind(target.id, _expr_tokens(value, state, findings))
        return
    if isinstance(target, ast.Starred):
        values = value.elts if isinstance(value, (ast.List, ast.Tuple)) else []
        aggregate: set[str] = set()
        for item in values:
            aggregate |= _expr_tokens(item, state, findings)
        if TOK_MAPPING in aggregate or TOK_MAPPING_CONTAINER in aggregate:
            aggregate = {TOK_MAPPING_CONTAINER}
        for name in _target_names(target):
            state.bind(name, aggregate)
        return
    if not isinstance(target, (ast.Tuple, ast.List)):
        return
    if not isinstance(value, (ast.Tuple, ast.List)):
        for name in _target_names(target):
            state.bind(name, set())
        return
    targets = target.elts
    values = value.elts
    stars = [i for i, item in enumerate(targets) if isinstance(item, ast.Starred)]
    if not stars:
        if len(targets) != len(values):
            for name in _target_names(target):
                state.bind(name, set())
            return
        for left, right in zip(targets, values):
            _bind_pattern(left, right, state, findings)
        return
    if len(stars) != 1:
        for name in _target_names(target):
            state.bind(name, set())
        return
    star = stars[0]
    prefix = targets[:star]
    suffix = targets[star + 1:]
    if len(values) < len(prefix) + len(suffix):
        for name in _target_names(target):
            state.bind(name, set())
        return
    for left, right in zip(prefix, values[:len(prefix)]):
        _bind_pattern(left, right, state, findings)
    for left, right in zip(suffix, values[-len(suffix):] if suffix else []):
        _bind_pattern(left, right, state, findings)
    captured = values[len(prefix): len(values) - len(suffix) if suffix else len(values)]
    star_target = targets[star]
    aggregate: set[str] = set()
    for item in captured:
        aggregate |= _expr_tokens(item, state, findings)
    if TOK_MAPPING in aggregate or TOK_MAPPING_CONTAINER in aggregate:
        aggregate = {TOK_MAPPING_CONTAINER}
    for name in _target_names(star_target):
        state.bind(name, aggregate)


def _scan_lambda(node: ast.Lambda, state: FlowState, findings: set[str]) -> None:
    child = state.copy()
    positional = [*node.args.posonlyargs, *node.args.args]
    default_offset = len(positional) - len(node.args.defaults)
    for index, arg in enumerate(positional):
        if index >= default_offset:
            child.bind(arg.arg, _expr_tokens(node.args.defaults[index - default_offset], state, findings))
        else:
            child.bind(arg.arg, set())
    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
        child.bind(arg.arg, _expr_tokens(default, state, findings) if default is not None else set())
    if node.args.vararg:
        child.bind(node.args.vararg.arg, set())
    if node.args.kwarg:
        child.bind(node.args.kwarg.arg, set())
    _scan_expr(node.body, child, findings, called=True)


def _scan_expr(node: ast.AST, state: FlowState, findings: set[str], *, called: bool = False) -> None:
    if isinstance(node, ast.Lambda):
        _scan_lambda(node, state, findings)
        return
    if isinstance(node, ast.NamedExpr):
        _expr_tokens(node, state, findings)
        _scan_expr(node.value, state, findings)
        return
    if called and TOK_REFLECTED in _expr_tokens(node, state, findings):
        findings.add("reflection:unresolved_callable_member")
    if isinstance(node, ast.Call):
        callee_tokens = _callee_tokens(node.func, state)
        if isinstance(node.func, ast.Name) and TOK_REFLECTED in state.tokens(node.func.id):
            findings.add("reflection:aliased_unresolved_callable_member")
        if callee_tokens & {"builtin:setattr", "builtin:delattr"} and len(node.args) >= 2 and _authority_expr(node.args[0], state):
            member = _constant_string(node.args[1])
            if member is None or member in AUTHORITY_MUTATION_NAMES:
                findings.add("authority:reflective_namespace_mutation")
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"__setattr__", "__delattr__"} and _is_type_object(node.func.value, state):
            if len(node.args) >= 2 and _authority_expr(node.args[0], state):
                member = _constant_string(node.args[1])
                if member is None or member in AUTHORITY_MUTATION_NAMES:
                    findings.add("authority:type_namespace_mutation")
        _scan_expr(node.func, state, findings, called=True)
        for arg in node.args:
            _scan_expr(arg, state, findings)
        for kw in node.keywords:
            _scan_expr(kw.value, state, findings)
        return
    for child in ast.iter_child_nodes(node):
        _scan_expr(child, state, findings)


def _terminates(body: list[ast.stmt]) -> bool:
    return bool(body) and isinstance(body[-1], (ast.Raise, ast.Return))


def _pattern_names(pattern: ast.pattern) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(pattern):
        if isinstance(node, ast.MatchAs) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.MatchStar) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            names.add(node.rest)
    return names


def _bind_match_pattern(pattern: ast.pattern, subject: ast.AST, state: FlowState, findings: set[str]) -> None:
    if isinstance(pattern, ast.MatchAs) and pattern.name:
        state.bind(pattern.name, _expr_tokens(subject, state, findings))
        return
    if isinstance(pattern, ast.MatchSequence) and isinstance(subject, (ast.List, ast.Tuple)) and len(pattern.patterns) == len(subject.elts):
        for subpattern, element in zip(pattern.patterns, subject.elts):
            _bind_match_pattern(subpattern, element, state, findings)
        return
    for name in _pattern_names(pattern):
        state.bind(name, set())


def _scan_statements(body: list[ast.stmt], state: FlowState, findings: set[str]) -> FlowState:
    current = state.copy()
    for statement in body:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                bound = alias.asname or alias.name.split(".")[0]
                current.bind(bound, {TOK_BUILTINS} if alias.name == "builtins" else set())
            continue
        if isinstance(statement, ast.ImportFrom):
            for alias in statement.names:
                bound = alias.asname or alias.name
                if statement.module == "builtins" and alias.name in MEMBER_NAMES:
                    current.bind(bound, {f"builtin:{alias.name}"})
                elif statement.module == "builtins" and alias.name == "vars":
                    current.bind(bound, {"builtin:vars"})
                elif statement.module == "builtins" and alias.name == "type":
                    current.bind(bound, {TOK_TYPE})
                elif alias.name in AUTHORITY_CLASS_NAMES:
                    current.bind(bound, {TOK_AUTHORITY})
                else:
                    current.bind(bound, set())
            continue
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            value = statement.value
            if value is not None:
                _scan_expr(value, current, findings)
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            for target in targets:
                if isinstance(target, ast.Attribute) and target.attr in AUTHORITY_MUTATION_NAMES and _authority_expr(target.value, current):
                    findings.add("authority:direct_namespace_mutation")
                if value is not None:
                    _bind_pattern(target, value, current, findings)
                else:
                    for name in _target_names(target):
                        current.bind(name, set())
            continue
        if isinstance(statement, ast.Delete):
            for target in statement.targets:
                for name in _target_names(target):
                    current.bind(name, set())
            continue
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in statement.decorator_list:
                _scan_expr(decorator, current, findings)
            child = current.copy()
            positional = [*statement.args.posonlyargs, *statement.args.args]
            offset = len(positional) - len(statement.args.defaults)
            for index, arg in enumerate(positional):
                child.bind(arg.arg, _expr_tokens(statement.args.defaults[index - offset], current, findings) if index >= offset else set())
            for arg, default in zip(statement.args.kwonlyargs, statement.args.kw_defaults):
                child.bind(arg.arg, _expr_tokens(default, current, findings) if default is not None else set())
            if statement.args.vararg:
                child.bind(statement.args.vararg.arg, set())
            if statement.args.kwarg:
                child.bind(statement.args.kwarg.arg, set())
            _scan_statements(statement.body, child, findings)
            current.bind(statement.name, set())
            continue
        if isinstance(statement, ast.ClassDef):
            for base in statement.bases:
                _scan_expr(base, current, findings)
            _scan_statements(statement.body, current.copy(), findings)
            current.bind(statement.name, {TOK_AUTHORITY} if statement.name in AUTHORITY_CLASS_NAMES else set())
            continue
        if isinstance(statement, ast.If):
            _scan_expr(statement.test, current, findings)
            left = _scan_statements(statement.body, current, findings)
            right = _scan_statements(statement.orelse, current, findings)
            feasible = []
            if not _terminates(statement.body):
                feasible.append(left)
            if not _terminates(statement.orelse):
                feasible.append(right)
            current = FlowState.merge(feasible or [left, right])
            continue
        if isinstance(statement, ast.Try):
            normal = _scan_statements(statement.body, current, findings)
            normal = _scan_statements(statement.orelse, normal, findings)
            exits: list[FlowState] = [normal]
            for handler in statement.handlers:
                branch = current.copy()
                if handler.name:
                    branch.bind(handler.name, set())
                branch = _scan_statements(handler.body, branch, findings)
                if not _terminates(handler.body):
                    exits.append(branch)
            if statement.finalbody:
                exits = [_scan_statements(statement.finalbody, branch, findings) for branch in exits]
            current = FlowState.merge(exits)
            continue
        if isinstance(statement, ast.Match):
            _scan_expr(statement.subject, current, findings)
            exits: list[FlowState] = []
            for case in statement.cases:
                branch = current.copy()
                _bind_match_pattern(case.pattern, statement.subject, branch, findings)
                if case.guard is not None:
                    _scan_expr(case.guard, branch, findings)
                branch = _scan_statements(case.body, branch, findings)
                if not _terminates(case.body):
                    exits.append(branch)
            current = FlowState.merge(exits or [current])
            continue
        if isinstance(statement, (ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith)):
            branches = [current]
            nested = [statement.body]
            if hasattr(statement, "orelse"):
                nested.append(statement.orelse)
            exits = [current]
            for part in nested:
                exits.append(_scan_statements(part, current, findings))
            current = FlowState.merge(exits)
            continue
        for child in ast.iter_child_nodes(statement):
            if isinstance(child, ast.expr):
                _scan_expr(child, current, findings)
    return current


def reflection_and_authority_findings(raw: str) -> set[str]:
    tree = ast.parse(raw)
    findings: set[str] = set()
    _scan_statements(tree.body, FlowState.initial(), findings)
    return findings


@dataclass
class BaseState:
    aliases: dict[str, str | None] = field(default_factory=dict)
    sequences: dict[str, tuple[str, ...] | None] = field(default_factory=dict)

    def copy(self) -> "BaseState":
        return BaseState(dict(self.aliases), dict(self.sequences))

    @staticmethod
    def merge(states: list["BaseState"]) -> "BaseState":
        merged = BaseState()
        names = set().union(*(set(s.aliases) | set(s.sequences) for s in states))
        for name in names:
            alias_values = [s.aliases.get(name) for s in states]
            seq_values = [s.sequences.get(name) for s in states]
            merged.aliases[name] = alias_values[0] if alias_values and all(v == alias_values[0] for v in alias_values) else None
            merged.sequences[name] = seq_values[0] if seq_values and all(v == seq_values[0] for v in seq_values) else None
        return merged


def _leaf(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _resolve_alias(name: str, state: BaseState) -> str | None:
    seen: set[str] = set()
    current = name
    while current not in seen:
        seen.add(current)
        if current not in state.aliases:
            return current
        next_name = state.aliases[current]
        if next_name is None:
            return None
        current = next_name
    return None


def _static_sequence(value: ast.AST, state: BaseState) -> tuple[str, ...] | None:
    if isinstance(value, ast.Name):
        if value.id in state.sequences:
            return state.sequences[value.id]
        resolved = _resolve_alias(value.id, state)
        return (resolved,) if resolved is not None else None
    if isinstance(value, ast.Attribute):
        return (value.attr,)
    if not isinstance(value, (ast.Tuple, ast.List)):
        return None
    result: list[str] = []
    for item in value.elts:
        if isinstance(item, ast.Starred):
            nested = _static_sequence(item.value, state)
        else:
            nested = _static_sequence(item, state)
        if nested is None or (not isinstance(item, ast.Starred) and len(nested) != 1):
            return None
        result.extend(nested)
    return tuple(result)


def _bind_base_target(target: ast.AST, value: ast.AST, state: BaseState) -> None:
    for name in _target_names(target):
        state.aliases[name] = None
        state.sequences[name] = None
    snapshot = _static_sequence(value, state)
    leaf = _leaf(value)
    if isinstance(target, ast.Name):
        if leaf is not None:
            state.aliases[target.id] = _resolve_alias(leaf, state)
        state.sequences[target.id] = snapshot
        return
    if not isinstance(target, (ast.Tuple, ast.List)) or not isinstance(value, (ast.Tuple, ast.List)):
        return
    values = value.elts
    targets = target.elts
    stars = [i for i, item in enumerate(targets) if isinstance(item, ast.Starred)]
    if not stars and len(targets) == len(values):
        for left, right in zip(targets, values):
            _bind_base_target(left, right, state)
        return
    if len(stars) == 1:
        star = stars[0]
        prefix = targets[:star]
        suffix = targets[star + 1:]
        if len(values) >= len(prefix) + len(suffix):
            for left, right in zip(prefix, values[:len(prefix)]):
                _bind_base_target(left, right, state)
            for left, right in zip(suffix, values[-len(suffix):] if suffix else []):
                _bind_base_target(left, right, state)
            captured = ast.Tuple(elts=values[len(prefix): len(values) - len(suffix) if suffix else len(values)], ctx=ast.Load())
            star_target = targets[star]
            if isinstance(star_target, ast.Starred) and isinstance(star_target.value, ast.Name):
                state.sequences[star_target.value.id] = _static_sequence(captured, state)


def broker_path_declarations(raw: str, label: str) -> list[tuple[str, int, str, set[str]]]:
    tree = ast.parse(raw)
    declarations: list[tuple[str, int, str, set[str]]] = []

    def walk(body: list[ast.stmt], state: BaseState) -> BaseState:
        current = state.copy()
        for statement in body:
            if isinstance(statement, ast.ImportFrom):
                for alias in statement.names:
                    current.aliases[alias.asname or alias.name] = alias.name
                continue
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                value = statement.value
                if value is not None:
                    targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                    for target in targets:
                        _bind_base_target(target, value, current)
                continue
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                child = current.copy()
                for arg in [*statement.args.posonlyargs, *statement.args.args, *statement.args.kwonlyargs]:
                    child.aliases[arg.arg] = None
                    child.sequences[arg.arg] = None
                if statement.args.vararg:
                    child.aliases[statement.args.vararg.arg] = None
                    child.sequences[statement.args.vararg.arg] = None
                if statement.args.kwarg:
                    child.aliases[statement.args.kwarg.arg] = None
                    child.sequences[statement.args.kwarg.arg] = None
                walk(statement.body, child)
                current.aliases[statement.name] = None
                current.sequences[statement.name] = None
                continue
            if isinstance(statement, ast.ClassDef):
                bases: set[str] = set()
                for base in statement.bases:
                    if isinstance(base, ast.Starred):
                        snapshot = _static_sequence(base.value, current)
                        if snapshot is None:
                            raise AssertionError(f"unresolved starred class base is forbidden: {label}:{statement.name}@L{statement.lineno}")
                        bases.update(snapshot)
                    elif isinstance(base, (ast.Name, ast.Attribute)):
                        leaf = _leaf(base)
                        resolved = _resolve_alias(leaf, current) if leaf is not None else None
                        if resolved is None:
                            raise AssertionError(f"unresolved ordinary class base is forbidden: {label}:{statement.name}@L{statement.lineno}")
                        bases.add(resolved)
                    else:
                        raise AssertionError(f"unresolved ordinary class base is forbidden: {label}:{statement.name}@L{statement.lineno}")
                declarations.append((label, statement.lineno, statement.name, bases))
                walk(statement.body, current.copy())
                current.aliases[statement.name] = statement.name
                current.sequences[statement.name] = None
                continue
            if isinstance(statement, ast.If):
                left = walk(statement.body, current)
                right = walk(statement.orelse, current)
                feasible = []
                if not _terminates(statement.body):
                    feasible.append(left)
                if not _terminates(statement.orelse):
                    feasible.append(right)
                current = BaseState.merge(feasible or [left, right])
                continue
            if isinstance(statement, ast.Try):
                normal = walk(statement.body, current)
                normal = walk(statement.orelse, normal)
                exits = [normal]
                for handler in statement.handlers:
                    branch = walk(handler.body, current)
                    if not _terminates(handler.body):
                        exits.append(branch)
                if statement.finalbody:
                    exits = [walk(statement.finalbody, branch) for branch in exits]
                current = BaseState.merge(exits)
                continue
            if isinstance(statement, ast.Match):
                exits = [walk(case.body, current) for case in statement.cases if not _terminates(case.body)]
                current = BaseState.merge(exits or [current])
                continue
        return current

    walk(tree.body, BaseState())
    return declarations


def _governed_python_sources(inventory: dict) -> list[Path]:
    paths = [BOUNDARY_SOURCE]
    for root_value in inventory["implementation_code_roots"]:
        root = ROOT / root_value
        if root.exists():
            paths.extend(sorted(root.rglob("*.py")))
    paths.extend(sorted(ASSURANCE_DIR.rglob("*.py")))
    return list(dict.fromkeys(paths))


def assert_broker_inventory(inventory: dict) -> None:
    declarations: list[tuple[str, int, str, set[str]]] = []
    for path in _governed_python_sources(inventory):
        declarations.extend(broker_path_declarations(path.read_text(encoding="utf-8"), path.relative_to(ROOT).as_posix()))
    descendants = {"BrokerFacingPath"}
    changed = True
    while changed:
        changed = False
        for _, _, name, bases in declarations:
            if name not in descendants and bases & descendants:
                descendants.add(name)
                changed = True
    discovered = [(label, line, name) for label, line, name, bases in declarations if name != "BrokerFacingPath" and name in descendants and bases & descendants]
    names = [item[2] for item in discovered]
    if set(names) != EXPECTED_PATH_CLASSES or len(names) != len(EXPECTED_PATH_CLASSES):
        raise AssertionError(f"v4 broker-path inventory mismatch: {discovered}")


def bracket_transaction_findings(inventory: dict) -> list[str]:
    findings: list[str] = []
    suffixes = {".ts", ".tsx", ".js", ".mjs", ".cjs", ".go", ".rs", ".java", ".kt", ".cs"}
    pattern = re.compile(r"\[\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*\]\s*(?:<[^\n;{}()]*>|::\s*<[^\n;{}()]*>)?\s*\(")
    for root_value in inventory["implementation_code_roots"]:
        root = ROOT / root_value
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in suffixes:
                continue
            raw = path.read_text(encoding="utf-8", errors="ignore")
            for match in pattern.finditer(raw):
                transaction = _normalized_transaction(match.group(1))
                if transaction is not None:
                    findings.append(f"{path.relative_to(ROOT).as_posix()}:transaction_api:{transaction}:bracket_member")
    return findings


def run_negative_controls() -> None:
    must_find = {
        "branch_retains_type": "kind = type\nif flag:\n    kind = Helper\nkind.__setattr__(InboxAcknowledgePath, '__bases__', (EvilBase,))",
        "qualified_type": "import builtins as b\nb.type(InboxAcknowledgePath).__setattr__(InboxAcknowledgePath, '__bases__', (EvilBase,))",
        "lambda_default": "(lambda resolve=getattr: resolve(client, transaction_name)())()",
        "walrus_mapping": "[*namespaces] = [(namespace := vars(client))]\ntransaction = namespaces[0][transaction_name]\ntransaction()",
        "try_survivor": "try:\n    namespace = vars(client)\nexcept Exception:\n    raise\ntransaction = namespace[transaction_name]\ntransaction()",
        "match_binding": "match [vars(client)]:\n    case [namespace]:\n        transaction = namespace[transaction_name]\n        transaction()",
    }
    for label, source in must_find.items():
        if not reflection_and_authority_findings(source):
            raise AssertionError(f"{label} escaped v4 flow guard")

    shadow = "def run(InboxAcknowledgePath):\n    setattr(InboxAcknowledgePath, dynamic_name, value)"
    if reflection_and_authority_findings(shadow):
        raise AssertionError("lexically shadowed protected class spelling produced false authority finding")

    parameter_sequence = "Bases = (object,)\ndef make(Bases):\n    class EscapingPath(*Bases):\n        pass"
    try:
        broker_path_declarations(parameter_sequence, "negative-control")
    except AssertionError:
        pass
    else:
        raise AssertionError("function parameter sequence did not invalidate inherited base snapshot")

    conditional_sequence = "Bases = (object,)\nif flag:\n    Bases = choose_bases()\nclass EscapingPath(*Bases):\n    pass"
    try:
        broker_path_declarations(conditional_sequence, "negative-control")
    except AssertionError:
        pass
    else:
        raise AssertionError("conditional unresolved sequence did not fail closed")

    probe = 'client["commitTransaction"]()\nclient[\'send_offsets_to_transaction\']()'
    pattern = re.compile(r"\[\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*\]\s*(?:<[^\n;{}()]*>|::\s*<[^\n;{}()]*>)?\s*\(")
    found = {_normalized_transaction(match.group(1)) for match in pattern.finditer(probe)}
    if {"committransaction", "sendoffsetstotransaction"} - found:
        raise AssertionError("bracket transaction member syntax escaped v4 non-Python control")


def main() -> int:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    findings: list[str] = []
    for path in _governed_python_sources(inventory):
        for finding in sorted(reflection_and_authority_findings(path.read_text(encoding="utf-8"))):
            findings.append(f"{path.relative_to(ROOT).as_posix()}:{finding}")
    findings.extend(bracket_transaction_findings(inventory))
    if findings:
        raise AssertionError(f"v4 control-flow/authority/bracket findings: {findings}")
    assert_broker_inventory(inventory)
    run_negative_controls()
    print(
        "d4a_controlflow_authority_bracket_v4=PASS "
        "flow=branch_union+defaults+lambda+walrus+try+match+lexical_shadowing "
        "authority=qualified_and_aliased_type "
        "broker_paths=parameter_and_branch_sequence_invalidation "
        "nonpython=bracket_transaction_members"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
