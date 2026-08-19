# ADR-017 — Availability, Degraded Modes and Bulkheads

**Status:** accepted  
**Date:** 2026-08-17  
**Reversibility:** costly across runtime behavior

## Context

Not every dependency has the same criticality. A monitoring provider outage should degrade monitoring for that tenant, not authentication/ITSM globally. A slow webhook must not starve monitoring jobs. Cache loss should differ from database loss.

Drivers: `QA-AVAIL-001`, `QA-BULK-001`, `INV-EXT-001`, `INV-ASYNC-003`, `SEC-ABUSE-002`.

## Decision

Every runtime dependency/capability SHALL declare a **failure mode** and **degradation policy**.

Baseline categories:

- **authoritative transactional dependency unavailable:** fail closed for mutations requiring it; readiness/degraded status reflects inability to serve affected cell/domain;
- **external tenant provider unavailable:** fail fast/circuit after bounded retries; serve previously stored state with explicit staleness where product permits;
- **performance cache unavailable:** bypass/fallback to authoritative store under protected concurrency where safe;
- **security authority unavailable:** fail closed unless a separately documented durable/local verification path remains valid;
- **realtime fanout unavailable:** durable state continues; clients reconnect/resync;
- **reporting/AIOps optional workload unavailable:** isolate queue/runtime; core operations continue.

Bulkheads SHALL exist by cell, workload class and where necessary tenant/destination. Retry storms are controlled by jitter/backoff/concurrency budgets and circuit breakers.

Control-plane data SHOULD be cached/versioned so an outage does not automatically stop already-admitted stable tenant traffic; lifecycle/migration/suspension operations may require stronger control-plane availability.

## Consequences

### Positive
- predictable partial failure instead of cascading outage;
- operational status can explain degraded capability;
- noisy tenants/destinations are bounded.

### Negative / cost
- every dependency needs explicit semantics and tests;
- stale-data UX and reconciliation paths are required.

## Validation

Chaos/fault-injection matrix covers provider, cache, queue, cell database, realtime, control plane, reporting and worker failures. SLO numeric targets remain defined by later SLO work.

## Exit / revisit conditions

Specific thresholds/circuit values change through configuration/operational ADR; dependency categories remain.