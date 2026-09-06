#!/usr/bin/env python3
from __future__ import annotations

import unittest

from cancel_stale_pr_runs import Context, execute, run_matches_pr, select_stale_runs


class CancelStalePrRunsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ctx = Context(
            repository="SupportingBasesOfficial/ProjectJLMirror",
            pr_number=85,
            head_sha="current-sha",
            head_branch="ci/example",
            current_run_id=999,
        )

    def run(self, **overrides):
        value = {
            "id": 100,
            "status": "in_progress",
            "event": "pull_request",
            "head_branch": "ci/example",
            "head_sha": "old-sha",
            "pull_requests": [{"number": 85}],
        }
        value.update(overrides)
        return value

    def test_accepts_only_active_stale_same_pr_run(self):
        self.assertTrue(run_matches_pr(self.run(), self.ctx))

    def test_current_sha_is_never_cancelled(self):
        self.assertFalse(run_matches_pr(self.run(head_sha="current-sha"), self.ctx))

    def test_current_controller_run_is_never_cancelled(self):
        self.assertFalse(run_matches_pr(self.run(id=999), self.ctx))

    def test_completed_run_is_never_cancelled(self):
        self.assertFalse(run_matches_pr(self.run(status="completed"), self.ctx))

    def test_other_branch_is_never_cancelled(self):
        self.assertFalse(run_matches_pr(self.run(head_branch="ci/other"), self.ctx))

    def test_other_pr_is_never_cancelled(self):
        self.assertFalse(run_matches_pr(self.run(pull_requests=[{"number": 84}]), self.ctx))

    def test_ambiguous_multi_pr_metadata_fails_closed(self):
        self.assertFalse(
            run_matches_pr(self.run(pull_requests=[{"number": 85}, {"number": 84}]), self.ctx)
        )

    def test_missing_pr_metadata_fails_closed(self):
        self.assertFalse(run_matches_pr(self.run(pull_requests=[]), self.ctx))

    def test_non_pull_request_event_is_never_cancelled(self):
        self.assertFalse(run_matches_pr(self.run(event="workflow_dispatch"), self.ctx))

    def test_select_stale_runs_is_sorted_and_bounded(self):
        runs = [
            self.run(id=300),
            self.run(id=200, status="queued"),
            self.run(id=400, head_sha="current-sha"),
        ]
        self.assertEqual(select_stale_runs(runs, self.ctx), [200, 300])

    def test_execute_dry_run_never_calls_canceller(self):
        cancelled = []

        def lister(**_kwargs):
            return [self.run(id=123)]

        def canceller(**kwargs):
            cancelled.append(kwargs["run_id"])

        result = execute(
            ctx=self.ctx,
            api_url="https://api.github.test",
            token="token",
            dry_run=True,
            lister=lister,
            canceller=canceller,
        )
        self.assertEqual(result, [123])
        self.assertEqual(cancelled, [])

    def test_execute_cancels_each_selected_stale_run(self):
        cancelled = []

        def lister(**_kwargs):
            return [self.run(id=321), self.run(id=123, status="queued")]

        def canceller(**kwargs):
            cancelled.append(kwargs["run_id"])

        result = execute(
            ctx=self.ctx,
            api_url="https://api.github.test",
            token="token",
            dry_run=False,
            lister=lister,
            canceller=canceller,
        )
        self.assertEqual(result, [123, 321])
        self.assertEqual(cancelled, [123, 321])


if __name__ == "__main__":
    unittest.main()
