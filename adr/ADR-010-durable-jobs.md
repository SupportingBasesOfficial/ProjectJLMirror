# ADR-010 — Durable Background Job Semantics

**Status:** accepted  
**Date:** 2026-08-17  
**Reversibility:** reversible at infrastructure layer if contract is preserved

## Context

Monitoring synchronization, report generation, exports, automation, reconciliation and delivery cannot safely depend on an HTTP request lifetime. Job systems may redeliver after timeout/crash. One tenant/destination must not consume unbounded worker capacity.

Drivers: `FR-MON-004`, `FR-AUTO-*`, `FR-INT-002`, `FR-INT-004`, `FR-OPS-003`, `INV-ASYNC-*`, `QA-ASYNC-001`, `QA-BULK-001`, `SEC-ABUSE-002`, `TM-002`, `TM-011`.

## Decision

The platform SHALL use a durable background-work capability whose contract supports:

- at-least-once execution;
- stable job/operation ID;
- logical tenant ID only for placement authority;
- schema/versioned payload;
- bounded retry with categorized retryability;
- exponential/jitter backoff policy where appropriate;
- timeout/cancellation semantics;
- deduplication/idempotency for side effects;
- dead-letter/quarantine/failure visibility;
- per-workload and per-tenant concurrency/rate controls;
- correlation/causation IDs;
- progress/resume for long-running administrative work where applicable.

Worker classes SHALL be separately scalable. Dangerous automation execution SHALL use a stronger runtime boundary than ordinary data-processing workers.

No queue vendor is selected by this ADR.

## Consequences

### Positive
- work survives API restarts and request timeouts;
- bulkheads can isolate noisy tenants/destinations;
- queue implementation remains replaceable behind a stable contract.

### Negative / cost
- developers must design idempotency and failure states explicitly;
- operational tooling for lag, poison jobs and retries is mandatory.

## Validation

Crash/redelivery/load tests SHALL demonstrate no prohibited duplicate side effect, bounded queue starvation and tenant-safe placement resolution. Queue outage recovery must not lose acknowledged durable work.

## Exit / revisit conditions

Queue technology may change through ADR while preserving these semantics. Semantics are relaxed only if a workload is proven disposable/best-effort and documented as such.