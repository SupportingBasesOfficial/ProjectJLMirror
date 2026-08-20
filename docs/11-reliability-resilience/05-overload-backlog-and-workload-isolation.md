# Overload, Backlog and Workload Isolation

**Status:** proposed baseline  
**Phase:** 11 — Reliability & Resilience

## Purpose

This document defines behavior when demand exceeds safe capacity. It prevents overload, tenant skew, replay, recovery or retry from collapsing unrelated capability and prevents queues from becoming unbounded promises.

## Overload invariants

- Every admitted resource-consuming action has an owning budget dimension.
- No queue, buffer, retry population, batch, response body, parser expansion or fanout is implicitly unlimited.
- One tenant, provider, destination, consumer, report, replay or recovery job cannot consume unrelated fleet capacity without an explicitly accepted shared critical dependency.
- Backlog age/size and drain capacity are evidence obligations even though Phase 12 owns their signal/SLI definitions.
- Overload protection cannot discard authoritative mutation, required audit/outbox, dedup/content-equivalence or recovery-continuity evidence.
- Security/recovery control work is not starved behind ordinary bulk work; exact reservation/priority numerics remain OPEN.
- Shedding/degradation is deterministic by workload class and never depends on undocumented framework defaults.

## Admission order

Where applicable, work is admitted in this order:

1. canonical transport/message bounds;
2. authentication/trusted producer validation;
3. logical tenant and current placement/admission checks;
4. operation/workload/tenant cost class;
5. concurrency/rate/backlog budget claim;
6. canonical request/message validation;
7. owning authorization/policy;
8. durable/effectful execution.

Cheap safe rejection may precede expensive checks, but no early step may reveal protected existence or transform untrusted scope into authority.

## Overload states

Each capability supports explicit states equivalent to:

```text
normal
pressure
saturated
brownout
recovery_drain
admission_closed
```

Exact names and triggers are Phase 12/implementation details. Phase 11 fixes allowed behavior and invariants in each state.

### `pressure`

Reduce optional fanout/prefetch/batch/concurrency, preserve core work, and prevent retry amplification.

### `saturated`

Reject/shed/defer new work according to profile. Do not accept work whose durable responsibility cannot be met.

### `brownout`

Disable declared optional/reconstructable work. Never weaken authorization, audit, idempotency, tenant isolation, recovery or governance checks.

### `recovery_drain`

Prioritize bounded reconciliation/recovery work without allowing it to starve current security authority or create duplicate effects. Ordinary effectful admission may remain closed.

### `admission_closed`

Reject new protected/effectful work while allowing narrowly scoped status/recovery controls under current authority.

## Backlog contract

Every durable backlog SHALL declare:

```text
logical backlog owner
work/message contract and data classification
tenant/source/destination isolation dimensions
admission policy
maximum size/age/cost as OPEN evidence-driven bounds
deadline/expiry semantics
retry population semantics
priority/fairness classes
drain concurrency and downstream budgets
poison/quarantine path
replay/recovery interaction
retention/erasure/legal-hold behavior
overflow behavior
permanent evidence and release blockers
```

An accepted durable intent cannot be silently dropped because a broker TTL expired. Expiry transitions to an owning-domain terminal/compensation/reconciliation outcome with evidence.

## Overflow behavior

Overflow choices are contract-specific:

- reject before durable acceptance;
- persist authoritative intent but delay transport publication;
- shed optional/reconstructable projection;
- coalesce only when the contract proves semantic equivalence and preserves required transitions;
- quarantine poison/unsupported work;
- cancel/expire under an explicit process policy;
- block protected effectful admission during recovery uncertainty.

`drop oldest`, `drop newest`, `last write wins` or unchecked coalescing are prohibited defaults for durable facts, commands, audit, security invalidation, governance decisions or recovery evidence.

## Fairness and starvation

Fairness SHALL be evaluated across:

- tenant, including large-tenant skew;
- integration/provider/destination;
- consumer/workload class;
- operation cost class;
- cell;
- core vs optional vs recovery/security work.

A scheduling mechanism may be weighted or hierarchical, but it SHALL prove:

- a noisy tenant/destination cannot starve unrelated scopes;
- a large legitimate tenant has an explicit capacity/isolation path rather than evading safety controls;
- poison ordered work does not head-of-line block unrelated ordering scopes;
- replay/backfill cannot starve current production correctness work;
- recovery does not starve current deny/revocation/governance propagation;
- fairness state loss does not create authority or erase accepted work.

Exact weights, quotas and reservation values remain OPEN.

## Load shedding classes

### Never shed after accepted responsibility without owner transition

- authoritative mutation commit;
- required audit/outbox intent;
- accepted durable job/process state;
- security revocation/deny propagation required for current authority;
- reliability/content-equivalence evidence;
- governance erasure/hold/fence evidence.

### May shed before acceptance by explicit profile

- optional report/AIOps request;
- non-authoritative realtime detail/fanout;
- reconstructable cache warmup/projection refresh;
- low-priority provider poll when current stored state remains valid under Product policy.

### Data-policy governed loss

High-volume telemetry may backpressure, buffer or drop only according to its accepted data-class contract. Transactional core capacity must remain protected, and loss/gaps are explicit rather than represented as complete data.

## Batching

Batching SHALL preserve individual logical identities unless the contract defines one atomic batch command.

Profiles declare maximum count/bytes/complexity as OPEN bounds, partial failure and acknowledgement semantics, tenant/source mixing restrictions, ordering/duplicate behavior, poison-item isolation, memory/decompression bounds and recovery behavior.

A partial batch failure cannot mark unprocessed items completed.

## Fanout and amplification

Every one-to-many path declares amplification and containment for global operations, event consumers, realtime subscriptions, external destinations, replay/backfill and provider transitions.

Fanout SHALL use bounded pagination/admission, persisted progress where durable, partial-failure state and tenant/destination budgets. A global message that causes unrestricted per-tenant work without explicit enumeration/authority is prohibited.

## Cost runaway controls

Every expensive capability identifies external calls, compute time, data scanned, output bytes, storage growth, retry attempts and fanout count. Phase 11 requires bounds and evidence points; exact pricing/quotas belong to Product/capacity evidence.

Cost controls SHALL NOT become covert authorization or silently discard required work. A limit transitions to a stable rejected/waiting/partial/terminal state owned by the capability.

## Recovery and backlog

After restore/PITR:

- queue depth/offset is not business truth;
- restored pending work reconciles against process/effect state;
- backlog redelivery preserves stable identity and content-equivalence evidence;
- completed `(R,F]` effects do not become eligible because receipts rolled back;
- unknown outcomes remain quarantine/reconciliation-blocked;
- recovery drain is isolated from ordinary workload and has a bounded convergence plan.

## Required fault/load vectors

- one tenant generates disproportionate provider sync/load;
- one webhook destination is slow while others remain healthy;
- broker outage accumulates durable outbox backlog then recovers;
- poison ordered message blocks only its declared ordering scope;
- replay/backfill competes with live events;
- cache loss causes synchronized authoritative-store fallback;
- Control Plane recovers while cells revalidate placement;
- realtime reconnect storm after gateway/fanout loss;
- telemetry plane outage approaches buffer bounds;
- recovery reconciliation spans many tenants in one cell;
- large report/export output reaches storage/worker limits;
- provider throttle affects many tenants simultaneously.

## Release blockers

Release is blocked by any unbounded accepted backlog/buffer/retry population, any path where one tenant/destination can exhaust unrelated capacity, any overflow rule that loses required evidence, any replay/recovery path that starves current correctness/security authority, or any brownout that weakens an invariant.

