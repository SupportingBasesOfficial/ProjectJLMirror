# Phase 14 — CI/CD Trust, Configuration and Secret Change Lifecycle

**Status:** proposed baseline

## CI/CD principal classes

Phase 14 defines logical release principals:

```text
principal.release-build@1
principal.release-publish@1
principal.release-promote@1
principal.release-deploy@1
principal.release-migrate@1
principal.release-verify@1
principal.release-emergency@1
```

One implementation may map several classes to one platform only when effective permissions remain independently bounded and auditable.

## Least privilege

- build principal cannot deploy production by default;
- publish principal can publish only artifact identities produced by accepted build authority;
- promotion principal cannot modify artifact bytes;
- deploy principal cannot forge promotion/provenance;
- migration principal is distinct from serving runtime and ordinary deploy authority where destructive privilege is needed;
- verification principal is read/observe oriented and cannot self-fix release state silently;
- emergency principal is bounded, exceptional and auditable.

## Configuration lifecycle

Configuration is released as a separately identified semantic/operational input, not baked into per-environment rebuilds.

A configuration change has:

- exact configuration identity/generation;
- owning authority;
- compatibility/security classification;
- target environment/runtime scope;
- validation evidence;
- promotion/deployment relationship;
- rollback/forward-recovery classification.

## Secret lifecycle

Artifacts and ordinary configuration contain secret references, not production secret values. Secret rotation/revocation is independently governed and does not require artifact rebuild unless artifact semantics truly change.

Release automation receives only scoped secret references/credentials needed by its stage. Logs/provenance/SBOM must not contain secret values.

## Configuration vs Product authority

Feature/config/environment state cannot resolve Product applicability or authorization merely because a release toggles a component. Product authority remains upstream.

## Pipeline resumption

A pipeline retry/resume revalidates current approval/principal/artifact/config/target authority. A stale paused job cannot continue because it once held permission.

## CI/CD self-modification

Pipeline/workflow definitions are source/build inputs subject to review and provenance. A release workflow cannot silently modify its own authority/policy and use the modified state in the same trust decision without independent acceptance.

## Evidence

Every privileged stage emits tamper-resistant/accountable evidence sufficient to reconstruct who/what acted on which immutable artifact/config/target and with what result, without recording credentials.