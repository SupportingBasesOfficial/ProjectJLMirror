# ADR-019 — Scaling, Cell Expansion and Tenant Relocation

**Status:** proposed  
**Date:** 2026-08-17  
**Reversibility:** costly

## Context

Scale is multidimensional: requests, tenants, telemetry, workers, realtime connections, integrations and storage. Scaling one global stack eventually increases blast radius. Tenant placement must move without changing logical IDs/contracts, and relocation must retire stateful old-placement ownership such as long-lived realtime subscriptions rather than only reroute new requests/jobs.

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

Protected tenant realtime subscriptions are also placement-generation-bound. At relocation cutover, the retired source generation can no longer authorize continued tenant delivery: affected source subscriptions are removed or their connection is terminated within the accepted bound, and clients re-resolve/resubscribe to the current target placement and resynchronize authoritative state. An open source socket is not placement authority. A future transparent handoff may replace reconnect only if it re-establishes current authorization, target placement/admission generation and resync semantics.

Capacity management SHALL track at least tenants/cell, resources/tenant, telemetry ingest rate/cardinality, database size/IO, API saturation, worker lag, realtime connections, provider rate limits, object/artifact growth and per-tenant noisy-neighbor indicators.

Large tenants MAY move to dedicated cells without application contract changes.

## Consequences

### Positive
- predictable horizontal growth path;
- blast radius stays bounded as tenant fleet grows;
- relocation does not strand long-lived source realtime subscriptions on a retired placement generation;
- no premature microservice requirement.

### Negative / cost
- cell capacity/placement automation and migration tooling become platform features;
- relocation needs bounded realtime subscription retirement/resubscription in addition to request/job fencing;
- cross-cell aggregate reporting requires deliberate fanout/read models.

## Validation

Demonstrate second-cell provisioning, tenant cutover with concurrent requests/jobs and an active source realtime subscription, stale-writer rejection, source subscription retirement, target resubscription/snapshot-resync and load rebalancing before production relocation is enabled. A source socket that remains apparently current while indefinitely missing target-cell updates fails relocation validation.

## Exit / revisit conditions

Introduce region hierarchy or more specialized partitioning when residency/latency/capacity evidence requires it.
