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
EXPECTED_READINESS_COMMAND = "/jlmirror-g1-scope-ready"
EXPECTED_STATUS_CONTEXT = "JLMIRROR / g1-identity-tenant-shell-implementation-scope"
EXPECTED_READY_CONTEXT = "JLMIRROR / g1-identity-tenant-shell-merge-readiness"
EXPECTED_READINESS_VALIDATOR = "tools/assurance/validate_g1_identity_tenant_shell_scope_readiness.py"
EXPECTED_RUNTIME_WORKFLOW = ".github/workflows/g1-identity-tenant-shell-runtime.yml"
EXPECTED_RUNTIME_NAME = "JLMIRROR G1 Identity Tenant Shell Runtime"
EXPECTED_RUNTIME_ENTRYPOINT = "python tools/g1/run_identity_tenant_shell_runtime.py"
EXPECTED_PREFIXES = (
    "apps/g1-identity-tenant-shell/", "contracts/g1-identity-tenant-shell/",
    "implementation/g1-identity-tenant-shell/", "sql/g1/", "src/jlmirror_g1/",
    "tests/g1/", "tools/g1/",
)
EXPECTED_EXACT = (EXPECTED_RUNTIME_WORKFLOW,)
RUNTIME_ALLOWED_TRIGGERS = {"pull_request", "workflow_dispatch"}
RUNTIME_ALLOWED_ACTIONS = ("actions/checkout", "actions/setup-python", "actions/setup-node")


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
        (policy.get("implementation_pr_base_ref_policy") == "must_equal_repository_default_branch", "implementation PR base ref policy drift"),
        (policy.get("trusted_evaluator_event") == "issue_comment", "trusted evaluator event drift"),
        (policy.get("trusted_scope_attestation_command") == EXPECTED_ATTESTATION_COMMAND, "trusted scope attestation command drift"),
        (policy.get("trusted_scope_readiness_command") == EXPECTED_READINESS_COMMAND, "trusted scope readiness command drift"),
        (policy.get("trusted_evaluator_source") == "default_branch_issue_comment_workflow_plus_exact_default_branch_base_git_object", "trusted evaluator source drift"),
        (policy.get("trusted_scope_status_context") == EXPECTED_STATUS_CONTEXT, "trusted scope status context drift"),
        (policy.get("trusted_scope_readiness_status_context") == EXPECTED_READY_CONTEXT, "trusted scope readiness status context drift"),
        (policy.get("trusted_scope_status_publication") == "pending_then_final_coordinate_bound_evidence_on_resolved_pr_head", "trusted scope status publication drift"),
        (policy.get("trusted_scope_status_evidence_role") == "evidence_only_not_standalone_merge_authority", "trusted scope evidence role drift"),
        (policy.get("trusted_scope_freshness_rule") == "merge_readiness_revalidates_live_head_base_default_tip_label_and_trusted_status_run_provenance", "trusted scope freshness rule drift"),
        (policy.get("trusted_scope_concurrency_rule") == "per_pr_cancel_in_progress", "trusted scope concurrency rule drift"),
        (policy.get("trusted_status_creator_login") == "github-actions[bot]", "trusted status creator login drift"),
        (policy.get("trusted_status_creator_id") == 41898282, "trusted status creator id drift"),
        (policy.get("trusted_scope_merge_preflight_rule") == "live_revalidate_ready_evidence_current_coordinates_label_and_workflow_run_immediately_before_merge", "trusted merge preflight rule drift"),
        (policy.get("trusted_scope_readiness_validator") == EXPECTED_READINESS_VALIDATOR, "trusted scope readiness validator drift"),
        (policy.get("same_repository_required") is True, "same-repository requirement drift"),
        (policy.get("implementation_pr_requires_trusted_scope_attestation_on_exact_head") is True, "trusted scope attestation requirement drift"),
        (policy.get("implementation_pr_requires_trusted_scope_readiness_on_exact_head_base") is True, "trusted scope readiness requirement drift"),
        (policy.get("candidate_controlled_relevance_inference") == "forbidden", "candidate relevance inference drift"),
        (tuple(policy.get("allowed_prefixes", [])) == EXPECTED_PREFIXES, "implementation allowed prefixes drift"),
        (tuple(policy.get("allowed_exact_paths", [])) == EXPECTED_EXACT, "implementation exact paths drift"),
        (policy.get("diff_enforcement_rule") == EXPECTED_RULE, "implementation diff enforcement rule drift"),
    )
    for ok, msg in checks:
        if not ok:
            raise AssertionError(msg)


def validate_candidate_metadata(root: Path, head_sha: str, head_ref: str, labels: set[str], head_repo: str, base_repo: str, policy: dict[str, Any]) -> list[str]:
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


def _runtime_step_errors(step: Any, index: int) -> list[str]:
    if not isinstance(step, dict):
        return [f"runtime workflow step {index} must be an object"]
    if index < 3:
        if set(step) != {"uses"} or not isinstance(step.get("uses"), str):
            return [f"runtime workflow setup step {index} shape drift"]
        value = step["uses"]
        action, sep, sha = value.partition("@")
        expected_action = RUNTIME_ALLOWED_ACTIONS[index]
        if action != expected_action or not sep or len(sha) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in sha):
            return [f"runtime workflow setup step {index} must use {expected_action} pinned to a 40-hex SHA"]
        return []
    if set(step) != {"run"} or step.get("run") != EXPECTED_RUNTIME_ENTRYPOINT:
        return ["runtime workflow executable responsibility drift"]
    return []


def validate_runtime_workflow_text(text: str) -> list[str]:
    """Validate the future runtime workflow semantically.

    The governed .yml file is intentionally restricted to canonical JSON-form YAML.
    JSON is a YAML subset, and requiring this representation lets the gate parse a
    real object tree with the Python standard library instead of trusting lexical
    spellings, quoted keys, indentation, aliases, or equivalent YAML surface forms.
    """
    try:
        workflow = json.loads(text)
    except json.JSONDecodeError:
        return ["runtime workflow must use canonical JSON-form YAML for semantic validation"]
    if not isinstance(workflow, dict):
        return ["runtime workflow root must be an object"]
    errors: list[str] = []
    if set(workflow) != {"name", "on", "permissions", "jobs"}:
        errors.append(f"runtime workflow top-level key set drift: {sorted(map(str, workflow.keys()))}")
    if workflow.get("name") != EXPECTED_RUNTIME_NAME:
        errors.append("runtime workflow name drift")
    triggers = workflow.get("on")
    if not isinstance(triggers, dict) or set(triggers) != RUNTIME_ALLOWED_TRIGGERS or any(value != {} for value in triggers.values()):
        errors.append("runtime workflow trigger set/config drift")
    if workflow.get("permissions") != {}:
        errors.append("runtime workflow must have zero permissions")
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict) or set(jobs) != {"g1-runtime"}:
        errors.append("runtime workflow job set drift")
        return errors
    job = jobs.get("g1-runtime")
    if not isinstance(job, dict) or set(job) != {"runs-on", "steps"}:
        errors.append("runtime workflow job shape drift")
        return errors
    if job.get("runs-on") != "ubuntu-latest":
        errors.append("runtime workflow runner drift")
    steps = job.get("steps")
    if not isinstance(steps, list) or len(steps) != 4:
        errors.append("runtime workflow must contain exactly four canonical steps")
        return errors
    for index, step in enumerate(steps):
        errors.extend(_runtime_step_errors(step, index))
    return errors


def validate_runtime_workflow_from_head(root: Path, head_sha: str, paths: list[str]) -> list[str]:
    if EXPECTED_RUNTIME_WORKFLOW not in paths:
        return []
    try:
        text = git_bytes(root, "show", f"{head_sha}:{EXPECTED_RUNTIME_WORKFLOW}").decode("utf-8")
    except (subprocess.CalledProcessError, UnicodeDecodeError):
        return ["allowed G1 runtime workflow path must exist as UTF-8 text on candidate head"]
    return validate_runtime_workflow_text(text)


# no candidate-controlled relevance inference

def validate(base_sha: str, head_sha: str, head_ref: str, labels: set[str], head_repo: str, base_repo: str, *, root: Path = DEFAULT_ROOT) -> tuple[bool, list[str]]:
    """Validate an explicitly attested G1 implementation PR."""
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
        if not paths:
            errors.append("attested G1 implementation PR has no changed paths")
        else:
            errors.extend(validate_paths(paths, policy))
            errors.extend(validate_runtime_workflow_from_head(root, head_sha, paths))
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
    _classified, errors = validate(args.base, args.head, args.head_ref, labels, args.head_repo, args.base_repo, root=args.repo_root)
    for error in errors:
        print(f"G1_IMPLEMENTATION_SCOPE_ERROR: {error}", file=sys.stderr)
    if errors:
        return 1
    print("g1_implementation_scope=PASS classification=trusted_explicit_attestation default_base=required exact_head_status=evidence-only readiness=live-source-authenticated metadata=label+branch+claim complete_diff=allowlisted runtime_workflow=json-yaml-semantic+zero-permission+bounded-trigger+single-entrypoint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
