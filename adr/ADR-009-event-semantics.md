# ADR-009 — Domain and Integration Event Semantics

**Status:** proposed  
**Date:** 2026-08-17  
**Reversibility:** costly after external consumers exist

## Context

Events are needed for decoupled alerting, reporting, AIOps, webhooks and future service extraction, but using an event bus as a shared mutable model creates hidden coupling. Delivery systems commonly redeliver, reorder across partitions and fail transiently.

Drivers: `INV-CONTRACT-001`, `INV-ASYNC-001`, `QA-ASYNC-001`, `TM-011`.

## Decision

JLMIRROR distinguishes:

- **Domain event:** internal semantic fact emitted by the owning domain. It may initially be handled in-process.
- **Integration event:** durable, versioned fact safe for consumers outside the owning module/process.
- **Job/command:** request for work; not an event.

Integration events SHALL use a standard envelope containing at minimum stable event ID, event type, schema version, occurred time, logical tenant ID when tenant-scoped, aggregate/resource reference, correlation/causation IDs, and payload.

Delivery semantics are **at least once**. Consumers SHALL be idempotent/deduplicating where side effects matter. Ordering is guaranteed only when a specific contract declares an ordering key; global ordering is not assumed.

Events SHALL contain deliberate contract fields, not database-row dumps, unrestricted secrets or caller-controlled physical routing.

The durable event-broker product is not selected by this ADR.

## Consequences

### Positive
- explicit semantics between facts and work requests;
- safe future extraction of modules;
- compatible version evolution and replay are possible.

### Negative / cost
- event schema governance and compatibility testing are required;
- duplicate/order handling moves into consumer contracts;
- projections are eventually consistent.

## Validation

Contract tests SHALL verify envelope/schema compatibility, secret redaction, tenant identity and deduplication. Replay of a previously processed event must not create prohibited duplicate effects.

## Exit / revisit conditions

Revisit broker/partition implementation separately; semantic distinction and versioning remain unless product contracts change.
