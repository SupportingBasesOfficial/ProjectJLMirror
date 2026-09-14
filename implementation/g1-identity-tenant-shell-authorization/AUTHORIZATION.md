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
- the exact candidate HEAD has a successful trusted scope attestation under the stable status context `JLMIRROR / g1-identity-tenant-shell-implementation-scope`.

## Trusted scope attestation

The authoritative implementation-scope caller is `.github/workflows/g1-identity-tenant-shell-implementation-scope.yml` using the `issue_comment` event. `issue_comment` workflows are loaded from the repository default branch, so a candidate implementation PR cannot replace or skip the caller by editing its own workflow copy.

The canonical command is:

```text
/jlmirror-g1-scope-attest
```

When this command is posted on the implementation PR by an authorized repository participant, the default-branch workflow:

1. resolves the PR number and current repository default branch from the trusted event/API;
2. reads exact base SHA, exact head SHA, base/head refs, repositories and labels from the GitHub API;
3. requires the PR base ref to equal the current default branch and requires base/head repositories to equal the canonical repository;
4. publishes `pending` on the exact resolved PR HEAD under `JLMIRROR / g1-identity-tenant-shell-implementation-scope`;
5. checks out only the trusted default branch and fetches the candidate commits as Git objects/data;
6. materializes `tools/assurance/validate_g1_identity_tenant_shell_implementation_scope.py` from the exact default-branch base commit with `git show`;
7. executes only that base-owned validator against the exact `base...head` diff with rename detection disabled;
8. requires branch, label, claim, same-repository rule and complete path allowlist on the explicitly attested PR;
9. re-reads current PR HEAD/base/ref before final publication and publishes `success` only when HEAD, base SHA and base ref remain unchanged and the base ref is still the default branch; otherwise it publishes failure/stale evidence to the resolved HEAD and requires a new attestation.

Status-write authority is isolated from the analysis job: the jobs that publish pending/final status do not checkout or execute candidate Python. The workflow uses per-PR concurrency with superseded-run cancellation so an older attestation cannot overwrite a newer result.

`pull_request_target` remains forbidden by repository v1 assurance. Candidate-controlled `pull_request` orchestration is not authoritative for the implementation-scope decision.

There is no candidate-controlled `relevance=not-g1` success path and no authorization bootstrap exception. Invocation of the trusted default-branch attestation is the independent classifier. Once invoked for an implementation PR, omission of branch, label, claim, repository identity or G1 paths fails closed, including a diff containing only forbidden shared-core changes.

The attestation is exact-head/exact-base evidence. If implementation PR HEAD, base SHA, or base ref changes after resolution, the previous evidence is stale and a new `/jlmirror-g1-scope-attest` run is required before merge readiness may be considered.

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
