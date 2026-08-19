# System-Level Acceptance Criteria

**Status:** accepted

These criteria define cross-cutting proof required before a capability can be considered production-ready. Domain-specific criteria will extend them.

## AC-001 — Tenant isolation
Given two tenants A and B, authenticated/authorized activity scoped to A cannot read, mutate, subscribe to, export, report, query, or receive protected B data through HTTP, WebSocket, jobs, workers, webhooks, reports, direct-query tools, cache keys, or persistence paths.

## AC-002 — Authorization
Protected operations fail closed when membership, role, permission, resource scope, token/credential status, or tenant context is invalid or missing. Hiding UI controls alone never satisfies this criterion.

## AC-003 — Provider failure containment
When a monitoring or integration provider for Tenant A is unavailable or returns malformed data, unrelated tenants and platform capabilities not dependent on that provider continue to operate within their defined degraded-mode expectations.

## AC-004 — Retry safety
Every side-effecting operation configured for automatic retry demonstrates idempotency/deduplication under duplicate delivery, worker restart, timeout ambiguity, and redelivery.

## AC-005 — Auditability
A privileged mutation can be traced to actor/principal, tenant or platform scope, action, resource, time, outcome and correlation identifier without exposing secrets.

## AC-006 — Observability
A representative user request that causes asynchronous work can be correlated across web/BFF, API, persistence, queue/job, worker, external-provider call, and resulting state/event where applicable.

## AC-007 — Migration safety
A supported production schema change can be rolled through the active deployment strategy without requiring an unsafe simultaneous application/schema cutover. Failed tenant fan-out migration is observable and resumable.

## AC-008 — Recovery
Control-plane and tenant transactional backup/restore procedures are exercised in a non-production environment and prove data integrity. A backup job that has never been restored does not satisfy recovery acceptance.

## AC-009 — Public-data boundary
Public status output and externally distributed reports/exports expose only fields explicitly included by their public/external contract and cannot be used to query arbitrary internal tenant state.

## AC-010 — Secret containment
Automated checks and representative failure tests verify secrets are not present in logs, traces, metrics labels, errors, API responses, event payloads, queue messages, exports, or audit snapshots.

## AC-011 — Privileged execution
Script execution, SQL/data administration, and data transfer are separately authorized, bounded by resource/time limits, audited, and isolated according to their threat model.

## AC-012 — Capacity evidence
Before a scale-related infrastructure choice is declared final, representative load tests or measured production evidence demonstrate the target ingestion, request, job, connection, storage and query envelope with defined headroom.
