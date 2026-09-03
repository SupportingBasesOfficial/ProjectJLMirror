from __future__ import annotations

import ast
import json
import re
from pathlib import Path

# Import the patched v4 entry first so Protocol -> Protocol and equivalent
# stable lexical identities are installed before v4.main() is invoked.
import validate_controlflow_authority_and_bracket_calls_v4_entry  # noqa: F401
import validate_controlflow_authority_and_bracket_calls_v4 as v4

ROOT = Path(__file__).resolve().parents[3]
ASSURANCE_DIR = ROOT / "tools/assurance/d4a_semantic_boundary"
INVENTORY = ROOT / "implementation/d4-eventing-async/source-evidence/semantic-boundary/boundary-inventory.json"

AUTHORITY_NAMES = {"BrokerFacingPath", "InboxAcknowledgePath"}
EXPECTED_PATHS = {"OutboxDispatchPath", "ConsumerReceivePath", "InboxAcknowledgePath", "ReplayDispatchPath"}
TX = {"inittransactions", "begintransaction", "committransaction", "aborttransaction", "sendoffsetstotransaction"}


def norm(name: str) -> str:
    return name.lower().replace("_", "")


def constant_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = constant_string(node.left)
        right = constant_string(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def transparent_builtin(node: ast.AST, names: set[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in names
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in {"builtins", "b"}:
        return node.attr in names
    if isinstance(node, ast.NamedExpr):
        return transparent_builtin(node.value, names)
    if isinstance(node, (ast.Tuple, ast.List)):
        return any(transparent_builtin(x, names) for x in node.elts)
    if isinstance(node, ast.Subscript):
        if isinstance(node.value, (ast.Tuple, ast.List)) and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, int):
            idx = node.slice.value
            try:
                return transparent_builtin(node.value.elts[idx], names)
            except (IndexError, TypeError):
                return False
    return False


def contains_mapping_capture(node: ast.AST) -> bool:
    if isinstance(node, ast.NamedExpr):
        return contains_mapping_capture(node.value)
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name) and func.id == "vars":
                return True
            if isinstance(func, ast.Attribute) and func.attr == "vars":
                return True
    return False


def has_star_target(target: ast.AST) -> bool:
    return any(isinstance(node, ast.Starred) for node in ast.walk(target))


def authority_expr(node: ast.AST, authority_aliases: set[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in authority_aliases
    if isinstance(node, ast.Attribute):
        return node.attr in AUTHORITY_NAMES
    return False


def scan_python_residual(source: str) -> set[str]:
    tree = ast.parse(source)
    findings: set[str] = set()
    type_aliases = {"type"}
    mutation_aliases: set[str] = set()
    authority_aliases = set(AUTHORITY_NAMES)

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "builtins":
            for alias in node.names:
                bound = alias.asname or alias.name
                if alias.name == "type":
                    type_aliases.add(bound)
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if value is None:
                continue
            for target in targets:
                if isinstance(target, ast.Name):
                    if isinstance(value, ast.Name) and value.id in type_aliases:
                        type_aliases.add(target.id)
                    if isinstance(value, ast.Name) and value.id in authority_aliases:
                        authority_aliases.add(target.id)
                    if isinstance(value, ast.Attribute) and value.attr in {"__setattr__", "__delattr__"}:
                        owner = value.value
                        if isinstance(owner, ast.Name) and owner.id in type_aliases:
                            mutation_aliases.add(target.id)
                if has_star_target(target) and isinstance(value, ast.NamedExpr) and contains_mapping_capture(value):
                    findings.add("reflection:walrus_starred_mapping_capture")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            args = node.args
            defaults = list(args.defaults) + [d for d in args.kw_defaults if d is not None]
            if any(transparent_builtin(default, {"getattr", "hasattr", "setattr", "delattr", "vars", "type"}) for default in defaults):
                findings.add("reflection:transparent_default_builtin_capture")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in mutation_aliases:
            if len(node.args) >= 2 and authority_expr(node.args[0], authority_aliases):
                member = constant_string(node.args[1])
                if member is None or member in {"__bases__", "__getattribute__", "__getattr__", "acknowledge_after_durable_responsibility"}:
                    findings.add("authority:aliased_type_mutation_method")
    return findings


def simple_base_name(base: ast.AST) -> str | None:
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    return None


def all_tree_broker_descendants(source: str) -> list[str]:
    tree = ast.parse(source)
    classes: list[tuple[str, set[str]]] = []
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                aliases[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Name):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    aliases[target.id] = node.value.id
        elif isinstance(node, ast.ClassDef):
            bases = {name for base in node.bases if not isinstance(base, ast.Starred) if (name := simple_base_name(base)) is not None}
            classes.append((node.name, bases))
    descendants = {"BrokerFacingPath"}
    changed = True
    while changed:
        changed = False
        for local, source_name in list(aliases.items()):
            if source_name in descendants and local not in descendants:
                descendants.add(local)
                changed = True
        for name, bases in classes:
            if bases & descendants and name not in descendants:
                descendants.add(name)
                changed = True
    return [name for name, bases in classes if name != "BrokerFacingPath" and bases & descendants]


BRACKET_CALL = re.compile(r"\[\s*((?:['\"][A-Za-z_][A-Za-z0-9_]*['\"]\s*(?:\+\s*['\"][A-Za-z_][A-Za-z0-9_]*['\"]\s*)*))\]\s*(?:<[^;{}()]*>|::\s*<[^;{}()]*>)?\s*\(")
QUOTED = re.compile(r"['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]")


def scan_nonpython_computed_brackets(source: str) -> set[str]:
    findings: set[str] = set()
    for match in BRACKET_CALL.finditer(source):
        pieces = QUOTED.findall(match.group(1))
        if not pieces:
            continue
        member = "".join(pieces)
        if norm(member) in TX:
            findings.add(f"transaction_api:computed_bracket:{norm(member)}")
    return findings


def governed_sources(inventory: dict) -> list[Path]:
    paths: list[Path] = [ASSURANCE_DIR / "broker_boundary.py"]
    suffixes = {".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".go", ".rs", ".java", ".kt", ".cs"}
    for root_value in inventory["implementation_code_roots"]:
        root = ROOT / root_value
        if root.exists():
            paths.extend(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in suffixes)
    paths.extend(p for p in ASSURANCE_DIR.rglob("*.py") if p.is_file())
    return list(dict.fromkeys(paths))


def assert_negative_controls() -> None:
    cases = {
        "aliased_type_method": "mutate = type.__setattr__\nmutate(InboxAcknowledgePath, '__bases__', (EvilBase,))\n",
        "walrus_star": "[*namespaces] = (holder := [vars(client)])\ntransaction = namespaces[0][transaction_name]\ntransaction()\n",
        "transparent_default": "def run(resolve=(getattr,)[0]):\n    transaction = resolve(client, transaction_name)\n    transaction()\n",
    }
    expected = {
        "aliased_type_method": "authority:aliased_type_mutation_method",
        "walrus_star": "reflection:walrus_starred_mapping_capture",
        "transparent_default": "reflection:transparent_default_builtin_capture",
    }
    for name, source in cases.items():
        findings = scan_python_residual(source)
        assert expected[name] in findings, (name, findings)

    loop_source = "from broker_boundary import OutboxDispatchPath\nfor item in items:\n    class EscapingPath(OutboxDispatchPath):\n        pass\n"
    assert "EscapingPath" in all_tree_broker_descendants(loop_source)
    with_source = "from contextlib import nullcontext\nfrom broker_boundary import OutboxDispatchPath\nwith nullcontext():\n    class EscapingPath(OutboxDispatchPath):\n        pass\n"
    assert "EscapingPath" in all_tree_broker_descendants(with_source)
    assert scan_nonpython_computed_brackets('client["commit" + "Transaction"]()')
    assert scan_nonpython_computed_brackets("client['send_' + 'offsets_to_transaction']()")


def main() -> int:
    # Preserve all patched v4 guarantees first.
    v4.main()
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    findings: list[str] = []
    broker_descendants: list[str] = []
    for path in governed_sources(inventory):
        source = path.read_text(encoding="utf-8", errors="ignore")
        rel = path.relative_to(ROOT).as_posix()
        if path.suffix == ".py":
            findings.extend(f"{rel}:{item}" for item in sorted(scan_python_residual(source)))
            broker_descendants.extend(all_tree_broker_descendants(source))
        else:
            findings.extend(f"{rel}:{item}" for item in sorted(scan_nonpython_computed_brackets(source)))
    counts = {name: broker_descendants.count(name) for name in EXPECTED_PATHS}
    extras = [name for name in broker_descendants if name not in EXPECTED_PATHS]
    if extras or set(counts) != EXPECTED_PATHS or any(counts[name] != 1 for name in EXPECTED_PATHS):
        raise AssertionError(f"all-tree broker inventory mismatch extras={extras} counts={counts}")
    if findings:
        raise AssertionError("residual escape closure findings: " + "; ".join(findings))
    assert_negative_controls()
    print("d4a_residual_escape_closure_v5=PASS type_mutation_method_alias=closed walrus_starred_mapping=closed transparent_default_capture=closed loop_with_class_inventory=closed computed_bracket_member=closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
