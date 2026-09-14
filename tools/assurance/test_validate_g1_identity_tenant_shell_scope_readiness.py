#!/usr/bin/env python3
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "assurance"))
import validate_g1_identity_tenant_shell_scope_readiness as readiness

REPO = "SupportingBasesOfficial/ProjectJLMirror"
DEFAULT_BRANCH = "main"
BASE = "a" * 40
HEAD = "b" * 40
HEAD_REF = "impl/g1-identity-tenant-protected-shell-demo"
RUN_ID = 123456789
SERVER = "https://github.com"
PR_NUMBER = 1530


def must_reject(fn, fragment: str) -> None:
    try:
        fn()
    except AssertionError as exc:
        if fragment not in str(exc):
            raise AssertionError(f"expected {fragment!r}, got {exc!r}")
        return
    raise AssertionError(f"readiness mutation unexpectedly accepted: {fragment}")


def fixtures(evidence: str = "scope") -> tuple[dict, dict, dict, list[dict], dict, dict]:
    repository = {"default_branch": DEFAULT_BRANCH, "full_name": REPO}
    pr = {
        "state": "open",
        "base": {"ref": DEFAULT_BRANCH, "sha": BASE, "repo": {"full_name": REPO}},
        "head": {"ref": HEAD_REF, "sha": HEAD, "repo": {"full_name": REPO}},
        "labels": [{"name": readiness.REQUIRED_LABEL}],
    }
    branch = {"commit": {"sha": BASE}}
    context, description, _, mode = readiness.evidence_contract(evidence, BASE, HEAD)
    statuses = [{
        "context": context,
        "state": "success",
        "description": description,
        "target_url": f"{SERVER}/{REPO}/actions/runs/{RUN_ID}",
        "created_at": "2026-09-14T20:00:00Z",
        "creator": {"login": readiness.TRUSTED_CREATOR_LOGIN, "id": readiness.TRUSTED_CREATOR_ID},
    }]
    run = {
        "id": RUN_ID,
        "name": readiness.WORKFLOW_NAME,
        "path": readiness.WORKFLOW_PATH,
        "event": "issue_comment",
        "status": "completed",
        "conclusion": "success",
        "head_branch": DEFAULT_BRANCH,
        "head_sha": BASE,
        "repository": {"full_name": REPO},
    }
    jobs = {"jobs": [{
        "name": readiness.expected_publisher_job_name(
            pr_number=PR_NUMBER,
            mode=mode,
            base_sha=BASE,
            head_sha=HEAD,
            head_ref=HEAD_REF,
        ),
        "status": "completed",
        "conclusion": "success",
    }]}
    return repository, pr, branch, statuses, run, jobs


def validate(repository: dict, pr: dict, branch: dict, statuses: list[dict], run: dict, jobs: dict, *, evidence: str = "scope") -> None:
    readiness.validate_live_readiness(
        repository=repository,
        pr=pr,
        branch=branch,
        statuses=statuses,
        run=run,
        jobs=jobs,
        repo=REPO,
        pr_number=PR_NUMBER,
        server_url=SERVER,
        evidence=evidence,
    )


def falsify_live_readiness_guards() -> None:
    repository, pr, branch, statuses, run, jobs = fixtures("scope")
    validate(repository, pr, branch, statuses, run, jobs)

    ready_repository, ready_pr, ready_branch, ready_statuses, ready_run, ready_jobs = fixtures("ready")
    validate(ready_repository, ready_pr, ready_branch, ready_statuses, ready_run, ready_jobs, evidence="ready")

    spoof = copy.deepcopy(statuses)
    spoof[0]["creator"] = {"login": "contributor", "id": 999}
    must_reject(lambda: validate(repository, pr, branch, spoof, run, jobs), "no trusted G1 scope attestation status")

    spoof_bot_name_only = copy.deepcopy(statuses)
    spoof_bot_name_only[0]["creator"] = {"login": readiness.TRUSTED_CREATOR_LOGIN, "id": 999}
    must_reject(lambda: validate(repository, pr, branch, spoof_bot_name_only, run, jobs), "no trusted G1 scope attestation status")

    forged_same_bot_wrong_pr = copy.deepcopy(jobs)
    forged_same_bot_wrong_pr["jobs"][0]["name"] = readiness.expected_publisher_job_name(
        pr_number=9999,
        mode="attest",
        base_sha=BASE,
        head_sha=HEAD,
        head_ref=HEAD_REF,
    )
    must_reject(lambda: validate(repository, pr, branch, statuses, run, forged_same_bot_wrong_pr), "exact publisher job identity")

    forged_same_bot_wrong_mode = copy.deepcopy(jobs)
    forged_same_bot_wrong_mode["jobs"][0]["name"] = readiness.expected_publisher_job_name(
        pr_number=PR_NUMBER,
        mode="ready",
        base_sha=BASE,
        head_sha=HEAD,
        head_ref=HEAD_REF,
    )
    must_reject(lambda: validate(repository, pr, branch, statuses, run, forged_same_bot_wrong_mode), "exact publisher job identity")

    forged_same_bot_wrong_ref = copy.deepcopy(jobs)
    forged_same_bot_wrong_ref["jobs"][0]["name"] = readiness.expected_publisher_job_name(
        pr_number=PR_NUMBER,
        mode="attest",
        base_sha=BASE,
        head_sha=HEAD,
        head_ref="impl/g1-identity-tenant-protected-shell-other",
    )
    must_reject(lambda: validate(repository, pr, branch, statuses, run, forged_same_bot_wrong_ref), "exact publisher job identity")

    stale_base = copy.deepcopy(statuses)
    stale_base[0]["description"] = f"G1 scope PASS base={'c' * 40} head={HEAD}"
    must_reject(lambda: validate(repository, pr, branch, stale_base, run, jobs), "coordinates are stale or malformed")

    stale_tip = copy.deepcopy(branch)
    stale_tip["commit"]["sha"] = "d" * 40
    must_reject(lambda: validate(repository, pr, stale_tip, statuses, run, jobs), "base SHA is not the current default-branch tip")

    missing_label = copy.deepcopy(pr)
    missing_label["labels"] = []
    must_reject(lambda: validate(repository, missing_label, branch, statuses, run, jobs), "missing current required canonical label")

    renamed_head = copy.deepcopy(pr)
    renamed_head["head"]["ref"] = "feature/renamed"
    must_reject(lambda: validate(repository, renamed_head, branch, statuses, run, jobs), "head ref is not canonical G1 prefix")

    changed_default_branch = copy.deepcopy(repository)
    changed_default_branch["default_branch"] = "trunk"
    must_reject(lambda: validate(changed_default_branch, pr, branch, statuses, run, jobs), "base ref is not the current default branch")

    wrong_event = copy.deepcopy(run)
    wrong_event["event"] = "push"
    must_reject(lambda: validate(repository, pr, branch, statuses, wrong_event, jobs), "event must be issue_comment")

    wrong_path = copy.deepcopy(run)
    wrong_path["path"] = ".github/workflows/other.yml"
    must_reject(lambda: validate(repository, pr, branch, statuses, wrong_path, jobs), "workflow path drift")

    wrong_base_run = copy.deepcopy(run)
    wrong_base_run["head_sha"] = "e" * 40
    must_reject(lambda: validate(repository, pr, branch, statuses, wrong_base_run, jobs), "run is not bound to the exact current base SHA")

    failed_publisher = copy.deepcopy(jobs)
    failed_publisher["jobs"][0]["conclusion"] = "failure"
    must_reject(lambda: validate(repository, pr, branch, statuses, run, failed_publisher), "exact publisher job is not completed successfully")

    malformed_target = copy.deepcopy(statuses)
    malformed_target[0]["target_url"] = "https://example.invalid/run/123"
    must_reject(lambda: validate(repository, pr, branch, malformed_target, run, jobs), "target_url is not a canonical workflow run")

    untrusted_newer = copy.deepcopy(statuses)
    untrusted_newer.append({
        "context": readiness.SCOPE_CONTEXT,
        "state": "success",
        "description": f"G1 scope PASS base={BASE} head={HEAD}",
        "target_url": f"{SERVER}/{REPO}/actions/runs/999999999",
        "created_at": "2026-09-14T21:00:00Z",
        "creator": {"login": "contributor", "id": 999},
    })
    validate(repository, pr, branch, untrusted_newer, run, jobs)


def main() -> int:
    falsify_live_readiness_guards()
    print("g1_scope_readiness_falsification=PASS spoofed_status=blocked exact_publisher_job=pr+mode+base+head+ref live_default_branch=required head_ref=required stale_base=blocked missing_label=blocked wrong_workflow_run=blocked ready_evidence=source_authenticated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
