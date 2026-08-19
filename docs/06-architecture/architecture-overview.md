# Architecture Overview

**Status:** accepted  
**Baseline date:** 2026-08-18

## Purpose

This document defines the accepted logical architecture derived from accepted product requirements, invariants, quality scenarios, domain ownership and the threat model. It intentionally separates architectural structure from replaceable infrastructure products.

## Primary drivers

The architecture is shaped by:

- `INV-TENANT-*`: every tenant-scoped path has validated tenant context and trusted placement;
- `INV-DATA-*`: one logical owner per mutable aggregate and no cross-domain database mutation;
- `INV-ASYNC-*`: retriable side effects require idempotency/deduplication and tenant-safe job identity;
- `INV-EXT-*`: provider failure must not become platform-wide failure;
- `QA-AVAIL-001`: one tenant/provider outage must be bounded;
- `QA-SCALE-001`: tenant placement must scale/migrate without changing logical contracts;
- `QA-REC-001`: tenant recovery must be possible without destructive restoration of unrelated tenants;
- `TM-002`, `TM-004`, `TM-012`: async confused-deputy, tenant cache/topic collision and placement races must be designed out.

## Architectural style

JLMIRROR uses a **modular monolith for synchronous business capabilities, independent worker runtimes for asynchronous workloads, and a cell-based data-plane architecture controlled by a small global control plane**.

A bounded context is a code/data ownership boundary, not automatically a deployable service. Distribution is introduced only when a measurable scale, security, runtime, failure-isolation, release-cadence or ownership requirement justifies it.

## Logical topology

```text
Users / API Clients / External Systems
                 |
          Edge / Ingress
                 |
        +--------+--------+
        |                 |
    Web / BFF        Public/API Edge
        |                 |
        +--------+--------+
                 |
        Tenant-aware Routing
                 |
       +---------+----------+
       |                    |
 Control Plane         Data Plane Cells
       |                    |
 tenant identity        Cell A / B / ... / N
 placement                  |
 global catalog             +-- API runtime
 commercial meta            +-- worker runtimes
                            +-- transactional data
                            +-- telemetry storage
                            +-- ephemeral/cache plane
                            +-- object/artifact storage
```

An initial deployment MAY operate one data-plane cell. The architecture MUST NOT encode an assumption that only one cell will ever exist.

## Control plane

The control plane owns global platform-management concerns:

- immutable tenant identity;
- tenant lifecycle and placement intent;
- cell/placement registry;
- global platform configuration/catalog;
- cross-tenant administration metadata;
- global marketplace catalog;
- global commercial/customer metadata where appropriate.

The control plane does not become a universal database for tenant operational state.

## Data-plane cell

A cell is the default blast-radius and horizontal-scale unit for tenant operational workloads. Each cell contains the runtime and data dependencies needed to serve an assigned tenant set.

A cell SHALL support:

- multiple stateless API replicas;
- independently scalable worker classes;
- a transactional database boundary;
- a telemetry-storage boundary that may be specialized independently;
- tenant-safe ephemeral/cache semantics;
- durable asynchronous execution;
- artifact/object storage references;
- cell-local health and observability signals.

Large, regulated or unusually noisy tenants MAY be placed in a dedicated cell without changing tenant-facing identifiers or contracts.

## Domain runtime

The initial synchronous API runtime hosts bounded-context modules inside one deployable application. Modules expose application contracts and own their state/rules. They SHALL NOT mutate another context through database access.

The initial architecture favors one cohesive business deployment because it preserves simple transactions and operational efficiency while boundaries are still evolving. Worker runtimes MAY reuse application/domain packages but SHALL run as separate processes/deployments from the request API where workload or risk requires it.

## Communication

Use the narrowest mechanism that satisfies consistency and latency:

1. **In-process application call** for synchronous same-deployment use cases requiring an immediate answer.
2. **Durable integration event** for state changes that can propagate asynchronously across ownership boundaries.
3. **Durable job/command** for requested background work.
4. **Read model/projection** for expensive cross-domain reporting/experience reads.
5. **External API/webhook** for integrations outside the platform trust boundary.

Network calls are not introduced merely to preserve conceptual domain boundaries.

## Data classes

The architecture distinguishes:

- control-plane metadata;
- tenant transactional state;
- high-volume telemetry/history;
- immutable/tamper-resistant audit evidence;
- ephemeral/cache state;
- generated binary artifacts/exports.

A single storage engine is not required to serve every data class. Transactional ownership remains explicit even when multiple domains are physically co-located.

## Security boundaries

Tenant, principal, permission and correlation context are explicit on every protected unit of work. Physical placement is resolved only from trusted control-plane metadata. Caller-controlled database/schema/cluster identifiers are rejected as routing authority.

Internal network location is not authorization. Workers, caches, queues, WebSocket/realtime gateways, exports, reports and administrative tools remain subject to tenant and permission enforcement appropriate to their boundary.

## Edge boundary

The product MAY use CDN/edge/serverless capabilities for static delivery, WAF/routing and web composition, but core domain execution SHALL NOT depend on edge-runtime limitations. Long-running requests, durable workers, WebSockets/realtime gateways, database sessions, provider connectors and controlled execution require general-purpose runtime capability.

## Evolution

The modular monolith is not a permanent ban on services. A context or workload is extracted only when evidence shows a durable need for independent scaling, fault containment, security isolation, runtime specialization, deployment cadence or ownership. Existing contracts/events are the extraction seam.

## Technology decisions

This overview does not by itself select queue, cache, event-broker, telemetry-store, secrets-manager, object-storage or hosting vendors. Technology is accepted only by an ADR whose requirements and validation gates justify the choice.