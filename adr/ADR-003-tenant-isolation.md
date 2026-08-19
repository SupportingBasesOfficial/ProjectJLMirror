# ADR-003 — Tenant Isolation Model and Isolation Classes

**Status:** accepted  
**Date:** 2026-08-17  
**Reversibility:** high-risk/costly once data volume grows

## Context

Tenant isolation is an invariant across API, persistence, cache, async, realtime, reporting and administration. A schema/database per tenant maximizes physical separation but creates migration/pool/operational fleet cost. Pure application filtering is insufficient. A single isolation model also cannot economically fit every customer size/regulatory profile.

Drivers: `INV-TENANT-001..003`, `SEC-TEN-001..003`, `SEC-EXEC-004`, `QA-ISO-001`, `TM-001`, `TM-004`, `TM-012`.

## Options considered

### A — Application filtering only
Rejected. A missing filter becomes a data breach.

### B — Schema/database per tenant by default
Good isolation, but schema fleet migrations, connection management and high-volume telemetry make very large tenant fleets expensive.

### C — Pooled cell tenancy with data-layer enforcement plus optional dedicated isolation class
Shared domain tables include immutable logical `tenant_id`; application authorization and database-enforced tenant policies constrain access. Tenants needing stronger/noisy-neighbor isolation can be assigned dedicated data-plane capacity/cell.

## Decision

Select **Option C** as the default model.

Within a shared cell, protected tenant records SHALL carry an immutable tenant identifier and SHALL be constrained by server-side authorization plus database-layer tenant isolation. When PostgreSQL is used (ADR-006), tenant-scoped tables SHALL use RLS or an equivalently enforceable database policy as a defense-in-depth layer.

The normal application/worker path MAY establish a transaction-local tenant context because SQL executed there is platform-owned and tenant selection has already been resolved through trusted application logic. That mutable session mechanism SHALL NOT be the sole tenant authority for a surface that executes caller-authored SQL.

Interactive/direct SQL against pooled protected data MUST use a tenant binding the SQL principal cannot replace—for example a tenant-bound database principal whose tenant mapping is protected from that principal, or an equivalently mediated/physically isolated query surface. If an implementation cannot prove an unforgeable tenant binding for arbitrary SQL, the console SHALL NOT receive direct access to pooled protected base tables.

Isolation classes:

- **pooled:** tenant shares cell data infrastructure under strict logical/data-layer isolation;
- **dedicated-cell:** tenant receives isolated cell runtime/data resources;
- additional regulated/residency classes MAY be introduced through ADR/RFC.

Physical placement SHALL NOT alter the logical tenant ID.

## Consequences

### Positive
- migrations occur per cell/schema fleet rather than thousands of tenant schemas;
- connection pooling and telemetry ingestion scale more naturally;
- RLS/data-policy testing gives independent defense against missing application predicates;
- dedicated isolation remains possible without separate product semantics;
- privileged query tooling cannot treat a caller-writable session variable as tenant authority.

### Negative / cost
- pooled database errors can have multi-tenant impact;
- RLS/policy correctness becomes critical and must be tested continuously;
- tenant-level restore/export needs dedicated tooling instead of simple schema restore;
- interactive SQL requires a separate tenant-binding design rather than reuse of the application GUC alone.

## Validation

Automated isolation tests SHALL cover API, repository, cache, queue, realtime, reporting, export and administration. Known Tenant B identifiers must return no protected data when executed in Tenant A context.

Interactive SQL tests SHALL attempt `SET`, `set_config`, role changes, session-authorization changes and other supported session mutation paths. None may change the tenant authority used by the query policy.

## Exit / revisit conditions

Revisit if required regulatory guarantees mandate database-per-tenant, or if benchmark/operational evidence shows pooled policy overhead or blast radius is unacceptable.

## Migration / rollout

New schemas/tables include tenant key and policy from inception. Dedicated-cell tenants use the same logical contracts to avoid forks.