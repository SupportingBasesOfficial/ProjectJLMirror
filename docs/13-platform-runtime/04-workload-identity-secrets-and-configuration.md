# Phase 13 — Workload Identity, Secrets and Configuration Contracts

**Status:** proposed baseline  
**Phase:** 13 — Platform & Runtime

## Purpose

This document defines machine/workload identity, secret-reference consumption and configuration-generation semantics for Phase 13 runtimes.

It preserves the accepted rule that identity authenticates a principal but does not by itself grant tenant/domain authority.

## Workload identity contract

Each protected runtime profile receives an authenticated machine principal with stable logical identity and replaceable credentials.

Conceptual fields/evidence:

```text
workload_profile_id
service_principal_id
runtime_class
cell/environment scope where applicable
credential_generation
issued_at / expires_at where mechanism supports it
revocation/currentness evidence
allowed capability classes
```

Exact credential protocol, issuer, certificate/token mechanism and workload-identity product remain OPEN.

## Identity rules

- credentials are independently revocable from the business entity/service code they authenticate;
- credentials are scoped to the minimum service/runtime capabilities required;
- ordinary runtime code SHALL NOT infer tenant authorization from service identity alone;
- a service principal from another cell/environment is not automatically trusted for the same capability;
- network namespace, node, host, cluster or private IP membership is not identity;
- a workload identity is not a user/session token and cannot impersonate human Product authority by default;
- principal/credential rotation does not require changing canonical API/event/resource identities.

## Bootstrap

A runtime bootstrap sequence establishes, in order:

1. runtime/profile identity from an accepted bootstrap trust root/mechanism;
2. current non-secret configuration and references;
3. access to only the secret/key references allowed by the runtime profile;
4. authoritative state-port connectivity using least-privilege identities;
5. placement/admission/configuration currentness required for serving;
6. Phase 12 observability identity and health registration.

A runtime that cannot establish required current identity/configuration/secret authority remains not-ready or quarantined according to the owning profile.

## Secret references

Ordinary source/configuration stores references such as a stable secret purpose/reference identity, never production secret values.

Reference rules:

- a reference does not grant read authority;
- the workload principal must be authorized for the reference class;
- secret values SHALL NOT be copied into domain events, job payloads, logs, traces, metric labels, audit snapshots or general configuration documents;
- secret rotation is independent of the business/provider/config entity that refers to it;
- runtime secret caches, if any, are bounded, protected, revocation-aware where required and non-authoritative;
- a missing/expired/revoked secret cannot be replaced by an older restored value merely because it is locally available.

## Secret and key authority classes

Phase 13 distinguishes at least:

- connector/provider credentials;
- application-to-state-port credentials;
- workload/service communication credentials;
- signing/verifier/key authority referenced by accepted API/event/security contracts;
- privileged migration/admin credentials;
- recovery-specific authority.

One broad secret principal with unrestricted access to all classes is prohibited as the normal platform pattern.

## Configuration classes

Configuration is separated into:

1. **Product/business authority** — owned upstream; runtime cannot choose it.
2. **semantic platform configuration** — changes behavior/authority and requires accepted governance/compatibility.
3. **runtime operational configuration** — resource/network/runtime tuning that must remain within accepted profiles.
4. **secret references** — identifiers only; secret values are separate authority.
5. **placement/admission configuration** — trusted Control Plane authority, not general config.

Feature flags/runtime config cannot convert unresolved Product scope/applicability into Product authority.

## Configuration generation

Semantically relevant runtime configuration carries a monotonic/versioned generation or equivalent immutable identity sufficient to detect stale/incompatible state.

Rules:

- `configuration_generation` is distinct from `placement_version`, `runtime_generation`, `credential_generation` and data schema version;
- stale configuration that would weaken security, recovery, tenant isolation or accepted failure behavior fails closed/quarantined rather than silently using an older permissive state;
- last-known-good configuration use is allowed only for profiles whose upstream reliability semantics permit it and whose currentness bounds/evidence are satisfied;
- config rollback cannot resurrect retired credentials, revoked authority, erased data policy or obsolete placement.

## Rotation and revocation

Rotation/revocation SHALL support mixed runtime generations without semantic ambiguity.

A runtime may temporarily hold old and new credential/config generations only when the owning migration/rotation protocol defines:

- accepted overlap purpose;
- which generation may create new work;
- retirement/fence criterion;
- verification of already-created obligations;
- rollback behavior;
- observability without exposing protected values.

Historical verification authority required by accepted Phase 10/11 evidence must remain available or be migrated equivalently before old verifier/key generations are retired.

## Least privilege by runtime class

- BFF: browser-session and approved API/realtime-ticket capabilities; no DB-owner/admin secrets.
- API: application state-port credentials for owned operations; no migration-owner/recovery super-authority.
- Worker: workload-specific state/connector references only.
- Realtime: connection/replay/current-authority dependencies only; no generic tenant DB owner.
- Parser: no general secret access.
- Automation: target-specific credential context, not platform-global secrets.
- Migration/admin: dedicated privileged references unavailable to serving runtimes.
- Recovery: dedicated recovery authorities and current security/governance references; not an unrestricted universal secret reader.

## Evidence and blockers

Acceptance/conformance evidence must prove:

- cross-profile secret denial;
- credential rotation/revocation without business-ID rewrite;
- stale configuration rejection;
- no secret-value propagation to ordinary state/signals;
- bootstrap failure remains non-ready;
- restored old runtime/config cannot re-enable revoked authority;
- Product/placement authority cannot be forged through ordinary configuration.

Exact workload-identity issuer, KMS/secret-manager, config-distribution and credential protocol remain OPEN.