#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "assurance"))
import validate_g1_identity_tenant_shell_implementation_scope as scope

POLICY = {
    "allowed_prefixes": [
        "apps/g1-identity-tenant-shell/",
        "contracts/g1-identity-tenant-shell/",
        "implementation/g1-identity-tenant-shell/",
        "sql/g1/",
        "src/jlmirror_g1/",
        "tests/g1/",
        "tools/g1/",
    ],
    "allowed_exact_paths": [scope.EXPECTED_RUNTIME_WORKFLOW],
    "implementation_pr_head_prefix": scope.EXPECTED_HEAD_PREFIX,
    "implementation_pr_required_label": scope.EXPECTED_LABEL,
    "implementation_claim_path": scope.EXPECTED_CLAIM_PATH,
    "implementation_claim_authorization_id": scope.EXPECTED_AUTHORIZATION_ID,
    "same_repository_required": True,
    "implementation_pr_base_ref_policy": "must_equal_repository_default_branch",
    "diff_enforcement_rule": scope.EXPECTED_RULE,
    "diff_policy_source": "pull_request_exact_base_commit",
    "trusted_evaluator_event": "issue_comment",
    "trusted_scope_attestation_command": scope.EXPECTED_ATTESTATION_COMMAND,
    "trusted_scope_readiness_command": scope.EXPECTED_READINESS_COMMAND,
    "trusted_evaluator_source": "default_branch_issue_comment_workflow_plus_exact_default_branch_base_git_object",
    "trusted_scope_status_context": scope.EXPECTED_STATUS_CONTEXT,
    "trusted_scope_readiness_status_context": scope.EXPECTED_READY_CONTEXT,
    "trusted_scope_status_publication": "pending_then_final_coordinate_bound_evidence_on_resolved_pr_head",
    "trusted_scope_status_evidence_role": "evidence_only_not_standalone_merge_authority",
    "trusted_scope_freshness_rule": "merge_readiness_revalidates_live_head_base_default_tip_label_and_trusted_status_run_provenance",
    "trusted_scope_concurrency_rule": "per_pr_cancel_in_progress",
    "trusted_status_creator_login": "github-actions[bot]",
    "trusted_status_creator_id": 41898282,
    "trusted_scope_merge_preflight_rule": "live_revalidate_ready_evidence_current_coordinates_label_and_workflow_run_immediately_before_merge",
    "trusted_scope_readiness_validator": scope.EXPECTED_READINESS_VALIDATOR,
    "implementation_pr_requires_trusted_scope_attestation_on_exact_head": True,
    "implementation_pr_requires_trusted_scope_readiness_on_exact_head_base": True,
    "candidate_controlled_relevance_inference": "forbidden",
}
REPO = "SupportingBasesOfficial/ProjectJLMirror"
SAFE_RUNTIME_WORKFLOW = """name: JLMIRROR G1 Identity Tenant Shell Runtime

on:
  pull_request:
  workflow_dispatch:

permissions: {}

jobs:
  g1-runtime:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@1111111111111111111111111111111111111111
      - uses: actions/setup-python@2222222222222222222222222222222222222222
      - uses: actions/setup-node@3333333333333333333333333333333333333333
      - run: python tools/g1/run_identity_tenant_shell_runtime.py
"""


def run_git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def write(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_repo() -> tuple[tempfile.TemporaryDirectory[str], Path, str]:
    td = tempfile.TemporaryDirectory()
    root = Path(td.name)
    subprocess.check_call(["git", "init", "-b", "main", str(root)], stdout=subprocess.DEVNULL)
    run_git(root, "config", "user.email", "g1-test@example.invalid")
    run_git(root, "config", "user.name", "G1 Scope Test")
    manifest = {
        "implementation_authority_after_merge": "granted_for_exact_g1_identity_tenant_protected_shell_only",
        "implementation_path_policy": POLICY,
    }
    write(root, scope.AUTHORIZATION_MANIFEST, json.dumps(manifest))
    run_git(root, "add", ".")
    run_git(root, "commit", "-m", "base")
    return td, root, run_git(root, "rev-parse", "HEAD")


def write_claim(root: Path) -> None:
    write(
        root,
        scope.EXPECTED_CLAIM_PATH,
        json.dumps({
            "schema_version": 1,
            "authorization_id": scope.EXPECTED_AUTHORIZATION_ID,
            "slice_id": scope.EXPECTED_SLICE_ID,
        }),
    )


def commit_head(root: Path, message: str = "head") -> str:
    run_git(root, "add", ".")
    run_git(root, "commit", "-m", message)
    return run_git(root, "rev-parse", "HEAD")


def must_reject(paths: list[str], fragment: str) -> None:
    errors = scope.validate_paths(paths, POLICY)
    if not any(fragment in error for error in errors):
        raise AssertionError(f"expected rejection containing {fragment!r}, got {errors!r}")


def falsify_shared_core_mutation() -> None:
    for path in (
        "src/jlmirror_authority/session.py",
        "docs/09-api-contracts/authentication-authorization-and-tenant-context.md",
        "implementation/g1-identity-tenant-shell-authorization/AUTHORIZATION_MANIFEST.json",
    ):
        must_reject([path], "unauthorized G1 implementation path")


def falsify_mixed_diff_escape() -> None:
    errors = scope.validate_paths(
        ["src/jlmirror_g1/session_bridge.py", "tests/g1/test_shell.py", "src/jlmirror_authority/session.py"],
        POLICY,
    )
    assert errors == ["unauthorized G1 implementation path: src/jlmirror_authority/session.py"]


def falsify_policy_rule_weakening() -> None:
    weakened = dict(POLICY)
    weakened["diff_enforcement_rule"] = "implementation_pr_declares_its_own_paths"
    assert "implementation diff enforcement rule drift" in scope.validate_paths(["src/jlmirror_g1/shell.py"], weakened)


def falsify_real_git_diff_gate() -> None:
    td, root, base = make_repo()
    try:
        write_claim(root)
        write(root, "src/jlmirror_g1/shell.py", "allowed\n")
        write(root, "src/jlmirror_authority/session.py", "forbidden\n")
        head = commit_head(root, "mixed")
        classified, errors = scope.validate(
            base,
            head,
            scope.EXPECTED_HEAD_PREFIX + "/slice",
            {scope.EXPECTED_LABEL},
            REPO,
            REPO,
            root=root,
        )
        assert classified
        assert "unauthorized G1 implementation path: src/jlmirror_authority/session.py" in errors
        changed = scope.changed_paths(root, base, head)
        assert "src/jlmirror_g1/shell.py" in changed
        assert "src/jlmirror_authority/session.py" in changed
    finally:
        td.cleanup()


def falsify_candidate_metadata_fail_closed() -> None:
    td, root, base = make_repo()
    try:
        write_claim(root)
        write(root, "src/jlmirror_g1/shell.py", "allowed\n")
        head = commit_head(root, "candidate")

        classified, errors = scope.validate(base, head, "feature/not-canonical-g1", {scope.EXPECTED_LABEL}, REPO, REPO, root=root)
        assert classified and "G1 implementation PR missing required canonical head prefix" in errors

        classified, errors = scope.validate(base, head, scope.EXPECTED_HEAD_PREFIX + "/slice", set(), REPO, REPO, root=root)
        assert classified and "G1 implementation PR missing required canonical label" in errors

        run_git(root, "rm", scope.EXPECTED_CLAIM_PATH)
        head_without_claim = commit_head(root, "missing-claim")
        classified, errors = scope.validate(
            base,
            head_without_claim,
            scope.EXPECTED_HEAD_PREFIX + "/slice",
            {scope.EXPECTED_LABEL},
            REPO,
            REPO,
            root=root,
        )
        assert classified and any("missing or malformed required claim" in error for error in errors)
    finally:
        td.cleanup()


def falsify_all_voluntary_metadata_omission() -> None:
    td, root, base = make_repo()
    try:
        write(root, "src/jlmirror_authority/session.py", "forbidden-hidden-g1\n")
        head = commit_head(root, "hidden-g1-shared-core-only")
        classified, errors = scope.validate(
            base,
            head,
            "feature/not-canonical-g1",
            set(),
            REPO,
            REPO,
            root=root,
        )
        assert classified
        assert "G1 implementation PR missing required canonical head prefix" in errors
        assert "G1 implementation PR missing required canonical label" in errors
        assert "G1 implementation PR missing or malformed required claim" in errors
        assert "unauthorized G1 implementation path: src/jlmirror_authority/session.py" in errors
    finally:
        td.cleanup()


def falsify_runtime_workflow_semantics() -> None:
    td, root, base = make_repo()
    try:
        write_claim(root)
        unsafe = SAFE_RUNTIME_WORKFLOW.replace("  pull_request:\n", "  pull_request_target:\n").replace("permissions: {}", "permissions:\n  contents: write\n  statuses: write")
        write(root, scope.EXPECTED_RUNTIME_WORKFLOW, unsafe)
        head = commit_head(root, "unsafe-runtime-workflow")
        classified, errors = scope.validate(
            base,
            head,
            scope.EXPECTED_HEAD_PREFIX + "/slice",
            {scope.EXPECTED_LABEL},
            REPO,
            REPO,
            root=root,
        )
        assert classified
        assert any("trigger set drift" in error or "forbidden authority/capability marker: pull_request_target:" in error for error in errors), errors
        assert any("zero-permission declaration" in error or "contents: write" in error for error in errors), errors

        direct_errors = scope.validate_runtime_workflow_text(SAFE_RUNTIME_WORKFLOW.replace(scope.EXPECTED_RUNTIME_ENTRYPOINT, "kubectl apply -f prod.yml"))
        assert any("executable responsibility drift" in error or "kubectl" in error for error in direct_errors), direct_errors
    finally:
        td.cleanup()


def prove_allowed_paths() -> None:
    td, root, base = make_repo()
    try:
        write_claim(root)
        write(root, "apps/g1-identity-tenant-shell/frontend/index.html", "ok\n")
        write(root, "src/jlmirror_g1/app.py", "ok\n")
        write(root, "tools/g1/run_identity_tenant_shell_runtime.py", "print('g1 runtime proof')\n")
        write(root, scope.EXPECTED_RUNTIME_WORKFLOW, SAFE_RUNTIME_WORKFLOW)
        head = commit_head(root, "allowed")
        classified, errors = scope.validate(
            base,
            head,
            scope.EXPECTED_HEAD_PREFIX + "/slice",
            {scope.EXPECTED_LABEL},
            REPO,
            REPO,
            root=root,
        )
        assert classified and not errors, errors
    finally:
        td.cleanup()


def main() -> int:
    prove_allowed_paths()
    falsify_shared_core_mutation()
    falsify_mixed_diff_escape()
    falsify_policy_rule_weakening()
    falsify_real_git_diff_gate()
    falsify_candidate_metadata_fail_closed()
    falsify_all_voluntary_metadata_omission()
    falsify_runtime_workflow_semantics()
    print("g1_implementation_scope_falsification=PASS shared_core=blocked mixed_diff=blocked real_git_diff=executed metadata=label+branch+claim_fail_closed all_metadata_omission=blocked runtime_workflow=semantic-authority-bounded explicit_trusted_classification=required default_base_policy=required exact_head_status=evidence-only live_readiness=required allowed_paths=accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())