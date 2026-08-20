# Phase 11 — Reliability & Resilience Overview

**Status:** proposed baseline  
**Phase:** 11 — Reliability & Resilience  
**Authority anchor:** `main@6d8550b67ddeb6ca1ecac71df36a1185cd3b3c92`  
**Accepted predecessor:** Phase 10 — Events / Async Contracts and the accepted post-Phase-10 roadmap

## Purpose

Phase 11 defines deterministic platform behavior under failure, overload, duplication, delay, partial loss, stale authority and ambiguous outcomes. It converts accepted Product, Quality, Security, ADR, System Design, Data Architecture and Phase 09/10 contracts into enforceable reliability profiles without selecting a cloud, broker, orchestrator, database-HA product, retry library, circuit-breaker library or physical topology.

The phase answers:

> When a capability or dependency is impaired, what work remains eligible, what must stop, what may degrade, what authority remains current, what evidence must survive and what proves safe resumption?

It does not claim that a future runtime has passed the required tests. It defines the obligations that implementation, release and runtime evidence must later satisfy.

## Normative inheritance

This package SHALL preserve the complete accepted repository authority. In particular:

- tenant isolation remains invariant across normal, degraded and recovery paths;
- logical tenant/resource/message/operation identity remains independent of physical topology and provider identity;
- network, broker, cache, process or node presence never creates trust;
- application use cases own authoritative local transaction boundaries;
- required domain mutation, audit intent and outbox evidence remain atomic where accepted;
- asynchronous delivery remains at least once unless an end-to-end business proof establishes more;
- broker acknowledgement follows durable consumer responsibility;
- timeout, redelivery, process death and lease expiry do not prove effect absence;
- ambiguous external outcomes reconcile by stable operation identity before retry eligibility;
- current placement and current authorization are re-established where accepted contracts require them;
- replay, restore, relocation and failover cannot resurrect retired authority or blindly repeat protected effects;
- Phase 09 owns realtime connection/subscription authority; Phase 10 owns async/realtime message representation;
- outbound webhooks remain Product-gated and, when enabled, retain immutable delivery meaning and destination-generation binding;
- secrets never enter ordinary payloads, logs, traces, metrics labels, quarantine views or audit snapshots;
- recovery preserves `(R,F]`, `uncertainty != absence` and recovery quarantine.

A Phase 11 rule that appears to conflict with accepted upstream authority is invalid until the owning authority is explicitly amended through governance.

## Reliability principles

### REL-P-01 — Eligibility is established, not inferred

Work is executable only when its owning authority can prove current eligibility. Missing state, expired time, process death, queue redelivery or a circuit transition cannot manufacture permission.

### REL-P-02 — Failure propagation is bounded

Failure of one tenant, provider, destination, consumer contract, workload class, cell or optional capability SHALL NOT consume unrelated global capacity or invalidate unrelated authority.

### REL-P-03 — Degradation preserves invariants

A degraded mode may reduce freshness, throughput or optional capability. It SHALL NOT weaken tenant isolation, authorization, audit, idempotency, message-integrity comparison, recovery fences, erasure/retention governance or secret handling.

### REL-P-04 — Every retry has a safety proof and a budget

Retry requires a stable logical identity, an idempotent/reconcilable effect model, a classified failure and bounded aggregate resource consumption. Unclassified or ambiguous work is not automatically retryable.

### REL-P-05 — Backpressure is explicit

Every asynchronous or fanout boundary declares how it admits, delays, sheds, rejects, quarantines or expires work. Unlimited queues, buffers, concurrency and retry are prohibited.

### REL-P-06 — Redundancy does not equal authority

Replicas, failover candidates and restored copies do not become authoritative merely because they are reachable. Authority transfers require current generation/fence and continuity evidence.

### REL-P-07 — Recovery continuity is part of normal design

Each reliability profile declares what evidence survives restore and what must be reconciled through `(R,F]` before work resumes. Recovery is not postponed to Phase 15.

### REL-P-08 — Observability is required, not designed here

Every property declares evidence and signal requirements. Phase 12 owns the vendor-neutral signal taxonomy, SLI/SLO/health meanings, telemetry contracts, alerting and SRE operating model.

## Reliability decision model

Every capability/dependency profile SHALL declare:

```text
profile_id
owning capability
tenant/global scope
authority and durable truth
dependency/failure domain
failure classes
allowed degradation modes
prohibited fallbacks
retry eligibility and stable identity
timeout/deadline semantics
concurrency/bulkhead/backpressure dimensions
ambiguity and reconciliation owner
recovery continuity state and resumption gate
security/privacy constraints
capacity/performance/cost dimensions
required fault vectors
permanent evidence
compatibility class and release blockers
OPEN mechanism/numeric decisions
```

The normative semantic manifest is defined in `08-reliability-semantic-manifest.md`.

## Package structure

| Document | Normative responsibility |
|---|---|
| `01-reliability-resilience-overview.md` | authority, principles, ownership and phase boundary |
| `02-capability-dependency-criticality.md` | capability/dependency inventory, criticality and blast-radius ownership |
| `03-failure-degradation-profiles.md` | failure taxonomy, degradation classes and fail-open/fail-closed rules |
| `04-timeout-retry-circuit-bulkhead-backpressure.md` | deadline, retry, circuit, bulkhead and propagation semantics |
| `05-overload-backlog-and-workload-isolation.md` | overload admission, bounded queues, fairness and noisy-neighbor containment |
| `06-ambiguity-reconciliation-and-recovery-continuity.md` | ambiguity state, reconciliation, `(R,F]`, failover and safe resumption |
| `07-capability-resilience-profiles.md` | required behavior for control plane, cells, providers, async, realtime, webhooks, artifacts and privileged workloads |
| `08-reliability-semantic-manifest.md` | enforcement-oriented manifest and consistency rules |
| `09-reliability-validation-and-fault-matrix.md` | fault vectors, evidence classes and release blockers |
| `10-compatibility-and-change-classification.md` | semantic compatibility and change governance |
| `11-traceability-and-evidence.md` | upstream/downstream traceability and evidence ownership |
| `12-phase-11-open-decisions-and-blockers.md` | OPEN registry, closure gates and acceptance blockers |
| `13-security-privacy-threat-model-delta.md` | changed trust boundaries, threat actors, confused-deputy analysis and security/privacy delta |

All common enforcement artifacts required by the roadmap are mandatory. An empty registry or no-applicable-case entry carries explicit evidence; an artifact itself cannot be omitted or marked `not_applicable`.

## Ownership model

Phase 11 uses logical capability ownership, not future team names:

- an owning domain/application capability owns its business effect and compensation/reconciliation semantics;
- Platform Management owns tenant placement/cell lifecycle authority already accepted upstream;
- each consumer contract owns its inbox/effect completion and quarantine behavior;
- each provider adapter owns provider-specific error normalization and retry mapping behind platform classes;
- artifact/governance owners control release, erasure and delivery-generation eligibility;
- Security authority owns current authorization/revocation/deny decisions and their fail-closed behavior;
- each configuration-owning capability owns accepted content/schema/applicability while Platform Management owns governed distribution and generation evidence;
- the customer-monitoring ingestion capability owns the durable accepted-observation boundary, scoped identity, replay/checkpoint continuity and monotonic projection contract; it is distinct from optional operational telemetry;
- each protected-effect capability owns its mandatory audit boundary with Security/Data policy; optional telemetry cannot weaken or substitute that boundary;
- Phase 12 later defines diagnostic signal ownership;
- Phase 13 later maps logical roles to runtime isolation;
- Phase 15 later assigns operational/on-call/runbook authority.

No generic worker, queue administrator, infrastructure retry mechanism or AI-assisted diagnostic system may decide whether a protected ambiguous effect is safe to repeat or whether any protected gate is eligible to pass.

## Phase boundary

Phase 11 SHALL define:

- semantic failure and degradation behavior;
- retry eligibility and prohibited retry classes;
- boundedness and isolation dimensions;
- ambiguity/reconciliation ownership;
- safe failover/recovery prerequisites;
- evidence and fault-test obligations;
- compatibility consequences and blockers.

Phase 11 SHALL NOT select or finalize:

- observability backend, signal transport, dashboard, alerting/paging product or numeric SLO/error budget;
- runtime/orchestrator/cloud/service-mesh/database-HA/broker/cache/KMS product;
- physical region/cell topology, replica count, quorum or failover mechanism;
- CI/CD, artifact-signing or progressive-delivery implementation;
- incident command, staffing, runbooks or break-glass procedure;
- unsupported Product behavior, including outbound webhook families or active-inline artifacts.

## Mandatory overlays

Every reliability profile SHALL include:

1. **Security / Privacy:** authority, revocation, tenant isolation, secret/data classification, abuse, disclosure and recovery-governance continuity.
2. **Capacity / Performance / Cost:** bounded resource dimensions, tenant skew, amplification paths, measurement points and evidence-driven closure gates.
3. **Verification / Assurance:** deterministic tests, concurrency/fault injection, chaos/load/skew vectors, evidence provenance and release blockers.

Recovery continuity, semantic compatibility and OPEN-decision discipline are transversal and cannot be delegated to a final section only.

## Acceptance effect

If accepted, this package fixes the Phase 11 semantic reliability baseline and unlocks Phase 12 only. It does not select technology, authorize implementation, prove runtime reliability, authorize production or merge itself.
