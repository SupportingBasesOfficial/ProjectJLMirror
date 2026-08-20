# Publication, Outbox and Producer Authority

**Status:** proposed baseline  
**Phase:** 10 — Events / Async Contracts

## Purpose

This document defines how authoritative JLMIRROR state becomes asynchronous publication without losing facts, publishing uncommitted facts, leaking provider/storage topology or allowing stale producers to remain authoritative after relocation/recovery/cutover.

The accepted system invariant remains: when a committed authoritative mutation requires publication, the owning use case persists the outbox record in the same transaction as the mutation and required audit/accountability intent.

## Transactional publication boundary

Representative same-cell flow:

```text
BEGIN
  establish trusted transaction-local TenantContext
  validate current state/invariants
  mutate owning-domain state
  persist required audit/audit-intent
  append immutable logical outbox message(s)
COMMIT

outbox dispatcher
  -> claim committed publication work
  -> publish
  -> observe broker/provider acknowledgement
  -> update mutable dispatch state
```

The dispatcher is not allowed to decide whether the domain fact happened. It only delivers a fact already committed by the owning transaction.

## Outbox logical record

The accepted outbox record contains or deterministically derives:

```text
event_id / message_id
contract_name
contract_version
message_class
tenant_id (except explicit global contract)
producer / owning capability
producer_generation where required
subject / aggregate_type + aggregate_id where relevant
occurred_at
correlation_id
causation_id
data_classification
payload
publication state / attempt metadata
```

Implementation may split immutable message evidence and mutable delivery state into separate tables/records. That split is preferred when it improves protection of committed message meaning.

## Immutable publication evidence

Once the authoritative transaction commits, normal runtime SHALL NOT rewrite the semantic statement represented by the outbox message.

Immutable portions include as applicable:

- `message_id`;
- contract identity/version;
- tenant/global scope;
- logical producer identity;
- occurrence time;
- subject/resource identity;
- correlation/causation linkage;
- payload/evidence fields that define the published fact;
- data classification.

Mutable operational fields may include:

- claim/lease owner;
- attempt count;
- next attempt time;
- last error class;
- published/delivered timestamp;
- broker receipt/reference;
- quarantine state.

A retry worker may change delivery bookkeeping but may not transform yesterday's committed fact into a different fact.

## Producer authority

A message is trusted as internally produced only when it comes from an accepted producer boundary.

The logical producer is a bounded context/application capability, not:

- a pod;
- hostname;
- queue client;
- function execution;
- database schema;
- physical cell ID in the consumer contract.

Transport authentication between publisher and broker is necessary but not sufficient to define business authority. Publication credentials/ACLs must constrain which producer may publish which logical contract namespaces.

## Tenant-scoped producer authority

For a tenant-scoped message, the producer derives `tenant_id` from trusted application/domain context.

A producer SHALL NOT create cross-tenant publication by copying arbitrary `tenant_id` from user/provider payload text.

Where a provider callback triggered the mutation, the callback adapter first performs the accepted Phase 09 authentication/freshness/replay/tenant-binding/canonical-entity process. Only normalized trusted integration context may influence the owning use case and resulting outbox tenant scope.

## Producer generation and source retirement

Some contracts require protection against stale publishers after:

- tenant relocation;
- source cell retirement;
- provider/source cutover;
- active/passive failover;
- recovery epoch change;
- ownership transfer.

For such contracts, publication is bound to a trusted producer/source generation.

The fixed property is:

```text
retired producer/source generation
  -> cannot regain authority merely because delayed publication arrives
```

The contract declares whether generation is:

- encoded in the logical envelope;
- bound in trusted broker/route context;
- validated against current placement/source authority at the consumer;
- irrelevant because the event is an immutable historical fact whose occurrence remains valid after relocation.

Generation semantics are contract-specific. Exact generation representation remains OPEN.

## Historical fact versus current-source signal

Not every message from an old generation is invalid.

The contract SHALL distinguish:

### Historical fact

A fact committed while generation `N` was authoritative may remain a valid historical event after generation `N+1` becomes current. Delayed delivery is acceptable if consumers can safely process it according to event occurrence/order/replay semantics.

### Current-source signal/command

A job, realtime source signal or action that requires current placement/source authority must reject/retire stale generation `N` after `N+1` is authoritative.

This distinction prevents overusing source generation to erase legitimate history while still blocking stale execution authority.

## Outbox claim semantics

Multiple dispatchers may run concurrently.

Outbox claiming must provide one clear publication-attempt owner per record at a time using database-safe claim/lease/locking semantics. However, dispatcher exclusivity does **not** imply exactly-once delivery:

- a publish can succeed and acknowledgement be lost;
- a dispatcher may crash after publish before updating local state;
- broker redelivery may occur.

Therefore consumers remain duplicate-safe under the accepted at-least-once contract.

## Publication acknowledgement

A broker acknowledgement means only the broker-specific responsibility boundary documented by the selected transport profile.

It does not mean:

- every consumer processed the message;
- every downstream business effect succeeded;
- realtime clients saw the message;
- external webhook destinations received it.

The outbox dispatcher marks publication state according to the accepted broker profile, but downstream effects retain their own durable contracts.

## Publish ambiguity

If the publisher cannot know whether the broker accepted a message, retrying the same logical `message_id` is preferred over inventing a new message identity.

The transport adapter must preserve stable logical identity across ambiguous retry so consumers can deduplicate exact re-publication.

A publisher timeout does not create a second semantic event.

## Broker outage

A broker outage must not roll back already-committed domain state simply because async publication is delayed.

The platform keeps the durable outbox backlog and:

- retries under bounded backoff/jitter;
- enforces per-workload concurrency budgets;
- exposes backlog age/count/oldest-pending metrics;
- escalates operationally when SLO bounds are exceeded;
- does not drop committed messages merely to restore latency.

Where Product semantics require synchronous confirmation of a downstream effect, that use case must use the accepted synchronous/process contract rather than pretending outbox publication is synchronous completion.

## Backpressure

Publication architecture SHALL support bounded backpressure so one noisy tenant/domain cannot create unbounded memory/concurrency pressure.

Controls may include:

- dispatcher concurrency partitions by cell/domain/tenant class;
- rate budgets;
- backlog thresholds;
- admission degradation for non-critical producers;
- workload isolation.

Exact values/topology remain evidence-driven OPEN decisions.

Backpressure must not corrupt immutable message identity or tenant scope.

## Event construction

The event/integration message is constructed from authoritative use-case/domain state at commit time.

Rules:

- no post-commit ORM row reload is allowed to silently change the already-committed event meaning;
- payload fields required for the contract are captured/deterministically derivable from committed state;
- provider-native payloads are normalized before publication;
- large artifacts/telemetry blobs are referenced rather than embedded without bound;
- secrets are removed before persistence/publication.

## Multiple events from one transaction

One authoritative mutation may legitimately produce several logical messages.

Each message gets its own identity/contract semantics. Transactional commit groups their existence with the mutation, but consumers do not assume cross-message atomic processing unless an explicit process/batch contract says so.

Event order within one transaction is not automatically global broker order. If relative order matters, the producing contract defines a stable aggregate/process sequence or causal linkage.

## Cross-domain publication

A domain does not publish another domain's facts by reading its tables directly.

Cross-domain integration uses:

- owning-domain outbox publication;
- explicit application/domain contract;
- process manager/orchestrator that owns its own process events.

This preserves future service extraction and data ownership.

## Provider-derived publication

Provider adapters may publish normalized integration facts only after accepted provider trust processing.

A provider-native event ID may be retained as external-reference/dedup evidence, but:

- `contract_name` remains JLMIRROR-owned;
- `tenant_id` comes from trusted integration configuration/context;
- provider event name/version is adapter metadata, not canonical platform semantics;
- consumers do not need Zabbix-specific payloads to understand monitoring domain facts.

## Telemetry boundary

Raw high-rate observation transport is not forced through the general outbox if the accepted telemetry plane uses a specialized ingestion/storage path.

Outbox/event publication is appropriate for bounded durable semantic outputs such as:

- committed state transitions;
- alert/process lifecycle facts;
- integration changes;
- operational triggers;
- derived notifications.

The owning telemetry/monitoring contract decides when raw observation identity versus event publication is appropriate.

## Recovery continuity

After PITR/restore, publication state can be older than external broker state.

The platform must not infer:

```text
outbox row says unpublished
=> broker definitely never received it
```

For `(R,F]` recovery:

- stable `message_id` is preserved/reconstructed for committed facts;
- broker/output evidence is reconciled where available;
- re-publication uses the same logical message identity when the same fact is being recovered;
- consumers remain duplicate-safe;
- immutable audit/process/outcome evidence is reconciled before destructive cleanup.

If the system cannot prove whether an irreversible downstream effect has already happened, downstream consumer recovery remains reconciliation-blocked rather than relying on outbox state alone.

## Cleanup/retention

Outbox cleanup is governed by:

- publication/consumer recovery requirements;
- replay policy;
- audit/evidence policy;
- recovery horizon;
- contract retention needs.

Deletion of a published outbox row is safe only when required durable evidence exists elsewhere or the accepted retention policy says the publication evidence is no longer required for correctness/recovery.

Numeric retention remains OPEN.

## Observability

Publisher telemetry includes safe dimensions such as:

```text
contract_name / version
producer capability
cell/workload class
tenant hash/reference where policy permits
publish attempts
success/failure class
backlog count/age
claim latency
broker acknowledgement latency
quarantine count
```

Payloads, credentials and confidential tenant fields are not copied into normal logs.

## Required fault tests

Publication implementations test:

- crash before authoritative transaction commit -> no committed fact/outbox publication;
- crash after commit before dispatcher sees row -> message remains publishable;
- broker accepts publish, publisher loses ack -> retry uses same logical message identity;
- concurrent dispatchers do not corrupt attempt state;
- stale producer generation cannot publish current-authority commands/signals after retirement;
- historical facts from a retired generation remain processable when contract says they remain valid history;
- broker outage/backlog does not lose committed outbox facts;
- restore to before publication while broker/consumer evidence survives -> recovery does not invent a new semantic event identity;
- provider payload cannot forge producer/tenant authority;
- secret-bearing payload fails publication contract.

## Intentionally OPEN

- broker/product;
- outbox dispatcher implementation;
- claim/lease primitive;
- topic/queue topology;
- producer credential mechanism;
- producer-generation encoding;
- numeric backlog/retry/retention limits;
- exact serializer.

The transactional fact-to-outbox property, stable message identity, producer/tenant authority and recovery continuity are not OPEN.
