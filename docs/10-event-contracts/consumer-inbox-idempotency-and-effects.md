# Consumer Inbox, Idempotency and Effect Completion

**Status:** proposed baseline  
**Phase:** 10 — Events / Async Contracts

## Purpose

This document defines how a consumer turns an at-least-once message into at-most-one logical protected effect within the consumer contract, including crash consistency, trusted message identity scope, cross-authority effects and current authorization/placement at execution time.

## Consumer contract identity

Every async consumer has a stable logical `consumer_contract` independent of process instance, worker pool, deployment or broker subscription name.

The consumer contract declares:

- accepted producer/message contracts and versions;
- tenant/global scope;
- message identity scope derivation;
- message-content equivalence evidence policy;
- effect owner;
- duplicate/effect completion policy;
- ordering profile if any;
- retry/quarantine behavior;
- current authorization/placement requirements;
- recovery/replay semantics.

A queue/consumer-group name may map to this contract operationally but is not the canonical consumer identity.

## Trusted message identity scope

For duplicate-sensitive messages, the inbox identity is:

```text
(consumer_contract, message_identity_scope, message_id)
```

`message_identity_scope` is non-null and server-derived from trusted envelope/producer context.

It includes every dimension required to prevent collisions across:

- tenant/global boundary;
- logical producer/source;
- provider/integration source when relevant;
- source/producer generation when the source ID namespace resets across generations;
- other contract-specific source namespace.

A constant/global scope is valid only when the contract proves `message_id` is globally unique across every allowed producer/source for the entire dedup/recovery horizon.

Payload-controlled fields cannot select a weaker scope.

## Inbox is not a pre-check

Inbox deduplication SHALL NOT be implemented as:

```text
if not seen(message_id):
  do_effect()
  mark_seen()
```

That pattern is unsafe under concurrency and crash.

The inbox is a durable execution/completion protocol.

## Co-resident local effect

When inbox receipt and authoritative consumer effect share one transaction authority, they commit atomically.

Representative flow:

```text
BEGIN
  establish trusted TenantContext when tenant-scoped
  derive message_identity_scope
  create/lock unique inbox receipt
  validate accepted message contract/current state
  verify current policy/authorization where execution requires it
  apply owning-domain effect
  persist required audit/outbox/result linkage
  mark inbox receipt completed
COMMIT
```

Properties:

- concurrent duplicate delivery has one logical effect owner;
- crash before commit leaves neither completed receipt nor committed effect;
- crash after commit leaves both effect and completed receipt/result linkage;
- redelivery after broker ack loss observes the completed result and no-ops/replays safely;
- same raw `message_id` under a different trusted identity scope remains independently processable.

## Unique constraint / atomic admission

The durable store enforces uniqueness for the effective inbox identity or an equivalent atomic create-or-observe/CAS contract.

A read-then-insert race is prohibited.

The implementation may represent states such as:

```text
admitted
processing
completed
failed_terminal
reconciliation_required
quarantined
```

Exact names are implementation details; the contract must preserve one logical executor/effect eligibility.

## Receipt completion

A receipt is considered `completed` only when the consumer can deterministically prove the protected effect/result established by that message.

Completion may link to:

- stable resource revision;
- operation/process ID;
- authoritative result record;
- explicit no-op/terminal transition result.

A completed receipt without effect/result linkage sufficient for deterministic redelivery behavior is not accepted for duplicate-sensitive effects.

## Duplicate behavior

A duplicate message under the same trusted identity scope:

- MUST NOT execute the protected logical effect again;
- MAY return/record the existing result/no-op status internally;
- may still refresh observability/ack state;
- may reconcile an existing cross-authority operation if completion is not yet authoritative.

A duplicate is not an error requiring a new message identity.

A delivery is eligible to be classified as an ordinary duplicate only after the consumer can establish that the repeated scoped identity still denotes the **same immutable logical message content** under the accepted contract.

## Same ID, different semantic content

If the same trusted identity scope and `message_id` arrives with semantically different immutable contract content, the consumer treats it as integrity/producer-contract failure.

It SHALL NOT:

- silently process the second payload;
- silently suppress the second payload as an ordinary duplicate;
- overwrite the original inbox/evidence;
- select first/last based on arrival order.

For every duplicate-sensitive consumer, the durable correctness evidence SHALL retain enough information to compare repeated deliveries for semantic equivalence throughout the full dedup/redelivery/replay/recovery horizon. The accepted evidence may be one of:

- a safe canonical fingerprint/hash over the immutable contract identity plus immutable envelope/payload semantics;
- the original immutable canonical message representation where classification/retention permits it;
- another durable comparison authority that proves equivalence without depending on mutable current state.

The comparison profile defines exactly which immutable fields are covered. At minimum it cannot omit dimensions whose change would make the same scoped `message_id` represent a different logical message, such as contract/version, trusted tenant/source scope, immutable subject/occurrence identity where applicable, and canonical payload semantics.

A fingerprint is therefore not optional merely because the full payload is not retained. If payload erasure/minimization removes the original bytes, a safe surviving fingerprint/tombstone/equivalent comparison authority remains for as long as the scoped ID can legitimately reappear and be deduplicated.

A mismatch is fail-closed integrity evidence. It enters a governed producer-integrity/quarantine path and cannot acknowledge success as though a normal duplicate had been observed.

## Cross-authority effects

When inbox state and protected effect cannot share one transaction, neither unsafe ordering is allowed:

```text
receipt completed -> effect later
```

can lose the effect after crash, while:

```text
effect first -> receipt later
```

can duplicate the effect after redelivery.

The effect authority therefore persists a stable `operation_id` / result identity atomically with the effect, or uses an equivalent discoverable outcome protocol.

The inbox references that identity and reconciliation decides whether another attempt is eligible.

## External irreversible effects

For external effects:

- derive/persist stable platform `operation_id` before/with attempt according to the owning process contract;
- use provider-side idempotency identity where available without making provider identity the platform operation identity;
- treat timeout/connection loss as ambiguous when the provider may have committed;
- persist `reconciliation_required` or equivalent durable ambiguity state;
- reconcile provider/domain truth before a new effect attempt.

Broker redelivery is not permission to call the provider again blindly.

## Current tenant placement

A tenant-scoped worker re-resolves current placement before protected execution.

The message's logical `tenant_id` identifies the tenant but does not pin a historical cell.

If the message was routed to a stale cell/generation:

- stop protected effect;
- re-resolve placement;
- establish current `TenantContext`;
- resume only under the current authoritative boundary.

A broker topic containing a cell name is deployment routing, not durable tenant authority.

## Current authorization for delayed work

A message/job does not preserve the human requester's old authorization unless an explicitly accepted capability/delegation contract says so.

For work that depends on current human/tenant/policy authority, the consumer re-evaluates at execution/resume time:

- tenant active/access state;
- membership when applicable;
- role/permission/scope;
- step-up/approval validity when the owning use case requires it;
- plan/feature/policy constraints.

If authority was revoked, the consumer follows the owning process terminal/wait/compensation policy. It does not retry until authorization magically returns.

## Service/machine authority

Some system jobs execute under a platform service principal rather than a human principal.

The contract explicitly declares:

- service authority class;
- tenant scope;
- allowed operation;
- whether originating actor is audit context only;
- revocation/policy checks required at execution.

A generic worker service identity SHALL NOT imply unrestricted cross-tenant mutation authority.

## Process-manager consumers

A persisted process manager may consume several signal types.

The process manager:

- loads durable current process state;
- applies a versioned state transition;
- deduplicates the signal;
- emits next outbox messages atomically with the process transition where co-resident;
- handles stale/out-of-order signals explicitly.

Queue order alone does not define the process state machine.

## Projection consumers

A read-model/search/cache projection may accept at-least-once events with idempotent upsert/revision semantics rather than a heavy inbox per message when the contract proves duplicate/out-of-order safety.

Acceptable mechanisms include:

- monotonic aggregate revision/CAS;
- natural unique fact identity;
- last-applied sequence per authoritative stream;
- rebuildable projection where duplicates cannot create external effects.

The contract records which mechanism provides safety.

If such a lightweight mechanism still classifies repeated `message_id` values as duplicates, it must retain equivalent message-content comparison evidence whenever silent content-reuse suppression would violate the contract.

## Notification consumers

Email/SMS/push/webhook-like external notifications are externally visible effects and require a stable operation/delivery identity when duplicate delivery would be harmful or confusing.

A message receipt alone is insufficient deduplication if the external channel can accept an ambiguous attempt.

## Inbox retention

Inbox/dedup evidence is retained for at least the period during which the same logical message may be redelivered/replayed/recovered and duplication would remain unsafe.

The retained correctness evidence includes the message-content equivalence fingerprint/original/equivalent authority required to detect scoped `message_id` reuse with different immutable content for that same horizon.

Exact retention is contract/SLO evidence-driven and OPEN.

A consumer SHALL NOT advertise/support replay farther back than its effect-safety and content-equivalence evidence can handle unless a separate replay reconciliation mechanism exists.

## Recovery continuity

After restore/PITR/partial loss:

```text
missing inbox receipt != never processed
older result linkage != effect absent
missing content-equivalence evidence != safe duplicate
```

Before duplicate-sensitive execution resumes, recovery reconciles `(R,F]` against surviving:

- business outcome state;
- operation/process records;
- provider/external acknowledgements;
- outbox/inbox evidence;
- message-content fingerprint/original/equivalence evidence;
- audit/accountability;
- broker/replay/checkpoint evidence where trustworthy.

If outcome or message-content equivalence remains uncertain, execution stays fail-closed/reconciliation-blocked. Recovery SHALL NOT downgrade a same-ID/different-content integrity ambiguity into ordinary duplicate success because a restored snapshot lost the original comparison evidence.

## Replay interaction

Operational replay may intentionally re-deliver old messages.

The consumer contract declares whether replay should:

- deduplicate as already completed;
- rebuild a projection using an isolated rebuild namespace/target;
- recompute a derived non-effectful view;
- invoke a special reconciliation path.

Replay SHALL NOT disable the normal inbox and thereby repeat irreversible effects.

A projection rebuild that needs to process historical messages again uses a distinct projection generation/build identity rather than pretending original effect receipts never existed.

Supported replay that depends on normal deduplication also retains enough message-content equivalence evidence to reject historical ID reuse with changed immutable semantics.

## Consumer schema validation

Before protected effects, consumers validate:

- contract name/version;
- envelope trust/context;
- tenant/global scope;
- payload schema/size/classification;
- required identity/order metadata.

A consumer does not guess an alternate version/parser after validation fails.

## Data minimization

Inbox records store only what is required for correctness/recovery/audit.

They SHOULD prefer:

- message identity;
- safe canonical fingerprint/equivalence evidence;
- result/operation linkage;
- status/timestamps;
- trusted source metadata;

rather than copying the full confidential payload indefinitely.

Data minimization may replace full retained content with a safe fingerprint/tombstone, but it cannot erase the last evidence needed to distinguish an ordinary duplicate from conflicting reuse during the supported dedup/recovery horizon.

## Consumer isolation

One consumer contract's receipt must not suppress another independent consumer contract. This is why `consumer_contract` participates in inbox identity.

Two consumers of the same event may independently complete different logical effects.

## Batching

When a transport delivers a batch, each logical message retains independent inbox/effect identity unless the consumer contract explicitly defines a single atomic batch command.

Partial batch failure does not justify marking unprocessed messages completed.

## Observability

Consumer telemetry includes safe:

```text
consumer_contract
producer_contract/version
message class
admitted/completed/duplicate/reconciled/quarantined counts
content-identity mismatch/integrity-failure counts
processing latency
inbox contention
current placement re-resolution
external ambiguity age/count
```

Payload and secrets are redacted according to classification.

## Required fault tests

Every duplicate-sensitive consumer tests as applicable:

- simultaneous same-message deliveries;
- same raw ID across distinct authoritative source/tenant scopes;
- same scoped `message_id` with identical canonical immutable content is classified as a normal duplicate;
- same scoped `message_id` with changed contract version, trusted immutable scope/subject semantics or canonical payload fails closed as integrity/producer-contract failure;
- original payload is minimized/erased but surviving fingerprint/equivalence evidence still detects conflicting same-ID content reuse;
- restore to a point before local fingerprint/equivalence evidence while conflicting/surviving message evidence exists does not classify the new arrival as a safe duplicate;
- crash after inbox admission but before local effect;
- crash after local effect statements but before transaction commit;
- crash after atomic commit before broker acknowledgement;
- cross-authority effect succeeds then receipt finalization crashes;
- external provider accepts effect then response is lost;
- delayed job after user/session/membership permission is revoked;
- tenant relocates before worker execution;
- restore to before completed inbox while surviving effect evidence exists;
- replay of historical message does not duplicate irreversible effect;
- projection rebuild uses isolated generation semantics rather than erasing production dedup truth;
- malicious payload cannot forge message identity scope/tenant/producer authority.

## Intentionally OPEN

- inbox table/store product;
- receipt state naming;
- exact retention duration;
- exact fingerprint/hash algorithm and storage representation, subject to accepted collision/security properties;
- worker/service auth mechanism;
- broker consumer-group topology;
- provider-side idempotency implementation;
- projection rebuild tooling.

The trusted scoped identity, durable message-content equivalence evidence, atomic/crash-safe effect completion and fail-closed ambiguity/recovery properties are fixed.
