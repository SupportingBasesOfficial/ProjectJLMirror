# Timeout, Retry, Circuit, Bulkhead and Backpressure Profiles

**Status:** proposed baseline  
**Phase:** 11 — Reliability & Resilience

## Purpose

This document defines how latency and failure-control mechanisms preserve correctness and bound amplification. It fixes semantics while leaving libraries, algorithms and numeric values OPEN until evidence supports them.

## End-to-end deadline model

An operation SHALL have one logical deadline/budget profile when bounded completion is required. Nested components consume the remaining budget; they do not each restart an independent full timeout that can multiply total latency without bound.

A timeout profile declares:

- operation class and owner;
- connect/acquire/first-byte/request/overall stages as applicable;
- caller deadline propagation rules;
- server-side work cancellation or continuation semantics;
- whether an effect may have crossed an authority boundary;
- durable operation state after caller response loss;
- retry eligibility and evidence;
- numeric values as evidence-driven OPENs.

Untrusted caller/provider deadline hints are validated and bounded. A deadline is not authorization and cannot bypass durable completion or reconciliation.

## Timeout truth rule

```text
local timeout = local observation
local timeout != remote failure
local timeout != effect absence
```

If an external or cross-authority effect may have been accepted, the stable operation enters reconciliation. If no effect boundary was crossed and durable state proves no commit, retry may be eligible under the profile.

## Retry eligibility

A new attempt is eligible only when all required conditions hold:

1. failure is classified retryable by the owning contract;
2. stable logical message/job/operation identity is preserved;
3. the effect is idempotent, deduplicated, CAS-protected or reconcilable;
4. current tenant placement and authorization/policy are re-established where required;
5. prior outcome is not ambiguous, or reconciliation explicitly authorizes the next attempt;
6. operation deadline and aggregate retry budget remain valid;
7. workload/tenant/dependency concurrency budget admits the attempt;
8. retry does not target retired generation or stale destination authority.

Failure to prove any safety condition yields terminal, wait or reconciliation state—not a blind retry.

## Aggregate retry budget

Retry budgets apply across the complete call/work chain, not independently per layer.

The profile SHALL bound, using OPEN evidence-driven numerics:

- total attempts across client, API, worker, connector and transport layers;
- total elapsed retry window;
- maximum concurrent attempts per operation/tenant/dependency;
- queued retry volume and age;
- cumulative cost/bytes/provider calls;
- hedged/speculative attempts if ever allowed;
- recursion/redrive/replay amplification.

Lower layers SHALL NOT retry an operation already retried by an upper layer unless the combined policy proves the aggregate bound and identity safety.

## Backoff and jitter

Backoff SHALL:

- reduce synchronized retry pressure;
- be bounded by deadline and retention/recovery horizon;
- honor trusted provider hints only after validation;
- avoid immediate reset merely because a process restarted;
- avoid identical schedules across a large tenant fleet;
- preserve priority/fairness without starving recovery/security control work.

Exact curve, jitter distribution, caps and attempt counts remain OPEN.

## Circuit semantics

A circuit is a local/dependency-protection mechanism, not business truth, authorization or proof of provider outcome.

Every circuit profile declares:

- protected dependency and scope (tenant/integration/destination/cell/workload);
- failures counted and failures excluded;
- behavior while open;
- probe/half-open concurrency semantics;
- interaction with retry/backlog and trusted throttling hints;
- state-loss behavior;
- fallback authority;
- required evidence and numeric OPENs.

Circuits SHALL NOT be globally shared where a tenant/destination-specific failure would unnecessarily block unrelated traffic. Circuit state loss may reduce protection temporarily only within a bounded conservative policy; it cannot make ambiguous effects retryable or restore stale authority.

## Bulkhead semantics

Bulkheads SHALL exist at the dimensions required to prevent correlated exhaustion:

- cell;
- workload/consumer contract;
- tenant and large-tenant isolation class;
- provider/integration/destination;
- operation/resource-cost class;
- privileged automation/parser/admin/recovery runtime class;
- realtime connection/subscription class;
- optional vs core work.

A bulkhead profile defines queue/admission/concurrency ownership, fairness, overflow mode, cancellation/drain behavior and resumption. Exact pool sizes remain OPEN.

One generic global worker pool for provider sync, webhook delivery, reporting, replay, recovery and dangerous automation is prohibited because it defeats accepted isolation.

## Concurrency admission

Concurrency control happens before expensive work or external effects where possible. Admission identity is scoped so a noisy actor cannot evade limits by changing superficial transport identifiers.

Required dimensions include as applicable:

- principal/API credential;
- tenant;
- route/operation/contract;
- provider/integration/destination;
- worker class/consumer contract;
- cell;
- global emergency bound;
- data/result size and expected cost.

Global emergency throttles MAY preserve platform safety but SHALL NOT erase durable accepted work or bypass tenant fairness/audit.

## Backpressure propagation

Each boundary declares how inability to accept more work propagates:

```text
caller admission
  -> durable intent/outbox
  -> transport backlog
  -> consumer concurrency
  -> downstream dependency
  -> result/reconciliation
```

Allowed responses include bounded reject, defer, shed, pause consumption, reduce concurrency, circuit, or quarantine according to the contract.

Forbidden behaviors include:

- unbounded memory buffering;
- accepting durable work with no drain/expiry/recovery policy;
- acknowledging before durable responsibility to reduce queue pressure;
- dropping required audit/outbox/reliability evidence;
- propagating provider overload into fleet-wide retry;
- buffering secrets or unrestricted confidential payloads outside accepted stores;
- using broker offsets as the only business progress evidence.

## Hedging/speculation

Hedged or duplicate requests are prohibited for effectful operations unless the owning contract proves a single logical effect through stable identity and authoritative deduplication/reconciliation. Read hedging, if later used, remains subject to tenant isolation, consistency class, capacity budget and stale-response rules.

## Cancellation and lease expiry

Cancellation records intent; it does not rewind completed effects. A transport interrupt does not prove business cancellation.

Lease expiry:

- may allow another local executor only after durable state proves the prior executor cannot still commit the protected effect, or the effect authority provides fencing;
- never alone authorizes another external irreversible attempt;
- uses generation/term/fencing where concurrent stale execution could commit;
- enters reconciliation when prior effect outcome is unknown.

## Required fault vectors

Implementation evidence SHALL include:

- timeout before request leaves process;
- timeout after remote acceptance but before response;
- nested retries across client/API/worker/provider;
- process restart resetting local attempt counters/circuit state;
- provider throttling with synchronized tenant fleet;
- half-open probe storm;
- stale worker after lease transfer;
- queue outage followed by backlog surge;
- tenant/destination retry storm while unrelated workloads remain available;
- cancellation racing effect commit;
- circuit open during recovery/control work;
- deadline expiry while outcome is ambiguous.

## Release blockers

Release is blocked if an effectful path treats timeout, circuit-open, process death, lease expiry or redelivery as proof of effect absence; if retry amplification is unbounded across layers; if one tenant/destination can consume all workers; or if a retry changes logical identity/destination/generation without an explicit new operation.

