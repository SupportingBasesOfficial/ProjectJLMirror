# Data Architecture Overview

**Status:** proposed baseline  
**Primary ADRs:** ADR-003, ADR-006, ADR-008, ADR-018, ADR-019

## Purpose

JLMIRROR separates data by authority, workload and lifecycle rather than forcing every record into one physical pattern.

## Data planes/classes

### Control Plane transactional data

Global authoritative metadata required to operate the SaaS:

- tenants and lifecycle;
- cells and placement;
- platform/global administration;
- global identity/session authority where applicable;
- global catalog/marketplace metadata;
- platform-global commercial/customer relationship.

### Cell transactional data

Authoritative tenant-owned business state for Organization & Access, Monitoring current state, Alerting, ITSM, Automation, Infrastructure, AIOps result metadata, FinOps, Reporting definitions/projections, Integrations and governed operations.

### Telemetry data

High-volume append-oriented history such as metric samples, event history, logs/traces/capacity observations. It is tenant-scoped but may use a specialized physical store behind a stable port.

### Artifact/object data

Generated reports, exports, attachments and other large binary artifacts. Transactional storage owns metadata/reference; object storage owns bytes.

### Ephemeral data

Caches, rate counters, realtime fanout, circuit state and other reconstructable/short-lived state. It is not durable business truth.

### Audit/governance data

Append-oriented accountability/evidence with restricted mutation privileges and policy-driven retention.

## Physical topology

```text
Control Plane PostgreSQL
  +-- platform/global identity/commercial metadata

Cell A PostgreSQL                Cell B PostgreSQL
  +-- pooled tenant state          +-- pooled tenant state
  +-- outbox/inbox/idempotency     +-- outbox/inbox/idempotency
  +-- tenant audit metadata        +-- tenant audit metadata
        |                                 |
        +--> telemetry port               +--> telemetry port
        +--> object storage               +--> object storage
        +--> ephemeral port               +--> ephemeral port
```

A dedicated-cell tenant uses the same logical model. Initial infrastructure may physically co-locate components, but code/contracts depend on logical boundaries rather than co-location.

## PostgreSQL role

PostgreSQL is the canonical transactional store selected by ADR-006. It owns relational invariants and transactionally consistent business state. It is not required to retain unlimited high-volume telemetry or binary artifacts.

## Tenant identity rule

Every pooled tenant-owned record contains immutable logical `tenant_id` as a first-class column even when tenant could be inferred from a parent. Redundant tenant identity is intentional: it enables RLS, composite relationship validation, indexing, export/recovery and relocation safety.

## Identifier rule

Internal aggregate IDs are stable, opaque and independent of provider/customer-readable identifiers. Exact generation strategy is implementation-level until accepted separately, but IDs must remain globally safe for relocation/service extraction.

Human-readable numbers/slugs are separate attributes and may change without changing internal identity.

## Time rule

Persistent event/business timestamps use timezone-aware instants (PostgreSQL `timestamptz` or equivalent). Business-local timezone is stored as configuration/reference when local-calendar interpretation is needed.

## Monetary rule

Money uses exact decimal/numeric representation plus ISO currency identity. Floating-point money is prohibited.

## JSON rule

JSON/JSONB is appropriate for provider payload metadata, versioned event payloads and genuinely flexible extension data. Core business entities/invariants are modeled relationally rather than hidden in unvalidated generic JSON.
