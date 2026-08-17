# ADR-018 — Backup, Restore and Disaster-Recovery Model

**Status:** proposed  
**Date:** 2026-08-17  
**Reversibility:** costly

## Context

`INV-RECOVERY-001` requires tested restoration. Cells reduce blast radius but create multiple recovery units. Tenant-level operator error must not require destructive restore of every tenant. RPO/RTO are not yet numerically committed.

Drivers: `QA-REC-001`, `INV-RECOVERY-001`, `FR-OPS-003`, `AP-11`.

## Decision

Recovery is designed at multiple scopes:

1. **control plane:** encrypted backups/PITR as supported by selected store, with tested restoration of tenant/placement/catalog metadata;
2. **cell transactional store:** automated backups plus point-in-time recovery capability;
3. **tenant logical recovery:** tooling to restore/export a tenant into an isolated verification namespace/environment before controlled reintroduction;
4. **object artifacts:** versioning/retention according to data policy where needed;
5. **telemetry:** backup/retention strategy based on business value, cost and re-ingest possibility, separate from transactional assumptions.

Restore procedures SHALL be rehearsed. Backup existence without a successful restore test is not accepted recovery capability.

RPO/RTO numerical objectives remain OPEN until SLO/business-tier work. Production commitments cannot be made before those objectives and corresponding restore measurements are accepted.

## Consequences

### Positive
- recovery matches cell and tenant blast radius;
- tenant operator error does not automatically imply fleet rollback;
- evidence-based RPO/RTO becomes possible.

### Negative / cost
- logical tenant restore tooling is non-trivial for pooled data;
- restore rehearsals consume operational capacity.

## Validation

Scheduled restore tests SHALL cover control plane, a representative cell and tenant-scoped recovery. Integrity, authorization, placement and audit consistency are validated before reintroduction.

## Exit / revisit conditions

Storage-specific backup technology may change; multi-scope tested recovery remains.
