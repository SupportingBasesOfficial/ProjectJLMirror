# Recovery, Retention and Reconciliation

**Status:** proposed baseline  
**Phase:** 10 — Events / Async Contracts

## Purpose

This document applies the accepted Gate B recovery model to asynchronous publication, consumption, replay, process work, realtime projections and webhook delivery.

The central invariant is:

```text
uncertainty != absence
missing recovered async state != never published / never consumed / never executed
restore or offset rewind != retry permission
```

## Recovery interval

For a recovery point `R` and later write fence `F`, the async recovery interval `(R,F]` includes reliability/security/accountability evidence that may survive outside the restored business snapshot.

Relevant evidence includes as applicable:

- committed outbox messages;
- broker publication receipts/checkpoints;
- consumer inbox/dedup receipts;
- stable consumer effect/result identities;
- process/job operation records;
- provider/external operation acknowledgements;
- webhook delivery evidence;
- replay/projection generation state;
- producer/source generation authority;
- audit/accountability evidence;
- authorization/security generation state required to prevent stale authority.

## Recovery quarantine

A restored cell/consumer/dispatcher does not immediately resume duplicate-sensitive protected effects merely because the database is online.

Before effectful async admission resumes, the applicable recovery gate:

1. establishes/validates recovery generation/fence state;
2. identifies the `(R,F]` continuity interval;
3. reconciles required reliability/effect evidence;
4. retires stale producer/consumer/replay authority where continuity cannot be proven;
5. releases only scopes whose correctness/security continuity is established.

The exact implementation may quarantine by cell, tenant, consumer contract, workload or operation class. The fail-closed property is fixed.

## Outbox recovery

A restored outbox can show a committed message as unpublished even when the broker accepted it after `R`.

Recovery therefore:

- preserves/reconstructs the original logical `message_id` for the committed fact;
- re-publishes the **same** logical message identity when publication must be retried;
- relies on consumer at-least-once duplicate safety;
- reconciles available broker/publication evidence;
- does not invent another semantic event because local `published_at` rolled back.

If the authoritative business mutation itself is intentionally rolled back while later immutable external consequences survive, owning-domain recovery/compensation policy decides how to reconcile the business fact; the dispatcher alone does not synthesize corrective events.

## Inbox recovery

A restored inbox may lack a receipt for an effect that actually committed after `R`.

Missing/older receipt is recovery uncertainty.

Before the same message becomes effect-eligible, recovery reconciles as applicable:

- authoritative local business outcome;
- operation/result linkage;
- provider/external acknowledgement;
- audit evidence;
- other surviving inbox/outbox/process records.

If effect outcome cannot be established, the message remains `reconciliation_required`/quarantined/fail-closed rather than executing again.

## Broker offset/checkpoint recovery

Broker offsets/checkpoints are transport progress, not business-effect truth.

Moving an offset backward may redeliver messages. This is safe only because consumer effect completion is independently duplicate-safe.

Moving an offset forward must not skip messages for which the consumer has not reached its durable responsibility boundary.

After recovery, a checkpoint is reconciled with durable consumer state before being treated as authoritative progress.

## Producer/source generation recovery

A restored control plane or producer store must not reactivate an old producer/source generation that was retired after `R`.

Where generation is security/correctness authority:

- current generation evidence survives/reconciles through `(R,F]`;
- old-generation current-source commands/signals remain invalid;
- outstanding capabilities/messages from invalidated epochs are rejected where required;
- historical facts produced while an older generation was valid may remain historical facts according to contract semantics.

Exact generation/epoch encoding remains OPEN.

## Realtime recovery

Realtime is non-authoritative.

After gateway/fanout/replay-state loss:

- Phase 09 admission/replay continuity rules decide whether outstanding connection capabilities remain valid;
- active subscription authority is re-established or connections are retired;
- retained realtime replay/cursor state may be invalidated;
- clients receive/experience `resync_required` and reload authoritative state;
- no business recovery depends on reconstructing every ephemeral socket message.

If the channel promises durable bounded resume, its retained replay state is recovery-classified accordingly; otherwise availability yields to snapshot resync.

## Process/job recovery

A queue job is not process truth.

Persisted process/operation state determines whether work is:

- pending;
- running/owned;
- completed;
- cancelled/denied;
- reconciliation-required;
- eligible for another attempt.

After restore, a queued/redelivered job must reconcile against the process/operation identity before protected effects resume.

A restored `pending` process record is not retry permission if an external effect from `(R,F]` may have completed.

## Webhook delivery recovery

A subscriber may already have received a webhook after `R` while restored local delivery state says pending.

The platform may retry the same at-least-once delivery identity, but:

- source event identity is preserved;
- a new semantic event is not invented;
- signing/subscription current state is revalidated;
- audit/disclosure evidence is reconciled;
- stronger partner exactly-once requirements require explicit partner idempotency/reconciliation.

## Replay state recovery

Replay operations are persisted privileged processes.

A restore must not:

- accidentally restart a replay from zero without its target generation/dedup semantics;
- redirect replay to production side-effect consumers that were not originally targeted;
- forget that a privileged replay was cancelled/disabled;
- lose audit scope/range evidence.

Replay resumes only after current operator/service authority and target generation/process state are re-established.

## Retention classes

Async retention is not one universal TTL.

Contracts classify retained evidence such as:

```text
message publication evidence
consumer dedup/effect evidence
process/operation state
quarantine evidence
replay source/history
schema/contract definitions
webhook delivery evidence
realtime resume state
operational logs/metrics
```

Each class is retained according to correctness, Product, compliance and recovery needs.

## Correctness retention horizon

Dedup/idempotency evidence remains available for at least the period in which:

- the same message can legitimately redeliver/replay; and
- duplicate effect would remain unsafe; or
- an alternate durable operation/result authority can prove the effect.

A broker retention window longer than inbox correctness evidence can create unsafe historical re-execution unless replay/consumer contracts explicitly handle it.

Therefore replay support and dedup retention are designed together.

## Schema retention

Historical messages may outlive current deployment code.

The platform retains enough contract/schema/version information to:

- validate/replay supported history;
- interpret audit/evidence;
- run deterministic upcasters/adapters where accepted;
- explain quarantined old messages.

Deleting old schema definitions while retaining old messages that may be replayed is prohibited.

## Data erasure and message history

Tenant deletion/erasure may require removing retained message payloads while preserving legally required minimal audit/accountability evidence.

Contracts declare whether payload is:

- deletable after projection/effect completion;
- required for replay/recovery;
- transformable to redacted/tombstone evidence;
- retained under legal hold.

Erasure does not permit rewriting historical audit evidence into a false statement that delivery/effect never occurred.

The implementation may separate immutable minimal evidence from deletable payload material.

## Legal hold

Where legal hold applies, cleanup/retention processes use the accepted governance serialization/fencing model.

Ordinary broker retention policies SHALL NOT delete held evidence behind the governance authority.

Exact legal/compliance rules remain Product/policy inputs, not invented by Phase 10.

## Quarantine retention

Quarantined payload/evidence is not retained forever by default.

Retention must balance:

- remediation/replay needs;
- data classification;
- audit/compliance;
- storage/cost;
- whether stable source/result references can replace full payload retention.

Expiry of quarantine evidence cannot silently convert an unresolved irreversible effect into retry eligibility.

## Reconciliation ownership

Every reconciliation case has an owning capability/process.

A generic queue worker does not decide arbitrarily whether an external effect happened.

Reconciliation may compare:

- provider authoritative state;
- domain resource/process state;
- payment/external operation identity;
- audit/receipt evidence;
- source system sequence/state.

The result is durably recorded before retry eligibility changes.

## Forward recovery versus rollback

For irreversible external effects, forward recovery/compensation may be safer than trying to pretend the effect never happened.

The owning process/domain decides:

- carry forward effect evidence;
- reconstruct local state;
- compensate with a new explicit operation;
- quarantine for operator decision.

Phase 10 messages represent those decisions but do not replace the domain state machine.

## Recovery and authorization

Recovery SHALL NOT resurrect revoked authority.

After restore:

- workers use current service/human policy;
- stale sessions/memberships are not re-enabled from old message context;
- stale producer generations remain retired;
- realtime subscriptions/capabilities follow current authority/replay epoch;
- replay/admin actions require current authorization.

## Recovery and topology change

Recovery may restore into different infrastructure/provider/broker topology.

Contracts remain valid because they reference logical:

- tenant;
- message/contract;
- producer/consumer;
- operation/process;
- source generation.

They do not require old queue/topic/cell physical identity to remain canonical.

## Validation/fault injection

Recovery tests include:

- restore before outbox publish while broker already received message;
- restore before inbox completion while local/external effect survives;
- broker offset rewind with completed inbox effects;
- source generation retired after `R` but restore predates retirement;
- process state restored before external provider success;
- realtime resume/replay state lost -> resync/fail closed, not assumed continuity;
- webhook success record rolled back while subscriber may have received it;
- quarantine/reconciliation state lost locally while effect ambiguity survives externally;
- old schema version replay after rolling deployment;
- erasure/legal-hold continuity through recovery;
- stale authorization/placement state cannot be revived by recovered message/job context.

## Release blockers

Release/recovery is blocked if:

- restored absence is treated as proof of no publication/consumption/effect;
- same committed fact is recovered with a new semantic message identity causing duplicate effect;
- offset/checkpoint is the only evidence of completed consumer work;
- old producer generation can regain current-source authority;
- unresolved external ambiguity ages/expires into retry eligibility;
- replay can restart without target generation/audit scope;
- retained messages outlive the schema/version needed to interpret supported replay;
- legal hold/erasure governance can be bypassed by broker cleanup;
- revoked authority can be resurrected by old async state.

## Intentionally OPEN

- numeric retention durations;
- broker/event-history retention product;
- recovery-generation encoding;
- schema archive implementation;
- reconciliation tooling;
- legal-hold storage mechanism;
- quarantine retention values;
- exact RPO/RTO/SLO values.

The `(R,F]` continuity, fail-closed ambiguity and reliability-evidence preservation properties are fixed.
