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

Admission inherits the canonical parsing/authentication boundaries already accepted in Phase 09 and Phase 10. Reliability controls SHALL NOT introduce a second parser, alternate normalization, or body-field interpretation that can disagree with the owning request/message contract.

Where applicable, admission is staged as follows:

1. enforce canonical transport/framing/raw-byte and parser-complexity bounds that can be established without trusting semantic payload fields;
2. perform the exact upstream authentication/trusted-producer step at the representation required by that contract (including exact-raw authentication only where the accepted ingress profile requires it);
3. establish the canonical request/message envelope and structured interpretation required before protected semantic fields are consumed;
4. establish logical tenant and current placement/admission from trusted authority;
5. derive operation/workload/tenant cost class only from trusted canonical fields and accepted server-side contract metadata;
6. claim concurrency/rate/backlog budget for the resulting authoritative scope/cost class;
7. complete owning schema/contract validation and authorization/policy checks required before effect, preserving the same canonical interpretation;
8. execute durable/effectful work only after all required authority and budget gates pass.

A cheap pre-validation throttle MAY run before full semantic parsing, but it may use only transport facts or already-trusted canonical metadata and SHALL use a conservative class when the final cost/scope is not yet established. Unvalidated payload text, aliases, duplicate members, malformed encodings, caller-selected tenant/source fields, claimed operation names or attacker-controlled cost hints SHALL NOT select a cheaper budget, different tenant bucket, privileged workload class or wider admission scope.

If final canonical validation changes the applicable resource class, the implementation atomically acquires/adjusts to the correct budget before expensive/effectful continuation or rejects; it does not continue under an underpriced provisional claim. Budget adjustment cannot leak protected resource existence or become authorization.

Cheap safe rejection may precede expensive checks, but no early step may reveal protected existence, transform untrusted scope into authority, or create a semantic interpretation different from the owning Phase 09/10 contract.

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

Optional operational telemetry MAY shed only before its declared optional acceptance boundary. Customer monitoring observations that crossed their durable acceptance boundary SHALL NOT be reclassified as optional or dropped under pressure: downstream historical, current-state and signal projections defer from the durable accepted-observation record, preserve checkpoints and stop new intake before overwriting accepted responsibility.

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
- provider throttle affects many tenants simultaneously;
- **`FV-OVER-002` adversarial admission variant:** malformed/duplicate/alias payload fields attempt to select a cheaper cost class, different tenant budget or privileged workload class before canonical validation; the test proves trusted scope remains unchanged, the attempt is bounded/rejected, and unrelated tenants/workloads remain isolated;
- **`FV-OVER-002` provisional-budget variant:** a conservative pre-validation claim is refined to a more expensive canonical cost class; the test proves the correct authoritative budget is acquired or the request is rejected before effect, never continued under the cheaper provisional claim.

These two admission variants are mandatory whenever the selected profile admits work whose final resource class can depend on structured request/message content. They are executions of the existing canonical `FV-OVER-002` and therefore inherit `RB-REL-013` and the profile's four evidence levels; they do not create a new failure enum, OPEN or fault-vector identity.

## Release blockers

Release is blocked by any unbounded accepted backlog/buffer/retry population, any path where one tenant/destination can exhaust unrelated capacity, any overflow rule that loses required evidence, any replay/recovery path that starves current correctness/security authority, any pre-validation cost/scope derivation that lets untrusted payload semantics choose a cheaper or different admission bucket (an `RB-REL-013` isolation failure), or any brownout that weakens an invariant.
