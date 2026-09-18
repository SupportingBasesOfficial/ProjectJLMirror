#!/usr/bin/env python3
from __future__ import annotations

import copy
import validate_g8_human_operations_scope_readiness as validator

REPO = "SupportingBasesOfficial/ProjectJLMirror"
SERVER = "https://github.com"
BASE = "a" * 40
HEAD = "b" * 40
HEAD_REF = "impl/g8-human-operations-demo"
PR_NUMBER = 3003
RUN_ID = 434343


def fixtures(evidence: str):
    repository = {"default_branch": "main"}
    pr = {
        "state": "open",
        "base": {"ref": "main", "sha": BASE, "repo": {"full_name": REPO}},
        "head": {"ref": HEAD_REF, "sha": HEAD, "repo": {"full_name": REPO}},
        "labels": [{"name": validator.REQUIRED_LABEL}],
    }
    branch = {"commit": {"sha": BASE}}
    context, description, _label, mode = validator.evidence_contract(evidence, BASE, HEAD)
    statuses = [{
        "id": 101,
        "context": context,
        "state": "success",
        "description": description,
        "target_url": f"{SERVER}/{REPO}/actions/runs/{RUN_ID}",
        "created_at": "2026-09-18T00:00:00Z",
        "creator": {"login": validator.TRUSTED_CREATOR_LOGIN, "id": validator.TRUSTED_CREATOR_ID},
    }]
    run = {
        "id": RUN_ID,
        "name": validator.WORKFLOW_NAME,
        "path": validator.WORKFLOW_PATH,
        "event": "issue_comment",
        "status": "completed",
        "conclusion": "success",
        "head_branch": "main",
        "head_sha": BASE,
        "repository": {"full_name": REPO},
    }
    job_name = validator.expected_publisher_job_name(
        pr_number=PR_NUMBER, mode=mode, base_sha=BASE, head_sha=HEAD, head_ref=HEAD_REF
    )
    jobs = {"jobs": [{"name": job_name, "status": "completed", "conclusion": "success"}]}
    return [repository, pr, branch, statuses, run, jobs]


def validate(args, evidence: str):
    return validator.validate_live_readiness(
        repository=args[0],
        pr=args[1],
        branch=args[2],
        statuses=args[3],
        run=args[4],
        jobs=args[5],
        repo=REPO,
        pr_number=PR_NUMBER,
        server_url=SERVER,
        evidence=evidence,
    )


def reject(mutator, fragment: str, *, evidence: str = "scope"):
    args = copy.deepcopy(fixtures(evidence))
    mutator(args)
    try:
        validate(args, evidence)
    except AssertionError as exc:
        if fragment.lower() not in str(exc).lower():
            raise AssertionError(f"wrong readiness failure: expected={fragment!r} actual={exc!r}") from exc
        return
    raise AssertionError(f"readiness mutation unexpectedly accepted: {fragment}")


def main() -> int:
    validate(fixtures("scope"), "scope")
    validate(fixtures("ready"), "ready")

    reject(lambda a: a[1]["labels"].clear(), "required canonical label")
    reject(lambda a: a[1]["head"].update(ref="feature/not-g8"), "canonical G8 prefix")
    reject(lambda a: a[2]["commit"].update(sha="c" * 40), "default-branch tip")
    reject(lambda a: a[3][0]["creator"].update(id=999), "canonical GitHub Actions publisher")
    reject(lambda a: a[3][0].update(description="stale"), "coordinates are stale")
    reject(lambda a: a[4].update(path=".github/workflows/other.yml"), "workflow path drift")
    reject(lambda a: a[4].update(head_sha="d" * 40), "exact current base SHA")
    reject(lambda a: a[5]["jobs"][0].update(name="wrong publisher"), "exact publisher job identity")
    reject(lambda a: a[5]["jobs"][0].update(conclusion="failure"), "publisher job is not completed successfully")

    print("g8_scope_readiness_falsification=PASS live_coordinates=bound creator=bound workflow=bound publisher_job=bound")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
