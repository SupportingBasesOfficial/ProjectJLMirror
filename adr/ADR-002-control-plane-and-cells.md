# ADR-002 — Control Plane and Cell-Based Data Plane

**Status:** proposed  
**Date:** 2026-08-17  
**Reversibility:** costly

## Context

JLMIRROR must scale tenant count/workload, contain failures and permit tenant placement/migration without exposing physical routing to callers. One global operational stack creates an ever-growing blast radius. Database-per-tenant for every tenant creates fleet-management cost. Region/service sharding without a placement abstraction leaks topology into application code.

Drivers: `FR-PLAT-001..005`, `FR-MON-004`, `QA-AVAIL-001`, `QA-SCALE-001`, `QA-REC-001`, `TM-012`.

## Options considered

### A — Single global data plane
Operationally simple early, but blast radius and database/worker scaling become global.

### B — Tenant-per-stack
Strong isolation but expensive provisioning, upgrades and observability at high tenant counts.

### C — Global control plane plus cells
A small control plane owns tenant identity/placement; each cell serves a bounded set of tenants and contains their operational runtimes/data dependencies.

## Decision

Select **Option C**.

JLMIRROR SHALL have a global logical control plane and one or more data-plane cells. The initial production system MAY run a single cell, but tenant-facing code MUST resolve placement through control-plane metadata and MUST NOT encode the cell as part of tenant identity.

A cell is the normal horizontal scaling and failure-containment unit. Dedicated cells MAY be used for tenants requiring stronger isolation or disproportionate capacity.

## Consequences

### Positive
- bounded provider/worker/database blast radius;
- controlled capacity expansion;
- tenant relocation becomes an operational process rather than application rewrite;
- natural isolation class for noisy or regulated tenants.

### Negative / cost
- requires highly reliable placement metadata and routing;
- cross-cell administrative/reporting operations must be deliberately designed;
- migration/cutover semantics become a first-class concern.

## Validation

- single-cell deployment works without special-case code;
- adding a second cell requires configuration/placement, not contract changes;
- tenant A failure/load in one cell does not materially affect unrelated cell;
- placement lookup latency and availability meet SLO targets to be established.

## Exit / revisit conditions

Revisit if measured workload demonstrates cells add cost without meaningful isolation, or if regulatory/data-residency needs require a stronger hierarchy such as regions above cells.

## Migration / rollout

Begin with control-plane placement abstraction even with one cell. Introduce additional cells only after automated provisioning, health, migration and observability controls exist.
