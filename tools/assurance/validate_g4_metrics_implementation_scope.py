#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import unicodedata
import sys
from pathlib import Path

MANIFEST_PATH = "implementation/g4-metrics-authorization/AUTHORIZATION_MANIFEST.json"
EXECUTABLE_SUFFIXES = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".sh", ".bash", ".sql", ".go", ".rs", ".java", ".kt", ".cs", ".rb", ".php"}
PERSISTENCE_RECEIVERS = ("database", "db", "repository", "repo", "prisma", "postgres", "postgresql", "pg", "sqlalchemy", "psycopg", "cursor")
PERSISTENCE_WRITES = ("insert", "update", "delete", "save", "upsert", "commit", "persist", "executemany")
SQL_MUTATION_RE = re.compile(r"\b(?:insert\s+into\s+[^\s;()]+|update\s+[^\s;()]+\s+set\b|delete\s+from\s+[^\s;()]+|merge\s+into\s+[^\s;()]+|truncate(?:\s+table)?\s+[^\s;()]+|alter\s+(?:table|schema)\s+[^\s;()]+|drop\s+(?:table|schema|view|function|procedure)\s+[^\s;()]+|create\s+(?:table|schema|view|function|procedure)\s+[^\s;()]+)", re.IGNORECASE)

def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()

def allowed(path: str, policy: dict) -> bool:
    return path in set(policy.get("allowed_exact_paths") or []) or any(path.startswith(prefix) for prefix in policy.get("allowed_prefixes") or [])

def candidate_text(root: Path, path: str, head: str) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(root), "show", f"{head}:{path}"], text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return ""

def semantic_fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"\\u\\{?([0-9a-fA-F]{4,6})\\}?", lambda m: chr(int(m.group(1), 16)), normalized)
    normalized = re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), normalized)
    return re.sub(r"[^a-z0-9]+", "", normalized)


def semantic_errors(path: str, text: str, policy: dict) -> list[str]:
    if Path(path).suffix.lower() not in EXECUTABLE_SUFFIXES:
        return []
    errors: list[str] = []
    folded = semantic_fold(text)
    for marker in policy.get("forbidden_code_markers") or []:
        marker_folded = semantic_fold(str(marker))
        if marker_folded and marker_folded in folded:
            errors.append(f"forbidden G4 semantic marker '{marker}' in {path}")
    if SQL_MUTATION_RE.search(text):
        errors.append(f"direct SQL/schema mutation is forbidden in G4 executable artifact: {path}")
    receivers = set(PERSISTENCE_RECEIVERS)
    assignment_re = re.compile(
        r"\b(?:const\s+|let\s+|var\s+)?([A-Za-z_$][\w$]*)\s*=\s*(?:(?:self|this)\s*\.\s*)?([A-Za-z_$][\w$]*)\b"
    )
    changed = True
    while changed:
        changed = False
        for alias, source in assignment_re.findall(text):
            if source.casefold() in {name.casefold() for name in receivers} and alias not in receivers:
                receivers.add(alias)
                changed = True

    receiver = "|".join(sorted((re.escape(x) for x in receivers), key=len, reverse=True))
    method = "|".join(re.escape(x) for x in PERSISTENCE_WRITES)
    property_write_re = re.compile(rf"\b(?:{receiver})\s*\.\s*(?:{method})\b", re.IGNORECASE)
    bracket_write_re = re.compile(rf"\b(?:{receiver})\s*\[\s*['\"](?:{method})['\"]\s*\]", re.IGNORECASE)
    getattr_write_re = re.compile(rf"\bgetattr\s*\(\s*(?:{receiver})\s*,\s*['\"](?:{method})['\"]\s*\)", re.IGNORECASE)
    if property_write_re.search(text) or bracket_write_re.search(text) or getattr_write_re.search(text):
        errors.append(f"direct persistence write is forbidden in G4 executable artifact: {path}")
    return errors


def runtime_workflow_errors(text: str, policy: dict) -> list[str]:
    errors: list[str] = []
    try:
        workflow = json.loads(text)
    except json.JSONDecodeError:
        return ["G4 runtime workflow must use canonical JSON-compatible workflow structure"]
    if workflow.get("name") != policy.get("runtime_workflow_name"):
        errors.append("G4 runtime workflow name drift")
    if workflow.get("permissions") != {}:
        errors.append("G4 runtime workflow must default to zero permissions")
    triggers = workflow.get("on")
    if not isinstance(triggers, dict) or set(triggers) != {"pull_request", "workflow_dispatch"}:
        errors.append("G4 runtime workflow trigger surface drift")
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict) or set(jobs) != {"g4-runtime"}:
        errors.append("G4 runtime workflow must contain exactly g4-runtime job")
        return errors
    job = jobs["g4-runtime"]
    if not isinstance(job, dict) or job.get("runs-on") not in {"ubuntu-24.04", "ubuntu-latest"}:
        errors.append("G4 runtime job runner drift")
    steps = job.get("steps") if isinstance(job, dict) else None
    if not isinstance(steps, list) or not steps:
        errors.append("G4 runtime workflow steps missing")
        return errors
    allowed_actions = set(policy.get("runtime_allowed_actions") or [])
    runs: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            errors.append("G4 runtime workflow step must be an object")
            continue
        use = step.get("uses")
        run = step.get("run")
        if use is not None:
            if use not in allowed_actions:
                errors.append(f"G4 runtime workflow uses unauthorized action: {use}")
            if set(step) != {"uses"}:
                errors.append("G4 runtime action steps may not override repository, ref, path, credentials, env, shell, or other inputs")
            if run is not None:
                errors.append("G4 runtime workflow step cannot combine uses and run")
        elif run is not None:
            if set(step) != {"run"}:
                errors.append("G4 runtime run step may contain only the canonical run command")
            if not isinstance(run, str):
                errors.append("G4 runtime workflow run step must be a string")
            else:
                runs.append(run.strip())
        else:
            errors.append("G4 runtime workflow step must contain uses or run")
    if runs != [policy.get("runtime_entrypoint")]:
        errors.append("G4 runtime workflow must execute exactly the canonical runtime entrypoint once")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--labels-json", required=True)
    parser.add_argument("--head-repo", required=True)
    parser.add_argument("--base-repo", required=True)
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    errors: list[str] = []
    manifest = json.loads(subprocess.check_output(["git", "-C", str(root), "show", f"{args.base}:{MANIFEST_PATH}"], text=True))
    policy = manifest["implementation_path_policy"]
    if manifest.get("implementation_authority_after_merge") != "granted_for_exact_g4_metrics_only": errors.append("base does not grant exact G4 implementation authority")
    if args.head_repo != args.base_repo: errors.append("implementation PR must use the canonical repository")
    if not args.head_ref.startswith(policy["implementation_pr_head_prefix"]): errors.append("implementation head prefix is not canonical G4 prefix")
    try:
        labels = set(json.loads(args.labels_json))
    except Exception:
        labels = set(); errors.append("labels-json is invalid")
    if policy["implementation_pr_required_label"] not in labels: errors.append("implementation PR missing required G4 label")
    changed = [p for p in git(root, "diff", "--name-only", "--no-renames", f"{args.base}...{args.head}").splitlines() if p]
    if not changed: errors.append("implementation diff is empty")
    forbidden_tokens = tuple(str(x).lower() for x in policy.get("forbidden_path_tokens") or [])
    for path in changed:
        lower_path = path.lower()
        if not allowed(path, policy):
            errors.append(f"path outside G4 implementation authority: {path}")
            continue
        if any(token in lower_path for token in forbidden_tokens):
            errors.append(f"forbidden G4 path token in {path}")
        if path.startswith(tuple(policy.get("semantic_scan_prefixes") or [])):
            text = candidate_text(root, path, args.head)
            errors.extend(semantic_errors(path, text, policy))
    runtime_path = policy["runtime_workflow"]
    runtime_text = candidate_text(root, runtime_path, args.head)
    if not runtime_text:
        errors.append("G4 runtime workflow missing")
    else:
        errors.extend(runtime_workflow_errors(runtime_text, policy))
    claim_path = policy["implementation_claim_path"]
    claim_text = candidate_text(root, claim_path, args.head)
    if not claim_text:
        errors.append("G4 implementation claim missing")
    else:
        try:
            claim = json.loads(claim_text)
            if set(claim) != {"schema_version","authorization_id","slice_id"}: errors.append("G4 implementation claim shape drift")
            if claim.get("schema_version") != 1 or claim.get("authorization_id") != "g4.metrics@1" or claim.get("slice_id") != "g4.metrics@1": errors.append("G4 implementation claim identity drift")
        except Exception:
            errors.append("G4 implementation claim is invalid JSON")
    for error in errors:
        print(f"G4_SCOPE_ERROR: {error}", file=sys.stderr)
    if errors: return 1
    print(f"g4_scope=PASS base={args.base} head={args.head} changed_files={len(changed)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
