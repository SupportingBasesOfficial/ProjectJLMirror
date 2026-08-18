# ADR-008 — Transaction Boundaries and Transactional Outbox

**Status:** proposed  
**Date:** 2026-08-17  
**Reversibility:** costly after event consumers proliferate

## Context

JLMIRROR must mutate durable state and reliably trigger asynchronous consequences (notifications, webhooks, projections, workflows). Publishing directly to a broker before/after commit creates dual-write failure windows. Long external calls inside database transactions increase lock duration and couple availability. Required audit evidence has the same dual-write problem if appended only after the protected mutation commits.

Drivers: `INV-ASYNC-001`, `INV-DATA-004`, `QA-ASYNC-001`, `TM-011`, `SEC-AUD-001`, `SEC-AUD-003`, `AP-05`.

## Decision

The **application use case** owns the database transaction boundary for a single transactional ownership scope.

When a successful transaction must produce durable asynchronous consequences, domain state changes and an **outbox record** SHALL commit atomically in the same PostgreSQL transaction. A dispatcher publishes the outbox item to the accepted event transport and marks publication state idempotently.

When an audit record is required for a local authoritative mutation and the audit record is owned in the same transactional boundary, the audit append SHALL commit atomically with the mutation. If final audit evidence is stored in another persistence authority, a durable audit intent/outbox record SHALL commit atomically with the mutation and delivery to the external audit sink is retried/reconciled. A required audit trail MUST NOT depend solely on post-commit best effort.

External network calls SHALL NOT normally execute inside the database transaction. Multi-domain/external workflows requiring multiple durable steps use a process manager/saga-like orchestration with explicit compensation/reconciliation instead of pretending to have a distributed ACID transaction.

The same principle applies to any cross-persistence write: one authority must durably accept the intent/observation first, and the remaining effects are idempotent projections/reconciled consequences rather than an uncoordinated dual write.

## Consequences

### Positive
- removes the most common database/event dual-write gap;
- required local audit cannot be lost in a crash after business commit;
- event/audit publication can retry safely;
- transactions remain short and local;
- eventual-consistency points are explicit.

### Negative / cost
- outbox tables/dispatchers and retention/monitoring are required;
- consumers must handle duplicate delivery;
- multi-step workflows become explicit state machines;
- external audit sinks require durable intent and reconciliation.

## Validation

Fault injection SHALL cover crash before commit, after commit/before publish, duplicate publish, dispatcher restart and consumer replay. No committed event-worthy state may be permanently invisible to the dispatcher.

For required audit, fault injection SHALL prove there is no state in which the protected mutation commits successfully while neither the required audit record nor its durable atomic audit intent exists.

## Exit / revisit conditions

A broker supporting transactional integration with the authoritative database could justify a different mechanism, but equivalent atomicity guarantees must be demonstrated.
