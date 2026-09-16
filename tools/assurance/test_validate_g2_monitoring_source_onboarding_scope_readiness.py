#!/usr/bin/env python3
from __future__ import annotations

import validate_g2_monitoring_source_onboarding_scope_readiness as validator

REPO = "SupportingBasesOfficial/ProjectJLMirror"
SERVER = "https://github.com"
DEFAULT = "main"
BASE = "a" * 40
HEAD = "b" * 40
HEAD_REF = "impl/g2-monitoring-source-onboarding-demo"
PR_NUMBER = 2002
RUN_ID = 424242


def fixtures(evidence: str = "scope"):
    repository = {"default_branch": DEFAULT}
    pr = {
        "state": "open",
        "base": {"ref": DEFAULT, "sha": BASE, "repo": {"full_name": REPO}},
        "head": {"ref": HEAD_REF, "sha": HEAD, "repo": {"full_name": REPO}},
        "labels": [{"name": validator.REQUIRED_LABEL}],
    }
    branch = {"commit": {"sha": BASE}}
    context, description, _label, mode = validator.evidence_contract(evidence, BASE, HEAD)
    statuses = [{
        "id": 100,
        "context": context,
        "state": "success",
        "description": description,
        "target_url": f"{SERVER}/{REPO}/actions/runs/{RUN_ID}",
        "created_at": "2026-09-15T00:00:00Z",
        "creator": {"login": validator.TRUSTED_CREATOR_LOGIN, "id": validator.TRUSTED_CREATOR_ID},
    }]
    run = {
        "id": RUN_ID,
        "name": validator.WORKFLOW_NAME,
        "path": validator.WORKFLOW_PATH,
        "event": "issue_comment",
        "status": "completed",
        "conclusion": "success",
        "head_branch": DEFAULT,
        "head_sha": BASE,
        "repository": {"full_name": REPO},
    }
    job_name = validator.expected_publisher_job_name(
        pr_number=PR_NUMBER, mode=mode, base_sha=BASE, head_sha=HEAD, head_ref=HEAD_REF
    )
    jobs = {"jobs": [{"name": job_name, "status": "completed", "conclusion": "success"}]}
    return repository, pr, branch, statuses, run, jobs


def must_reject(mutator, fragment: str, *, evidence: str = "scope") -> None:
    args = list(fixtures(evidence))
    mutator(*args)
    try:
        validator.validate_live_readiness(
            repository=args[0], pr=args[1], branch=args[2], statuses=args[3], run=args[4], jobs=args[5],
            repo=REPO, pr_number=PR_NUMBER, server_url=SERVER, evidence=evidence,
        )
    except AssertionError as exc:
        if fragment.lower() not in str(exc).lower():
            raise AssertionError(f"wrong failure for {fragment}: {exc}") from exc
        return
    raise AssertionError(f"mutation unexpectedly accepted: {fragment}")


def main() -> int:
    for evidence in ("scope", "ready"):
        validator.validate_live_readiness(
            repository=fixtures(evidence)[0], pr=fixtures(evidence)[1], branch=fixtures(evidence)[2],
            statuses=fixtures(evidence)[3], run=fixtures(evidence)[4], jobs=fixtures(evidence)[5],
            repo=REPO, pr_number=PR_NUMBER, server_url=SERVER, evidence=evidence,
        )

    must_reject(lambda r,p,b,s,run,j: p["labels"].clear(), "required canonical label")
    must_reject(lambda r,p,b,s,run,j: p["head"].update(ref="feature/not-g2"), "canonical G2 prefix")
    must_reject(lambda r,p,b,s,run,j: p["head"]["repo"].update(full_name="other/repo"), "head repository drift")
    must_reject(lambda r,p,b,s,run,j: b["commit"].update(sha="c" * 40), "current default-branch tip")
    must_reject(lambda r,p,b,s,run,j: s[0]["creator"].update(id=1), "no trusted G2")
    must_reject(lambda r,p,b,s,run,j: s[0].update(description="stale"), "coordinates are stale")
    must_reject(lambda r,p,b,s,run,j: s[0].update(target_url="https://example.invalid/run/1"), "target_url")
    must_reject(lambda r,p,b,s,run,j: s[0].pop("id"), "status id missing")
    must_reject(lambda r,p,b,s,run,j: run.update(event="pull_request"), "issue_comment")
    must_reject(lambda r,p,b,s,run,j: run.update(path=".github/workflows/other.yml"), "workflow path drift")
    must_reject(lambda r,p,b,s,run,j: run.update(head_sha="d" * 40), "exact current base SHA")
    must_reject(lambda r,p,b,s,run,j: j["jobs"][0].update(name="g2-publish-final spoof"), "exact publisher job identity")
    must_reject(lambda r,p,b,s,run,j: j["jobs"][0].update(conclusion="failure"), "publisher job is not completed successfully")

    def newer_pending_same_second(r,p,b,s,run,j):
        newer = dict(s[0])
        newer["id"] = 101
        newer["state"] = "pending"
        s.insert(0, newer)
    must_reject(newer_pending_same_second, "not successful")

    def duplicate_order_key(r,p,b,s,run,j):
        duplicate = dict(s[0])
        s.append(duplicate)
    must_reject(duplicate_order_key, "ordering is ambiguous")

    print("g2_scope_readiness_falsifier=PASS positive=2 negative=15")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
