# ADR-009 — Domain and Integration Event Semantics

**Status:** accepted  
**Date:** 2026-08-17  
**Reversibility:** costly after external consumers exist

## Context

Events are needed for decoupled alerting, reporting, AIOps, webhooks and future service extraction, but using an event bus as a shared mutable model creates hidden coupling. Delivery systems commonly redeliver, reorder across partitions and fail transiently. Event/message identifiers are not universally global: external providers, tenant-local streams and separate producers may reuse the same raw identifier value.

Drivers: `INV-CONTRACT-001`, `INV-ASYNC-001`, `QA-ASYNC-001`, `TM-011`.

## Decision

JLMIRROR distinguishes:

- **Domain event:** internal semantic fact emitted by the owning domain. It may initially be handled in-process.
- **Integration event:** durable, versioned fact safe for consumers outside the owning module/process.
- **Job/command:** request for work; not an event.

Integration events SHALL use a standard envelope containing at minimum stable event ID, event type, schema version, occurred time, logical tenant ID when tenant-scoped, aggregate/resource reference, correlation/causation IDs, trusted producer/source identity or namespace when required for global uniqueness/deduplication, and payload.

Delivery semantics are **at least once**. Consumers SHALL be idempotent/deduplicating where side effects matter. Ordering is guaranteed only when a specific contract declares an ordering key; global ordering is not assumed.

A consumer deduplication identity SHALL include the authoritative producer/source namespace in which the event/message ID is unique, unless the event contract explicitly guarantees that the ID is globally unique across every producer capable of feeding that consumer for the entire deduplication window. Tenant/global boundary, integration/provider/source identity and source generation/stream are included when required to prevent collisions. The namespace comes from trusted routing/envelope/integration context, not arbitrary payload fields.

Events SHALL contain deliberate contract fields, not database-row dumps, unrestricted secrets or caller-controlled physical routing.

The durable event-broker product is not selected by this ADR.

## Consequences

### Positive
- explicit semantics between facts and work requests;
- safe future extraction of modules;
- compatible version evolution and replay are possible;
- one producer/tenant cannot suppress another producer's legitimate message merely by reusing the same raw message ID.

### Negative / cost
- event schema governance and compatibility testing are required;
- duplicate/order handling and identity-scope rules move into consumer contracts;
- projections are eventually consistent.

## Validation

Contract tests SHALL verify envelope/schema compatibility, secret redaction, tenant identity and deduplication. Replay of a previously processed event within the same trusted identity scope must not create prohibited duplicate effects. Tests SHALL also feed the same raw event/message ID from distinct authoritative tenant/source scopes and prove the messages do not collide unless the contract explicitly defines the ID as globally unique.

## Exit / revisit conditions

Revisit broker/partition implementation separately; semantic distinction, versioning and collision-safe message identity semantics remain unless product contracts change.