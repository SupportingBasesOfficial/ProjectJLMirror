# Ordering, Sequencing and Replay

**Status:** proposed baseline  
**Phase:** 10 — Events / Async Contracts

## Purpose

This document defines when asynchronous ordering exists, how sequence/freshness differs from message identity, how gaps and stale producers are handled, and how historical replay occurs without converting old facts into duplicate side effects.

## No implicit global ordering

JLMIRROR does not promise one total order across all asynchronous messages.

A broker offset, partition number, publish timestamp or database sequence SHALL NOT be exposed as a universal platform ordering contract merely because one implementation provides it.

Global ordering would create unnecessary coupling and scale bottlenecks. Ordering is opt-in and scoped to the smallest logical boundary required by a consumer invariant.

## Ordering profiles

Each contract declares one of:

```text
unordered
causal_only
per_subject_ordered
per_process_ordered
per_source_ordered
custom_bounded_order
```

The exact profile name may be represented differently in tooling; the semantics must be explicit.

### `unordered`

Consumers must be correct under arbitrary reordering and duplicates.

### `causal_only`

Correlation/causation links describe why messages occurred, but no gap-free sequence is promised.

### `per_subject_ordered`

A logical subject/aggregate has a monotonic revision/sequence contract.

### `per_process_ordered`

A persisted operation/process manager defines monotonic process transition versioning.

### `per_source_ordered`

A provider/source stream defines a trustworthy source-local sequence under a trusted source/generation scope.

### `custom_bounded_order`

Used only when the contract documents the exact ordering scope, authority and failure behavior.

## Ordering key

Where ordered delivery/processing matters, the ordering key is derived from trusted logical contract context.

Examples:

```text
tenant_id + subject_id
tenant_id + operation_id
integration/source identity + source_generation
```

A caller/provider payload field does not select a partition/ordering namespace unless the adapter has validated it as the trusted logical identity required by the contract.

Physical broker partition IDs are not canonical ordering keys.

## Sequence semantics

A sequence/revision value is distinct from `message_id`.

The contract declares:

- sequence authority/source;
- scope in which the value is monotonic;
- whether sequence is gap-free, merely monotonic or best-effort;
- behavior on duplicate sequence;
- behavior on stale/lower sequence;
- behavior on gaps;
- rollover/generation rules if the source resets;
- recovery/replay behavior.

A consumer SHALL NOT infer gap-free semantics from an incrementing integer unless the contract explicitly guarantees it.

## Aggregate revisions

For domain facts tied to an authoritative aggregate/resource revision, the event may carry the accepted logical revision.

Consumers can use CAS/last-applied revision when their projection contract proves:

- the revision is authoritative for that subject;
- duplicate same revision is safely idempotent;
- stale/lower revisions do not regress projection state;
- gaps trigger the correct resync/reconciliation behavior rather than silent guessing.

The database row version implementation is not exposed unless it is itself the accepted logical revision contract.

## Source sequence and generation

Provider/source streams may reset sequence numbers across reconnection, provider reset, relocation or source replacement.

Where this can happen, sequence identity is scoped by a trusted source generation:

```text
source_identity + source_generation + sequence
```

A sequence value without its required source/generation context is not globally authoritative.

Stale generation messages may be:

- valid historical facts; or
- invalid current-source commands/signals.

The contract explicitly chooses based on semantic meaning.

## Deduplication is not ordering

The same message can be:

- duplicate but correctly ordered;
- unique but stale/out-of-order;
- unique and ahead with a gap;
- duplicate after replay.

Inbox identity and ordering sequence therefore remain separate fields/authorities.

A consumer SHALL NOT deduplicate solely on sequence if distinct logical messages may share sequence under different contracts/scopes.

## Broker ordering

Broker ordering guarantees may optimize delivery, but consumers rely only on the ordering semantics declared by the Phase 10 contract.

If a future broker replacement offers weaker native ordering, the adapter/topology must still satisfy the contract or the contract must be changed through compatibility review.

A topic/partition implementation is not allowed to silently strengthen consumer assumptions beyond the contract either, because those assumptions would become migration debt.

## Parallelism

Consumers may process messages concurrently across independent ordering scopes.

When strict per-subject/process ordering is required, the implementation serializes only that required scope rather than one entire tenant/domain/global stream where possible.

This preserves future scale and avoids unnecessary head-of-line blocking.

## Gap handling

A contract with meaningful sequence gaps declares one of:

```text
gap_tolerated
gap_requires_snapshot_resync
gap_requires_durable_replay
gap_requires_reconciliation
```

A consumer does not wait forever for a missing sequence unless the contract guarantees the message must eventually exist and provides bounded recovery semantics.

For realtime projections, a gap normally results in snapshot/API resynchronization rather than treating the socket stream as authoritative history.

## Realtime sequence/cursor

Realtime channels may expose a sequence/cursor only where the channel supports bounded replay/resume.

Properties:

- cursor/sequence is channel/subscription scoped;
- not authorization;
- not tenant placement authority;
- not guaranteed durable unless the channel contract says so;
- stale authorization or placement retirement invalidates continued delivery regardless of cursor validity;
- client can always fall back to authoritative resync according to the Phase 09/10 realtime contract.

## Event replay

Replay is an explicit operational contract that re-presents historical messages for a defined purpose.

Replay use cases may include:

- rebuilding a read model;
- recovering a consumer after data loss;
- reprocessing after a bug fix under a safe new projection generation;
- reconstructing derived state;
- controlled integration recovery.

Replay is not a generic mechanism to repeat irreversible business actions.

## Replay identity

When replay represents the **same historical logical message**, the original `message_id`, contract identity, occurrence time and trusted source scope are preserved.

This allows normal inbox/effect safety to recognize that a production effect already happened, but identity alone is not enough for duplicate-sensitive replay: the consumer must still be able to prove that the replayed immutable semantic content is equivalent to the originally admitted message under the accepted historical comparison profile.

Replay therefore preserves or makes available, for the supported duplicate-sensitive horizon:

- message-content fingerprint/original/equivalent evidence;
- the canonical comparison-profile/version required to interpret that evidence;
- any non-secret historical verifier/key-generation references and narrowly authorized verifier authority required by the accepted evidence form.

If historical equivalence cannot be proven because evidence, comparison profile or verifier authority is unavailable/retired/rolled back and no reviewed equality-preserving migration/equivalent authority exists, replay remains fail-closed/reconciliation-blocked for protected duplicate-sensitive effects. It SHALL NOT trust the repeated `message_id` alone or create a new effect simply because replay was operator initiated.

If data is transformed into a new semantic message/command as a new business decision, it receives a new `message_id` and explicit causation link rather than masquerading as original redelivery.

## Projection rebuild generation

A projection that intentionally needs to process all historical facts again uses a distinct rebuild/projection generation or isolated target.

This prevents the operator from deleting/ignoring production inbox truth to force re-execution.

Representative model:

```text
historical message identity remains unchanged
projection target generation = rebuild_N
consumer projection state/inbox namespace includes rebuild_N where contract permits
```

A rebuild generation is safe only for derived/reconstructable effects. It SHALL NOT be used to bypass idempotency for emails, payments, destructive automation, provider changes or other irreversible effects.

## Replay authorization

Starting a replay is a privileged administrative action.

It requires:

- current authorized operator/service authority;
- explicit contract/consumer/range scope;
- data-retention/classification eligibility;
- destination/target selection;
- audit record;
- rate/concurrency bounds;
- reconciliation checks for duplicate-sensitive consumers.

A user cannot request arbitrary cross-tenant replay by submitting tenant/message IDs without trusted authorization.

A replay operator's authorization does not grant authority to ignore missing historical equivalence evidence, use a fingerprint/MAC as a bearer capability, retrieve unrelated verifier material or query cross-tenant equality.

## Replay range

Replay range is expressed in logical/source terms appropriate to the contract, such as:

- occurrence time window;
- message ID range where ordered identity exists;
- aggregate/process revision range;
- source generation + sequence range;
- retained event-store cursor.

Broker-native offsets MAY implement this, but offsets are not the stable administrative API contract unless explicitly accepted.

## Contract-version replay

Historical messages retain their original contract version.

Consumers/replay tooling may use:

- retained compatible reader;
- deterministic adapter/upcaster into a newer internal representation;
- archived schema definition;
- migration/rebuild tool.

An upcaster must preserve historical semantic meaning. It cannot reinterpret an old fact as though newer fields/rules existed at occurrence time.

For duplicate-sensitive replay, a reader/upcaster/canonicalizer also preserves the accepted historical comparison-profile semantics or participates in a reviewed equality-preserving evidence migration before the old profile/verifier authority is retired. A newer parser cannot silently recompute an old receipt under different equality rules.

The canonical historical evidence remains the original accepted message contract/data plus the governed comparison authority required to prove equality where duplicate suppression is relied upon.

## Replay and retention

The platform SHALL NOT promise replay farther back than it can safely retain:

- message/event evidence;
- schema/version definitions and historical reader/upcaster semantics;
- tenant/data-classification authorization;
- consumer effect/dedup evidence required to prevent unsafe repetition;
- message-content equivalence evidence required to reject same-ID conflicting immutable content;
- comparison-profile/version and historical verifier authority required to interpret retained equivalence evidence.

Retaining an uninterpretable fingerprint/MAC is not safe replay retention. Retention windows and exact mechanisms remain evidence-driven OPEN decisions.

## Replay after restore/PITR

After recovery, broker/event-log progress and consumer inbox state may disagree.

The system follows `(R,F]` recovery reconciliation rather than blindly replaying from restored offsets.

Rules:

- missing restored inbox state does not mean old messages are safe to execute;
- missing/older equivalence evidence or missing/mismatched historical comparison-profile/verifier authority does not mean an old scoped ID is a safe duplicate;
- broker rewind does not authorize duplicate irreversible effect;
- restored source generation cannot reactivate retired producer authority;
- restored obsolete comparison verifier/profile is not current authority for unrelated messages or scopes;
- replay tooling reconciles stable operation/effect/audit/equivalence evidence and required historical comparison authority before enabling duplicate-sensitive execution;
- projection-only rebuild may proceed in an isolated generation once its source evidence is trusted.

## Reordering around relocation

Tenant relocation may create in-flight messages produced before and after cutover.

Contracts must remain correct without exposing physical cell IDs as consumer semantics.

Where current-source authority matters:

- source/producer generation distinguishes retired/current authority;
- target processing resolves current tenant placement;
- stale command/signal is rejected/reconciled;
- historical facts may still be processed under occurrence semantics.

A lower-latency arrival from the new cell does not automatically invalidate an older historical fact from the source cell.

## Cross-contract causality

A process may emit messages across several contract types.

Causation/correlation supports tracing and loop detection, but correctness relies on durable process/domain state.

Consumers SHALL NOT require all causally related messages to arrive in a single total order unless a specific process contract defines and enforces that invariant.

## Loop protection

Automations/integrations can accidentally create event feedback loops.

Protection may use:

- explicit process/automation execution identity;
- causation chain depth bounds;
- rule-specific reentrancy policy;
- deduplication/idempotency;
- rate/circuit limits.

Correlation ID alone is insufficient loop prevention because unrelated legitimate messages may share a workflow correlation.

## Observability

Ordering/replay telemetry records safe:

```text
contract
ordering scope
out_of_order count
duplicate/stale count
gap count/resync count
source generation mismatch
replay job/range/progress
projection rebuild generation
quarantine/reconciliation
historical comparison authority unavailable/profile-mismatch safe reason counts
```

Payloads, raw confidential comparison evidence and verifier material are not logged merely to diagnose ordering/replay.

## Required tests

Where applicable:

- two independent subjects process in parallel without false ordering coupling;
- duplicate `message_id` does not advance a sequence twice;
- stale/lower revision cannot regress authoritative projection;
- gap triggers documented resync/replay/reconciliation behavior;
- source sequence reset under new generation does not collide with old generation;
- delayed historical fact from retired generation remains valid when contract says historical;
- stale current-source command from retired generation cannot execute;
- replay preserves original identity;
- replay with the same scoped ID but conflicting immutable semantic content fails closed rather than being suppressed as a duplicate;
- replay whose retained evidence exists but required historical comparison profile/verifier is unavailable remains reconciliation-blocked;
- comparison-profile/canonicalization migration preserves historical equality before old authority retirement;
- restored obsolete comparison verifier/profile cannot become current authority for unrelated messages;
- projection rebuild uses isolated generation and cannot trigger irreversible production side effects;
- old contract version can be replayed under retained reader/upcaster without semantic rewrite or equivalence-profile drift;
- restore/offset rewind cannot repeat protected effect.

## Intentionally OPEN

- broker partitioning implementation/count;
- exact sequence representation;
- event-store/replay product;
- replay retention duration;
- rebuild tooling;
- broker offset/checkpoint implementation;
- source-generation encoding;
- exact comparison-profile representation, historical verifier/KMS backend and equality-preserving migration mechanism used by duplicate-sensitive replay.

The scoped-ordering, identity/sequence separation, confidentiality-safe historical message-equivalence verification and fail-closed replay safety properties are fixed.
