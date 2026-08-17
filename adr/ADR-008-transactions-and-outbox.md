# ADR-008 — Transaction Boundaries and Transactional Outbox

**Status:** proposed  
**Date:** 2026-08-17  
**Reversibility:** costly after event consumers proliferate

## Context

JLMIRROR must mutate durable state and reliably trigger asynchronous consequences (notifications, webhooks, projections, workflows). Publishing directly to a broker before/after commit creates dual-write failure windows. Long external calls inside database transactions increase lock duration and couple availability.

Drivers: `INV-ASYNC-001`, `INV-DATA-004`, `QA-ASYNC-001`, `TM-011`, `AP-05`.

## Decision

The **application use case** owns the database transaction boundary for a single transactional ownership scope.

When a successful transaction must produce durable asynchronous consequences, domain state changes and an **outbox record** SHALL commit atomically in the same PostgreSQL transaction. A dispatcher publishes the outbox item to the accepted event transport and marks publication state idempotently.

External network calls SHALL NOT normally execute inside the database transaction. Multi-domain/external workflows requiring multiple durable steps use a process manager/saga-like orchestration with explicit compensation/reconciliation instead of pretending to have a distributed ACID transaction.

Audit evidence that must be inseparable from a privileged mutation SHOULD commit in the same transaction when owned in the same data boundary.

## Consequences

### Positive
- removes the most common database/event dual-write gap;
- event publication can retry safely;
- transactions remain short and local;
- eventual-consistency points are explicit.

### Negative / cost
- outbox tables/dispatchers and retention/monitoring are required;
- consumers must handle duplicate delivery;
- multi-step workflows become explicit state machines.

## Validation

Fault injection SHALL cover crash before commit, after commit/before publish, duplicate publish, dispatcher restart and consumer replay. No committed event-worthy state may be permanently invisible to the dispatcher.

## Exit / revisit conditions

A broker supporting transactional integration with the authoritative database could justify a different mechanism, but equivalent atomicity guarantees must be demonstrated.
