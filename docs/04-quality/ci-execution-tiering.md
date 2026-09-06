# CI execution efficiency and stale-run cancellation

## Purpose

JLMirror keeps exact-HEAD assurance as the acceptance boundary while preventing obsolete pull-request runs from consuming hosted-runner capacity after a newer commit supersedes them.

This document governs the first optimization layer only. It does not weaken, skip, or reclassify any architecture, evidence, conformance, recovery, provenance, or implementation-readiness gate.

## Canonical rule

For a pull request with current head SHA `H`, a workflow run may be cancelled automatically only when all of these conditions are conclusively true:

1. the run is a `pull_request` event run;
2. the run belongs exclusively to the same pull-request number;
3. the run is on the same pull-request head branch;
4. the run is still active (`queued`, `in_progress`, `waiting`, `pending`, or `requested`);
5. the run's `head_sha` differs from `H`; and
6. the run is not the currently executing stale-run controller.

Unknown, incomplete, ambiguous, cross-PR, cross-branch, current-HEAD, completed, or non-`pull_request` runs fail closed and are not cancelled.

## Security boundary

The cancellation job requires `actions: write`, therefore it MUST NOT execute code from the pull-request HEAD.

The operational job:

- does not checkout the pull-request branch;
- downloads `tools/ci/cancel_stale_pr_runs.py` from the immutable `pull_request.base.sha` through the GitHub Contents API;
- compiles that trusted base-revision script before execution;
- supplies only event metadata and the scoped `GITHUB_TOKEN`;
- grants no repository-content write permission.

A separate read-only job checks out the exact pull-request HEAD solely to compile and run the cancellation-policy unit tests. That job has `contents: read` only and no Actions mutation authority.

During the bootstrap PR that first introduces the trusted controller, the privileged job is expected to observe that the base revision does not yet contain the controller, emit `bootstrap_run=true`, and perform no cancellation. After merge, subsequent PRs execute the trusted controller from their base revision.

## Exact-HEAD invariants

This optimization changes runner scheduling only.

It does not change these JLMirror acceptance rules:

- a superseded SHA can never provide acceptance evidence for the current SHA;
- the current exact HEAD must still satisfy every workflow applicable to that HEAD;
- `ready_for_review` runs on the same SHA are not stale and are not cancelled merely because an earlier same-SHA run exists;
- final panoramic/adversarial review remains anchored to the exact accepted SHA;
- merge remains an explicit, separate user authorization.

## Follow-on optimization layers

After this stale-run controller is accepted, further CI optimization may be proposed in separate reviewed changes:

1. narrow `paths` for expensive live-evidence workflows so unrelated domain changes do not start infrastructure probes;
2. separate fast deterministic guards from deep live-evidence execution where the evidence contract permits that split;
3. use matrix parallelism only for genuinely independent suites;
4. keep stateful evidence that depends on a single coherent runtime/provenance chain in one evidence unit unless an equivalence proof justifies sharding;
5. evaluate self-hosted runners only after trigger and scheduling waste has been removed.

None of those later optimizations are granted by this document.
