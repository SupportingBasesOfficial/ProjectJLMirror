# ADR-004 — Tenant Placement, Routing and Relocation

**Status:** accepted  
**Date:** 2026-08-17  
**Reversibility:** costly

## Context

Tenant identity must remain stable while physical deployment changes. Async workers must not trust caller-supplied database routing. Relocation can create split-brain writes if stale requests/jobs continue using old placement.

Drivers: `FR-PLAT-001..003`, `INV-TENANT-003`, `INV-ASYNC-002`, `QA-SCALE-001`, `TM-002`, `TM-012`.

## Decision

The control plane SHALL maintain a trusted **Tenant Placement** record keyed by immutable tenant ID. Placement contains logical fields such as:

- `tenant_id`;
- `cell_id`;
- `isolation_class`;
- `placement_version`;
- lifecycle state (`provisioning`, `active`, `migrating`, `suspended`, `decommissioning`, `failed` or equivalent);
- residency/region intent where required.

Callers, browser requests, API keys, jobs and events SHALL carry logical tenant identity, never unrestricted connection strings, schemas, cluster addresses or secret material as routing authority.

Each protected unit of work resolves/validates placement. Workers reject stale placement versions when a migration policy requires it.

Tenant relocation SHALL use a state machine with admission control, copy/synchronization, verification, cutover, stale-writer rejection and rollback/recovery steps.

## Consequences

### Positive
- stable identity across cells/regions;
- stale-worker race can be detected;
- placement data becomes auditable and manageable;
- jobs survive physical topology changes.

### Negative / cost
- control-plane availability/caching policy is critical;
- relocation requires operational orchestration;
- every runtime must implement the placement contract consistently.

## Validation

- forged physical routing is ignored/rejected;
- stale job during migration cannot write to retired placement;
- placement cache invalidation/cutover is tested under concurrency;
- migration produces no split authoritative state.

## Exit / revisit conditions

Revisit only if tenant placement becomes static by product constraint, which is contrary to current scale/recovery requirements.