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
- canonical comparison-profile/version and historical verifier lifecycle where the evidence form requires it;
- equivalence-evidence classification, trusted-scope/domain-separation and anti-oracle policy;
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

For every duplicate-sensitive consumer, the durable correctness evidence SHALL retain enough information to compare repeated deliveries for semantic equivalence throughout the full dedup/redelivery/replay/recovery horizon. Accepted evidence may be one of:

- a canonical collision-resistant fingerprint/digest over the immutable comparison surface when the source-data classification and entropy make that representation safe;
- an authenticated digest/MAC or equivalent protected comparison value when ordinary digest disclosure would create dictionary, correlation or oracle risk;
- the original immutable canonical message representation where classification/retention permits it;
- another durable comparison authority that proves equivalence without depending on mutable current state.

The comparison profile defines exactly which immutable fields are covered. At minimum it cannot omit dimensions whose change would make the same scoped `message_id` represent a different logical message, such as contract/version, trusted tenant/source scope, immutable subject/occurrence identity where applicable, and canonical payload semantics.

The comparison uses the same accepted canonical structured interpretation as protected contract validation. Each retained evidence record therefore identifies or inherits a stable comparison-profile/version sufficient to reproduce the same equality result throughout the supported horizon. Parser/canonicalization evolution cannot silently redefine equality for an already-admitted scoped identity.

Comparison begins only after the trusted `(consumer_contract, message_identity_scope, message_id)` has been derived. A fingerprint/MAC is never a substitute for that identity scope and SHALL NOT become a global reverse lookup, cross-tenant/cross-consumer equality namespace, authorization token, routing key, ordering authority, public identifier or bearer capability.

A plain unsalted/unkeyed digest of low-entropy confidential immutable content is not automatically safe: it may allow offline guessing even when the original payload was minimized. Where that risk exists, the accepted contract uses a protected/keyed comparison form or protected retained canonical evidence and applies the source data's classification, retention, logging and export restrictions to the derived evidence.

When keyed/authenticated evidence is used, inbox records retain only non-secret comparison-profile/verifier generation references. Key material remains behind the accepted secret/KMS authority. Rotation/retirement preserves historical verification for the supported horizon or completes a reviewed equality-preserving evidence migration before the old verifier is retired.

Loss, rollback, retirement or temporary unavailability of the evidence, comparison profile or required historical verifier authority is **unknown equivalence**, not a benign duplicate. The affected identity remains fail-closed/reconciliation-blocked and cannot become new protected-effect eligible until accepted authority proves equivalence.

A fingerprint is therefore not optional merely because the full payload is not retained. If payload erasure/minimization removes the original bytes, a safe surviving fingerprint/tombstone/equivalent comparison authority remains for as long as the scoped ID can legitimately reappear and be deduplicated. If policy destroys the last usable comparison authority, the corresponding old identity/replay path ceases to be effect-eligible or stays reconciliation-blocked.

Comparison/profile/KMS lookups are bounded and scoped so crafted duplicate IDs cannot create unbounded secret-store work or expose an equality oracle.

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

The retained correctness evidence includes the message-content equivalence fingerprint/original/equivalent authority **plus the comparison-profile/version and historical verifier authority required to interpret it** for that same horizon, or a governed equality-preserving migration/equivalent authority proves continuity. Retaining uninterpretable evidence bytes is not sufficient correctness retention.

Exact retention is contract/SLO evidence-driven and OPEN.

A consumer SHALL NOT advertise/support replay farther back than its effect-safety, content-equivalence evidence and historical comparison authority can handle unless a separate replay reconciliation mechanism exists.

## Recovery continuity

After restore/PITR/partial loss:

```text
missing inbox receipt != never processed
older result linkage != effect absent
missing content-equivalence evidence != safe duplicate
missing historical comparison profile/verifier != safe duplicate
```

Before duplicate-sensitive execution resumes, recovery reconciles `(R,F]` against surviving:

- business outcome state;
- operation/process records;
- provider/external acknowledgements;
- outbox/inbox evidence;
- message-content fingerprint/original/equivalence evidence;
- stable comparison-profile/version metadata and required non-secret historical verifier generation references;
- narrowly authorized historical verification authority where the accepted evidence profile requires it;
- audit/accountability;
- broker/replay/checkpoint evidence where trustworthy.

If outcome, message-content equivalence or the authority needed to prove historical equivalence remains uncertain, execution stays fail-closed/reconciliation-blocked. Recovery SHALL NOT downgrade a same-ID/different-content integrity ambiguity into ordinary duplicate success because a restored snapshot lost the original comparison evidence or historical verifier/profile authority.

A restored obsolete verifier/profile is not current authority for unrelated messages or scopes; it is usable only under the historical evidence generation that requires it.

## Replay interaction

Operational replay may intentionally re-deliver old messages.

The consumer contract declares whether replay should:

- deduplicate as already completed;
- rebuild a projection using an isolated rebuild namespace/target;
- recompute a derived non-effectful view;
- invoke a special reconciliation path.

Replay SHALL NOT disable the normal inbox and thereby repeat irreversible effects.

A projection rebuild that needs to process historical messages again uses a distinct projection generation/build identity rather than pretending original effect receipts never existed.

Supported replay that depends on normal deduplication also retains enough message-content equivalence evidence **and historical comparison-profile/verifier authority** to reject historical ID reuse with changed immutable semantics. If that authority is unavailable and no equality-preserving migration/equivalent authority exists, duplicate-sensitive replay remains reconciliation-blocked rather than trusting identity alone.

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
- protected canonical fingerprint/equivalence evidence appropriate to source-data classification;
- stable comparison-profile/version and non-secret verifier-generation reference where required;
- result/operation linkage;
- status/timestamps;
- trusted source metadata;

rather than copying the full confidential payload indefinitely.

Data minimization may replace full retained content with a safe fingerprint/tombstone, but it cannot erase the last evidence or historical comparison authority needed to distinguish an ordinary duplicate from conflicting reuse during the supported dedup/recovery horizon.

Derived comparison evidence is not assumed harmless metadata. Normal logs, metrics, quarantine and operator surfaces do not expose raw confidential content, unrestricted fingerprints/MACs or verifier material when the evidence profile makes those values sensitive or oracle-capable.

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
comparison-profile/verifier-unavailable safe reason counts
processing latency
inbox contention
current placement re-resolution
external ambiguity age/count
```

Payload, secrets and protected equivalence evidence are redacted according to classification.

## Required fault tests

Every duplicate-sensitive consumer tests as applicable:

- simultaneous same-message deliveries;
- same raw ID across distinct authoritative source/tenant scopes;
- same scoped `message_id` with identical canonical immutable content is classified as a normal duplicate;
- same scoped `message_id` with changed contract version, trusted immutable scope/subject semantics or canonical payload fails closed as integrity/producer-contract failure;
- original payload is minimized/erased but surviving fingerprint/equivalence evidence still detects conflicting same-ID content reuse;
- low-entropy confidential immutable content is not exposed through naive plain-digest logging, export or offline-guessable metadata;
- equivalent content in different trusted tenant/consumer/message-identity scopes cannot be correlated or deduplicated through an unrestricted fingerprint/equality lookup;
- comparison canonicalization/profile upgrade preserves the historical equality result or affected identities remain fail-closed until a reviewed equality-preserving migration completes;
- keyed/authenticated evidence remains historically verifiable across accepted key/profile rotation, or affected identities remain reconciliation-blocked when the historical verifier is unavailable/retired;
- restore to before comparison-profile/key rotation cannot resurrect an obsolete verifier as authority for unrelated messages;
- historical verifier/profile loss never converts unknown equivalence into duplicate success or protected-effect eligibility;
- crafted duplicate IDs cannot force unbounded KMS/secret-store/comparison work or expose an equality oracle;
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
- exact fingerprint/hash/MAC algorithm, domain-separation encoding and storage representation, subject to accepted collision/confidentiality/oracle properties;
- exact comparison-profile/version representation and equality-preserving migration mechanism;
- exact historical verifier/key-generation representation and KMS/secret backend;
- worker/service auth mechanism;
- broker consumer-group topology;
- provider-side idempotency implementation;
- projection rebuild tooling.

The trusted scoped identity, durable confidentiality-safe message-content equivalence evidence, historical comparison-profile/verifier continuity, atomic/crash-safe effect completion and fail-closed ambiguity/recovery properties are fixed.
