#!/usr/bin/env python3
"""Cancel obsolete GitHub Actions runs for one pull request.

This helper deliberately operates only on workflow-run metadata. It never checks out or
executes pull-request code. A run is cancellable only when all of the following hold:
- it belongs to the same repository pull request;
- it is a pull_request event run on the same head branch;
- it is still active;
- its head SHA differs from the current pull-request head SHA; and
- it is not the currently executing controller run.

Unknown or incomplete run metadata fails closed and is skipped.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any, Callable, Iterable
from urllib import error, parse, request

ACTIVE_STATUSES = frozenset({"queued", "in_progress", "waiting", "pending", "requested"})


@dataclass(frozen=True)
class Context:
    repository: str
    pr_number: int
    head_sha: str
    head_branch: str
    current_run_id: int


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def _nonempty(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError("value must be non-empty")
    return value


def run_matches_pr(run: dict[str, Any], ctx: Context) -> bool:
    """Return True only for an active stale run conclusively owned by this PR."""
    try:
        run_id = int(run["id"])
        status = str(run["status"])
        event = str(run["event"])
        head_branch = str(run["head_branch"])
        head_sha = str(run["head_sha"])
        pull_requests = run["pull_requests"]
    except (KeyError, TypeError, ValueError):
        return False

    if run_id == ctx.current_run_id:
        return False
    if status not in ACTIVE_STATUSES:
        return False
    if event != "pull_request":
        return False
    if head_branch != ctx.head_branch:
        return False
    if head_sha == ctx.head_sha:
        return False
    if not isinstance(pull_requests, list) or not pull_requests:
        return False

    pr_numbers: set[int] = set()
    for item in pull_requests:
        if not isinstance(item, dict):
            return False
        try:
            pr_numbers.add(int(item["number"]))
        except (KeyError, TypeError, ValueError):
            return False
    return pr_numbers == {ctx.pr_number}


def select_stale_runs(runs: Iterable[dict[str, Any]], ctx: Context) -> list[int]:
    return sorted(int(run["id"]) for run in runs if run_matches_pr(run, ctx))


def _api_json(
    *,
    method: str,
    url: str,
    token: str,
    payload: bytes | None = None,
) -> tuple[int, dict[str, Any] | None]:
    req = request.Request(
        url,
        data=payload,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "jlmirror-stale-pr-run-controller",
        },
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            body = response.read()
            decoded = json.loads(body) if body else None
            return response.status, decoded
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {method} {url} failed: HTTP {exc.code}: {body}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"GitHub API {method} {url} failed: {exc.reason}") from exc


def list_candidate_runs(*, api_url: str, token: str, ctx: Context) -> list[dict[str, Any]]:
    all_runs: list[dict[str, Any]] = []
    page = 1
    encoded_branch = parse.quote(ctx.head_branch, safe="")
    while True:
        url = (
            f"{api_url}/repos/{ctx.repository}/actions/runs"
            f"?event=pull_request&branch={encoded_branch}&per_page=100&page={page}"
        )
        status, payload = _api_json(method="GET", url=url, token=token)
        if status != 200 or not isinstance(payload, dict):
            raise RuntimeError("unexpected workflow-runs response")
        runs = payload.get("workflow_runs")
        if not isinstance(runs, list):
            raise RuntimeError("workflow-runs response omitted workflow_runs list")
        all_runs.extend(run for run in runs if isinstance(run, dict))
        if len(runs) < 100:
            break
        page += 1
        if page > 100:
            raise RuntimeError("workflow-run pagination exceeded fail-closed safety ceiling")
    return all_runs


def cancel_run(*, api_url: str, token: str, repository: str, run_id: int) -> None:
    url = f"{api_url}/repos/{repository}/actions/runs/{run_id}/cancel"
    status, _ = _api_json(method="POST", url=url, token=token, payload=b"")
    if status not in {202, 409}:
        raise RuntimeError(f"unexpected cancel response for run {run_id}: HTTP {status}")


def execute(
    *,
    ctx: Context,
    api_url: str,
    token: str,
    dry_run: bool,
    lister: Callable[..., list[dict[str, Any]]] = list_candidate_runs,
    canceller: Callable[..., None] = cancel_run,
) -> list[int]:
    runs = lister(api_url=api_url, token=token, ctx=ctx)
    stale_ids = select_stale_runs(runs, ctx)
    for run_id in stale_ids:
        if not dry_run:
            canceller(api_url=api_url, token=token, repository=ctx.repository, run_id=run_id)
    return stale_ids


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True, type=_nonempty)
    parser.add_argument("--pr-number", required=True, type=_positive_int)
    parser.add_argument("--head-sha", required=True, type=_nonempty)
    parser.add_argument("--head-branch", required=True, type=_nonempty)
    parser.add_argument("--current-run-id", required=True, type=_positive_int)
    parser.add_argument("--api-url", required=True, type=_nonempty)
    parser.add_argument("--token", required=True, type=_nonempty)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ctx = Context(
        repository=args.repository,
        pr_number=args.pr_number,
        head_sha=args.head_sha,
        head_branch=args.head_branch,
        current_run_id=args.current_run_id,
    )
    stale_ids = execute(
        ctx=ctx,
        api_url=args.api_url.rstrip("/"),
        token=args.token,
        dry_run=args.dry_run,
    )
    print(json.dumps({"stale_run_ids": stale_ids, "count": len(stale_ids), "dry_run": args.dry_run}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - fail closed at the process boundary.
        print(f"stale_run_controller=FAIL error={exc}", file=sys.stderr)
        raise
