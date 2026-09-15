#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path.cwd()
AUTHORIZATION_MANIFEST = "implementation/g2-monitoring-source-onboarding-authorization/AUTHORIZATION_MANIFEST.json"
EXPECTED_HEAD_PREFIX = "impl/g2-monitoring-source-onboarding"
EXPECTED_LABEL = "jlmirror-slice:g2-monitoring-source-onboarding"
EXPECTED_CLAIM_PATH = "implementation/g2-monitoring-source-onboarding/IMPLEMENTATION_CLAIM.json"
EXPECTED_AUTHORIZATION_ID = "g2.monitoring-source-onboarding@1"
EXPECTED_SLICE_ID = "g2.monitoring-source-onboarding@1"
EXPECTED_RULE = "every_changed_path_must_match_canonical_base_policy"
EXPECTED_SEMANTIC_RULE = "candidate_executable_artifacts_must_not_introduce_forbidden_g3_or_parallel_monitoring_authority"
EXPECTED_ATTESTATION_COMMAND = "/jlmirror-g2-scope-attest"
EXPECTED_READINESS_COMMAND = "/jlmirror-g2-scope-ready"
EXPECTED_STATUS_CONTEXT = "JLMIRROR / g2-monitoring-source-onboarding-implementation-scope"
EXPECTED_READY_CONTEXT = "JLMIRROR / g2-monitoring-source-onboarding-merge-readiness"
EXPECTED_READINESS_VALIDATOR = "tools/assurance/validate_g2_monitoring_source_onboarding_scope_readiness.py"
EXPECTED_RUNTIME_WORKFLOW = ".github/workflows/g2-monitoring-source-onboarding-runtime.yml"
EXPECTED_RUNTIME_NAME = "JLMIRROR G2 Monitoring Source Onboarding Runtime"
EXPECTED_RUNTIME_ENTRYPOINT = "python tools/g2/run_monitoring_source_onboarding_runtime.py"
EXPECTED_PREFIXES = (
    "apps/g2-monitoring-source-onboarding/",
    "contracts/g2-monitoring-source-onboarding/",
    "implementation/g2-monitoring-source-onboarding/",
    "tests/g2/",
    "tools/g2/",
)
EXPECTED_EXACT = (EXPECTED_RUNTIME_WORKFLOW,)
EXPECTED_FORBIDDEN_PATH_TOKENS = (
    "inventory", "monitoring-resource", "monitoring_resource", "metric", "problem",
    "health", "alert", "replacement", "cutover",
)
EXPECTED_FORBIDDEN_CODE_MARKERS = (
    "monitoring_resource", "resource_inventory", "metric_definition", "metric_current_state",
    "metric_observation", "problem_state", "health_projection", "alert_policy", "alerting.",
    "replacement_candidate", "replace_source_instance", "candidate_generation",
    "create table monitoring.", "create schema monitoring", "src/jlmirror_monitoring", "sql/wave4",
)
EXPECTED_SEMANTIC_SCAN_PREFIXES = (
    "apps/g2-monitoring-source-onboarding/",
    "contracts/g2-monitoring-source-onboarding/",
    "implementation/g2-monitoring-source-onboarding/",
    "tests/g2/",
    "tools/g2/",
)
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
    if data.get("implementation_authority_after_merge") != "granted_for_exact_g2_monitoring_source_onboarding_only":
        raise AssertionError("canonical base does not grant exact G2 implementation authority")
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
        raise AssertionError("G2 implementation claim must be a JSON object")
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
        (policy.get("trusted_scope_status_evidence_role") == "evidence_only_not_standalone_merge_authority", "trusted scope evidence role drift"),
        (policy.get("trusted_scope_freshness_rule") == "merge_readiness_revalidates_live_head_base_default_tip_label_and_trusted_status_run_provenance", "trusted scope freshness rule drift"),
        (policy.get("trusted_scope_concurrency_rule") == "per_pr_cancel_in_progress", "trusted scope concurrency rule drift"),
        (policy.get("trusted_status_creator_login") == "github-actions[bot]", "trusted status creator login drift"),
        (policy.get("trusted_status_creator_id") == 41898282, "trusted status creator id drift"),
        (policy.get("same_repository_required") is True, "same-repository requirement drift"),
        (policy.get("implementation_pr_requires_trusted_scope_attestation_on_exact_head") is True, "trusted scope attestation requirement drift"),
        (policy.get("implementation_pr_requires_trusted_scope_readiness_on_exact_head_base") is True, "trusted scope readiness requirement drift"),
        (policy.get("candidate_controlled_relevance_inference") == "forbidden", "candidate relevance inference drift"),
        (tuple(policy.get("allowed_prefixes", [])) == EXPECTED_PREFIXES, "implementation allowed prefixes drift"),
        (tuple(policy.get("allowed_exact_paths", [])) == EXPECTED_EXACT, "implementation exact paths drift"),
        (policy.get("diff_enforcement_rule") == EXPECTED_RULE, "implementation diff enforcement rule drift"),
        (policy.get("semantic_guard_rule") == EXPECTED_SEMANTIC_RULE, "semantic guard rule drift"),
        (tuple(policy.get("forbidden_path_tokens", [])) == EXPECTED_FORBIDDEN_PATH_TOKENS, "forbidden path token set drift"),
        (tuple(policy.get("forbidden_code_markers", [])) == EXPECTED_FORBIDDEN_CODE_MARKERS, "forbidden code marker set drift"),
        (tuple(policy.get("semantic_scan_prefixes", [])) == EXPECTED_SEMANTIC_SCAN_PREFIXES, "semantic scan prefix set drift"),
    )
    for ok, message in checks:
        if not ok:
            raise AssertionError(message)


def validate_candidate_metadata(root: Path, head_sha: str, head_ref: str, labels: set[str], head_repo: str, base_repo: str, policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if head_repo != base_repo:
        errors.append("G2 implementation PR must originate from the canonical repository")
    if not head_ref.startswith(EXPECTED_HEAD_PREFIX):
        errors.append("G2 implementation PR missing required canonical head prefix")
    if EXPECTED_LABEL not in labels:
        errors.append("G2 implementation PR missing required canonical label")
    try:
        claim = claim_from_head(root, head_sha, policy["implementation_claim_path"])
    except (subprocess.CalledProcessError, json.JSONDecodeError, UnicodeDecodeError):
        errors.append("G2 implementation PR missing or malformed required claim")
    else:
        if type(claim.get("schema_version")) is not int or claim.get("schema_version") != 1:
            errors.append("G2 implementation claim schema_version drift")
        if claim.get("authorization_id") != EXPECTED_AUTHORIZATION_ID:
            errors.append("G2 implementation claim authorization_id drift")
        if claim.get("slice_id") != EXPECTED_SLICE_ID:
            errors.append("G2 implementation claim slice_id drift")
    return errors


def validate_paths(paths: list[str], policy: dict[str, Any]) -> list[str]:
    errors = [] if policy.get("diff_enforcement_rule") == EXPECTED_RULE else ["implementation diff enforcement rule drift"]
    errors.extend(f"unauthorized G2 implementation path: {path}" for path in paths if not matches_policy(path, policy))
    return errors


def _semantic_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def validate_semantic_artifact(path: str, text: str, policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not any(path.startswith(prefix) for prefix in policy.get("semantic_scan_prefixes", [])):
        return errors
    lowered_path = path.lower()
    normalized_path = _semantic_key(path)
    for token in policy.get("forbidden_path_tokens", []):
        if token.lower() in lowered_path or _semantic_key(token) in normalized_path:
            errors.append(f"forbidden G2 semantic path token '{token}' in {path}")
    lowered_text = text.lower()
    normalized_text = _semantic_key(text)
    for marker in policy.get("forbidden_code_markers", []):
        if marker.lower() in lowered_text or _semantic_key(marker) in normalized_text:
            errors.append(f"forbidden G2 semantic code marker '{marker}' in {path}")
    return errors


def validate_candidate_semantics(root: Path, head_sha: str, paths: list[str], policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for path in paths:
        if not any(path.startswith(prefix) for prefix in policy.get("semantic_scan_prefixes", [])):
            continue
        try:
            text = git_bytes(root, "show", f"{head_sha}:{path}").decode("utf-8")
        except (subprocess.CalledProcessError, UnicodeDecodeError):
            errors.append(f"G2 semantic-scanned artifact must exist as UTF-8 text: {path}")
            continue
        errors.extend(validate_semantic_artifact(path, text, policy))
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
    if not isinstance(jobs, dict) or set(jobs) != {"g2-runtime"}:
        errors.append("runtime workflow job set drift")
        return errors
    job = jobs.get("g2-runtime")
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
        return ["allowed G2 runtime workflow path must exist as UTF-8 text on candidate head"]
    return validate_runtime_workflow_text(text)


def validate(base_sha: str, head_sha: str, head_ref: str, labels: set[str], head_repo: str, base_repo: str, *, root: Path = DEFAULT_ROOT) -> tuple[bool, list[str]]:
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
            errors.append("attested G2 implementation PR has no changed paths")
        else:
            errors.extend(validate_paths(paths, policy))
            errors.extend(validate_candidate_semantics(root, head_sha, paths, policy))
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
        print(f"G2_IMPLEMENTATION_SCOPE_ERROR: invalid labels metadata: {exc}", file=sys.stderr)
        return 1
    _classified, errors = validate(args.base, args.head, args.head_ref, labels, args.head_repo, args.base_repo, root=args.repo_root)
    for error in errors:
        print(f"G2_IMPLEMENTATION_SCOPE_ERROR: {error}", file=sys.stderr)
    if errors:
        return 1
    print("g2_implementation_scope=PASS classification=trusted_explicit_attestation path_scope=allowlisted semantic_scope=all-utf8-authorized-prefixes readiness=live-source-authenticated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
