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

Because PostgreSQL metadata and object bytes cannot be assumed to share an ACID transaction, artifact creation SHALL use a stable `artifact_id`/tenant identity, monotonic lifecycle/upload, delivery and governance/retention generations, and a staged lifecycle. The normal pattern commits a discoverable transactional artifact record and durable work intent before object upload, uploads bytes under a stable generation-bound non-public object identity, verifies version/checksum/size, and only then transitions metadata to terminal `READY/AVAILABLE` through a compare-and-set that proves the upload generation is still current. An equivalent storage-native staged manifest/fencing mechanism is acceptable if it provides the same discoverability, stale-writer rejection and reconciliation guarantees.

Every upload attempt is bound to the generation that authorized it. A deletion/erasure transition advances or terminally fences that generation **before** object cleanup begins. An older worker may finish transport I/O, but it MUST NOT be able to publish/finalize its bytes as the current artifact after the generation fence. Cancellation is operational optimization, not correctness authority.

Artifact delivery authority is also generation-bound. A download capability is acceptable only when the platform can make it unusable after its artifact delivery/lifecycle generation is fenced, either through an application-mediated current-state/generation check or an equivalent revocable storage/access generation. A direct signed capability that remains usable solely until expiry is not sufficient where current governance requires prompt revocation on deletion/erasure.

Capability redemption is not the end of delivery authorization. A protected download that has begun streaming uses a generation-bound active delivery lease/stream record or an equivalent stream-level fence. When erasure retires the delivery generation, older active streams are aborted, fenced or deterministically drained and their terminal state is observable. A mechanism that can reject only future capability presentations but cannot stop or account for an already-authorized stream cannot support a claim of prompt artifact non-releasability/confirmed erasure.

Legal-retention/legal-hold authority is versioned by a monotonic governance/retention generation or equivalent fencing state. Destructive object cleanup MUST NOT rely on a policy read followed by a later unconditional object deletion. Hold placement/release and destructive cleanup share one logical serialization authority: immediately before an irreversible object-delete/crypto-erasure boundary, the destructive path proves its expected governance generation is still current, no effective hold prohibits deletion and its destructive authorization token/fence is current. A governance mutation that wins that serialization boundary invalidates stale destructive authorization.

This serialization may be implemented by a single artifact-governance owner/process, storage-native conditional retention/version primitives or another mechanism with equivalent stale-delete rejection. The application SHALL NOT keep an ordinary database transaction open across an external object-store call merely to emulate this guarantee. If the platform cannot serialize governance changes with destructive cleanup strongly enough to reject stale deletion authority, destructive cleanup remains blocked/reconciliation-required.

Only terminal-ready metadata whose expected object identity/integrity and current lifecycle/delivery generations have been verified may authorize artifact release. A crash after metadata creation, object upload, metadata finalization, response delivery or object deletion must leave a state that deterministic reconciliation can classify and repair/idempotently complete.

Artifact deletion/erasure uses durable intent/tombstone, metadata-level publication fencing, delivery-capability fencing, active-stream fencing/draining, governance-generation serialization, idempotent object cleanup and a confirmed outcome. Confirmation is withheld until prior-generation upload/finalize attempts cannot publish, prior-generation delivery capabilities cannot start/restart release, prior-generation active streams cannot release further protected bytes, each destructive action observed current governance/hold authority at its irreversible boundary, and the relevant object/version inventory has been reconciled. If that proof is unavailable, the lifecycle remains `ERASURE_FENCING`/`DELETING`/`RECONCILIATION_REQUIRED`; a successful delete API response alone is not proof of erasure.

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
- deletion/erasure cannot be invalidated by a previously authorized upload publishing after the object-delete step;
- governed erasure cannot be bypassed by a previously minted delivery capability or already-active stream that outlives the artifact's current delivery generation;
- a legal hold that wins the governance serialization boundary cannot be bypassed by a stale destructive worker using earlier policy state.

### Negative / cost
- PostgreSQL becomes a deliberate core dependency;
- pooled cell database remains a shared failure resource;
- data-plane routing/backup and migration need strong operations;
- separate telemetry storage requires durable ingestion identity, scoped dedup namespace, projection checkpoints and reconciliation;
- artifact object storage requires staged lifecycle, upload-generation fencing, delivery-generation revocation, active-stream tracking/fencing, governance-generation serialization and governed orphan cleanup;
- deletion confirmation may remain pending while stale upload/object-version/delivery-capability/active-stream/governance state is reconciled.

## Validation

- isolation-policy tests under application roles;
- representative transaction/load benchmark;
- PITR/restore rehearsal;
- telemetry benchmark before selecting retention/storage specialization;
- crash/fault injection at every telemetry handoff boundary proves no accepted observation is silently split between authorities and duplicate retries are idempotent;
- telemetry identity tests reuse the same provider-local observation ID across distinct tenant/source/generation scopes and prove neither legitimate observation suppresses the other, while exact same-scope replay deduplicates;
- artifact fault injection before upload, after upload/before metadata finalize, after finalize/before response and during delete/erasure proves no completed-looking artifact points to absent/wrong bytes and no protected object remains indefinitely undiscoverable/unmanaged;
- artifact deletion is raced against an already-started upload/finalize attempt and proves the delete/erasure transition fences the prior generation before cleanup, stale completion cannot publish/finalize, and `confirmed` is not recorded until prior-generation publisher/object state is reconciled;
- mint a still-valid artifact download capability, begin governed erasure before expiry and prove the older delivery generation/capability cannot start a new release before the artifact is treated as fully non-releasable/erased;
- redeem a capability and begin streaming, then start erasure concurrently and prove the active older-generation delivery is aborted/drained or equivalently fenced before full non-releasability/confirmed erasure is claimed;
- race legal-hold placement against destructive artifact cleanup and prove a governance-generation/hold mutation that wins serialization rejects the stale destructive authorization before object destruction;
- artifact reconciliation validates stable identity, lifecycle/delivery/governance generations, active-stream state, object version/checksum and current governance before release or destructive cleanup;
- no application superuser credentials in normal runtime.

## Exit / revisit conditions

Revisit transactional store only with evidence that PostgreSQL cannot satisfy required consistency, scale, residency or operational requirements. Telemetry specialization is expected to be revisited earlier. Object-storage vendor/mechanism may change, but stable artifact identity, staged cross-store lifecycle, stale-writer generation fencing, delivery-capability/active-stream fencing, governance-generation serialization and governed reconciliation remain required.
