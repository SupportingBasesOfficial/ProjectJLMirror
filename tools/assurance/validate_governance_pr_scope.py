#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

DOCS_ALLOWED_PREFIXES = (
    "docs/",
    "governance/adversarial/learning-ledger.d/",
)
GOVERNANCE_ALLOWED_PREFIXES = (
    "docs/",
    "governance/",
    "tools/assurance/",
    ".github/workflows/",
    "implementation/",
)

RUNTIME_FORBIDDEN_PREFIXES = (
    "apps/",
    "src/",
    "sql/",
    "tests/",
    "docker/",
    "contracts/",
)
RUNTIME_FORBIDDEN_EXACT = {
    "Makefile",
    "compose.yml",
    "docker-compose.yml",
    "pyproject.toml",
    "package.json",
    "pnpm-lock.yaml",
}


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def scope_errors(*, head_ref: str, changed_paths: list[str]) -> list[str]:
    if not head_ref:
        return []
    if head_ref.startswith("docs/"):
        allowed = DOCS_ALLOWED_PREFIXES
        scope = "docs"
    elif head_ref.startswith("governance/"):
        allowed = GOVERNANCE_ALLOWED_PREFIXES
        scope = "governance"
    else:
        return []

    errors: list[str] = []
    for path in changed_paths:
        if path in RUNTIME_FORBIDDEN_EXACT or path.startswith(RUNTIME_FORBIDDEN_PREFIXES):
            errors.append(f"{scope}-scope branch carries forbidden runtime/substrate path: {path}")
            continue
        if not path.startswith(allowed):
            errors.append(f"{scope}-scope branch carries undeclared path outside governance allowlist: {path}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--head-ref", default="")
    args = parser.parse_args()

    if not args.base or not args.head or not args.head_ref:
        print("governance_pr_scope=SKIP non_pull_request_or_unclassified")
        return 0

    root = args.root.resolve()
    changed = [
        p for p in git(root, "diff", "--name-only", "--no-renames", f"{args.base}...{args.head}").splitlines()
        if p
    ]
    errors = scope_errors(head_ref=args.head_ref, changed_paths=changed)
    for error in errors:
        print(f"GOVERNANCE_PR_SCOPE_ERROR: {error}")
    if errors:
        return 1
    print(f"governance_pr_scope=PASS head_ref={args.head_ref} changed_paths={len(changed)} no_runtime_contamination=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
