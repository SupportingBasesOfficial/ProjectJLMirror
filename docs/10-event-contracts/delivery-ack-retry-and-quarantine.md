# Delivery, Acknowledgement, Retry and Quarantine

**Status:** proposed baseline  
**Phase:** 10 — Events / Async Contracts

## Purpose

This document defines message delivery semantics after publication. It prevents transport acknowledgement, lease expiry, retry policy or dead-letter tooling from becoming an accidental substitute for business-effect correctness.

## Default delivery model

JLMIRROR async delivery defaults to **at least once**.

Consumers SHALL be designed under the assumption that the same logical message can be:

- delivered more than once;
- delivered after a long delay;
- delivered after consumer restart;
- delivered after publisher retry following ambiguous acknowledgement;
- delivered out of order unless ordering is explicitly contracted;
- delivered again after broker/recovery replay.

Duplicate delivery is therefore not an exceptional bug condition.

## Exactly-once claims

A transport feature advertised as "exactly once", transactional publishing, deduplicated queueing or single delivery does not by itself establish exactly-once business effects.

An exactly-once business claim requires proof that the protected logical effect cannot be duplicated across:

- publisher crash;
- broker retry/redelivery;
- consumer crash;
- consumer acknowledgement loss;
- external-provider timeout/ambiguity;
- restore/PITR/replay;
- concurrent consumers.

Unless that proof exists, documentation and implementation use at-least-once language plus explicit idempotency/reconciliation.

## Delivery responsibility boundaries

A message progresses through distinct responsibilities:

```text
producer committed logical message
  -> broker accepted transport responsibility
  -> consumer accepted processing responsibility
  -> protected effect became durable or reconciliation-safe
  -> broker acknowledgement / checkpoint advancement
```

These boundaries SHALL NOT be collapsed into one vague "delivered" state.

## Broker acknowledgement

A consumer acknowledges or advances broker progress only according to the selected transport profile **after** the consumer has reached the durable responsibility boundary required by its contract.

For a co-resident inbox/effect transaction, acknowledgement occurs only after that transaction commits.

For a cross-authority/external effect, acknowledgement occurs only after the consumer has durable state sufficient to:

- prove the effect completed; or
- preserve a stable operation/reconciliation identity that prevents a second blind executor.

Acknowledging a message merely because it was parsed into memory is prohibited.

## Pre-ack and post-ack crash classes

Consumers SHALL test these classes explicitly.

### Crash before durable responsibility

The message may be redelivered and must remain executable if no protected effect was committed.

### Crash after durable effect/responsibility but before broker acknowledgement

Redelivery is expected. The consumer must observe completed inbox/result or reconciliation state and must not create a second logical effect.

### Crash after acknowledgement

The business effect/durable responsibility must already be safe. If work can still be lost after acknowledgement, the acknowledgement boundary is wrong.

## Retry classification

Failures are classified into stable categories:

```text
transient_retryable
throttled_retryable
stale_placement_reresolve
contract_permanent
policy_or_authorization_denied
poison_or_unknown
external_outcome_ambiguous
recovery_continuity_blocked
```

Transport adapters may map provider/broker exceptions into these classes but provider-native exception names do not become the canonical contract.

## Transient retry

Transient failures use bounded retries with:

- exponential or evidence-backed backoff;
- jitter;
- maximum attempts/time window;
- workload-specific concurrency budget;
- circuit/dependency protection where appropriate;
- safe `Retry-After`/provider hint honoring when trusted and bounded.

Exact numeric values remain OPEN until capacity/SLO evidence exists.

## Throttled retry

A trusted provider/broker throttling hint may influence the next eligible attempt.

Untrusted payload values cannot schedule arbitrary far-future or immediate retry loops without validation/bounds.

## Stale placement

A stale tenant placement/cell generation is not retried against the same stale target.

The worker:

1. stops protected execution on the stale authority;
2. re-resolves current placement;
3. establishes new trusted `TenantContext`;
4. re-evaluates current authorization/policy where required;
5. resumes only when the operation/message contract remains eligible.

Blind transport retry to the old cell is prohibited.

## Permanent contract failure

Messages that are malformed for their declared accepted contract/version, violate non-retryable schema invariants or reference an unsupported retired contract are not retried forever.

They enter a governed terminal/quarantine path with:

- safe reason class;
- contract/message identity;
- tenant/producer context where policy permits;
- audit/operational signal;
- bounded payload/evidence handling according to classification.

A permanent malformed message is not "fixed" by consumers guessing an alternate parser/schema.

## Authorization/policy denial

A delayed job or process action may become unauthorized because membership, tenant state, policy or plan changed after the message was created.

The worker SHALL treat current policy as authoritative.

The message does not preserve stale human authorization.

Depending on the owning process contract, the result may become:

- terminal denied/cancelled;
- waiting for operator/admin decision;
- compensated;
- reconciliation-required.

Automatic retry cannot restore revoked authority.

## Poison/unknown failure

Repeated unknown failures use a bounded retry policy and then quarantine.

Quarantine is not successful processing. It is a durable state requiring operational visibility and an explicit remediation/replay decision.

A poison message SHALL NOT consume unbounded resources indefinitely.

## External outcome ambiguity

If an irreversible external effect may have succeeded but the platform lacks authoritative completion evidence, the message/job enters durable ambiguity/reconciliation state.

Rules:

- timeout is not failure proof;
- worker lease expiry is not effect absence proof;
- broker redelivery is not retry permission;
- consumer restart is not retry permission;
- retry count exhaustion is not permission to start over.

The stable `operation_id`/provider-side identity is reconciled before any new effect attempt becomes eligible.

## Recovery continuity blocked

After restore/PITR/partial loss, a message may be present while inbox/effect evidence is older or missing.

The consumer SHALL NOT infer that the message is new merely because local dedup state is absent.

Affected duplicate-sensitive execution remains fail-closed/reconciliation-blocked until the accepted `(R,F]` continuity gate establishes safe eligibility.

## Quarantine model

Quarantine stores operational responsibility for a message that cannot safely proceed automatically.

Conceptual metadata:

```text
message_id
contract_name/version
trusted message_identity_scope
consumer_contract
quarantine_reason_class
first_failure_at
last_failure_at
attempt_count
safe error summary
operation/result reference when applicable
replay/remediation state
```

Payload retention follows the message data-classification/retention profile; quarantine is not an excuse to store unrestricted confidential payloads forever.

## Dead-letter queues

A broker-native DLQ may be used as one transport implementation, but the canonical platform contract is **quarantine**, not "whatever is in a vendor DLQ".

Broker DLQ state alone SHALL NOT be the only durable truth for:

- business operation state;
- reconciliation status;
- authorization denial;
- audit/accountability;
- remediation decision.

Changing broker vendors must not erase the platform meaning of a quarantined message.

## Re-drive / replay from quarantine

Re-drive is an explicit governed action.

Before re-drive:

- current contract compatibility is established;
- tenant/current placement is resolved where applicable;
- duplicate/effect state is reconciled;
- current authorization for privileged remediation is checked;
- the remediation action is audited;
- irreversible effects are not blindly repeated.

The same logical message normally preserves its original message identity when it is the same fact/work item being retried. A transformed/reissued new command that represents a new business decision gets a new message identity and explicit causation link.

## Retry storms and isolation

Retry systems SHALL defend against cascading failure.

Controls include:

- per-dependency concurrency limits;
- per-tenant/workload budgets;
- jitter/backoff;
- circuit/open-state handling;
- priority isolation for critical control/recovery work;
- maximum in-flight and batch sizes;
- global emergency throttles that do not corrupt correctness state.

One failing provider/tenant/consumer contract must not monopolize all workers.

## Scheduling semantics

`not_before`/delay is scheduling intent, not a correctness lease.

A delayed job becoming eligible does not mean:

- its prior authorization is still valid;
- its tenant placement is unchanged;
- an earlier ambiguous attempt did not succeed;
- dependencies are healthy.

Those conditions are re-established at execution time.

## Deadline semantics

A deadline defines whether starting/continuing the requested work is still contractually useful.

Deadline expiry does not undo an already-committed external effect and cannot convert ambiguous outcome into safe retry.

Process managers decide forward-recovery/compensation after deadline according to their durable state machine.

## Cancellation interaction

Cancelling a durable operation/job records cancellation intent under current authority.

Workers SHALL distinguish:

- cancellation requested before effect starts;
- effect already committed;
- external effect in ambiguous state;
- non-cancellable stage.

Broker message deletion or consumer interruption is not proof of business cancellation.

## Consumer acknowledgement metadata

Broker offsets/receipt handles/ack IDs are transport metadata.

They may be persisted for operational/recovery use but are not canonical business identities and are not exposed as platform resource IDs.

A restored offset that moves backward must remain safe because consumer inbox/effect completion is independently duplicate-safe.

## Ordering interaction

Retry of one failed ordered message may block later messages only when the contract explicitly requires strict ordering for that scope.

Otherwise the implementation may quarantine one poison message and allow unrelated messages/scopes to continue.

Broker-wide head-of-line blocking is not a contract requirement.

## Observability

Every consumer/delivery path emits safe metrics for:

```text
contract/consumer
attempts
latency
ack latency
retry class
quarantine count/age
ambiguous reconciliation count/age
stale placement count
current backlog/in-flight
```

Normal logs do not include credentials or unrestricted payloads.

## Required fault tests

Implementations test:

- duplicate delivery before first attempt;
- crash after durable local effect but before ack;
- external effect accepted then response/ack lost;
- lease timeout while original executor may still be active;
- stale placement during retry;
- current authorization revoked before delayed execution;
- poison message reaches bounded quarantine rather than infinite retry;
- DLQ/quarantine re-drive does not bypass dedup/reconciliation;
- restore to older inbox/offset state does not repeat completed effect;
- broker acknowledgement before durable responsibility is rejected by design tests/review;
- retry storms are bounded by workload/dependency budgets.

## Intentionally OPEN

- exact retry counts/backoff curves;
- broker ack mode;
- visibility timeout/lease values;
- DLQ product/topology;
- quarantine storage implementation;
- worker concurrency numbers;
- scheduling product.

The durable-responsibility-before-ack, bounded retry, fail-closed ambiguity and governed quarantine properties are fixed.
