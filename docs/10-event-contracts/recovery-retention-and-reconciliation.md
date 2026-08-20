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
- canonical message-content fingerprints/original/equivalence evidence needed to distinguish legitimate duplicate from conflicting scoped-ID reuse;
- stable consumer effect/result identities;
- process/job operation records;
- provider/external operation acknowledgements;
- webhook delivery identity/semantic-snapshot/destination-generation evidence;
- replay/projection generation state;
- producer/source generation authority;
- audit/accountability evidence;
- authorization/security generation state required to prevent stale authority.

## Recovery quarantine

A restored cell/consumer/dispatcher does not immediately resume duplicate-sensitive protected effects merely because the database is online.

Before effectful async admission resumes, the applicable recovery gate:

1. establishes/validates recovery generation/fence state;
2. identifies the `(R,F]` continuity interval;
3. reconciles required reliability/effect/equivalence evidence;
4. retires stale producer/consumer/replay/webhook-destination authority where continuity cannot be proven;
5. releases only scopes whose correctness/security continuity is established.

The exact implementation may quarantine by cell, tenant, consumer contract, workload or operation class. The fail-closed property is fixed.

## Outbox recovery

A restored outbox can show a committed message as unpublished even when the broker accepted it after `R`.

Recovery therefore:

- preserves/reconstructs the original logical `message_id` for the committed fact;
- re-publishes the **same** logical message identity when publication must be retried;
- preserves the immutable semantic content associated with that identity rather than reconstructing changed meaning from mutable current state;
- relies on consumer at-least-once duplicate safety plus content-equivalence validation;
- reconciles available broker/publication evidence;
- does not invent another semantic event because local `published_at` rolled back.

If the authoritative business mutation itself is intentionally rolled back while later immutable external consequences survive, owning-domain recovery/compensation policy decides how to reconcile the business fact; the dispatcher alone does not synthesize corrective events.

## Inbox recovery

A restored inbox may lack a receipt for an effect that actually committed after `R`. It may also retain a receipt while losing the fingerprint/original/equivalence evidence required to prove what immutable message content that receipt represented.

Missing/older receipt or missing/older content-equivalence evidence is recovery uncertainty.

Before the same message becomes effect-eligible **or is classified as an ordinary duplicate**, recovery reconciles as applicable:

- authoritative local business outcome;
- operation/result linkage;
- provider/external acknowledgement;
- original/canonical message-content fingerprint or equivalent immutable comparison evidence;
- audit evidence;
- other surviving inbox/outbox/process records.

If effect outcome or message-content equivalence cannot be established, the message remains `reconciliation_required`/quarantined/fail-closed rather than executing again or being silently acknowledged as a benign duplicate.

A restored consumer SHALL NOT interpret:

```text
same scoped message_id + missing comparison evidence
```

as proof that the arriving content is equivalent to the originally processed message.

If surviving evidence proves the same scoped ID is now associated with different immutable contract content, recovery records an integrity/producer-contract failure; it does not overwrite the historical receipt or select first/last payload by arrival order.

## Broker offset/checkpoint recovery

Broker offsets/checkpoints are transport progress, not business-effect truth.

Moving an offset backward may redeliver messages. This is safe only because consumer effect completion is independently duplicate-safe **and repeated scoped IDs can still be checked for immutable-content equivalence**.

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

A subscriber may already have received a webhook after `R` while restored local delivery state says pending. A newer destination configuration generation may also have replaced or revoked the generation to which the original disclosure obligation was bound.

Webhook recovery therefore reconciles the delivery as a stable semantic obligation, not as a mutable row rebuilt from current state.

For every affected obligation, recovery preserves/reconstructs as applicable:

- globally unique `webhook_delivery_id` or the accepted explicit external identity scope;
- source event/message identity;
- webhook contract name/version;
- tenant/subscription disclosure scope;
- immutable canonical semantic payload snapshot or deterministic immutable reproduction inputs;
- bound subscription/destination configuration generation;
- retired/revoked generation fences;
- surviving network-attempt/acknowledgement evidence;
- audit/disclosure evidence.

A missing restored `success` record does not prove the subscriber never received the delivery. A missing or older subscription/configuration row does not prove an old destination generation is current or eligible for retry.

While generation or semantic-snapshot continuity is unresolved, protected outbound attempts remain fail-closed/quarantined. Recovery SHALL NOT:

- reconstruct an existing `webhook_delivery_id` using changed current mutable domain state;
- change webhook contract/version or semantic payload under the same delivery ID;
- silently retarget the old delivery ID to whichever destination URL is current after restore;
- reactivate a destination generation retired after `R` merely because the restored store predates retirement.

If the original bound destination generation remains valid/eligible under the accepted retry profile, the platform may retry the **same immutable delivery obligation** under at-least-once semantics. If the generation is no longer eligible, the old obligation is fenced/cancelled/quarantined. A deliberate resend to a newer authorized destination generation is a **new delivery obligation with a new delivery ID** and explicit causation to the original.

Stronger partner exactly-once requirements still require explicit partner idempotency/reconciliation; HTTP acknowledgement alone is insufficient.

## Replay state recovery

Replay operations are persisted privileged processes.

A restore must not:

- accidentally restart a replay from zero without its target generation/dedup semantics;
- redirect replay to production side-effect consumers that were not originally targeted;
- forget that a privileged replay was cancelled/disabled;
- lose audit scope/range evidence;
- restore message identity without the equivalence evidence needed to detect conflicting immutable-content reuse.

Replay resumes only after current operator/service authority, target generation/process state and required content-equivalence evidence are re-established.

## Retention classes

Async retention is not one universal TTL.

Contracts classify retained evidence such as:

```text
message publication evidence
consumer dedup/effect evidence
message-content fingerprint/original/equivalence evidence
process/operation state
quarantine evidence
replay source/history
schema/contract definitions
webhook delivery identity + semantic snapshot + destination-generation evidence
realtime resume state
operational logs/metrics
```

Each class is retained according to correctness, Product, compliance and recovery needs.

## Correctness retention horizon

Dedup/idempotency evidence remains available for at least the period in which:

- the same message can legitimately redeliver/replay; and
- duplicate effect would remain unsafe; or
- an alternate durable operation/result authority can prove the effect.

For any consumer that classifies a repeated scoped `message_id` as a duplicate, correctness evidence also retains enough canonical fingerprint/original/equivalent authority to prove that the repeated immutable semantic content matches the originally admitted message throughout that same supported horizon.

A broker retention window longer than inbox correctness/equivalence evidence can create unsafe historical re-execution **or silent suppression of conflicting content** unless replay/consumer contracts explicitly handle it.

Therefore replay support, dedup retention and message-content equivalence retention are designed together.

For outbound webhooks, the supported retry/recovery horizon also retains enough immutable delivery-obligation and destination-generation/fence evidence to prove what bytes/semantics and disclosure authority a stable delivery ID represents. Expiring that evidence while the same ID may still be retried is prohibited.

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

If full message payload is erased while a scoped `message_id` can still legitimately redeliver/replay, a safe surviving fingerprint/tombstone/equivalence authority must remain sufficient to reject conflicting immutable-content reuse without retaining unnecessary confidential payload bytes.

For a webhook delivery whose full payload may be erased, any surviving dedup/recovery identity/tombstone must still prevent an old stable delivery ID from being reconstructed later with different semantics or disclosure authority.

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

Expiry of quarantine evidence cannot silently convert an unresolved irreversible effect or unresolved same-ID/content-integrity conflict into retry/duplicate eligibility.

## Reconciliation ownership

Every reconciliation case has an owning capability/process.

A generic queue worker does not decide arbitrarily whether an external effect happened or whether two conflicting immutable payloads are equivalent.

Reconciliation may compare:

- provider authoritative state;
- domain resource/process state;
- payment/external operation identity;
- retained message-content fingerprint/original/equivalence evidence;
- webhook delivery/generation/disclosure evidence;
- audit/receipt evidence;
- source system sequence/state.

The result is durably recorded before retry or duplicate-classification eligibility changes.

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
- retired/revoked webhook destination generations remain fenced until continuity proves otherwise;
- realtime subscriptions/capabilities follow current authority/replay epoch;
- replay/admin actions require current authorization.

## Recovery and topology change

Recovery may restore into different infrastructure/provider/broker topology.

Contracts remain valid because they reference logical:

- tenant;
- message/contract;
- producer/consumer;
- operation/process;
- source generation;
- webhook subscription/delivery/configuration generation.

They do not require old queue/topic/cell physical identity to remain canonical.

## Validation/fault injection

Recovery tests include:

- restore before outbox publish while broker already received message;
- restore before inbox completion while local/external effect survives;
- restore/partial loss of message-content equivalence evidence while same scoped ID redelivers with identical content;
- restore/partial loss of message-content equivalence evidence while same scoped ID redelivers with conflicting immutable content and consumer fails closed;
- broker offset rewind with completed inbox effects;
- source generation retired after `R` but restore predates retirement;
- process state restored before external provider success;
- realtime resume/replay state lost -> resync/fail closed, not assumed continuity;
- webhook success record rolled back while subscriber may have received it;
- webhook destination generation retired after `R` but restored state predates retirement;
- webhook semantic snapshot/projection mapper changes after `R` and an old stable delivery ID still reproduces original meaning;
- webhook restore cannot retarget an old delivery to the current destination or reuse old ID for a deliberate new-generation reissue;
- quarantine/reconciliation state lost locally while effect ambiguity survives externally;
- old schema version replay after rolling deployment;
- erasure/legal-hold continuity through recovery;
- stale authorization/placement state cannot be revived by recovered message/job context.

## Release blockers

Release/recovery is blocked if:

- restored absence is treated as proof of no publication/consumption/effect;
- same committed fact is recovered with a new semantic message identity causing duplicate effect;
- same scoped message identity can be considered a benign duplicate without durable evidence sufficient to compare immutable semantic content;
- content-equivalence evidence can be lost/expired/erased while the same scoped ID remains supported for redelivery/replay/recovery;
- offset/checkpoint is the only evidence of completed consumer work;
- old producer generation can regain current-source authority;
- unresolved external ambiguity ages/expires into retry eligibility;
- replay can restart without target generation/audit scope;
- retained messages outlive the schema/version needed to interpret supported replay;
- legal hold/erasure governance can be bypassed by broker cleanup;
- revoked authority can be resurrected by old async state;
- restored webhook state can mutate the semantic payload/contract of an existing delivery ID;
- restored/older webhook configuration can resurrect a retired destination generation or silently retarget an existing delivery obligation;
- webhook retry/recovery horizon outlives the immutable identity/snapshot/generation evidence needed to prove safe retry semantics.

## Intentionally OPEN

- numeric retention durations;
- broker/event-history retention product;
- recovery-generation encoding;
- schema archive implementation;
- reconciliation tooling;
- legal-hold storage mechanism;
- quarantine retention values;
- exact canonical fingerprint/hash algorithm and storage representation, subject to accepted collision/security properties;
- exact storage representation for webhook semantic snapshots and destination-configuration generations;
- exact Product-specific cancel/quarantine/reissue policy for retired webhook generations;
- exact RPO/RTO/SLO values.

The `(R,F]` continuity, fail-closed ambiguity, durable message-content equivalence, immutable webhook-delivery meaning/destination-generation continuity and reliability-evidence preservation properties are fixed.
