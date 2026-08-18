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

Each accepted observation has a canonical scoped deduplication identity, conceptually `(observation_identity_scope, observation_id)`, and exactly one declared **durable acceptance boundary** before downstream projections. `observation_identity_scope` is non-null and derived from trusted tenant/global, provider/integration/source and source-generation context as required by the producer contract. A provider-local observation/event/sequence ID is not assumed globally unique across tenants or integrations; the same raw ID in a different authoritative scope remains a different observation. A constant/global scope is allowed only when global uniqueness across all producers for the full deduplication window is explicitly proven.

The implementation may use a durable telemetry ingress journal/log, or a transactional write plus outbox when the transactional store is the acceptance authority. Historical samples, current-state projections and derived domain/integration signals are then produced idempotently from that durable handoff using the persisted canonical identity.

If a specialized telemetry store itself is the durable acceptance authority, it must provide an accepted replay/checkpoint/reconciliation mechanism sufficient to rebuild or repair downstream current-state/signals and enforce/prove the scoped observation identity contract. Provider acknowledgement/ingestion success is not emitted before the durable acceptance boundary succeeds.

### Artifact/object cross-store consistency

Generated binary artifacts SHALL be stored in object/blob storage with authoritative lifecycle metadata/reference in transactional state.

Because PostgreSQL metadata and object bytes cannot be assumed to share an ACID transaction, artifact creation SHALL use a stable `artifact_id`/tenant identity, a monotonic lifecycle/upload generation and a staged lifecycle. The normal pattern commits a discoverable transactional artifact record and durable work intent before object upload, uploads bytes under a stable generation-bound non-public object identity, verifies version/checksum/size, and only then transitions metadata to terminal `READY/AVAILABLE` through a compare-and-set that proves the upload generation is still current. An equivalent storage-native staged manifest/fencing mechanism is acceptable if it provides the same discoverability, stale-writer rejection and reconciliation guarantees.

Every upload attempt is bound to the generation that authorized it. A deletion/erasure transition advances or terminally fences that generation **before** object cleanup begins. An older worker may finish transport I/O, but it MUST NOT be able to publish/finalize its bytes as the current artifact after the generation fence. Cancellation is operational optimization, not correctness authority.

Only terminal-ready metadata whose expected object identity/integrity and current generation have been verified may authorize artifact release. A crash after metadata creation, object upload, metadata finalization, response delivery or object deletion must leave a state that deterministic reconciliation can classify and repair/idempotently complete.

Artifact deletion/erasure likewise uses durable intent/tombstone, metadata-level publisher fencing, idempotent object cleanup and a confirmed outcome. Confirmation is withheld until prior-generation upload/finalize attempts cannot publish and the relevant object/version inventory has been reconciled. If that proof is unavailable, the lifecycle remains `DELETING`/`RECONCILIATION_REQUIRED`; a successful delete API response alone is not proof of erasure.

A mutable stable object key that an already-started stale worker can recreate after deletion is not sufficient unless the selected object-store protocol provides equivalent generation/conditional-write fencing. Immutable/version-specific staging identities plus metadata-controlled publication are the default conceptual model.

Controlled staging/orphan inventory is reconciled/garbage-collected under current retention, erasure and legal-hold policy so protected bytes cannot remain indefinitely outside governance.

Ephemeral cache/pub-sub state SHALL NOT be durable business truth. Short-lived state whose loss changes correctness/security eligibility is not considered disposable merely because it has a TTL; its owning ADR defines required continuity/fail-closed semantics.

## Consequences

### Positive
- strong relational consistency for ITSM, authorization, commercial and configuration workflows;
- database-enforced tenant isolation is available;
- well-understood migration/backup tooling;
- telemetry can evolve independently when volume demands it;
- telemetry specialization does not introduce an implicit crash-prone dual write;
- provider-local telemetry IDs cannot collide across authoritative tenant/source scopes merely because their raw values match;
- object storage can scale binary artifacts without pretending metadata/object creation is atomic;
- artifact bytes remain discoverable/reconcilable for retention, erasure and recovery;
- deletion/erasure cannot be invalidated by a previously authorized upload publishing after the object-delete step.

### Negative / cost
- PostgreSQL becomes a deliberate core dependency;
- pooled cell database remains a shared failure resource;
- data-plane routing/backup and migration need strong operations;
- separate telemetry storage requires durable ingestion identity, scoped dedup namespace, projection checkpoints and reconciliation;
- artifact object storage requires staged lifecycle, upload-generation fencing, reconciliation and governed orphan cleanup;
- deletion confirmation may remain pending while stale upload/object-version state is reconciled.

## Validation

- isolation-policy tests under application roles;
- representative transaction/load benchmark;
- PITR/restore rehearsal;
- telemetry benchmark before selecting retention/storage specialization;
- crash/fault injection at every telemetry handoff boundary proves no accepted observation is silently split between authorities and duplicate retries are idempotent;
- telemetry identity tests reuse the same provider-local observation ID across distinct tenant/source/generation scopes and prove neither legitimate observation suppresses the other, while exact same-scope replay deduplicates;
- artifact fault injection before upload, after upload/before metadata finalize, after finalize/before response and during delete/erasure proves no completed-looking artifact points to absent/wrong bytes and no protected object remains indefinitely undiscoverable/unmanaged;
- artifact deletion is raced against an already-started upload/finalize attempt and proves the delete/erasure transition fences the prior generation before cleanup, stale completion cannot publish/finalize, and `confirmed` is not recorded until prior-generation publisher/object state is reconciled;
- artifact reconciliation validates stable identity, lifecycle generation, object version/checksum and current governance before release or destructive cleanup;
- no application superuser credentials in normal runtime.

## Exit / revisit conditions

Revisit transactional store only with evidence that PostgreSQL cannot satisfy required consistency, scale, residency or operational requirements. Telemetry specialization is expected to be revisited earlier. Object-storage vendor/mechanism may change, but stable artifact identity, staged cross-store lifecycle, stale-writer generation fencing and governed reconciliation remain required.
