# Failure and Degradation Profiles

**Status:** proposed baseline  
**Phase:** 11 — Reliability & Resilience

## Purpose

This document defines canonical failure classes and allowed degradation modes. Provider- or vendor-native errors map into these classes; they do not become platform semantics.

## Failure taxonomy

Every observed failure SHALL be classified as one or more of:

| Failure class | Meaning | Default eligibility |
|---|---|---|
| `unavailable` | dependency cannot accept required work | fail/degrade by profile; not automatic retry |
| `slow_or_timed_out` | local observation exceeded a bound; remote outcome may be unknown | reconcile if effect may have crossed authority |
| `throttled` | trusted dependency requests reduced rate/delay | bounded retry honoring validated hint |
| `saturated` | local/dependency capacity is exhausted or unsafe | shed/backpressure; prevent amplification |
| `partitioned` | participants cannot establish current shared authority | authority-sensitive paths fail closed |
| `stale` | data/generation/placement/authorization is older than required | re-resolve current authority; do not act stale |
| `duplicate` | same trusted scoped identity and equivalent immutable content | observe established result/no-op according to contract |
| `identity_conflict` | same scoped identity denotes different immutable content | integrity failure/quarantine; never duplicate success |
| `out_of_order_or_gap` | sequence expectation is violated | contract-specific buffer/reconcile/resync; no global assumption |
| `contract_permanent` | unsupported/malformed/semantically invalid contract | terminal/quarantine; no infinite retry |
| `policy_denied` | current authorization/tenant/plan/governance rejects work | terminal/wait/compensate by owner; retry cannot create authority |
| `poison_or_unknown` | repeated/unclassified failure without safe automatic resolution | bounded attempts then quarantine |
| `external_outcome_ambiguous` | an external/cross-authority effect may have happened | durable reconciliation required |
| `recovery_continuity_blocked` | `(R,F]` evidence is incomplete or contradictory | protected/effectful admission remains blocked |
| `compromised_or_untrusted` | integrity/authentication/trust cannot be established | fail closed; isolate and preserve evidence |
| `governance_blocked` | erasure, legal hold, retention or disclosure authority is uncertain | no re-exposure; destructive deletion blocked |

`unknown` SHALL NOT silently map to `transient_retryable`.

## Degradation modes

### `fail_closed`

Reject or stop protected work because current authority/correctness cannot be proven. Required for authorization, placement admission, replay uniqueness, protected erasure/deletion and ambiguous duplicate-sensitive recovery.

### `fail_fast`

Return/record a bounded dependency failure without waiting through cascading retry. Suitable for unavailable external providers after the accepted attempt/circuit policy.

### `stale_tolerant`

Serve previously stored/derived state only when Product/contract permits it, its source and freshness are explicit, it cannot authorize mutation/disclosure, and the read path remains tenant-safe.

### `queued_or_deferred`

Persist durable accepted responsibility and delay execution. It is allowed only when backlog, retention, deadline, authority recheck and recovery semantics are defined.

### `shed_or_reject`

Refuse new work or optional work to preserve core capacity. Shedding happens before expensive/irreversible processing where possible and follows tenant/principal/workload fairness policy.

### `reconciliation_blocked`

Keep a durable operation/message/process state non-executable until owning authority establishes outcome. It is not a transient retry loop.

### `resync_required`

Discard/ignore non-authoritative realtime/projection continuity and require authoritative snapshot/resynchronization under current authorization/placement.

### `capability_unavailable`

Disable a declared capability while unrelated capabilities continue. A generic platform-wide outage is not implied.

## Fail-open policy

The phrase `fail open` SHALL NOT be used without naming the exact authority and effect.

Permitted availability fallback is narrowly limited to cases such as bypassing a **performance cache** to an authoritative source under protected concurrency. That fallback does not bypass authorization, placement, tenant isolation, idempotency, audit, retention or recovery gates.

The following SHALL NOT fail open:

- current authorization/revocation/tenant-access evaluation;
- tenant placement/admission generation for protected work;
- replay/single-use capability consumption or continuity;
- message identity/content-equivalence integrity;
- irreversible external-effect ambiguity;
- protected artifact releasability/delivery-generation admission;
- legal-hold/erasure destructive authorization;
- recovery continuity required for protected/effectful resumption;
- secret/key authority.

## Staleness contract

Any stale-tolerant profile SHALL declare:

- authoritative source and projection/cache identity;
- freshness marker/source generation;
- maximum accepted staleness as an evidence-driven OPEN numeric;
- operations allowed while stale;
- operations prohibited while stale;
- tenant/data-classification rules;
- invalidation/fencing conditions;
- behavior when freshness cannot be proved.

Stale data cannot be presented as newly confirmed provider/current state. A stale positive authorization or stale no-hold/no-erasure state never grants authority.

## Degradation monotonicity

Degradation SHALL be monotonic with respect to safety:

- losing evidence cannot increase eligible operations;
- losing a dependency cannot widen tenant/principal scope;
- recovery cannot lower a generation/fence;
- circuit reset cannot make ambiguous work executable;
- backlog expiry cannot turn unknown outcome into effect absence;
- failover cannot make two writers authoritative;
- brownout cannot disable required audit/dedup/security checks.

## Brownout semantics

A brownout profile may reduce or disable optional/reconstructable work such as expensive reports, derived AIOps or non-authoritative realtime detail to preserve core operations.

Every brownout declares:

- entry/exit authority and evidence requirements (signals defined in Phase 12);
- optional capability set;
- preserved core capability set;
- prohibition against hidden Product/data-semantics changes;
- backlog cancellation/defer/resume behavior;
- compatibility behavior for clients;
- test vectors proving required security/recovery work still runs.

Brownout is not permission to return fabricated success or silently drop durable accepted work.

## Failover and split-brain safety

Reachability or health alone does not elect authority. A failover profile SHALL require:

- one logical current generation/term/fence;
- stale-writer rejection at the effect authority;
- no simultaneous protected write admission by old and new authority;
- reconciliation of in-flight/ambiguous operations;
- placement/source/realtime/webhook/artifact generation retirement as applicable;
- recovery quarantine when continuity cannot be proven.

Exact quorum, consensus, lease, database-HA or traffic-manager mechanisms remain OPEN. The single-current-authority and stale-writer-rejection properties are fixed.

## Degradation profile template

Each capability fills:

```text
profile_id:
trigger/failure classes:
affected authority and data:
allowed mode:
prohibited behavior:
scope/blast radius:
client/consumer semantic result:
durable state transition:
retry/reconciliation owner:
capacity/budget behavior:
recovery/resumption gate:
required evidence and fault vectors:
compatibility and blockers:
OPEN numerics/mechanisms:
```

## Required assurance

Tests SHALL prove that each mapped failure reaches one declared mode; no framework exception, timeout or broker redelivery falls through to an implicit default. Unmapped correctness/security failures are release-blocking until classified.

