# Phase 13 — Runtime Roles and Workload-Isolation Profiles

**Status:** proposed baseline  
**Phase:** 13 — Platform & Runtime

## Purpose

This document defines the stable runtime roles, their trust envelopes, authority boundaries, lifecycle expectations and isolation requirements.

A runtime role is not automatically a separate service. It is a conformance profile that may be co-located only when the required privilege, environment, resource, network and failure isolation remains enforceable.

## Isolation dimensions

Every runtime profile declares:

```text
runtime_profile_id
environment_class
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

Isolation is evaluated across environment, privilege, process/runtime, network/egress, resource/concurrency, state authority, tenant scope and failure blast radius. Sharing a host, cloud account/project, cluster, namespace or process does not erase those distinctions.

## Environment isolation rule

Every concrete runtime instance uses one exact canonical environment class allowed by the runtime semantic manifest:

```text
environment.development@1
environment.validation@1
environment.production@1
environment.recovery@1
```

Environment class is not authorization, tenant, Product or placement authority. A physical runtime shared across logical environment classes must preserve distinct principals, secrets, state-port bindings, network policy and data authority sufficient to satisfy `PRTV-044`; if that cannot be proven, the environments require physical separation.

`environment.recovery@1` is not ordinary serving authority. Development/validation are not permitted to inherit production credentials/data/traffic by convenience. Phase 14 may remap these classes physically under `OPEN-PRT-035`, but cannot redefine the isolation semantics.

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
- bounded outbound access only to approved platform/API dependencies;
- environment class never substitutes for session/tenant/current authority.

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
- no caller-selected physical database/cell routing;
- production serving authority requires current production principal/placement/state-port bindings, not merely `environment.production@1`.

## `runtime.worker@1`

Workers are specialized by workload profile rather than one universal super-worker.

### Canonical worker specialization IDs

The initial prepared specialization set is:

```text
worker.outbox-publication@1
worker.async-consumer@1
worker.provider-integration@1
worker.webhook-delivery@1
worker.reporting-export@1
worker.customer-telemetry@1
worker.artifact-lifecycle@1
worker.reconciliation@1
```

These are workload-isolation selectors under `runtime.worker@1`, not new business domains and not automatically separate deployables. A concrete worker instance declares exactly which accepted specialization set it implements.

Canonical binding intent:

| Worker specialization | Primary accepted reliability ownership | Typical Phase 12 evidence |
|---|---|---|
| `worker.outbox-publication@1` | `rel.outbox-publication@1`, `rel.broker-job-transport@1` | `health.async-worker@1`, `obs.async.progress@1`, `sli.async.progress@1` |
| `worker.async-consumer@1` | `rel.consumer-inbox-effect@1`, `rel.broker-job-transport@1` | `health.async-worker@1`, plus `health.message-equivalence@1` where duplicate-sensitive proof applies |
| `worker.provider-integration@1` | `rel.external-provider@1` plus durable transport/effect profile used by the operation | `health.provider-adapter@1`, `health.async-worker@1`, `sli.provider.outcome@1` |
| `worker.webhook-delivery@1` | `rel.webhook-delivery@1` | `health.webhook-delivery@1`, with Product-gated SLI/alert applicability preserved from Phase 12 |
| `worker.reporting-export@1` | `rel.reporting-derived@1` plus artifact profile when output becomes protected artifact | `health.async-worker@1`, `health.artifact@1` where applicable |
| `worker.customer-telemetry@1` | `rel.customer-telemetry-acceptance@1` | `health.customer-telemetry@1`, `sli.customer-telemetry.acceptance@1` |
| `worker.artifact-lifecycle@1` | `rel.artifact-storage@1` | `health.artifact@1`, Product applicability preserved for direct delivery SLI |
| `worker.reconciliation@1` | the exact affected reliability profile plus `rel.privileged-operations@1` only when privileged scope is required | `health.recovery@1` / `health.async-worker@1` as applicable; `sli.recovery.convergence@1` where recovery-owned |

Implementation SHALL NOT use the generic `runtime.worker@1` label to avoid declaring the actual specialization, environment, privileges, queues/transports, state ports, egress and bulkhead budget.

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

- explicit concurrency/bulkhead budget per worker specialization;
- at-least-once-safe behavior inherited from Phase 10/11;
- current tenant/placement/authorization re-establishment where required;
- bounded retry/backlog and no process-local dedup authority;
- one workload class cannot consume unrelated global worker capacity without an accepted shared budget;
- co-locating multiple worker specializations requires the same environment/privilege/egress/state/resource-union evidence as co-locating top-level runtime profiles;
- only `worker.reconciliation@1` may use `environment.recovery@1`, and only under explicit recovery authority as defined by the manifest.

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
- failure and capacity are isolated from ordinary API/worker progress;
- recovery environment does not serve normal protected realtime connections.

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
- no tenant workload may treat Control Plane reachability as tenant authorization;
- a development/validation Control Plane cannot own production placement merely because it shares physical infrastructure.

## `runtime.automation@1`

Responsibilities:

- controlled execution of accepted automation capabilities.

Requirements:

- explicit target scope, environment, credential context, timeout and resource budget;
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
- temporary filesystem/storage is non-authoritative, environment-isolated and cleaned according to classification;
- parser success never grants artifact releasability or domain acceptance by itself.

## `runtime.migration-admin@1`

Responsibilities:

- schema/data administration and migration work requiring privilege unavailable to normal application roles.

Requirements:

- principal distinct from application runtime;
- explicit environment/cell/data scope;
- no ordinary serving traffic;
- audit/accountability evidence;
- expected-generation/fencing where destructive or irreversible operations require it;
- Phase 14 owns when/how this runtime is invoked during release;
- production migration authority is distinct from development/validation authority.

## `runtime.recovery@1`

Responsibilities:

- privileged restore/reconciliation/fence advancement/resumption preparation under accepted Recovery authority.

Requirements:

- executes only in manifest-allowed validation/recovery environment classes;
- smaller trust envelope than general admin where feasible;
- cannot infer absence from restored missing state;
- cannot resume protected traffic until owning security/reliability/governance continuity predicates are satisfied;
- all `(R,F]` evidence handling is explicit and auditable;
- current secret/key/governance authorities are reconciled rather than rolled back by snapshot state;
- recovery environment reachability does not create production serving authority.

## `runtime.edge-optional@1`

May provide CDN, WAF, static delivery, request filtering/routing or web composition.

Hard boundary:

- no accepted business invariant may require an edge-only execution feature;
- long-running work, durable jobs, realtime, transactional database sessions, provider connectors and controlled execution require portable general-purpose capability;
- loss/replacement of edge product cannot require rewriting canonical application semantics;
- edge environment mapping never creates tenant/Product authority.

## Co-location rule

Two profiles or worker specializations MAY share a physical runtime only when the implementation proves:

- environment classes are compatible and remain separately enforceable where they differ;
- no privilege union creates a broader effective principal than any selected profile permits;
- network/secret/state access remains profile/environment-scoped;
- workload capacity/bulkheads remain enforceable;
- lifecycle/drain behavior is compatible;
- failure of one profile cannot silently defeat the isolation required by another.

If those properties cannot be proven, the profiles/environments require separate runtime isolation.

## Forbidden universal-runtime pattern

A runtime that simultaneously holds application DB-owner privilege, migration/admin privilege, unrestricted egress, general secret access, untrusted parsing, recovery authority and cross-environment production authority is prohibited as a default platform profile.
