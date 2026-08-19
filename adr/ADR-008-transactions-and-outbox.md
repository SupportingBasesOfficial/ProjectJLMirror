# ADR-008 — Transaction Boundaries and Transactional Outbox

**Status:** accepted  
**Date:** 2026-08-17  
**Reversibility:** costly after event consumers proliferate

## Context

JLMIRROR must mutate durable state and reliably trigger asynchronous consequences (notifications, webhooks, projections, workflows). Publishing directly to a broker before/after commit creates dual-write failure windows. Long external calls inside database transactions increase lock duration and couple availability. Required audit evidence has the same dual-write problem if appended only after the protected mutation commits. Projection transitions have the same failure mode when a state change and its required signal are persisted separately. API idempotency keys also fail under concurrency if callers merely check for an existing record before effectful processing without a unique atomic claim, and they remain crash-unsafe if a local mutation can commit separately from claim completion/result linkage. Inbox deduplication has an equivalent crash-consistency problem when a consumer receipt and the effect it protects are persisted in separate uncoordinated steps.

Drivers: `INV-ASYNC-001`, `INV-DATA-004`, `QA-ASYNC-001`, `TM-011`, `SEC-AUD-001`, `SEC-AUD-003`, `SEC-AUD-004`, `AP-05`.

## Decision

The **application use case** owns the database transaction boundary for a single transactional ownership scope.

When a successful transaction must produce durable asynchronous consequences, domain state changes and an **outbox record** SHALL commit atomically in the same PostgreSQL transaction. A dispatcher publishes the outbox item to the accepted event transport and marks publication state idempotently.

When an audit record is required for a local authoritative mutation and the audit record is owned in the same transactional boundary, the audit append SHALL commit atomically with the mutation. If final audit evidence is stored in another persistence authority, a durable audit intent SHALL commit atomically with the mutation and delivery to the external audit sink is retried/reconciled. A required audit trail MUST NOT depend solely on post-commit best effort.

The immutable evidence payload of a required external audit intent SHALL be protected from update/delete by normal application and dispatcher roles. Mutable retry/delivery metadata SHALL be segregated so delivery progress can change without granting the dispatcher authority to rewrite the committed accountability statement.

### Idempotency admission atomicity

For an operation whose API/application contract accepts an idempotency key to suppress duplicate logical effects, executable ownership SHALL be established through a durable unique claim before effectful processing begins.

The system derives a non-null canonical idempotency scope from trusted tenant/global context, operation identity and any principal/credential dimension that is part of that operation's semantics. The persistence authority enforces uniqueness for `(idempotency_scope, idempotency_key)` or an equivalent canonical identity.

Claim acquisition uses one atomic create-or-observe/compare-and-set database operation. A read-then-insert sequence without a database uniqueness/serialization guarantee is prohibited.

Concurrency semantics are:

- one contender creates the executable claim and becomes the sole logical executor;
- same key/scope with a different request fingerprint conflicts and executes nothing;
- same key/scope/fingerprint observing an in-progress claim does not become a second executor;
- same key/scope/fingerprint observing a completed claim reuses the established logical result according to the later API contract.

### Idempotent local completion atomicity

Claim acquisition and operation completion are separate correctness boundaries. A durable `in_progress` claim is not sufficient if the protected local mutation can commit without a durable completed result linkage.

When the idempotency claim and authoritative local mutation share the same PostgreSQL transactional boundary, successful execution SHALL atomically commit:

```text
BEGIN
  verify/lock/CAS executable idempotency claim
  apply authoritative domain mutation
  append required audit/outbox state
  persist stable operation/result reference or replay metadata
  finalize claim as completed
COMMIT
```

No valid outcome may contain a committed local mutation while the only durable claim state remains unrecoverably `in_progress` and disconnected from the result. A crash before commit leaves the mutation incomplete; a crash after commit leaves a completed claim/result that a retry can replay or reconstruct without re-executing the mutation.

If claim state and the local authoritative effect cannot share one transaction, the effect authority SHALL atomically persist a stable `operation_id`/result record with the mutation. Claim recovery MUST reconcile that durable result and finalize/replay the existing claim idempotently before any new execution eligibility is considered. Best-effort post-commit claim finalization without durable linkage is prohibited when duplication would violate the contract.

For irreversible external work, the claim carries or deterministically derives a stable logical `operation_id`. A crash or timeout after an external request may leave the result ambiguous; that state is reconciled through the stable operation identity/provider truth before another execution is allowed. Claim timeout/lease expiration alone is not evidence that the external effect did not happen.

### Inbox consumer-effect atomicity

For at-least-once event/message consumption, an inbox receipt is useful only if its completion semantics cannot lose or duplicate the logical effect it protects.

When the inbox receipt and authoritative consumer effect are co-resident in the same transactional boundary, the consumer SHALL atomically commit:

```text
BEGIN
  create/lock unique inbox receipt
  perform authoritative local consumer effect
  persist required audit/outbox/result linkage
  mark inbox receipt completed with stable effect/result reference
COMMIT
```

A consumer MUST NOT persist a completed receipt before the protected effect is durable, because a crash can then cause redelivery to suppress an effect that never happened. It also MUST NOT commit the protected effect while leaving no durable completed receipt/result linkage, because a crash can then make redelivery execute the effect again.

When the inbox authority and protected effect cannot share one transaction, the effect authority SHALL persist a stable `operation_id` / effect-result record atomically with the effect or use an equivalent protocol that makes outcome durably discoverable. Inbox completion and retry eligibility reconcile that authoritative outcome before re-execution. For ambiguous external effects, timeout/lease expiry or missing receipt completion alone does not authorize a duplicate attempt.

Broker acknowledgement timing is transport-specific, but the invariant is transport-independent: a crash cannot turn an already-committed effect into duplicate-execution eligibility or a pre-recorded receipt into silent effect loss.

### State-transition signal atomicity

When a conditional state transition semantically requires a downstream signal/event (for example a telemetry observation advancing a current-state projection), success of the state transition and durable existence of the signal intent MUST share one atomic durability boundary or an equivalent recoverable advancement record.

For PostgreSQL-owned current state, the preferred pattern is:

```text
BEGIN
  conditional state advance / compare-and-set
  if advanced:
      persist stable transition identity
      append outbox/signal intent
COMMIT
```

If the current-state authority is not the same database as the signal outbox, the authoritative state transition MUST durably persist a transition/advancement record sufficient for an idempotent dispatcher to produce the signal after crash/replay. A worker MUST NOT rely on the transient return value of a successful compare-and-set as the only evidence that a signal is required.

External network calls SHALL NOT normally execute inside the database transaction. Multi-domain/external workflows requiring multiple durable steps use a process manager/saga-like orchestration with explicit compensation/reconciliation instead of pretending to have a distributed ACID transaction.

The same principle applies to any cross-persistence write: one authority must durably accept the intent/observation first, and the remaining effects are idempotent projections/reconciled consequences rather than an uncoordinated dual write.

## Consequences

### Positive
- removes the most common database/event dual-write gap;
- concurrent idempotent requests have one durable logical executor rather than a race-prone pre-check;
- completed local idempotent effects cannot become detached from the claim/result needed to replay them after crash;
- co-resident inbox consumption cannot lose or duplicate a protected local effect across crash/redelivery;
- cross-authority consumers have a durable operation/result identity to reconcile rather than relying on receipt ordering guesses;
- required local audit cannot be lost in a crash after business commit;
- external audit intent remains accountable even during sink/dispatcher failure;
- a committed current-state transition cannot silently lose its required signal after worker crash;
- event/audit/signal publication can retry safely;
- transactions remain short and local;
- eventual-consistency points are explicit.

### Negative / cost
- outbox tables/dispatchers and retention/monitoring are required;
- idempotency claims require unique scope design, completion/result linkage, lifecycle/retention and reconciliation of ambiguous effects;
- cross-authority idempotent local effects require a stable durable operation/result record;
- inbox consumers require receipt/effect atomicity or explicit cross-authority operation/result reconciliation;
- consumers must handle duplicate delivery;
- state-transition producers need stable transition identity;
- multi-step workflows become explicit state machines;
- external audit sinks require protected durable intent plus segregated delivery state and reconciliation.

## Validation

Concurrency tests SHALL issue simultaneous same-scope/same-key requests and prove exactly one executable claim is acquired. Same-fingerprint contenders MUST NOT produce a second logical effect; different-fingerprint contenders MUST conflict. The test must exercise the database uniqueness/atomic claim path rather than only an application-level existence check.

For co-resident local idempotent mutations, fault injection SHALL crash after the domain mutation statement but before claim finalization and immediately after commit but before response delivery. The only accepted durable states are: mutation not committed + claim not completed, or mutation committed + result linkage + claim completed. Retry after response loss MUST replay/reconstruct the committed result without re-executing the mutation.

For cross-authority local effects, tests SHALL prove that the effect authority persists a stable operation/result record atomically with the mutation and that claim recovery uses that record to finalize/replay rather than re-run the operation.

Fault injection for externally effectful idempotent operations SHALL crash after claim, during provider interaction and after possible provider acceptance but before local completion. Recovery MUST use the existing claim/stable operation identity and reconcile ambiguous outcome rather than blindly executing a second irreversible effect.

Inbox fault injection SHALL cover crash before local effect, after effect statements but before co-resident commit, after atomic receipt/effect commit but before broker acknowledgement, and around cross-authority effect completion. Co-resident cases MUST preserve receipt/effect atomicity; cross-authority cases MUST reconcile stable operation/result identity before retry eligibility.

Fault injection SHALL also cover crash before commit, after commit/before publish, duplicate publish, dispatcher restart and consumer replay. No committed event-worthy state may be permanently invisible to the dispatcher.

For required audit, fault injection SHALL prove there is no state in which the protected mutation commits successfully while neither the required audit record nor its durable atomic audit intent exists. Role/permission tests SHALL additionally prove the dispatcher and normal application runtime cannot rewrite/delete committed audit-evidence payload while retaining the narrower ability to advance delivery metadata.

For transition-driven signals, fault injection SHALL crash the worker immediately after the state compare-and-set/advance and before ordinary post-update code. Replay/reconciliation MUST still discover the durable transition/signal intent and emit the logical signal once under idempotent delivery semantics.

## Exit / revisit conditions

A broker supporting transactional integration with the authoritative database could justify a different mechanism, but equivalent atomicity, transition-signal recoverability, inbox effect correctness, idempotent local completion and audit-evidence integrity guarantees must be demonstrated. API-contract details may refine idempotency headers/status codes, but may not weaken the unique atomic-claim/single-executor/result-linkage invariant.