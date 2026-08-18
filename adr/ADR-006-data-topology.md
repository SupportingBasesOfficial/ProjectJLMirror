# ADR-006 — Data Topology and Transactional Storage

**Status:** proposed  
**Date:** 2026-08-17  
**Reversibility:** costly/high-risk for core transactional store

## Context

JLMIRROR requires relational business invariants, transactions, authorization metadata, auditability, tenant-aware policies and evolving domain state. It also produces high-volume telemetry whose retention/cardinality/query profile can differ dramatically from transactional workloads. Binary reports/exports should not bloat the transactional database. Because artifact metadata and object bytes live in separate persistence authorities, artifact lifecycle also needs an explicit crash/reconciliation contract rather than an implicit cross-store transaction.

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

### Artifact/object cross-store consistency

Generated binary artifacts SHALL be stored in object/blob storage with authoritative lifecycle metadata/reference in transactional state.

Because PostgreSQL metadata and object bytes cannot be assumed to share an ACID transaction, artifact creation SHALL use a stable `artifact_id`/tenant identity and staged lifecycle. The normal pattern commits a discoverable transactional artifact record and durable work intent before object upload, uploads bytes under a stable non-public object identity, verifies version/checksum/size, and only then transitions metadata to terminal `READY/AVAILABLE`. An equivalent storage-native staged manifest is acceptable if it provides the same discoverability/reconciliation guarantees.

Only terminal-ready metadata whose expected object identity/integrity has been verified may authorize artifact release. A crash after metadata creation, object upload, metadata finalization, response delivery or object deletion must leave a state that deterministic reconciliation can classify and repair/idempotently complete.

Artifact deletion/erasure likewise uses durable intent/tombstone plus idempotent object cleanup and confirmed outcome; metadata is not simply discarded first while protected object bytes become undiscoverable. Controlled staging/orphan inventory is reconciled/garbage-collected under current retention, erasure and legal-hold policy so protected bytes cannot remain indefinitely outside governance.

Ephemeral cache/pub-sub state SHALL NOT be durable business truth. Short-lived state whose loss changes correctness/security eligibility is not considered disposable merely because it has a TTL; its owning ADR defines required continuity/fail-closed semantics.

## Consequences

### Positive
- strong relational consistency for ITSM, authorization, commercial and configuration workflows;
- database-enforced tenant isolation is available;
- well-understood migration/backup tooling;
- telemetry can evolve independently when volume demands it;
- telemetry specialization does not introduce an implicit crash-prone dual write;
- object storage can scale binary artifacts without pretending metadata/object creation is atomic;
- artifact bytes remain discoverable/reconcilable for retention, erasure and recovery.

### Negative / cost
- PostgreSQL becomes a deliberate core dependency;
- pooled cell database remains a shared failure resource;
- data-plane routing/backup and migration need strong operations;
- separate telemetry storage requires durable ingestion identity, projection checkpoints and reconciliation;
- artifact object storage requires staged lifecycle, reconciliation and governed orphan cleanup.

## Validation

- isolation-policy tests under application roles;
- representative transaction/load benchmark;
- PITR/restore rehearsal;
- telemetry benchmark before selecting retention/storage specialization;
- crash/fault injection at every telemetry handoff boundary proves no accepted observation is silently split between authorities and duplicate retries are idempotent;
- artifact fault injection before upload, after upload/before metadata finalize, after finalize/before response and during delete/erasure proves no completed-looking artifact points to absent/wrong bytes and no protected object remains indefinitely undiscoverable/unmanaged;
- artifact reconciliation validates stable identity, object version/checksum and current governance before release or destructive cleanup;
- no application superuser credentials in normal runtime.

## Exit / revisit conditions

Revisit transactional store only with evidence that PostgreSQL cannot satisfy required consistency, scale, residency or operational requirements. Telemetry specialization is expected to be revisited earlier. Object-storage vendor/mechanism may change, but stable artifact identity, staged cross-store lifecycle and governed reconciliation remain required.
