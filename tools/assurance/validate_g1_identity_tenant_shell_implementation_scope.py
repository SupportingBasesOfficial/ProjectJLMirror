#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
AUTHORIZATION_MANIFEST = "implementation/g1-identity-tenant-shell-authorization/AUTHORIZATION_MANIFEST.json"
EXPECTED_HEAD_PREFIX = "impl/g1-identity-tenant-protected-shell"
EXPECTED_RULE = "every_changed_path_must_match_canonical_base_policy"
EXPECTED_PREFIXES = (
    "apps/g1-identity-tenant-shell/",
    "contracts/g1-identity-tenant-shell/",
    "implementation/g1-identity-tenant-shell/",
    "sql/g1/",
    "src/jlmirror_g1/",
    "tests/g1/",
    "tools/g1/",
)
EXPECTED_EXACT = (".github/workflows/g1-identity-tenant-shell-runtime.yml",)


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def git_bytes(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def policy_from_base(base_sha: str) -> dict[str, Any]:
    raw = git_bytes("show", f"{base_sha}:{AUTHORIZATION_MANIFEST}")
    data = json.loads(raw.decode("utf-8"))
    policy = data.get("implementation_path_policy")
    if not isinstance(policy, dict):
        raise AssertionError("canonical base missing implementation_path_policy")
    if data.get("implementation_authority_after_merge") != "granted_for_exact_g1_identity_tenant_protected_shell_only":
        raise AssertionError("canonical base does not grant exact G1 implementation authority")
    return policy


def matches_policy(path: str, policy: dict[str, Any]) -> bool:
    prefixes = policy.get("allowed_prefixes")
    exact = policy.get("allowed_exact_paths")
    if not isinstance(prefixes, list) or not all(isinstance(v, str) and v for v in prefixes):
        raise AssertionError("invalid allowed_prefixes")
    if not isinstance(exact, list) or not all(isinstance(v, str) and v for v in exact):
        raise AssertionError("invalid allowed_exact_paths")
    return path in exact or any(path.startswith(prefix) for prefix in prefixes)


def changed_paths(base_sha: str, head_sha: str) -> list[str]:
    # --no-renames prevents a rename/copy representation from hiding either side
    # of a boundary crossing. Deletions and additions are evaluated independently.
    out = git("diff", "--name-only", "--no-renames", f"{base_sha}...{head_sha}")
    return [line for line in out.splitlines() if line]


def is_potentially_g1(head_ref: str, paths: list[str]) -> bool:
    if head_ref.startswith(EXPECTED_HEAD_PREFIX):
        return True
    return any(path in EXPECTED_EXACT or path.startswith(EXPECTED_PREFIXES) for path in paths)


def is_relevant(head_ref: str, paths: list[str], policy: dict[str, Any]) -> bool:
    configured = policy.get("implementation_pr_head_prefix")
    if configured != EXPECTED_HEAD_PREFIX:
        raise AssertionError("implementation PR head prefix drift")
    if tuple(policy.get("allowed_prefixes", [])) != EXPECTED_PREFIXES:
        raise AssertionError("implementation allowed prefixes drift")
    if tuple(policy.get("allowed_exact_paths", [])) != EXPECTED_EXACT:
        raise AssertionError("implementation exact paths drift")
    if head_ref.startswith(EXPECTED_HEAD_PREFIX):
        return True
    return any(matches_policy(path, policy) for path in paths)


def validate_paths(paths: list[str], policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if policy.get("diff_enforcement_rule") != EXPECTED_RULE:
        errors.append("implementation diff enforcement rule drift")
    for path in paths:
        if not matches_policy(path, policy):
            errors.append(f"unauthorized G1 implementation path: {path}")
    return errors


def validate(base_sha: str, head_sha: str, head_ref: str) -> tuple[bool, list[str]]:
    if not base_sha or not head_sha or not head_ref:
        return False, ["exact base/head/head-ref are required"]
    try:
        git("cat-file", "-e", f"{base_sha}^{{commit}}")
        git("cat-file", "-e", f"{head_sha}^{{commit}}")
        paths = changed_paths(base_sha, head_sha)
        if not is_potentially_g1(head_ref, paths):
            return False, []
        policy = policy_from_base(base_sha)
        relevant = is_relevant(head_ref, paths, policy)
        if not relevant:
            return False, []
        if not paths:
            return True, ["relevant G1 implementation PR has no changed paths"]
        return True, validate_paths(paths, policy)
    except (AssertionError, subprocess.CalledProcessError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return True, [str(exc)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--head-ref", required=True)
    args = parser.parse_args()
    relevant, errors = validate(args.base, args.head, args.head_ref)
    for error in errors:
        print(f"G1_IMPLEMENTATION_SCOPE_ERROR: {error}", file=sys.stderr)
    if errors:
        return 1
    if relevant:
        print("g1_implementation_scope=PASS relevance=g1 exact_base_head=bound complete_diff=allowlisted canonical_base_policy=authoritative")
    else:
        print("g1_implementation_scope=PASS relevance=not-g1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
