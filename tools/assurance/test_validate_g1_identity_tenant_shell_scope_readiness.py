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
RUN_ID = 123456789
SERVER = "https://github.com"


def must_reject(fn, fragment: str) -> None:
    try:
        fn()
    except AssertionError as exc:
        if fragment not in str(exc):
            raise AssertionError(f"expected {fragment!r}, got {exc!r}")
        return
    raise AssertionError(f"readiness mutation unexpectedly accepted: {fragment}")


def fixtures() -> tuple[dict, dict, list[dict], dict]:
    pr = {
        "state": "open",
        "base": {"ref": DEFAULT_BRANCH, "sha": BASE, "repo": {"full_name": REPO}},
        "head": {"ref": "impl/g1-identity-tenant-protected-shell-demo", "sha": HEAD, "repo": {"full_name": REPO}},
        "labels": [{"name": readiness.REQUIRED_LABEL}],
    }
    branch = {"commit": {"sha": BASE}}
    statuses = [{
        "context": readiness.SCOPE_CONTEXT,
        "state": "success",
        "description": f"G1 scope PASS base={BASE} head={HEAD}",
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
    return pr, branch, statuses, run


def validate(pr: dict, branch: dict, statuses: list[dict], run: dict) -> None:
    readiness.validate_live_readiness(
        pr=pr,
        branch=branch,
        statuses=statuses,
        run=run,
        repo=REPO,
        default_branch=DEFAULT_BRANCH,
        server_url=SERVER,
    )


def falsify_live_readiness_guards() -> None:
    pr, branch, statuses, run = fixtures()
    validate(pr, branch, statuses, run)

    spoof = copy.deepcopy(statuses)
    spoof[0]["creator"] = {"login": "contributor", "id": 999}
    must_reject(lambda: validate(pr, branch, spoof, run), "no trusted G1 scope attestation status")

    stale_base = copy.deepcopy(statuses)
    stale_base[0]["description"] = f"G1 scope PASS base={'c' * 40} head={HEAD}"
    must_reject(lambda: validate(pr, branch, stale_base, run), "coordinates are stale or malformed")

    stale_tip = copy.deepcopy(branch)
    stale_tip["commit"]["sha"] = "d" * 40
    must_reject(lambda: validate(pr, stale_tip, statuses, run), "base SHA is not the current default-branch tip")

    missing_label = copy.deepcopy(pr)
    missing_label["labels"] = []
    must_reject(lambda: validate(missing_label, branch, statuses, run), "missing current required canonical label")

    wrong_event = copy.deepcopy(run)
    wrong_event["event"] = "push"
    must_reject(lambda: validate(pr, branch, statuses, wrong_event), "event must be issue_comment")

    wrong_path = copy.deepcopy(run)
    wrong_path["path"] = ".github/workflows/other.yml"
    must_reject(lambda: validate(pr, branch, statuses, wrong_path), "workflow path drift")

    wrong_base_run = copy.deepcopy(run)
    wrong_base_run["head_sha"] = "e" * 40
    must_reject(lambda: validate(pr, branch, statuses, wrong_base_run), "run is not bound to the exact current base SHA")

    malformed_target = copy.deepcopy(statuses)
    malformed_target[0]["target_url"] = "https://example.invalid/run/123"
    must_reject(lambda: validate(pr, branch, malformed_target, run), "target_url is not a canonical workflow run")


def main() -> int:
    falsify_live_readiness_guards()
    print("g1_scope_readiness_falsification=PASS spoofed_status=blocked stale_base=blocked skip_ci_base_advance=blocked missing_label=blocked wrong_workflow_run=blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
