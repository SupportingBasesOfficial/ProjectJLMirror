# Cross-Cell and Global Operations

**Status:** accepted  
**Primary ADRs:** ADR-002, ADR-004, ADR-019

## Principle

Cross-cell visibility does not create cross-cell mutation transactions. Each cell remains authoritative for tenant operational state assigned to it.

## Platform administration

Global operations use the Control Plane to discover target tenant placement, then invoke explicit tenant-scoped operations in the authoritative cell under a privileged, audited operation context.

The platform administrator cannot obtain authority by connecting directly to arbitrary cell storage with normal runtime credentials.

## Global search/reporting

Global administrative analytics/reporting SHOULD use asynchronous projections or a dedicated analytics/read plane rather than synchronous distributed joins across every cell database.

Projection records carry source cell, tenant, source version/time and classification metadata. Highly sensitive fields are excluded unless the product requirement explicitly needs them.

## Cross-cell orchestration

When one global process affects multiple tenants/cells (for example fleet configuration rollout), use a persisted control-plane operation:

```text
Global operation
   |
   +-- target tenant/cell task A -> status
   +-- target tenant/cell task B -> status
   +-- target tenant/cell task N -> status
   |
   v
aggregate progress / partial failure / resume
```

Partial failure is first-class. The orchestrator records which targets completed, failed, were skipped or need retry.

## No shared mutable singleton

Cells do not depend on a single mutable in-memory process for locks, schedulers or placement. Leadership/coordination mechanisms, when required, must be recoverable and safe across process restart.

## Tenant-local scheduling

Tenant recurring jobs should execute in/for the tenant's authoritative cell. After relocation, schedule ownership follows current placement; duplicate schedules are prevented by operation identity/lease/deduplication semantics rather than assuming one immortal scheduler.

## Data residency

A future region hierarchy may sit above cells. Contracts use logical tenant identity and data classification so residency changes do not require business-domain ID changes.
