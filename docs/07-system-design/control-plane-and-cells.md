# Control Plane and Cell Design

**Status:** proposed baseline  
**Primary ADRs:** ADR-002, ADR-003, ADR-004, ADR-016, ADR-017, ADR-019

## Control Plane responsibilities

The Control Plane is intentionally small and globally scoped. It owns metadata required to manage and locate tenant workloads, not the tenant's operational business data.

Canonical control-plane responsibilities:

- immutable tenant registry;
- cell registry and health/capacity metadata;
- tenant placement and isolation class;
- tenant lifecycle operations (provision, suspend, relocate, decommission);
- platform/global administrator authorization data;
- global identity/session authority where selected by identity design;
- global marketplace/catalog metadata;
- customer commercial relationship that is platform-global;
- global configuration that is not tenant operational state.

## Cell responsibilities

A Cell is the normal unit of tenant execution, horizontal scaling and failure containment.

Each cell contains or is connected to:

- tenant API runtime;
- workload-specific worker pools;
- realtime gateway/fanout capability;
- one authoritative cell transactional database boundary;
- telemetry ingestion/storage port;
- ephemeral/cache/coordination port;
- object/artifact storage namespace;
- provider connector execution;
- cell-level observability and health.

A dedicated cell uses the same logical contracts and data model as a pooled cell; it changes isolation/capacity, not product semantics.

## Tenant placement record

The trusted placement model contains, at minimum:

```text
tenant_id          immutable logical tenant identity
cell_id            currently authoritative cell
isolation_class    pooled | dedicated-cell | future accepted class
placement_version  monotonically increasing routing generation
state              provisioning | active | migrating | suspended |
                   decommissioning | failed (or accepted equivalent)
region_intent      optional residency/region policy
updated_at         control-plane change time
```

A caller may name a `tenant_id`; it may never select `cell_id`, database address, schema, secret reference or connection string as routing authority.

## Routing contract

1. Ingress obtains authenticated principal and intended logical tenant.
2. Trusted placement resolution returns cell + placement version.
3. Routing metadata is propagated over an authenticated internal channel.
4. The destination cell validates that the tenant is admitted to that cell and that placement is acceptable.
5. Cell business authorization is evaluated independently.
6. A stale placement generation is rejected or re-resolved; it is never silently trusted.

## Stable traffic during Control Plane impairment

Stable already-admitted tenant traffic SHOULD be capable of continuing from a bounded, versioned placement cache when all of the following are true:

- the cached record is cryptographically/internally trusted;
- its policy TTL has not expired;
- the tenant is not known to be migrating/suspended/decommissioning;
- the destination cell independently recognizes the tenant placement/version.

Lifecycle, relocation, suspension and other topology-changing operations require authoritative Control Plane state and fail closed when it cannot be safely obtained.

## Cell health states

A cell exposes at least:

- `healthy`: accepts admitted traffic;
- `degraded`: accepts a declared subset with degraded dependencies;
- `draining`: no new tenant placement; existing work drains according to rollout/migration policy;
- `unavailable`: ingress does not route normal tenant traffic;
- `maintenance`: controlled operator state.

The exact state machine may be extended, but automation must not infer health from a single process liveness check.

## Cross-cell rule

Tenant operational mutations never require synchronous writes to two cells. Cross-cell/platform aggregation is performed through deliberate read/projection mechanisms, not distributed SQL joins or distributed transactions.

## Capacity rule

Placement decisions consider multidimensional capacity: tenant count, API load, worker load, provider load, database/storage pressure, telemetry ingest, realtime connections and noisy-neighbor profile. A single `tenant_count` threshold is insufficient.
