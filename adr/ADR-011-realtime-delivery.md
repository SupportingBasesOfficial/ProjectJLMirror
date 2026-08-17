# ADR-011 — Realtime Delivery Semantics

**Status:** proposed  
**Date:** 2026-08-17  
**Reversibility:** reversible at transport layer

## Context

Operators need near-real-time alerts, health/state updates and execution progress. Realtime transport is lossy across reconnects and multi-replica fanout; treating it as authoritative creates missed-state and duplicate-delivery bugs. Tenant/topic collisions are a security risk.

Drivers: `FR-ALT-002`, `FR-ALT-004`, `INV-REALTIME-001`, `TM-004`, `QA-OBS-001`.

## Decision

JLMIRROR SHALL use **WebSocket** as the initial authenticated browser realtime transport for operational subscriptions. The transport is a notification/update channel, not durable business truth.

Every protected subscription SHALL be authorized before joining a tenant/resource scope. Fanout keys/channels use canonical tenant-aware namespaces. Realtime messages carry stable event/update ID, schema version, tenant scope, resource/topic and correlation metadata where applicable.

Clients SHALL tolerate duplicate delivery, reconnect and missed transient messages. On reconnect/gap detection, clients re-query authoritative API/read models or use a bounded replay mechanism where a feature explicitly provides one.

Durable events/jobs and database state remain authoritative. Ephemeral pub/sub may be used behind the gateway but loss of ephemeral fanout must not corrupt business state.

## Consequences

### Positive
- strong fit for interactive NOC/operator experience;
- horizontally scalable gateways are possible;
- no false exactly-once promise;
- reconnect semantics are explicit.

### Negative / cost
- connection lifecycle/heartbeats/backpressure need operations;
- some edge/serverless platforms may be unsuitable for long-lived connections;
- replay/current-state query paths must exist.

## Validation

Test cross-tenant subscription attempts, reconnect storms, duplicate delivery, gateway restart, fanout dependency failure and stale authorization. A missed realtime frame must be recoverable through authoritative state.

## Exit / revisit conditions

SSE or another transport may replace/supplement WebSocket for unidirectional/public workloads if it materially reduces cost/complexity while preserving semantics.
