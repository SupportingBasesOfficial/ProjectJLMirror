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

Examples: current authorization/revocation, tenant placement admission, configuration content/applicability/generation, replay-consumption authority, artifact governance/delivery-generation fences, producer/source generations.

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

| Capability/dependency | `reliability_profile_id` | `profile_version` | Authority / truth | Minimum degradation | Required isolation | Resumption prerequisite |
|---|---|---|---|---|---|---|
| Control Plane placement/lifecycle | `rel.control-plane-placement` | `1` | current tenant placement, cell admission intent, lifecycle deny state | bounded stable admitted traffic may continue only from trusted versioned state; topology changes stop | control plane vs cells; tenant lifecycle operations | current authority and generation/fence proven |
| Cell transactional store | `rel.cell-transactional-store` | `1` | tenant transactional truth and co-resident reliability state | affected cell mutations unavailable/fail closed | cell is primary blast-radius unit | authoritative store/failover generation current; recovery gates pass |
| Security/session authority | `rel.security-session-authority` | `1` | current authentication/authorization/revocation | deny new protected decisions unless current local verification is explicitly valid | principal/tenant/scope | current non-regressing generation/deny state proven |
| Placement/reference cache | `rel.placement-reference-cache` | `1` | bounded trusted copy, not original authority | safe last-known-good only within profile and destination-cell admission | cache key tenant/version; protected fallback concurrency | freshness/admission remains provable |
| Performance cache | `rel.performance-cache` | `1` | derived data | bypass to authority only when safe and bounded; otherwise degrade | tenant/operation bulkhead | stampede controlled; authority healthy |
| Replay/capability consume state | `rel.replay-consume-state` | `1` | single/bounded-use correctness authority | protected admission fails closed | capability epoch/scope | continuity recovered or new trusted epoch invalidates old capabilities |
| Secret/KMS authority | `rel.secret-key-authority` | `1` | secret/key release and cryptographic usability | operations needing unavailable secrets fail; no plaintext fallback | runtime/cell/tenant/secret namespace | current key/secret authority and rotation state proven |
| Configuration authority/distribution | `rel.configuration-authority` | `1` | accepted configuration content, applicability, rollout and generation | last-known-good only when schema, signature/authority, scope and generation remain valid; unsafe or contradictory rollout stops | tenant/cell/runtime-role/config namespace and rollout generation | one accepted generation, target coverage and rollback/forward-recovery state proven |
| Outbox/publication | `rel.outbox-publication` | `1` | committed async intent | publication pauses; originating commit remains valid | cell/producer/contract | dispatcher resumes same immutable message identity |
| Broker/job transport | `rel.broker-job-transport` | `1` | delivery transport, not business truth | async progress pauses; bounded backlog | workload/tenant/consumer | durable intent/process truth reconciled before progress |
| Consumer inbox/effect | `rel.consumer-inbox-effect` | `1` | duplicate/effect completion authority | duplicate-sensitive execution stops if evidence incomplete | consumer contract/source/tenant | outcome and content equivalence proven |
| External provider | `rel.external-provider` | `1` | external truth may be unavailable/slow/ambiguous | provider-dependent capability fails fast/circuits; stored state only with explicit staleness | tenant/integration/provider/destination | provider and local operation truth reconciled |
| Realtime fanout/gateway | `rel.realtime-fanout` | `1` | advisory delivery only | live updates pause/shed; authoritative API/read state remains | connection/tenant/topic/cell | fresh auth/placement and resync |
| Webhook delivery | `rel.webhook-delivery` | `1` | external disclosure obligation when Product-enabled | destination-specific attempts pause/quarantine; business fact not rolled back | tenant/subscription/destination generation | immutable obligation and destination-generation eligibility proven |
| Optional telemetry plane | `rel.telemetry-plane` | `1` | non-authoritative historical/derived input by accepted optional class | bounded shed/reject; never block business truth or claim completeness | telemetry vs transactional core; tenant/source | loss/classification and ordering/dedup state explicit |
| Accepted customer telemetry | `rel.customer-telemetry-acceptance` | `1` | canonical customer observation identity and durable acceptance responsibility feeding historical/current-state/signal projections | unavailable intake is bounded `queued_or_deferred` without acknowledgement; pre-acceptance saturation may `shed_or_reject` without acknowledgement; accepted observations remain durable and post-acceptance saturation keeps their projection obligations `queued_or_deferred` without optional-loss downgrade | tenant/integration/source/generation and acceptance vs projection workloads | acceptance/checkpoint watermarks, monotonic projection token and durable transition intent reconcile |
| Mandatory audit plane | `rel.mandatory-audit-plane` | `1` | mandatory accountability evidence at an accepted protected-effect boundary | affected protected effect fails closed when durable audit responsibility cannot be established | audit vs optional telemetry; tenant/subject/effect/source | durable audit responsibility and continuity proven before affected effect admission |
| Object/artifact storage | `rel.artifact-storage` | `1` | protected bytes; metadata authority is separate | generation/releasability remains explicit; no false available state | tenant/artifact/generation | metadata/object integrity and governance fences reconcile |
| Reporting/AIOps workers | `rel.reporting-derived` | `1` | optional/derived workload unless Product says otherwise | delay/shed/isolate | separate queue/pool/budget | backlog bounded and dependencies healthy |
| Automation/SQL/admin/recovery | `rel.privileged-operations` | `1` | privileged effects | fail closed when scope/authority/isolation unavailable | dedicated trust envelope | current authority, target scope, audit and resource policy proven |

Every ID above SHALL resolve to exactly one versioned record in the canonical catalog in `07-capability-resilience-profiles.md`. A row without a resolvable profile is a Phase 11 acceptance blocker.

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
