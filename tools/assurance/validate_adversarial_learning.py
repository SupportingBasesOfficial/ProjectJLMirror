#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

TAXONOMY = Path("governance/adversarial/finding-taxonomy.json")
INVARIANTS = Path("governance/adversarial/engineering-invariants.json")
LEDGER = Path("governance/adversarial/learning-ledger.json")
LEDGER_SHARDS = Path("governance/adversarial/learning-ledger.d")
BOOTSTRAP_EXCEPTIONS = Path("governance/adversarial/bootstrap-exceptions.json")
STOP_POLICY = Path("governance/adversarial/review-stop-policy.json")
WORKFLOW = Path(".github/workflows/deterministic-assurance.yml")
SOURCE_PROBE_PATH = Path("tools/assurance/d4d_trace_context_source.py")
FALSIFICATION_PATHS = {
    Path('tools/assurance/test_validate_d4d_selection.py'),
    Path('tools/assurance/test_validate_d4c_selection.py'),
    Path('tools/assurance/d4b_wire_schema/test_source_evidence.py'),

    Path("tools/assurance/test_validate_d4d_trace_context_source.py"),
    Path("tools/assurance/test_validate_adversarial_learning.py"),
    Path("tools/assurance/test_validate_g1_identity_tenant_shell_authorization.py"),
    Path("tools/assurance/test_validate_g1_identity_tenant_shell_implementation_scope.py"),
}
MATERIAL_BADGE = re.compile(r"(?:\bP[012]\s+Badge\b|\[P[012]\])")


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _flatten_comments(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, list):
            result.extend(_flatten_comments(item))
        elif isinstance(item, dict):
            result.append(item)
    return result


def _template_matches(template: str, candidate: str) -> bool:
    parts = re.split(r"(\{[A-Za-z_][A-Za-z0-9_]*\})", template)
    pattern = "^" + "".join(r"[^\s]+" if part.startswith("{") and part.endswith("}") else re.escape(part) for part in parts) + "$"
    return re.fullmatch(pattern, candidate) is not None


def _executed_source_probes(path: Path) -> tuple[set[str], list[str]]:
    errors: list[str] = []
    module_name = "_jlmirror_adversarial_guardrail_source"
    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            return set(), [f"cannot load executable source probes from {path}"]
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        run_probes = getattr(module, "run_probes", None)
        if not callable(run_probes):
            return set(), [f"registered source probe file has no callable run_probes: {path}"]
        checks = run_probes()
        if not isinstance(checks, dict) or any(not isinstance(k, str) or not isinstance(v, bool) for k, v in checks.items()):
            return set(), [f"run_probes returned a malformed check map: {path}"]
        failed = sorted(k for k, v in checks.items() if not v)
        if failed:
            errors.append("registered executable source probes failed: " + ",".join(failed))
        return set(checks), errors
    except Exception as exc:
        return set(), [f"registered executable source probes could not run: {path}: {type(exc).__name__}: {exc}"]
    finally:
        sys.modules.pop(module_name, None)


def _direct_calls(statements: list[ast.stmt]) -> list[ast.Call]:
    calls: list[ast.Call] = []
    for statement in statements:
        if isinstance(statement, (ast.Return, ast.Raise)):
            break
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            calls.append(statement.value)
    return calls


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    return None


def _reachable_main_falsifiers(path: Path) -> tuple[set[str], list[str]]:
    errors: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except Exception as exc:
        return set(), [f"cannot parse falsifier file {path}: {type(exc).__name__}: {exc}"]
    functions = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    main = functions.get("main")
    if main is None:
        return set(), [f"registered falsifier file has no main(): {path}"]

    has_entrypoint = False
    for node in tree.body:
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not (
            isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name)
            and test.left.id == "__name__"
            and len(test.ops) == 1
            and isinstance(test.ops[0], ast.Eq)
            and len(test.comparators) == 1
            and isinstance(test.comparators[0], ast.Constant)
            and test.comparators[0].value == "__main__"
        ):
            continue
        for call in _direct_calls(node.body):
            if _call_name(call) == "main":
                has_entrypoint = True
    if not has_entrypoint:
        errors.append(f"registered falsifier main() is not directly invoked by __main__ entrypoint: {path}")

    credited: set[str] = set()
    for call in _direct_calls(main.body):
        name = _call_name(call)
        if isinstance(name, str) and name.startswith("falsify_") and name in functions:
            credited.add(name)
    return credited, errors


def _registered_guardrail_probes(root: Path) -> tuple[dict[Path, set[str]], list[str]]:
    errors: list[str] = []
    probes: dict[Path, set[str]] = {}
    source_path = root / SOURCE_PROBE_PATH
    if source_path.is_file():
        source_probes, source_errors = _executed_source_probes(source_path)
        probes[SOURCE_PROBE_PATH] = source_probes
        errors.extend(source_errors)
    for rel in FALSIFICATION_PATHS:
        path = root / rel
        if not path.is_file():
            errors.append(f"registered falsifier file missing: {rel}")
            continue
        executed, falsifier_errors = _reachable_main_falsifiers(path)
        probes[rel] = executed
        errors.extend(falsifier_errors)
    return probes, errors


def _load_ledger_entries(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    entries: list[dict[str, Any]] = []
    ledger_path = root / LEDGER
    try:
        data = _load(ledger_path)
        base_entries = data.get("entries", [])
        if not isinstance(base_entries, list):
            errors.append("learning-ledger entries must be a list")
        else:
            entries.extend(row for row in base_entries if isinstance(row, dict))
    except Exception as exc:
        errors.append(f"cannot load learning ledger: {type(exc).__name__}: {exc}")
    shard_dir = root / LEDGER_SHARDS
    if shard_dir.is_dir():
        for path in sorted(shard_dir.glob("*.json")):
            try:
                data = _load(path)
                shard_entries = data.get("entries", [])
                if not isinstance(shard_entries, list):
                    errors.append(f"learning ledger shard entries must be a list: {path.relative_to(root)}")
                else:
                    entries.extend(row for row in shard_entries if isinstance(row, dict))
            except Exception as exc:
                errors.append(f"cannot load learning ledger shard {path.relative_to(root)}: {type(exc).__name__}: {exc}")
    return entries, errors


def validate_bootstrap_exceptions(root: Path) -> tuple[set[int], list[str]]:
    errors: list[str] = []
    path = root / BOOTSTRAP_EXCEPTIONS
    if not path.is_file():
        return set(), [f"bootstrap exceptions missing: {BOOTSTRAP_EXCEPTIONS}"]
    try:
        data = _load(path)
    except Exception as exc:
        return set(), [f"cannot load bootstrap exceptions: {type(exc).__name__}: {exc}"]
    rows = data.get("exceptions", [])
    if not isinstance(rows, list):
        return set(), ["bootstrap exceptions must be a list"]
    ids: set[int] = set()
    for row in rows:
        if not isinstance(row, dict):
            errors.append("bootstrap exception row must be an object")
            continue
        rid = row.get("review_comment_id")
        if not isinstance(rid, int):
            errors.append("bootstrap exception review_comment_id must be integer")
            continue
        ids.add(rid)
    return ids, errors


def validate(root: Path, review_comments: Path | None = None) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    probes, probe_errors = _registered_guardrail_probes(root)
    errors.extend(probe_errors)
    entries, ledger_errors = _load_ledger_entries(root)
    errors.extend(ledger_errors)

    seen_ids: set[str] = set()
    seen_review_ids: set[int] = set()
    generations: list[int] = []
    for entry in entries:
        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or not entry_id:
            errors.append("learning entry missing id")
        elif entry_id in seen_ids:
            errors.append(f"duplicate learning entry id: {entry_id}")
        else:
            seen_ids.add(entry_id)
        review_id = entry.get("review_comment_id")
        if isinstance(review_id, int):
            if review_id in seen_review_ids:
                errors.append(f"duplicate learning review_comment_id: {review_id}")
            seen_review_ids.add(review_id)
        generation = entry.get("guardrail_generation")
        if not isinstance(generation, int) or isinstance(generation, bool):
            errors.append(f"learning entry guardrail_generation must be integer: {entry_id}")
        else:
            generations.append(generation)
        guardrails = entry.get("guardrails")
        if not isinstance(guardrails, list) or not guardrails:
            errors.append(f"learning entry guardrails missing: {entry_id}")
            continue
        for guardrail in guardrails:
            if not isinstance(guardrail, dict):
                errors.append(f"learning entry guardrail malformed: {entry_id}")
                continue
            path_value = guardrail.get("path")
            probe = guardrail.get("probe")
            if not isinstance(path_value, str) or not isinstance(probe, str):
                errors.append(f"learning entry guardrail path/probe malformed: {entry_id}")
                continue
            rel = Path(path_value)
            if rel not in probes:
                errors.append(f"learning entry guardrail path is not registered executable evidence: {entry_id}:{path_value}")
                continue
            if probe not in probes[rel]:
                errors.append(f"learning entry guardrail probe is not main-reachable executable evidence: {entry_id}:{path_value}:{probe}")

    if generations and generations != sorted(generations):
        errors.append("learning guardrail_generation must be monotonically nondecreasing")

    if review_comments is not None:
        try:
            comments = _flatten_comments(json.loads(review_comments.read_text(encoding="utf-8")))
        except Exception as exc:
            errors.append(f"cannot load review comments: {type(exc).__name__}: {exc}")
            comments = []
        material_ids = {
            row.get("id")
            for row in comments
            if isinstance(row.get("id"), int)
            and isinstance(row.get("body"), str)
            and MATERIAL_BADGE.search(row["body"])
        }
        exception_ids, exception_errors = validate_bootstrap_exceptions(root)
        errors.extend(exception_errors)
        missing = sorted(material_ids - seen_review_ids - exception_ids)
        if missing:
            errors.append("material PR findings missing from learning ledger or bootstrap exception: " + ",".join(map(str, missing)))
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--review-comments", type=Path)
    args = parser.parse_args()
    errors = validate(args.root, args.review_comments)
    for error in errors:
        print("ADVERSARIAL_LEARNING_ERROR:", error)
    if errors:
        raise SystemExit(1)
    print("adversarial_learning=PASS registered_guardrails=main-reachable executable")


if __name__ == "__main__":
    main()
