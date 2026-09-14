#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path.cwd()
AUTHORIZATION_MANIFEST = "implementation/g1-identity-tenant-shell-authorization/AUTHORIZATION_MANIFEST.json"
EXPECTED_HEAD_PREFIX = "impl/g1-identity-tenant-protected-shell"
EXPECTED_LABEL = "jlmirror-slice:g1-identity-tenant-shell"
EXPECTED_CLAIM_PATH = "implementation/g1-identity-tenant-shell/IMPLEMENTATION_CLAIM.json"
EXPECTED_AUTHORIZATION_ID = "g1.identity-tenant-protected-shell@1"
EXPECTED_SLICE_ID = "g1.identity-tenant-protected-shell@1"
EXPECTED_RULE = "every_changed_path_must_match_canonical_base_policy"
EXPECTED_ATTESTATION_COMMAND = "/jlmirror-g1-scope-attest"
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


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True, stderr=subprocess.DEVNULL).strip()


def git_bytes(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.DEVNULL)


def policy_from_base(root: Path, base_sha: str) -> dict[str, Any]:
    data = json.loads(git_bytes(root, "show", f"{base_sha}:{AUTHORIZATION_MANIFEST}").decode("utf-8"))
    policy = data.get("implementation_path_policy")
    if not isinstance(policy, dict):
        raise AssertionError("canonical base missing implementation_path_policy")
    if data.get("implementation_authority_after_merge") != "granted_for_exact_g1_identity_tenant_protected_shell_only":
        raise AssertionError("canonical base does not grant exact G1 implementation authority")
    return policy


def matches_policy(path: str, policy: dict[str, Any]) -> bool:
    prefixes, exact = policy.get("allowed_prefixes"), policy.get("allowed_exact_paths")
    if not isinstance(prefixes, list) or not all(isinstance(v, str) and v for v in prefixes):
        raise AssertionError("invalid allowed_prefixes")
    if not isinstance(exact, list) or not all(isinstance(v, str) and v for v in exact):
        raise AssertionError("invalid allowed_exact_paths")
    return path in exact or any(path.startswith(prefix) for prefix in prefixes)


def changed_paths(root: Path, base_sha: str, head_sha: str) -> list[str]:
    out = git(root, "diff", "--name-only", "--no-renames", f"{base_sha}...{head_sha}")
    return [line for line in out.splitlines() if line]


def claim_from_head(root: Path, head_sha: str, claim_path: str) -> dict[str, Any]:
    value = json.loads(git_bytes(root, "show", f"{head_sha}:{claim_path}").decode("utf-8"))
    if not isinstance(value, dict):
        raise AssertionError("G1 implementation claim must be a JSON object")
    return value


def configured_policy(policy: dict[str, Any]) -> None:
    checks = (
        (policy.get("implementation_pr_head_prefix") == EXPECTED_HEAD_PREFIX, "implementation PR head prefix drift"),
        (policy.get("implementation_pr_required_label") == EXPECTED_LABEL, "implementation PR required label drift"),
        (policy.get("implementation_claim_path") == EXPECTED_CLAIM_PATH, "implementation claim path drift"),
        (policy.get("implementation_claim_authorization_id") == EXPECTED_AUTHORIZATION_ID, "implementation claim authorization id drift"),
        (policy.get("trusted_evaluator_event") == "issue_comment", "trusted evaluator event drift"),
        (policy.get("trusted_scope_attestation_command") == EXPECTED_ATTESTATION_COMMAND, "trusted scope attestation command drift"),
        (policy.get("trusted_evaluator_source") == "default_branch_issue_comment_workflow_plus_exact_base_git_object", "trusted evaluator source drift"),
        (policy.get("same_repository_required") is True, "same-repository requirement drift"),
        (policy.get("implementation_pr_requires_trusted_scope_attestation_on_exact_head") is True, "trusted scope attestation requirement drift"),
        (tuple(policy.get("allowed_prefixes", [])) == EXPECTED_PREFIXES, "implementation allowed prefixes drift"),
        (tuple(policy.get("allowed_exact_paths", [])) == EXPECTED_EXACT, "implementation exact paths drift"),
        (policy.get("diff_enforcement_rule") == EXPECTED_RULE, "implementation diff enforcement rule drift"),
    )
    for ok, msg in checks:
        if not ok:
            raise AssertionError(msg)


def validate_candidate_metadata(
    root: Path,
    head_sha: str,
    head_ref: str,
    labels: set[str],
    head_repo: str,
    base_repo: str,
    policy: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if head_repo != base_repo:
        errors.append("G1 implementation PR must originate from the canonical repository")
    if not head_ref.startswith(EXPECTED_HEAD_PREFIX):
        errors.append("G1 implementation PR missing required canonical head prefix")
    if EXPECTED_LABEL not in labels:
        errors.append("G1 implementation PR missing required canonical label")
    try:
        claim = claim_from_head(root, head_sha, policy["implementation_claim_path"])
    except (subprocess.CalledProcessError, json.JSONDecodeError, UnicodeDecodeError):
        errors.append("G1 implementation PR missing or malformed required claim")
    else:
        if type(claim.get("schema_version")) is not int or claim.get("schema_version") != 1:
            errors.append("G1 implementation claim schema_version drift")
        if claim.get("authorization_id") != EXPECTED_AUTHORIZATION_ID:
            errors.append("G1 implementation claim authorization_id drift")
        if claim.get("slice_id") != EXPECTED_SLICE_ID:
            errors.append("G1 implementation claim slice_id drift")
    return errors


def validate_paths(paths: list[str], policy: dict[str, Any]) -> list[str]:
    errors = [] if policy.get("diff_enforcement_rule") == EXPECTED_RULE else ["implementation diff enforcement rule drift"]
    errors.extend(f"unauthorized G1 implementation path: {path}" for path in paths if not matches_policy(path, policy))
    return errors


def validate(
    base_sha: str,
    head_sha: str,
    head_ref: str,
    labels: set[str],
    head_repo: str,
    base_repo: str,
    *,
    root: Path = DEFAULT_ROOT,
) -> tuple[bool, list[str]]:
    """Validate an explicitly attested G1 implementation PR.

    The trusted default-branch caller is the independent classifier. There is no
    candidate-controlled relevance inference and therefore no not-G1 success path.
    """
    root = root.resolve()
    if not all((base_sha, head_sha, head_ref, head_repo, base_repo)):
        return True, ["exact base/head/head-ref/head-repo/base-repo are required"]
    try:
        git(root, "cat-file", "-e", f"{base_sha}^{{commit}}")
        git(root, "cat-file", "-e", f"{head_sha}^{{commit}}")
        policy = policy_from_base(root, base_sha)
        configured_policy(policy)
        paths = changed_paths(root, base_sha, head_sha)
        errors = validate_candidate_metadata(root, head_sha, head_ref, labels, head_repo, base_repo, policy)
        errors.extend(["attested G1 implementation PR has no changed paths"] if not paths else validate_paths(paths, policy))
        return True, errors
    except (AssertionError, subprocess.CalledProcessError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return True, [str(exc)]


def parse_labels(value: str) -> set[str]:
    parsed = json.loads(value)
    if not isinstance(parsed, list) or any(not isinstance(item, str) for item in parsed):
        raise ValueError("labels JSON must be an array of strings")
    return set(parsed)


def main() -> int:
    parser = argparse.ArgumentParser()
    for arg in ("base", "head", "head-ref", "labels-json", "head-repo", "base-repo"):
        parser.add_argument(f"--{arg}", required=True)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    try:
        labels = parse_labels(args.labels_json)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"G1_IMPLEMENTATION_SCOPE_ERROR: invalid labels metadata: {exc}", file=sys.stderr)
        return 1
    _classified, errors = validate(
        args.base,
        args.head,
        args.head_ref,
        labels,
        args.head_repo,
        args.base_repo,
        root=args.repo_root,
    )
    for error in errors:
        print(f"G1_IMPLEMENTATION_SCOPE_ERROR: {error}", file=sys.stderr)
    if errors:
        return 1
    print("g1_implementation_scope=PASS classification=trusted_explicit_attestation metadata=label+branch+claim complete_diff=allowlisted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
