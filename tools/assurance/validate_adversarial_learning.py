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
WORKFLOW = Path(".github/workflows/deterministic-assurance.yml")
SOURCE_PROBE_PATH = Path("tools/assurance/d4d_trace_context_source.py")
FALSIFICATION_PATHS = {
    Path("tools/assurance/test_validate_d4d_trace_context_source.py"),
    Path("tools/assurance/test_validate_adversarial_learning.py"),
}
MATERIAL_BADGE = re.compile(r"\bP[012] Badge\b")


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


def _main_called_falsifiers(path: Path) -> tuple[set[str], list[str]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        return set(), [f"cannot parse registered falsification file {path}: {type(exc).__name__}: {exc}"]
    functions = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    main = functions.get("main")
    if main is None:
        return set(), [f"registered falsification file has no main function: {path}"]
    called = {
        node.func.id
        for node in ast.walk(main)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    executed = {name for name in called if name in functions and name.startswith("falsify_")}
    return executed, []


def _resolve_executable_checks(root: Path) -> tuple[dict[Path, set[str]], list[str]]:
    checks: dict[Path, set[str]] = {}
    errors: list[str] = []
    source_path = root / SOURCE_PROBE_PATH
    if source_path.is_file():
        checks[SOURCE_PROBE_PATH], source_errors = _executed_source_probes(source_path)
        errors.extend(source_errors)
    else:
        errors.append(f"registered executable source probe path missing: {SOURCE_PROBE_PATH}")
    for rel in FALSIFICATION_PATHS:
        path = root / rel
        if not path.is_file():
            errors.append(f"registered falsification path missing: {rel}")
            continue
        checks[rel], file_errors = _main_called_falsifiers(path)
        errors.extend(file_errors)
    return checks, errors


def validate_review_surface_coverage(root: Path) -> list[str]:
    workflow = root / WORKFLOW
    if not workflow.is_file():
        return [f"learning reconciliation workflow missing: {WORKFLOW}"]
    try:
        text = workflow.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [f"learning reconciliation workflow must be UTF-8: {WORKFLOW}"]
    required_markers = {
        "issue_comment trigger": "issue_comment:",
        "PR-only issue-comment job guard": "github.event.issue.pull_request != null",
        "issue-comment event reconciliation": "github.event_name == 'issue_comment'",
        "top-level issue comment collection": "repos/${GITHUB_REPOSITORY}/issues/${PR_NUMBER}/comments?per_page=100",
        "issue-comment PR number resolution": "github.event.pull_request.number || github.event.issue.number",
        "issue-comment exact PR head lookup": "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}",
    }
    return [f"learning reconciliation workflow missing {name}" for name, marker in required_markers.items() if marker not in text]


def validate(root: Path, review_comments: Path | None = None) -> list[str]:
    errors: list[str] = []
    taxonomy = _load(root / TAXONOMY)
    invariants = _load(root / INVARIANTS)
    ledger = _load(root / LEDGER)

    if taxonomy.get("schema_version") != 1:
        errors.append("taxonomy schema_version must be 1")
    if invariants.get("schema_version") != 1:
        errors.append("invariants schema_version must be 1")
    if ledger.get("schema_version") != 1:
        errors.append("ledger schema_version must be 1")

    invariant_rows = invariants.get("invariants")
    class_rows = taxonomy.get("classes")
    entries = ledger.get("entries")
    if not isinstance(invariant_rows, list) or not isinstance(class_rows, list) or not isinstance(entries, list):
        return errors + ["taxonomy, invariants and ledger collections must be arrays"]

    invariant_ids = [row.get("id") for row in invariant_rows if isinstance(row, dict)]
    if len(invariant_ids) != len(set(invariant_ids)) or any(not isinstance(i, str) or not i for i in invariant_ids):
        errors.append("invariant ids must be unique non-empty strings")
    invariant_set = set(invariant_ids)

    class_ids = [row.get("id") for row in class_rows if isinstance(row, dict)]
    if len(class_ids) != len(set(class_ids)) or any(not isinstance(i, str) or not i for i in class_ids):
        errors.append("class ids must be unique non-empty strings")
    class_map = {row["id"]: row for row in class_rows if isinstance(row, dict) and isinstance(row.get("id"), str)}
    for cid, row in class_map.items():
        refs = row.get("invariant_ids")
        if not isinstance(refs, list) or not refs or not set(refs).issubset(invariant_set):
            errors.append(f"class {cid} must reference only known invariants")
        if not isinstance(row.get("description"), str) or len(row["description"].strip()) < 40:
            errors.append(f"class {cid} description is too weak")

    errors.extend(validate_review_surface_coverage(root))
    executable_checks, executable_errors = _resolve_executable_checks(root)
    errors.extend(executable_errors)

    entry_ids: set[str] = set()
    review_ids: set[int] = set()
    generations: dict[str, int] = defaultdict(int)
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("ledger entry must be an object")
            continue
        eid = entry.get("id")
        if not isinstance(eid, str) or not eid or eid in entry_ids:
            errors.append("ledger entry ids must be unique non-empty strings")
            continue
        entry_ids.add(eid)
        cid = entry.get("class_id")
        if cid not in class_map:
            errors.append(f"{eid}: unknown class_id")
            continue
        refs = entry.get("invariant_ids")
        allowed_refs = set(class_map[cid].get("invariant_ids", []))
        if not isinstance(refs, list) or not refs or not set(refs).issubset(allowed_refs):
            errors.append(f"{eid}: invariant_ids must be a non-empty subset of class invariants")
        if not isinstance(entry.get("root_cause"), str) or len(entry["root_cause"].strip()) < 40:
            errors.append(f"{eid}: root_cause is missing or too local")
        audit = entry.get("horizontal_audit")
        if not isinstance(audit, list) or not audit or any(not isinstance(v, str) or len(v.strip()) < 4 for v in audit):
            errors.append(f"{eid}: horizontal_audit must record audited siblings/boundaries")
        guardrails = entry.get("guardrails")
        if not isinstance(guardrails, list) or not guardrails:
            errors.append(f"{eid}: at least one permanent guardrail is required")
        else:
            for guardrail in guardrails:
                if not isinstance(guardrail, dict) or not isinstance(guardrail.get("path"), str):
                    errors.append(f"{eid}: malformed guardrail")
                    continue
                rel = Path(guardrail["path"])
                if not (root / rel).is_file():
                    errors.append(f"{eid}: guardrail path does not exist: {guardrail['path']}")
                    continue
                probe = guardrail.get("probe")
                if not isinstance(probe, str) or not probe.strip():
                    errors.append(f"{eid}: guardrail must name the probe/check it relies on")
                    continue
                registered = executable_checks.get(rel)
                if registered is None:
                    errors.append(f"{eid}: no executable guardrail resolver registered for path: {guardrail['path']}")
                    continue
                if not any(_template_matches(probe, actual) for actual in registered):
                    errors.append(f"{eid}: declared guardrail does not resolve to an executed check: {probe}")
        if entry.get("systemic_guardrail_updated") is not True:
            errors.append(f"{eid}: systemic_guardrail_updated must be true")
        generation = entry.get("guardrail_generation")
        if not isinstance(generation, int) or generation <= generations[cid]:
            errors.append(f"{eid}: recurring class {cid} must advance guardrail_generation")
        else:
            generations[cid] = generation

        source = entry.get("source")
        rid = entry.get("review_comment_id")
        if source == "external_review":
            if not isinstance(rid, int) or rid <= 0:
                errors.append(f"{eid}: external_review requires positive review_comment_id")
            elif rid in review_ids:
                errors.append(f"{eid}: duplicate review_comment_id {rid}")
            else:
                review_ids.add(rid)
        elif source == "internal_audit":
            if rid is not None:
                errors.append(f"{eid}: internal_audit must not impersonate external review identity")
        else:
            errors.append(f"{eid}: source must be external_review or internal_audit")

    if review_comments is not None:
        comments = _flatten_comments(_load(review_comments))
        material = {
            comment.get("id")
            for comment in comments
            if isinstance(comment.get("id"), int)
            and isinstance(comment.get("body"), str)
            and MATERIAL_BADGE.search(comment["body"])
        }
        missing = sorted(material - review_ids)
        if missing:
            errors.append("material PR review findings missing from learning ledger: " + ",".join(map(str, missing)))

    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--review-comments", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    errors = validate(root, args.review_comments)
    for error in errors:
        print("ADVERSARIAL_LEARNING_ERROR:", error)
    if errors:
        raise SystemExit(1)
    print("adversarial_learning=PASS taxonomy=linked invariants=linked ledger=complete recurrence=guardrail-advancing guardrail-checks=executed dynamic_findings=all-surfaces-mapped")


if __name__ == "__main__":
    main()
