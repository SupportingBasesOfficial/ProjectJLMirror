# ADR-011 — Realtime Delivery Semantics

**Status:** proposed  
**Date:** 2026-08-17  
**Reversibility:** reversible at transport layer

## Context

Operators need near-real-time alerts, health/state updates and execution progress. Realtime transport is lossy across reconnects and multi-replica fanout; treating it as authoritative creates missed-state and duplicate-delivery bugs. Tenant/topic collisions are a security risk. Long-lived connections also outlive individual authorization decisions, so authorization checked only at connect/join time can become stale after membership, permission, session or tenant-state changes.

Drivers: `FR-ALT-002`, `FR-ALT-004`, `INV-REALTIME-001`, `SEC-AUTHZ-*`, `TM-003`, `TM-004`, `QA-OBS-001`.

## Decision

JLMIRROR SHALL use **WebSocket** as the initial authenticated browser realtime transport for operational subscriptions. The transport is a notification/update channel, not durable business truth.

Every protected connection/subscription SHALL be authenticated and authorized before joining a tenant/resource scope. Fanout keys/channels use canonical tenant-aware namespaces. Realtime messages carry stable event/update ID, schema version, tenant scope, resource/topic and correlation metadata where applicable.

### Authorization freshness and revocation

Authorization is not a one-time handshake property. A realtime gateway MUST stop protected delivery when the principal/session/membership/permission/tenant state no longer authorizes a subscription.

The implementation SHALL support all of the following semantics:

- connection establishment and every new protected subscription evaluate current authorization;
- authorization/session/membership changes that can remove access produce an invalidation/revocation signal or equivalent mechanism capable of reaching active realtime gateways;
- affected subscriptions are re-evaluated and removed, or the connection is terminated, when access is revoked;
- periodic bounded revalidation provides defense in depth when an invalidation signal is missed or delayed;
- reconnect always performs fresh authentication/authorization rather than inheriting prior subscription authority;
- a gateway that cannot safely establish current authorization fails closed for protected delivery;
- any accepted propagation/revalidation delay is explicitly bounded by a later security/SLO policy rather than being unlimited.

An authorization generation/version or equivalent freshness marker MAY be used so gateways can detect stale authorization state without embedding mutable permission sets as permanent socket authority.

Clients SHALL tolerate duplicate delivery, reconnect and missed transient messages. On reconnect/gap detection, clients re-query authoritative API/read models or use a bounded replay mechanism where a feature explicitly provides one.

Durable events/jobs and database state remain authoritative. Ephemeral pub/sub may be used behind the gateway but loss of ephemeral fanout must not corrupt business state.

## Consequences

### Positive
- strong fit for interactive NOC/operator experience;
- horizontally scalable gateways are possible;
- no false exactly-once promise;
- reconnect semantics are explicit;
- revocation/permission changes do not leave indefinitely authorized stale sockets.

### Negative / cost
- connection lifecycle/heartbeats/backpressure need operations;
- authorization invalidation and periodic revalidation add coordination/load;
- some edge/serverless platforms may be unsuitable for long-lived connections;
- replay/current-state query paths must exist.

## Validation

Test cross-tenant subscription attempts, reconnect storms, duplicate delivery, gateway restart, fanout dependency failure and stale authorization.

A release test MUST establish a protected subscription, then revoke membership/permission/session or suspend tenant access and verify that protected delivery stops according to the accepted bounded revocation policy without waiting for a manual reconnect. Failure to terminate/restrict a known unauthorized live subscription is release-blocking.

A missed realtime frame must be recoverable through authoritative state.

## Exit / revisit conditions

SSE or another transport may replace/supplement WebSocket for unidirectional/public workloads if it materially reduces cost/complexity while preserving these authorization and recovery semantics.
