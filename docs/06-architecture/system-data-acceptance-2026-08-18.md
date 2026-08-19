# Canonical Baseline Acceptance — Gate B

**Status:** accepted  
**Acceptance date:** 2026-08-18  
**Acceptance act:** merge of the Gate B governance pull request that introduces this record
**Depends on:** accepted Gate A baseline and accepted ADR-001 through ADR-020

## Purpose

This record formalizes **Gate B** of JLMIRROR design governance. Gate A made Product, Requirements, Domains, Quality, Security, Architecture and ADR-001 through ADR-020 normative upstream authorities. Gate B accepts the reviewed **System Design** and **Data Architecture** layers that refine those authorities into runtime, persistence, consistency, isolation, recovery and validation mechanics.

Gate B acceptance makes the canonical System/Data baseline normative under `docs/00-foundation/document-governance.md`. It does not authorize System/Data documents to redefine an accepted requirement, security rule or ADR; any such contradiction must be resolved by changing the higher authority through the appropriate governance process.

## Accepted scope

Gate B accepts all current canonical documents in:

- `docs/07-system-design/*` — 9 System Design documents;
- `docs/08-data/*` — 10 Data Architecture documents.

The accepted System Design scope includes:

- system/runtime shape and Control Plane/Data Plane Cell boundaries;
- `TenantContext`, placement/admission and relocation-aware routing lifecycle;
- request authentication/authorization and mandatory BFF boundary;
- transaction ownership, idempotency, outbox/inbox and durable async semantics;
- realtime authorization, replay-authority continuity, placement-generation freshness and provider/cache boundaries;
- cross-cell/global operations and failure/degradation behavior;
- the System Design Validation Matrix and its release-blocking invariant tests.

The accepted Data Architecture scope includes:

- logical data planes/classes and PostgreSQL transactional authority;
- logical schemas, ownership and tenant-safe relational integrity;
- tenant isolation/RLS and separate trust rules for platform-owned SQL versus caller-authored SQL;
- data-access/query and schema-evolution/migration rules;
- scoped telemetry observation identity, durable acceptance, monotonic current-state projection and transition-signal durability;
- durable reliability records, idempotency/inbox/outbox and tamper-resistant audit evidence;
- recovery `(R,F]` continuity, revocation/governance/legal-hold/cryptographic-erasure continuity and artifact/object reconciliation;
- artifact publication, delivery and destructive-governance fencing, including active-stream/lease admission races;
- tenant relocation, source write/realtime retirement and recovery-driven cutover gates;
- Data Architecture Readiness Gates D1-D12.

## Acceptance does not mean rollout evidence already exists

The validation matrices, readiness gates, recovery rehearsals, capacity checks and migration gates become **normative criteria** under Gate B. Their acceptance does **not** assert that every production environment, benchmark, migration, restore rehearsal or fault-injection test has already been executed.

A later implementation or release remains blocked wherever the accepted documents require evidence that has not yet been produced. Gate B therefore freezes the design obligations; it does not manufacture operational evidence.

## Core invariants preserved by Gate B

Gate B preserves, among others, these non-negotiable invariants from the accepted upstream baseline and PR #3 hardening:

- trusted logical tenant identity and placement authority; caller-controlled physical routing is never authority;
- multi-layer tenant isolation with server authorization and data-layer enforcement; pooled protected tables carry non-null immutable `tenant_id`;
- caller-authored SQL cannot use a mutable session/GUC value as its tenant authority;
- application-owned local transactions; no external network call is part of an ordinary database transaction;
- transactional outbox and crash-safe idempotency/inbox completion; timeout/lease expiry is not proof an external effect did not occur;
- accepted asynchronous default is at-least-once with stable operation/message identity and idempotent/reconcilable effects;
- protected browser WebSocket admission validates expected Origin, capability, current authorization, replay-authority continuity and atomic shared single-winner consumption before `101 Switching Protocols`;
- a consumed capability remains invalid across replay-authority restart/loss/restore, and missing replay state is never interpreted as unused;
- protected realtime subscriptions remain authorization- and placement-generation-fresh; relocation retires stale source subscriptions and requires target resubscription/resynchronization;
- provider callbacks enforce raw transport bounds before expensive authentication/parsing and remain subject to authenticity, freshness/replay and tenant-binding controls;
- telemetry deduplication uses trusted scoped observation identity distinct from ordering identity; current projections advance monotonically and required transition signals are durably coupled to advancement;
- recovery classifies rollback-subject state separately from safety/accountability/security-authority/governance continuity across `(R,F]`; material uncertainty fails closed or remains quarantined;
- PITR does not silently reverse later revocations, governed erasure/anonymization, legal holds or approved cryptographic-erasure decisions;
- protected artifacts use discoverable staged metadata/object lifecycle, upload-publication fencing, delivery-generation fencing, atomic active-lease admission, active-stream termination/drain and governance-generation serialization at destructive boundaries before confirmed erasure;
- readiness/validation failures classified as release blockers remain blockers regardless of happy-path success.

## Intentionally OPEN after Gate B

Gate B does not select or silently close implementation choices that were intentionally deferred. Known OPEN items include:

- queue technology/vendor;
- cache/replay-authority product or primitive;
- pub/sub or durable event-broker product;
- telemetry physical storage engine beyond the accepted port, identity, ordering, replay and lifecycle semantics;
- object-storage vendor/mechanism beyond the accepted staged lifecycle, integrity, fencing, reconciliation and governance invariants;
- secret-manager/KMS vendor;
- cloud provider and container/orchestrator product;
- exact globally unique ID generation algorithm;
- exact authentication/token protocol details not already constrained by the accepted trust/BFF/realtime model;
- numeric SLO, RPO, RTO, percentile latency, queue-lag, relocation-invalidation and authorization/revalidation thresholds;
- capacity measurements, benchmark-derived specialization/partitioning/sizing thresholds and rollup windows;
- exact HTTP status/header/idempotency/cursor/error representations not already fixed by the accepted baseline, which belong to Phase 09 API & Contracts. The protected-WebSocket success/rejection semantics around `101 Switching Protocols` are already fixed and are not reopened;
- exact broker acknowledgement, partitioning and transport mechanics, which belong to Phase 10 Events/Async Contracts and may not weaken the accepted inbox/outbox/idempotency semantics;
- artifact provenance/signing and software-supply-chain release-signing policy deferred by `TM-014`;
- future service extraction decisions governed by ADR-020 and measured evidence.

An item explicitly marked OPEN, deferred or "to be defined" elsewhere remains unresolved even if it is not repeated in this inventory.

## Review evidence

Gate B is based on reviewed and already-merged design content rather than newly invented architecture:

- **PR #3** performed iterative System/Data hardening across tenant isolation, realtime authorization/replay, idempotency/inbox/outbox, telemetry identity/order, recovery continuity, governance/erasure, artifact lifecycle and relocation. Its final Codex review of head `fbf03a562b` reported no major issues; it was squash-merged as `67fbd78b9f3af469e669a67a9bf0f003cffdecd4`.
- **Gate A / PR #4** subsequently accepted the upstream Product/Requirement/Quality/Security/Architecture/ADR authorities after governance reconciliation and a final clean Codex review. Gate A was squash-merged as `9ee612f317c42c651a989c0c240f8b3fd43118b0`.
- This Gate B pull request must itself receive a clean review focused on hierarchy, status/prose consistency, preservation of OPEN decisions, absence of semantic weakening and correctness of the Phase 09/10 boundary before merge.

Changing `Status` alone is not sufficient evidence of acceptance. The Gate B diff is expected to preserve the hardened System/Data semantics, with only governance-status/prose adjustments and this acceptance record.

## Phase boundary after Gate B

After Gate B is accepted and merged, **Phase 09 — API & Contracts may begin** as a new, separately reviewed normative design phase. Phase 09 derives external/API representations from the accepted upstream requirements, security, ADRs, System Design and Data Architecture; it may refine representation but may not weaken their invariants.

Gate B does **not** start **Phase 10 — Events / Async Contracts**. Phase 10 remains a separate contract boundary following the accepted Phase 09 work and must preserve the already accepted asynchronous consistency/idempotency/inbox/outbox semantics.

Gate B also does not authorize implementation to outrun unresolved evidence gates. Production release still requires all applicable accepted readiness/validation criteria.

## Change discipline

After Gate B acceptance:

- semantic changes to System/Data invariants require an ADR/RFC/governance change appropriate to their impact and may require synchronized changes to upstream accepted authorities;
- Phase 09/10 contracts may specialize representation and transport details but cannot silently redefine tenant isolation, authorization, consistency, recovery, governance, artifact or telemetry semantics;
- implementation is subordinate to the accepted design, not a source of truth that silently overrides it;
- newly discovered contradictions are governance defects and are resolved before downstream implementation depends on them.

## Validation / rollout

Gate B is a documentation-governance transition only. It performs no production deployment, schema migration, data copy, tenant relocation, secret/key operation, recovery cutover or artifact lifecycle action.

Operational evidence required by the accepted System Design Validation Matrix and Data Architecture Readiness Gates is produced and reviewed in the implementation/release phases where the relevant capability exists.