# ADR-019 — Scaling, Cell Expansion and Tenant Relocation

**Status:** proposed  
**Date:** 2026-08-17  
**Reversibility:** costly

## Context

Scale is multidimensional: requests, tenants, telemetry, workers, realtime connections, integrations and storage. Scaling one global stack eventually increases blast radius. Tenant placement must move without changing logical IDs/contracts.

Drivers: `AP-12`, `FR-PLAT-002..003`, `FR-MON-003..004`, `QA-SCALE-001`, `QA-PERF-001`, `TM-012`.

## Decision

Scaling order:

1. scale stateless API/realtime replicas within a cell;
2. scale worker pools independently by workload lag/saturation;
3. tune/scale transactional/telemetry dependencies within their supported envelope;
4. add cells and place new/large tenants into available capacity;
5. relocate tenants between cells when capacity, residency, isolation or maintenance requires it;
6. extract services only when ADR-020 criteria are met.

Placement is versioned (ADR-004). Relocation uses explicit states and prevents stale writers. Jobs/events always identify logical tenant and re-resolve/admit placement rather than persisting physical routes.

Capacity management SHALL track at least tenants/cell, resources/tenant, telemetry ingest rate/cardinality, database size/IO, API saturation, worker lag, realtime connections, provider rate limits, object/artifact growth and per-tenant noisy-neighbor indicators.

Large tenants MAY move to dedicated cells without application contract changes.

## Consequences

### Positive
- predictable horizontal growth path;
- blast radius stays bounded as tenant fleet grows;
- no premature microservice requirement.

### Negative / cost
- cell capacity/placement automation and migration tooling become platform features;
- cross-cell aggregate reporting requires deliberate fanout/read models.

## Validation

Demonstrate second-cell provisioning, tenant cutover with concurrent requests/jobs, stale-writer rejection and load rebalancing before production relocation is enabled.

## Exit / revisit conditions

Introduce region hierarchy or more specialized partitioning when residency/latency/capacity evidence requires it.
