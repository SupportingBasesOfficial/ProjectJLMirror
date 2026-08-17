# Architecture Principles

## AP-01 — Tenant isolation is an invariant

Tenant separation is enforced in multiple layers. No component may treat tenant identity as optional for tenant-scoped work.

## AP-02 — Business domains own state and rules

Each mutable business concept has one logical owner. Other domains interact through explicit application contracts, queries, commands, or events rather than directly mutating another domain's storage.

## AP-03 — External systems are adapters

Zabbix, ITSM products, payment providers, notification providers, identity providers, and future sources are integrations behind stable ports. Their native models must not become the platform's ubiquitous language.

## AP-04 — Architecture precedes infrastructure choice

Requirements define capabilities such as durable jobs, distributed revocation, time-series storage, or real-time delivery. Specific technologies are selected through ADRs and may be replaced when requirements change.

## AP-05 — Strong consistency is selective

Identity, authorization, privileged administration, approvals, financial state, and critical mutations favor strong consistency. Monitoring projections, analytics, reports, AIOps, and notifications may use eventual consistency when explicitly designed for it.

## AP-06 — Failure propagation is bounded

Failure of one tenant, external provider, worker class, report, webhook destination, or optional capability must not cause avoidable global failure.

## AP-07 — Retry requires idempotency

Any operation that can be retried must define duplication semantics. Durable asynchronous processing assumes at-least-once behavior unless a stronger guarantee is proven.

## AP-08 — Observability is part of the contract

Important requests, jobs, events, integration calls, and privileged actions must be traceable through structured telemetry with correlation identifiers and tenant-safe metadata.

## AP-09 — Security is enforced at every trust boundary

Authentication, authorization, tenant resolution, input validation, data access controls, secrets handling, network/runtime isolation, and audit are complementary layers.

## AP-10 — The API is not the domain

HTTP, WebSocket, queues, databases, caches, and frameworks are delivery or infrastructure mechanisms. Core policies and use cases remain independent of them where practical.

## AP-11 — Migrations are product changes

Schema and data migrations are versioned, observable, resumable where necessary, and designed for rolling deployment. Destructive change follows expand/migrate/contract patterns.

## AP-12 — Scale is multidimensional

Capacity is modeled across tenants, resources, metrics, events, concurrent connections, jobs, integrations, storage growth, and query patterns. Scaling decisions use measured bottlenecks rather than generic claims.

## AP-13 — Public output is a projection

Public status, exports, reports, webhooks, and marketplace-facing data expose deliberate contracts, not direct internal table representations.

## AP-14 — Privileged capability has a smaller trust envelope

SQL consoles, script execution, data transfer, tenant relocation, and global administration use dedicated authorization, audit, resource limits, and execution boundaries.

## AP-15 — Evolution is designed in

Module boundaries are explicit enough to permit selective service extraction, cluster placement, provider replacement, and storage specialization without rewriting business semantics.