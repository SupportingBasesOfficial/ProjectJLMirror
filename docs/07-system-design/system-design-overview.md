# System Design Overview

**Status:** proposed baseline  
**Depends on:** ADR-001 through ADR-020

## Purpose

This document turns the accepted JLMIRROR architecture into runtime mechanics. It defines how requests, tenant placement, authorization, transactions, asynchronous work, realtime delivery, failure containment and cross-cell operations behave without binding the design to an unselected queue/cache/cloud vendor.

## System shape

JLMIRROR consists of a global logical **Control Plane** and one or more **Data Plane Cells**.

```text
Internet / Clients
        |
        v
Web / BFF / API ingress
        |
        +----------> Control Plane API
        |                 |
        |                 +-- tenant lifecycle
        |                 +-- placement
        |                 +-- global identity/platform admin
        |                 +-- global catalog/commercial control
        |
        v
Tenant routing by immutable tenant_id
        |
   +----+---------------------------+
   |                                |
   v                                v
 Cell A                           Cell N
   |                                |
   +-- tenant API                   +-- tenant API
   +-- worker pools                 +-- worker pools
   +-- realtime gateway             +-- realtime gateway
   +-- transactional store          +-- transactional store
   +-- telemetry adapter/plane       +-- telemetry adapter/plane
   +-- ephemeral dependencies        +-- ephemeral dependencies
```

The initial deployment MAY contain one cell. No tenant-facing contract may depend on there being exactly one cell.

## Core runtime rules

1. Tenant identity is logical and immutable. Physical cell/database routing is never caller authority.
2. Every tenant-scoped unit of work has a validated `TenantContext`.
3. Every mutable aggregate has one logical owning domain.
4. Synchronous mutations occur inside an application-owned transaction in one authoritative transactional boundary.
5. Cross-boundary propagation uses durable records/events/jobs; distributed transactions are not assumed.
6. At-least-once delivery is the default asynchronous assumption; side effects require idempotency/deduplication.
7. Realtime delivery is advisory/fanout, never the sole source of authoritative state.
8. Failure of a provider, destination, workload class, tenant or cell is bounded according to the degradation matrix.
9. Control-plane placement is versioned; stale writers are rejected during relocation/cutover.
10. All important work is correlatable by stable operation/request/event identifiers without leaking secrets.

## Runtime boundaries

### Web/BFF

Owns browser-specific session handling, CSRF/browser protection, route composition and safe propagation to APIs. It does not own business rules.

### Control Plane API

Owns global platform operations: tenant lifecycle, placement, cells, platform administration, global identity/session authority where applicable, global catalog and commercial/platform metadata.

### Cell API

Owns synchronous tenant-scoped use cases for domains physically placed in that cell. It independently validates tenant context and authorization; ingress routing is not trusted as authorization.

### Worker pools

Execute durable asynchronous commands/jobs. Pools are separated by workload/security characteristics so slow reporting, webhook delivery or provider synchronization cannot consume all execution capacity.

### Realtime gateway

Maintains authorized long-lived connections and distributes protected realtime signals. Clients recover authoritative state through API resynchronization.

### Automation execution boundary

Runs high-risk scripts/commands outside the primary API runtime with resource, network, credential, target and output controls.

## Consistency model

**Strong consistency is preferred** for identity/session authority, tenant lifecycle/placement changes, authorization policy changes, approvals, commercial/financial mutation and state transitions whose invariant must be immediate.

**Eventual consistency is permitted** for monitoring synchronization, derived AIOps findings, report projections, notifications, public status projections and other explicitly derived views.

Eventual consistency must expose freshness/state where operationally material; it is never an excuse for ambiguous ownership.

## Design completion criteria

A runtime flow is not implementable until it declares:

- owning domain;
- tenant/global scope;
- authorization policy;
- transaction boundary;
- authoritative state;
- asynchronous/retry semantics;
- idempotency identity when retriable;
- failure/degraded behavior;
- audit requirements;
- observability/correlation requirements;
- migration/backward-compatibility implications.
