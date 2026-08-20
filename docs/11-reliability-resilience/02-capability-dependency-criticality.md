# Capability and Dependency Criticality

**Status:** proposed baseline  
**Phase:** 11 — Reliability & Resilience

## Purpose

This document inventories logical capability/dependency classes and defines their minimum failure-containment obligations. Criticality is about correctness and authority impact, not a vendor tier or a single availability number.

## Criticality dimensions

Each profile SHALL classify all applicable dimensions:

| Dimension | Question |
|---|---|
| Authority | Can impairment change who/what is allowed to act? |
| Correctness | Can impairment duplicate, lose, reorder or corrupt a protected logical effect? |
| Confidentiality | Can fallback disclose tenant, secret or governed data? |
| Durability | Can accepted work/evidence become unrecoverable? |
| Blast radius | Is impact tenant, destination, workload, cell, control-plane or fleet-wide? |
| Recoverability | What continuity evidence is required before resumption? |
| Optionality | Can the capability be unavailable without invalidating core operations? |
| Amplification | Can retry/fanout/backlog turn local failure into global pressure? |

The result is a profile, not a single score. Numeric availability targets belong to Phase 12/business evidence.

## Criticality classes

### `authority_critical`

Loss or uncertainty can grant stale access, placement, publication, delivery, erasure or retry authority. It fails closed for new protected decisions unless a separately accepted current local verification path proves authority.

Examples: current authorization/revocation, tenant placement admission, replay-consumption authority, artifact governance/delivery-generation fences, producer/source generations.

### `transactional_truth_critical`

Required for authoritative mutation or for proving a protected result. Affected mutations fail closed. Reachable replicas or restored copies require current authority/fence before writes.

Examples: cell transactional data, control-plane placement/lifecycle state, co-resident inbox/effect and idempotency completion records.

### `continuity_critical`

May be short-lived or auxiliary in normal operation, but loss changes duplicate/replay/recovery eligibility. It is not disposable cache state.

Examples: message-content equivalence evidence, external operation outcomes, replay epochs, dedup receipts over the supported horizon, immutable webhook obligation/generation evidence.

### `durable_progress_critical`

Tracks accepted work/process state. Transport lag may delay execution, but accepted durable responsibility must remain discoverable.

Examples: outbox, process managers, quarantine and reconciliations.

### `derived_reconstructable`

Can be lost and rebuilt without changing authoritative truth or current authority. Rebuild is bounded and isolated from core workloads.

Examples: ordinary performance cache, many read projections and ephemeral realtime fanout.

### `optional_isolated`

Failure may remove an optional capability while core authoritative operations continue.

Examples: reporting/AIOps derived workloads when not on a critical decision path.

An implementation SHALL NOT downgrade a dependency from an authority/continuity class to derived merely because it is stored in a cache, broker or TTL-based product.

## Capability/dependency map

| Capability/dependency | Authority / truth | Minimum degradation | Required isolation | Resumption prerequisite |
|---|---|---|---|---|
| Control Plane placement/lifecycle | current tenant placement, cell admission intent, lifecycle deny state | bounded stable admitted traffic may continue only from trusted versioned state; topology changes stop | control plane vs cells; tenant lifecycle operations | current authority and generation/fence proven |
| Cell transactional store | tenant transactional truth and co-resident reliability state | affected cell mutations unavailable/fail closed | cell is primary blast-radius unit | authoritative store/failover generation current; recovery gates pass |
| Security/session authority | current authentication/authorization/revocation | deny new protected decisions unless current local verification is explicitly valid | principal/tenant/scope | current non-regressing generation/deny state proven |
| Placement/reference cache | bounded trusted copy, not original authority | safe last-known-good only within profile and destination-cell admission | cache key tenant/version; protected fallback concurrency | freshness/admission remains provable |
| Performance cache | derived data | bypass to authority only when safe and bounded; otherwise degrade | tenant/operation bulkhead | stampede controlled; authority healthy |
| Replay/capability consume state | single/bounded-use correctness authority | protected admission fails closed | capability epoch/scope | continuity recovered or new trusted epoch invalidates old capabilities |
| Secret/KMS authority | secret/key release and cryptographic usability | operations needing unavailable secrets fail; no plaintext fallback | runtime/cell/tenant/secret namespace | current key/secret authority and rotation state proven |
| Outbox/publication | committed async intent | publication pauses; originating commit remains valid | cell/producer/contract | dispatcher resumes same immutable message identity |
| Broker/job transport | delivery transport, not business truth | async progress pauses; bounded backlog | workload/tenant/consumer | durable intent/process truth reconciled before progress |
| Consumer inbox/effect | duplicate/effect completion authority | duplicate-sensitive execution stops if evidence incomplete | consumer contract/source/tenant | outcome and content equivalence proven |
| External provider | external truth may be unavailable/slow/ambiguous | provider-dependent capability fails fast/circuits; stored state only with explicit staleness | tenant/integration/provider/destination | provider and local operation truth reconciled |
| Realtime fanout/gateway | advisory delivery only | live updates pause/shed; authoritative API/read state remains | connection/tenant/topic/cell | fresh auth/placement and resync |
| Webhook delivery | external disclosure obligation when Product-enabled | destination-specific attempts pause/quarantine; business fact not rolled back | tenant/subscription/destination generation | immutable obligation and destination-generation eligibility proven |
| Telemetry plane | high-volume historical/derived input by accepted class | bounded buffer/backpressure/drop only by declared data policy | telemetry vs transactional core; tenant/source | data-class policy and ordering/dedup state safe |
| Object/artifact storage | protected bytes; metadata authority is separate | generation/releasability remains explicit; no false available state | tenant/artifact/generation | metadata/object integrity and governance fences reconcile |
| Reporting/AIOps workers | optional/derived workload unless Product says otherwise | delay/shed/isolate | separate queue/pool/budget | backlog bounded and dependencies healthy |
| Automation/SQL/admin/recovery | privileged effects | fail closed when scope/authority/isolation unavailable | dedicated trust envelope | current authority, target scope, audit and resource policy proven |

## Failure-domain hierarchy

Reliability containment SHALL reason at least across:

```text
operation/request
  -> principal or credential
  -> tenant
  -> integration/provider/destination
  -> consumer contract / workload class
  -> runtime role
  -> data-plane cell
  -> control-plane capability
  -> future region/residency scope (OPEN topology)
  -> fleet
```

A profile explicitly identifies where containment is possible and where a shared critical dependency legitimately expands blast radius. Hidden fleet-wide dependencies are release blockers.

## Dependency graph obligations

Every capability SHALL declare:

- hard synchronous dependencies;
- durable asynchronous dependencies;
- optional/derived dependencies;
- authority dependencies;
- recovery-continuity dependencies;
- external-provider dependencies;
- amplification fanout and retry paths;
- fallback path and the authority used by that fallback.

A fallback is invalid when it:

- depends recursively on the same failed authority;
- increases load on an already saturated dependency without a concurrency bound;
- changes tenant, authorization, data-classification or consistency semantics;
- turns stale/missing evidence into permission;
- requires an unaccepted Product behavior.

## Ownership and escalation handoff

Phase 11 assigns logical ownership. Phase 15 later assigns named operational owners and escalation paths. Until Phase 15, every row still identifies the owning capability/process so failure policy cannot become orphan infrastructure behavior.

## Evidence requirements

Implementation conformance SHALL later prove:

- failure injection at each declared domain contains impact at or below the declared blast radius;
- shared dependency impairment does not bypass tenant/current-authority checks;
- cache/fallback paths remain bounded under concurrency;
- continuity-critical evidence loss causes fail-closed/reconciliation behavior;
- optional workload failure does not consume core authority capacity;
- second-cell behavior does not change logical contract identity.

