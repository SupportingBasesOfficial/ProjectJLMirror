# ADR-006 — Data Topology and Transactional Storage

**Status:** proposed  
**Date:** 2026-08-17  
**Reversibility:** costly/high-risk for core transactional store

## Context

JLMIRROR requires relational business invariants, transactions, authorization metadata, auditability, tenant-aware policies and evolving domain state. It also produces high-volume telemetry whose retention/cardinality/query profile can differ dramatically from transactional workloads. Binary reports/exports should not bloat the transactional database.

Drivers: `FR-MON-003`, `FR-GOV-003`, `INV-DATA-*`, `INV-ASYNC-001`, `QA-PERF-001`, `QA-REC-001`, `SEC-TEN-002`.

## Options considered

### Core transactional store
- document database: flexible but weaker fit for relational workflow/invariants;
- distributed SQL from day one: powerful but unnecessary operational complexity before evidence;
- PostgreSQL: mature ACID transactions, relational constraints, indexing, JSON when appropriate, RLS and strong ecosystem.

## Decision

Select **PostgreSQL** as the canonical transactional database technology for control-plane and cell transactional domain state.

Within each cell, pooled tenant tables use immutable tenant IDs and database isolation policies per ADR-003. Database roles for application, migration and privileged administration remain distinct.

High-volume telemetry SHALL be behind a separate storage port/plane. PostgreSQL MAY be used initially where measured load fits, but no ADR currently requires all metric/log/trace history to remain in the transactional cluster. A time-series/columnar specialization requires benchmark evidence and a dedicated ADR.

### Cross-store telemetry consistency

When historical telemetry and transactional current-state live in different persistence authorities, ingestion SHALL NOT perform an uncoordinated dual write and then acknowledge success.

Each accepted observation has a stable `observation_id` (or equivalent source identity) and exactly one declared **durable acceptance boundary** before downstream projections. The implementation may use a durable telemetry ingress journal/log, or a transactional write plus outbox when the transactional store is the acceptance authority. Historical samples, current-state projections and derived domain/integration signals are then produced idempotently from that durable handoff.

If a specialized telemetry store itself is the durable acceptance authority, it must provide an accepted replay/checkpoint/reconciliation mechanism sufficient to rebuild or repair downstream current-state/signals. Provider acknowledgement/ingestion success is not emitted before the durable acceptance boundary succeeds.

Generated binary artifacts SHALL be stored in object/blob storage with metadata/reference in transactional state.

Ephemeral cache/pub-sub state SHALL NOT be durable business truth.

## Consequences

### Positive
- strong relational consistency for ITSM, authorization, commercial and configuration workflows;
- database-enforced tenant isolation is available;
- well-understood migration/backup tooling;
- telemetry can evolve independently when volume demands it;
- telemetry specialization does not introduce an implicit crash-prone dual write.

### Negative / cost
- PostgreSQL becomes a deliberate core dependency;
- pooled cell database remains a shared failure resource;
- data-plane routing/backup and migration need strong operations;
- separate telemetry storage requires durable ingestion identity, projection checkpoints and reconciliation.

## Validation

- isolation-policy tests under application roles;
- representative transaction/load benchmark;
- PITR/restore rehearsal;
- telemetry benchmark before selecting retention/storage specialization;
- crash/fault injection at every telemetry handoff boundary proves no accepted observation is silently split between authorities and duplicate retries are idempotent;
- no application superuser credentials in normal runtime.

## Exit / revisit conditions

Revisit transactional store only with evidence that PostgreSQL cannot satisfy required consistency, scale, residency or operational requirements. Telemetry specialization is expected to be revisited earlier.
