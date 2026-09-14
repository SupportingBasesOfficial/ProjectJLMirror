#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Any

TRUSTED_CREATOR_LOGIN = "github-actions[bot]"
TRUSTED_CREATOR_ID = 41898282
REQUIRED_LABEL = "jlmirror-slice:g1-identity-tenant-shell"
SCOPE_CONTEXT = "JLMIRROR / g1-identity-tenant-shell-implementation-scope"
READY_CONTEXT = "JLMIRROR / g1-identity-tenant-shell-merge-readiness"
WORKFLOW_NAME = "JLMIRROR G1 Identity Tenant Shell Implementation Scope"
WORKFLOW_PATH = ".github/workflows/g1-identity-tenant-shell-implementation-scope.yml"


def req(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def api(endpoint: str) -> Any:
    return json.loads(subprocess.check_output(["gh", "api", endpoint], text=True))


def live_coordinates(pr: dict[str, Any], branch: dict[str, Any], *, repo: str, default_branch: str) -> tuple[str, str, str]:
    req(pr.get("state") == "open", "implementation PR must remain open")
    base = pr.get("base") or {}
    head = pr.get("head") or {}
    req(base.get("ref") == default_branch, "implementation PR base ref is not the current default branch")
    req((base.get("repo") or {}).get("full_name") == repo, "implementation PR base repository drift")
    req((head.get("repo") or {}).get("full_name") == repo, "implementation PR head repository drift")
    base_sha = base.get("sha")
    head_sha = head.get("sha")
    head_ref = head.get("ref")
    req(isinstance(base_sha, str) and len(base_sha) == 40, "implementation PR base SHA missing")
    req(isinstance(head_sha, str) and len(head_sha) == 40, "implementation PR head SHA missing")
    req(isinstance(head_ref, str) and head_ref, "implementation PR head ref missing")
    req(((branch.get("commit") or {}).get("sha")) == base_sha, "implementation PR base SHA is not the current default-branch tip")
    labels = {row.get("name") for row in pr.get("labels", []) if isinstance(row, dict)}
    req(REQUIRED_LABEL in labels, "implementation PR missing current required canonical label")
    return base_sha, head_sha, head_ref


def evidence_contract(evidence: str, base_sha: str, head_sha: str) -> tuple[str, str, str]:
    if evidence == "scope":
        return SCOPE_CONTEXT, f"G1 scope PASS base={base_sha} head={head_sha}", "scope attestation"
    if evidence == "ready":
        return READY_CONTEXT, f"G1 ready PASS base={base_sha} head={head_sha}", "merge-readiness"
    raise AssertionError("unknown G1 trusted evidence kind")


def select_trusted_evidence(statuses: list[dict[str, Any]], *, evidence: str, repo: str, server_url: str, base_sha: str, head_sha: str) -> tuple[dict[str, Any], int]:
    context, expected_description, label = evidence_contract(evidence, base_sha, head_sha)
    trusted = [
        row for row in statuses
        if isinstance(row, dict)
        and row.get("context") == context
        and (row.get("creator") or {}).get("login") == TRUSTED_CREATOR_LOGIN
        and (row.get("creator") or {}).get("id") == TRUSTED_CREATOR_ID
    ]
    req(bool(trusted), f"no trusted G1 {label} status from canonical GitHub Actions publisher")
    trusted.sort(key=lambda row: str(row.get("created_at") or ""))
    status = trusted[-1]
    req(status.get("state") == "success", f"latest trusted G1 {label} is not successful")
    req(status.get("description") == expected_description, f"trusted G1 {label} coordinates are stale or malformed")
    target_url = status.get("target_url")
    prefix = f"{server_url.rstrip('/')}/{repo}/actions/runs/"
    req(isinstance(target_url, str) and target_url.startswith(prefix), f"trusted G1 {label} target_url is not a canonical workflow run")
    suffix = target_url[len(prefix):]
    req(bool(re.fullmatch(r"[1-9][0-9]*", suffix)), f"trusted G1 {label} target_url run id is malformed")
    return status, int(suffix)


def validate_workflow_run(run: dict[str, Any], *, run_id: int, repo: str, default_branch: str, base_sha: str) -> None:
    req(run.get("id") == run_id, "trusted G1 workflow run id drift")
    req(run.get("name") == WORKFLOW_NAME, "trusted G1 workflow name drift")
    req(run.get("path") == WORKFLOW_PATH, "trusted G1 workflow path drift")
    req(run.get("event") == "issue_comment", "trusted G1 workflow event must be issue_comment")
    req(run.get("status") == "completed" and run.get("conclusion") == "success", "trusted G1 workflow run is not completed successfully")
    req(run.get("head_branch") == default_branch, "trusted G1 workflow did not execute from the default branch")
    req(run.get("head_sha") == base_sha, "trusted G1 workflow run is not bound to the exact current base SHA")
    repository = run.get("repository") or {}
    req(repository.get("full_name") == repo, "trusted G1 workflow repository drift")


def validate_live_readiness(*, pr: dict[str, Any], branch: dict[str, Any], statuses: list[dict[str, Any]], run: dict[str, Any], repo: str, default_branch: str, server_url: str, evidence: str = "scope") -> tuple[str, str, int]:
    base_sha, head_sha, _head_ref = live_coordinates(pr, branch, repo=repo, default_branch=default_branch)
    _status, run_id = select_trusted_evidence(statuses, evidence=evidence, repo=repo, server_url=server_url, base_sha=base_sha, head_sha=head_sha)
    validate_workflow_run(run, run_id=run_id, repo=repo, default_branch=default_branch, base_sha=base_sha)
    return base_sha, head_sha, run_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--default-branch", required=True)
    parser.add_argument("--server-url", default=os.environ.get("GITHUB_SERVER_URL", "https://github.com"))
    parser.add_argument("--evidence", choices=("scope", "ready"), default="scope")
    args = parser.parse_args()
    try:
        pr = api(f"repos/{args.repo}/pulls/{args.pr_number}")
        branch = api(f"repos/{args.repo}/branches/{args.default_branch}")
        base_sha, head_sha, _ = live_coordinates(pr, branch, repo=args.repo, default_branch=args.default_branch)
        statuses = api(f"repos/{args.repo}/commits/{head_sha}/statuses?per_page=100")
        _status, run_id = select_trusted_evidence(statuses, evidence=args.evidence, repo=args.repo, server_url=args.server_url, base_sha=base_sha, head_sha=head_sha)
        run = api(f"repos/{args.repo}/actions/runs/{run_id}")
        validate_workflow_run(run, run_id=run_id, repo=args.repo, default_branch=args.default_branch, base_sha=base_sha)
    except (AssertionError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"G1_SCOPE_READINESS_ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"g1_scope_readiness=PASS evidence={args.evidence} base={base_sha} head={head_sha} trusted_creator={TRUSTED_CREATOR_LOGIN}:{TRUSTED_CREATOR_ID} run_id={run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
