# JLMIRROR Deterministic Assurance

**Profile:** `jlmirror-deterministic-assurance/v1`  
**Role:** observer-only deterministic evidence  
**Normative authority:** none — this tooling implements bounded checks under the accepted Review and Assurance Governance; it does not replace the Native Assurance Gate or merge authorization.

## Purpose

This directory contains repository-local checks that can be executed by GitHub Actions or locally without network access and without mutating repository state.

The intended progression is:

```text
commit / PR HEAD
  -> deterministic assurance
  -> PASS or findings
  -> deliberate correction if required
  -> new HEAD
  -> deterministic assurance re-runs
  -> Native Assurance / panoramic review
  -> READY_FOR_MERGE
  -> separate explicit merge authorization
```

A PASS means only that the exact analyzed state produced no finding in the implemented deterministic coverage set. It is not architectural proof, security proof, normative acceptance or merge authority.

## v1 checks

### Workflow privilege and supply-chain policy

For `.github/workflows/*.yml` and `.yaml`, v1 rejects:

- `permissions: write-all`;
- known GitHub workflow write permissions such as `contents: write`, `pull-requests: write`, `id-token: write` and similar, including inline permission maps;
- `pull_request_target` in this observer-only profile, including inline trigger syntax;
- GitHub `secrets.*` references or `secrets: inherit`;
- GitHub environment bindings that could introduce environment-scoped credentials/deployment authority;
- `continue-on-error: true`, because assurance failures must remain job-failing evidence;
- external step or reusable-workflow `uses:` dependencies not pinned to an immutable 40-hex commit SHA;
- Docker action references until a separately reviewed immutable-digest policy exists;
- `actions/checkout` without both `persist-credentials: false` and `allow-unsafe-pr-checkout: false`;
- obvious repository-mutation commands such as `git push`, `git commit`, PR mutation commands and HTTP/API write methods.

These checks are intentionally conservative. A future workflow that genuinely needs a narrow evidence-publication write permission must introduce and review that capability deliberately rather than silently weakening v1.

### Documentation integrity

v1 rejects:

- broken relative Markdown links;
- relative links that escape the repository root;
- unbalanced triple-backtick code fences.

### High-confidence secret material marker

v1 rejects PEM/OpenSSH private-key block markers in repository text files. This is a narrow deterministic guard and does not replace GitHub secret scanning or a dedicated secret scanner.

## Negative tests

`test_validate_repository.py` falsifies the current policy with explicit negative cases. The workflow runs these tests before scanning the repository.

## Exact-state evidence

The GitHub workflow checks out the pull-request HEAD SHA when running on `pull_request`, otherwise the triggering `github.sha`, and verifies that the checked-out commit equals the expected SHA before executing the validator.

The validator prints its profile identifier and Python runtime version. GitHub Actions logs additionally record the hosted-runner image/version and effective `GITHUB_TOKEN` permissions, allowing later evidence to distinguish a current run from stale or materially different execution context.

The workflow therefore produces evidence for a specific commit and execution profile, not for a branch name in the abstract.

## Observer-only boundary

The workflow is designed with:

```text
permissions:
  contents: read
```

It is intentionally secretless for pull-request analysis. It does not persist checkout credentials, bind a GitHub environment, upload fixes, push, commit, merge, create dependency-update PRs, resolve review threads, change normative status or enable auto-merge.

Changes to the workflow, validator, tests or their pinned action dependencies create a new repository HEAD and require ordinary review under repository governance.
