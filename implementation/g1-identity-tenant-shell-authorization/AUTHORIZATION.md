# G1 Identity + Tenant + Protected Shell — Implementation Authorization

**Status:** proposed exact-scope authorization  
**Canonical base:** `main@7c20c9301711e9a4bf355517d7aa23faad7a05b7`  
**Authorization ID:** `g1.identity-tenant-protected-shell@1`

## Purpose

This is the separate implementation-authorization gate required before canonical Product code may begin for the first full-stack JLMirror slice.

It does not implement G1. It authorizes only the bounded product path needed to expose already accepted Identity/BFF/current-authorization semantics through a real backend/BFF/frontend shell, together with the minimum G0 bootstrap required to run and prove that slice.

## Authorization on acceptance

If this exact package is reviewed, accepted and separately merged, canonical implementation may begin for exactly one vertical slice:

- `g1.identity-tenant-protected-shell@1`.

The machine-readable transition is exact:

```text
implementation_authority_before_merge = blocked
implementation_authority_after_merge = granted_for_exact_g1_identity_tenant_protected_shell_only
```

`merge_authorization = not_granted` remains separate from implementation authority. This proposal does not authorize its own merge.

The observable outcome is an authenticated user entering a tenant-scoped JLMirror application shell while the BFF establishes current platform authorization independently of token validity and forbidden/cross-tenant context fails closed.

## Implementation path authority

Post-merge G1 implementation authority is constrained to the following exact path policy. The implementation PR does not get to choose or broaden its own repository boundary.

Allowed prefixes:

- `apps/g1-identity-tenant-shell/`;
- `contracts/g1-identity-tenant-shell/`;
- `implementation/g1-identity-tenant-shell/`;
- `sql/g1/`;
- `src/jlmirror_g1/`;
- `tests/g1/`;
- `tools/g1/`.

Allowed exact path:

- `.github/workflows/g1-identity-tenant-shell-runtime.yml`.

All existing shared paths, including `src/jlmirror_authority/**`, accepted Wave 1–3 substrate, shared governance, shared runtime and unrelated contracts, are read-only under this authorization. If G1 cannot be completed without modifying shared existing substrate or any path outside the policy above, implementation MUST stop and obtain a separate successor authorization.

A PR may exercise this G1 implementation authority only when all of the following are simultaneously true:

- its head branch starts with `impl/g1-identity-tenant-protected-shell`;
- the GitHub PR carries `jlmirror-slice:g1-identity-tenant-shell`;
- its head contains `implementation/g1-identity-tenant-shell/IMPLEMENTATION_CLAIM.json` with exact schema/version, authorization ID and slice ID;
- head and base belong to the same canonical repository;
- the PR base ref equals the repository current default branch;
- the PR base SHA equals the current default-branch tip at the time of trusted verification;
- the exact candidate HEAD has trusted scope evidence under `JLMIRROR / g1-identity-tenant-shell-implementation-scope`;
- immediately before merge readiness is considered, the exact current HEAD/base also passes the live source-authenticated readiness command and evidence contract described below.

## Trusted scope attestation and live readiness

The authoritative caller is `.github/workflows/g1-identity-tenant-shell-implementation-scope.yml` using only the `issue_comment` event. `issue_comment` workflows are loaded from the repository default branch, so a candidate implementation PR cannot replace or skip the authoritative caller by editing its own workflow copy.

There are two canonical commands:

```text
/jlmirror-g1-scope-attest
/jlmirror-g1-scope-ready
```

`/jlmirror-g1-scope-attest` performs the bounded implementation-scope proof. The trusted default-branch workflow:

1. resolves the PR number, current default branch and current default-branch tip through trusted GitHub event/API state;
2. re-reads exact base SHA, exact head SHA, base/head refs, repositories and labels;
3. requires the PR base ref to equal the current default branch, base/head repositories to equal the canonical repository, the PR base SHA to equal the current default-branch tip, and the required label to be present now;
4. publishes `pending` on the exact resolved PR HEAD under `JLMIRROR / g1-identity-tenant-shell-implementation-scope`;
5. checks out only the trusted default branch and fetches the candidate commits as Git objects/data;
6. materializes `tools/assurance/validate_g1_identity_tenant_shell_implementation_scope.py` from the exact current base commit;
7. executes only that base-owned validator against the exact `base...head` diff with rename detection disabled;
8. requires branch, label, claim, same-repository rule and complete path allowlist;
9. re-reads current HEAD, base SHA, base ref, current default-branch tip and current labels before final publication;
10. publishes success only when those live coordinates and mutable authority metadata remain valid, using the coordinate-bound description `G1 scope PASS base=<base_sha> head=<head_sha>`.

The resulting scope status is **evidence only**. A green status by itself is not merge authority and is not sufficient to establish current readiness.

`/jlmirror-g1-scope-ready` is the second trusted gate. It exists specifically so readiness does not depend on a skippable `push` workflow or on persistence of an old green status. The default-branch caller materializes `tools/assurance/validate_g1_identity_tenant_shell_scope_readiness.py` from the exact current base object and revalidates live GitHub state. It requires all of the following at verification time:

- PR remains open;
- base ref remains the repository default branch;
- base SHA equals the current default-branch tip, so a default-branch advance is detected even if the advancing commit used an Actions skip directive such as `[skip ci]`;
- head SHA remains the exact candidate being considered;
- required `jlmirror-slice:g1-identity-tenant-shell` label is still present;
- latest trusted scope evidence is `success` and encodes the same exact base/head coordinates;
- the evidence creator is exactly `github-actions[bot]` with GitHub user ID `41898282`;
- the evidence `target_url` points to a real GitHub Actions run in this repository;
- that run is the canonical `JLMIRROR G1 Identity Tenant Shell Implementation Scope` workflow at `.github/workflows/g1-identity-tenant-shell-implementation-scope.yml`;
- the run event is `issue_comment`, it completed successfully, its head branch is the current default branch, and its workflow head SHA equals the exact current base SHA.

If those checks pass, final readiness evidence is published under `JLMIRROR / g1-identity-tenant-shell-merge-readiness` with the exact description `G1 ready PASS base=<base_sha> head=<head_sha>`. The final publisher again re-reads current HEAD/base/default-tip/label before it may publish success.

Status-write authority is isolated from analysis/readiness verification: exactly two publisher jobs have `statuses: write`; they do not checkout or execute candidate code. Scope analysis and live readiness verification remain read-only. `pull_request_target` remains forbidden. Candidate-controlled `pull_request` orchestration is not authoritative.

A status with the right context but wrong creator, wrong creator ID, stale coordinates, noncanonical `target_url`, wrong workflow path/name/event, stale base SHA, removed label, changed HEAD or changed default-branch tip is not trusted evidence. A same-repository contributor cannot satisfy the readiness contract merely by publishing a look-alike green status.

There is no candidate-controlled `relevance=not-g1` success path and no authorization bootstrap exception. Invocation of the trusted default-branch attestation is the independent classifier. Once invoked, omission of branch, label, claim, repository identity or any path outside the allowlist fails closed, including a diff containing only forbidden shared-core changes.

## Merge-readiness and merge preflight rule

`/jlmirror-g1-scope-ready` MUST be run on the exact implementation PR state after scope attestation and after all ordinary exact-head CI/review gates are otherwise ready.

A previously successful readiness status is still evidence rather than authority. Immediately before any separately authorized merge, the same live readiness verifier MUST be executed/re-evaluated against current GitHub state and the exact ready evidence. The preflight must again prove current HEAD, current base SHA, current default-branch tip, current required label, trusted creator identity, coordinate-bound ready description, and the real canonical successful workflow run.

Therefore:

```text
GREEN_STATUS != CURRENT_READINESS
STATUS_CONTEXT != TRUSTED_PUBLISHER_PROVENANCE
OLD_SCOPE_PASS != CURRENT_BASE_VALIDATION
READY_EVIDENCE != MERGE_AUTHORIZATION
READY_FOR_MERGE != AUTHORIZED_TO_MERGE
```

This live preflight is what makes a default-branch advance, label removal or stale/spoofed status fail closed even when no automatic invalidation event ran.

## Allowed G0 bootstrap inside the G1 slice

G0 is not authorized as a speculative platform program. Only bootstrap required by the G1 slice may be introduced:

- one reproducible local dependency stack for G1;
- one database migration/bootstrap entrypoint needed by G1;
- one backend/BFF start entrypoint;
- one frontend start entrypoint;
- one fixture/test tenant and identity bootstrap;
- exact-head local/CI parity commands;
- container/runtime proof for components introduced by G1.

No shared foundation may be invented unless G1 consumes it immediately or an accepted architecture contract requires it.

## Accepted authority consumed

G1 SHALL reuse rather than redefine accepted Wave 1 identity/BFF/current-authorization substrate, accepted D3 Identity/Security mechanism dispositions, canonical API/BFF/security contracts, canonical tenant/current-authority rules, and the AI E2E delivery constitution/roadmap.

The following remain mechanically true:

```text
JWT_VALIDITY != CURRENT_AUTHORIZATION
IDP_IDENTITY != PLATFORM_MEMBERSHIP_AUTHORITY
WORKLOAD_IDENTITY != TENANT_BUSINESS_AUTHORITY
NETWORK_PRESENCE != TRUST
BROWSER_SESSION_HANDLE != BUSINESS_AUTHORITY
CLIENT_TENANT_ID != TENANT_AUTHORITY
```

## Product surface authorized

The later implementation slice may add only what is needed for OIDC Authorization Code + PKCE S256 through the confidential BFF, opaque server-side BFF session capability, current tenant admission, current membership/permission read, authenticated shell routes, protected application shell states, browser E2E for allowed/forbidden cross-tenant paths, and adversarial stale/revoked-authority proof.

## Explicit non-authority

This gate does **not** authorize G2 Monitoring Source onboarding, Monitoring UI, Resource/Metric/Problem/Health product surfaces, Alerting policy/lifecycle, ACK/notification/escalation, ITSM, Automation, AIOps, FinOps, Commercial behavior, production deployment, production C3 numerics, provider-native authorization truth, browser refresh tokens/long-lived platform credentials, client-supplied tenant identity as authority, or speculative generic frontend information architecture.

## Historical authority rule

Earlier D3/D4 records that state canonical Product implementation authority was not granted remain immutable source-time truth. This successor authorization, if accepted, authorizes only this exact G1 slice and does not rewrite those historical snapshots.

```text
HISTORICAL_NOT_GRANTED != CURRENT_AUTHORIZATION_REGRESSION
SUCCESSOR_G1_AUTHORIZATION != GLOBAL_PRODUCT_AUTHORITY
G1_AUTHORIZED != G2_AUTHORIZED
G1_AUTHORIZED != PRODUCTION_AUTHORIZED
READY_FOR_MERGE != AUTHORIZED_TO_MERGE
```

## Merge boundary

This document remains a proposal until the exact PR HEAD passes dedicated authorization validation, deterministic assurance, panoramic/adversarial review and zero unresolved material findings, followed by separate explicit owner authorization for squash merge.
