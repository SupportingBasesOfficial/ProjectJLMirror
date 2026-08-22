# Phase 13 — Runtime Roles and Workload-Isolation Profiles

**Status:** proposed baseline  
**Phase:** 13 — Platform & Runtime

## Purpose

This document defines the stable runtime roles, their trust envelopes, authority boundaries, lifecycle expectations and isolation requirements.

A runtime role is not automatically a separate service. It is a conformance profile that may be co-located only when the required privilege, resource, network and failure isolation remains enforceable.

## Isolation dimensions

Every runtime profile declares:

```text
runtime_profile_id
principal_class
allowed capabilities
forbidden capabilities
tenant-context rule
network ingress class
network egress class
state ports
secret-reference classes
resource/concurrency envelope
lifecycle/drain behavior
health/observability bindings
recovery behavior
```

Isolation is evaluated across privilege, process/runtime, network/egress, resource/concurrency, state authority, tenant scope and failure blast radius. Sharing a host, cluster or process does not erase those distinctions.

## `runtime.web-bff@1`

Responsibilities:

- first-party confidential browser session boundary;
- browser-facing composition and short-lived realtime ticket minting where accepted;
- no domain database ownership;
- no long-running durable business execution.

Requirements:

- browser credentials/session secrets are not delegated to ordinary browser JS;
- BFF cannot be the only authorization barrier for Platform API;
- edge acceleration MAY front it, but core BFF semantics require a general-purpose compatible runtime when needed;
- tenant/current authority is reconstructed according to accepted API/BFF contracts;
- bounded outbound access only to approved platform/API dependencies.

## `runtime.api@1`

Responsibilities:

- modular-monolith synchronous application/domain execution;
- authoritative local transaction orchestration through accepted state ports;
- outbox/audit intent atomicity where required.

Requirements:

- stateless process memory except bounded non-authoritative caches;
- no direct mutation of another bounded context's owned state;
- no unrestricted provider/network access outside approved adapters;
- graceful admission stop and bounded request drain;
- no caller-selected physical database/cell routing.

## `runtime.worker@1`

Workers are specialized by workload profile rather than one universal super-worker.

Required specialization dimensions include as applicable:

- event/inbox effect processing;
- outbox publication;
- provider synchronization;
- webhook delivery;
- reporting/export generation;
- customer telemetry processing;
- artifact lifecycle work;
- reconciliation/replay/recovery-adjacent work that does not require privileged recovery authority.

Requirements:

- explicit concurrency/bulkhead budget per workload profile;
- at-least-once-safe behavior inherited from Phase 10/11;
- current tenant/placement/authorization re-establishment where required;
- bounded retry/backlog and no process-local dedup authority;
- one workload class cannot consume unrelated global worker capacity without an accepted shared budget.

## `runtime.realtime@1`

Responsibilities:

- protected connection admission;
- atomic single-use capability consume before `101` where required;
- current authorization/placement checks;
- delivery, revocation interruption and resync behavior.

Requirements:

- open socket is not frozen authority;
- connection-local state is disposable and reconstructable through accepted resync semantics;
- reconnect/restart cannot make a consumed capability usable again;
- failure and capacity are isolated from ordinary API/worker progress.

## `runtime.control-plane@1`

Responsibilities:

- tenant registry/lifecycle;
- cell registry;
- placement intent/version;
- global platform-management metadata and applicable global authorities.

Requirements:

- cannot become universal tenant operational database;
- topology-changing operations require current authoritative state;
- stable admitted traffic may use accepted bounded last-known-good placement evidence under Phase 11 rules;
- no tenant workload may treat Control Plane reachability as tenant authorization.

## `runtime.automation@1`

Responsibilities:

- controlled execution of accepted automation capabilities.

Requirements:

- explicit target scope, credential context, timeout and resource budget;
- dedicated execution boundary distinct from primary API process;
- deny-by-default network/egress beyond the automation profile;
- outputs bounded/classified before persistence or exposure;
- no implicit infrastructure-admin or database-owner privilege.

## `runtime.untrusted-parser@1`

Responsibilities:

- parsing/rendering/transformation of content whose parser or active-content risk requires isolation.

Requirements:

- no tenant database credential;
- no general secret access;
- no unrestricted network egress;
- bounded CPU/memory/time/input/output;
- temporary filesystem/storage is non-authoritative and cleaned according to classification;
- parser success never grants artifact releasability or domain acceptance by itself.

## `runtime.migration-admin@1`

Responsibilities:

- schema/data administration and migration work requiring privilege unavailable to normal application roles.

Requirements:

- principal distinct from application runtime;
- explicit scope/environment authorization;
- no ordinary serving traffic;
- audit/accountability evidence;
- expected-generation/fencing where destructive or irreversible operations require it;
- Phase 14 owns when/how this runtime is invoked during release.

## `runtime.recovery@1`

Responsibilities:

- privileged restore/reconciliation/fence advancement/resumption preparation under accepted Recovery authority.

Requirements:

- smaller trust envelope than general admin where feasible;
- cannot infer absence from restored missing state;
- cannot resume protected traffic until owning security/reliability/governance continuity predicates are satisfied;
- all `(R,F]` evidence handling is explicit and auditable;
- current secret/key/governance authorities are reconciled rather than rolled back by snapshot state.

## `runtime.edge-optional@1`

May provide CDN, WAF, static delivery, request filtering/routing or web composition.

Hard boundary:

- no accepted business invariant may require an edge-only execution feature;
- long-running work, durable jobs, realtime, transactional database sessions, provider connectors and controlled execution require portable general-purpose capability;
- loss/replacement of edge product cannot require rewriting canonical application semantics.

## Co-location rule

Two profiles MAY share a physical runtime only when the implementation proves:

- no privilege union creates a broader effective principal than either profile permits;
- network/secret/state access remains profile-scoped;
- workload capacity/bulkheads remain enforceable;
- lifecycle/drain behavior is compatible;
- failure of one profile cannot silently defeat the isolation required by the other.

If those properties cannot be proven, the profiles require separate runtime isolation.

## Forbidden universal-runtime pattern

A runtime that simultaneously holds application DB-owner privilege, migration/admin privilege, unrestricted egress, general secret access, untrusted parsing and recovery authority is prohibited as a default platform profile.