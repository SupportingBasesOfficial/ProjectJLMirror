# Event & Async Contracts Overview

**Status:** proposed baseline  
**Phase:** 10 — Events / Async Contracts  
**Depends on:** accepted Product/Requirements/Security/Architecture/ADR/System Design/Data Architecture and accepted Phase 09 API & Contracts baseline

## Purpose

Phase 10 defines the stable asynchronous contract system through which JLMIRROR publishes facts, schedules durable work, coordinates long-running processes, projects realtime signals and optionally delivers outbound webhooks without coupling business semantics to one broker, queue, pub/sub, gateway, storage engine or deployment topology.

The goal is not to force every interaction to become asynchronous. Synchronous application contracts remain valid where the accepted consistency model requires them. Phase 10 governs the cases where work or information crosses a transaction, process, cell, provider or time boundary and therefore needs durable message identity, compatibility, retry, replay, recovery and observability semantics.

The architecture must remain coherent when:

- the modular monolith later extracts selected bounded contexts into services;
- one cell becomes many cells or dedicated tenant cells/regions;
- multiple producers or provider adapters feed the same consumer capability;
- queue/broker technology changes;
- old and new application versions coexist during rolling deployment;
- broker delivery is duplicated, delayed, reordered or temporarily unavailable;
- a consumer crashes before, during or after an effect;
- a cell/store is restored to an earlier point while later external effects or reliability evidence survive;
- realtime clients disconnect, miss messages or remain connected during authorization/placement changes;
- event volume grows by orders of magnitude without forcing raw telemetry through one general-purpose broker.

## Normative inheritance

Phase 10 does not redefine accepted upstream invariants. It materializes them as message contracts.

The following are already fixed and remain normative:

- the application use case owns the authoritative mutation transaction;
- required outbox rows are committed with the authoritative mutation;
- normal external/cross-cell calls are outside ordinary database transactions;
- default event/job delivery is **at least once**;
- broker semantics alone never justify an exactly-once business claim;
- consumers protect duplicate-sensitive effects using inbox/idempotency/natural uniqueness/CAS/reconciliation as appropriate;
- a message/job does not carry durable human authorization merely because an earlier request had it;
- workers re-resolve current tenant placement and establish their own trusted `TenantContext` before protected execution;
- provider-native models remain adapter-owned and do not become platform ubiquitous language;
- replay/deduplication state that protects irreversible effects is reliability state, not disposable cache state;
- recovery preserves the accepted `(R,F]` continuity/reconciliation model and `uncertainty != absence`;
- realtime is advisory acceleration, not authoritative business state;
- Phase 09 owns realtime connection/subscription authority lifecycle; Phase 10 owns the subscription request/ack and message representation but may not weaken current authorization or placement freshness.

## Contract families

Phase 10 distinguishes asynchronous message classes because they have different meanings and retry rules.

### Domain event

A domain event states that an accepted business/domain fact occurred in an owning bounded context.

A domain event:

- is named in platform/domain language rather than provider language;
- is immutable as a historical statement;
- does not command another domain to perform an action merely by naming a fact;
- may trigger projections, process managers or downstream reactions.

### Integration event

An integration event is a deliberately published contract for consumption outside the producer's local module boundary. It may be derived from one or more domain facts but is versioned as its own stable consumer-facing async contract.

Extraction into another service does not automatically turn every internal domain event into a public integration event.

### Job / work command

A job is a durable instruction to attempt work. It is **not** evidence that the work happened.

Jobs require explicit effect identity, retry classification and current authorization/placement re-establishment where protected execution is involved.

### Process signal

A process signal advances or informs a persisted long-running process/saga/process manager. The authoritative process state remains durable owner-domain state rather than queue position.

### Realtime projection message

A realtime message accelerates a client view of already-authoritative state or process progress. Missing realtime messages are recoverable by resynchronizing through authoritative API/read models.

### Outbound webhook delivery

An outbound webhook is an external delivery projection of an accepted platform event/contract. It has independent delivery identity, authentication/signing, retry and endpoint-security semantics and does not make the destination authoritative for platform state.

## Facts, commands and projections are not interchangeable

Contracts SHALL not blur these meanings:

```text
fact:       something happened
command:    attempt this work
projection: here is a non-authoritative view/update signal
```

A consumer must know whether receiving a message means:

- authoritative fact already committed;
- durable work should be attempted;
- process state should be reconciled;
- UI/read projection should refresh.

A queue name or topic name does not define that semantic meaning.

## Contract identity

Every async contract has a stable logical identity independent of transport topology.

At minimum:

```text
contract_name
contract_version
message_class
owning_producer_capability
tenant/global scope
payload schema
compatibility policy
```

Broker topic, queue name, exchange, partition, subject, subscription group, cell-local channel or provider-native event type are transport/deployment metadata, not canonical contract identity.

## Logical message envelope

All published Phase 10 messages inherit a common logical envelope. Exact wire serialization is governed separately and remains replaceable until accepted.

The canonical logical fields are defined in `message-envelope-and-classes.md` and include stable message identity, contract identity/version, producer authority, tenant/global scope, timestamps, correlation/causation and optional subject/ordering metadata.

Payloads contain contract data only. Secrets, access tokens, refresh tokens, raw credentials and unrestricted provider secrets are forbidden.

## Tenant isolation

A tenant-scoped message carries a trusted producer-derived tenant identity in its envelope. Payload text cannot select or override another tenant.

Every consumer:

1. validates the accepted message contract;
2. derives trusted message identity scope;
3. re-resolves current placement where protected tenant state is touched;
4. establishes its own `TenantContext`;
5. performs current authorization/policy checks where the work requires authority at execution time;
6. executes under the consumer's owning-domain contract.

A broker route/topic is not sufficient tenant authority.

## Producer ownership and publication

An owning use case that commits an authoritative fact and requires async publication writes the corresponding outbox record in the same transaction as the mutation/audit intent.

The dispatcher publishes after commit. It may retry publication, but it does not invent or rewrite the domain fact after the fact has been committed.

Published contract identity and immutable payload/evidence are separated from mutable dispatch attempt state.

## Delivery semantics

Default delivery is **at least once**.

Therefore:

- duplicate delivery is expected;
- broker acknowledgement is not the business completion boundary;
- consumer effects must be crash-safe;
- retry after timeout/lease loss first reconciles durable effect state when outcome can be ambiguous;
- poison messages are quarantined after bounded policy rather than retried forever;
- backoff/jitter/concurrency budgets prevent retry storms.

Exactly-once wording is prohibited unless the owning business effect proves exactly-once semantics end-to-end. A broker's exactly-once/transaction feature by itself does not satisfy that requirement.

## Ordering

Global ordering is not promised.

Per-aggregate, per-stream or per-process ordering is opt-in and contract-specific. Where ordering matters, the contract declares:

- ordering scope;
- trusted ordering key;
- sequence/version semantics;
- whether gaps are allowed;
- consumer behavior on duplicate, stale, out-of-order or gap detection;
- replay behavior.

Deduplication identity and ordering identity are separate concepts.

## Replay

Replay is a governed operational capability, not ordinary redelivery with an operator-controlled flag.

A replay contract defines:

- source authority and replay range;
- whether the original message identity is preserved;
- consumer eligibility and dedup interaction;
- authorization/data-retention constraints;
- ordering/gap expectations;
- observability and audit;
- behavior when original contract versions are no longer directly consumable.

Replaying an old event does not authorize repeating an already-completed irreversible side effect.

## Recovery continuity

Async correctness must survive restore/PITR/partial-loss scenarios.

After recovery, missing outbox/inbox/dedup/consumer offset/replay state is not automatically interpreted as "never published", "never consumed" or "safe to execute".

The accepted `(R,F]` recovery interval reconciles as applicable:

- committed business facts;
- outbox publication state;
- inbox/dedup receipts;
- stable process/operation results;
- provider/external acknowledgements;
- audit/accountability evidence;
- consumer progress/checkpoints;
- source/producer generation authority.

A restored cell/consumer remains fail-closed or reconciliation-blocked for duplicate-sensitive effects until continuity is established.

## Realtime boundary

Phase 10 defines the realtime message/request/ack protocol representation only after Phase 09 admission and subscription authority checks succeed.

A realtime message never becomes authorization. The gateway must continue enforcing Phase 09 current session/membership/permission/tenant and placement-generation lifecycle rules throughout the subscription.

When authority or placement is retired, Phase 10 delivery stops because Phase 09 says the subscription is no longer authorized; the message protocol does not override that decision.

## Telemetry volume boundary

High-volume telemetry is not automatically routed through the general event broker.

Raw metrics/observations may use the accepted specialized telemetry plane. Phase 10 contracts are appropriate for durable transitions, operational signals, process triggers, integration events and bounded derived notifications where consumer semantics require them.

A future broker choice must not force bulk telemetry into a topology that conflicts with the accepted telemetry architecture.

## Provider boundary

Provider callbacks/reads are normalized by adapters before platform events are published. Provider-native payloads, event names and identifiers may be retained as external references/evidence, but consumers subscribe to JLMIRROR-owned contracts.

Replacing Zabbix or adding another provider must not require every downstream consumer to rewrite around provider-native message schemas.

## Compatibility

Async compatibility includes more than payload fields. Security/correctness-sensitive semantics include:

- contract identity/version;
- tenant/global scope;
- message identity scope;
- producer authority/generation;
- delivery/ack policy;
- retry/quarantine policy;
- ordering/partition/sequence semantics;
- replay behavior;
- consumer effect/idempotency policy;
- retention/recovery continuity;
- data classification;
- realtime/webhook projection behavior.

A change can therefore be breaking even when a JSON schema is unchanged.

## Contract-first rule

A new async contract is not implementation-ready until it declares at minimum:

- message class and owning producer capability;
- stable `contract_name` and version policy;
- tenant/global scope;
- canonical message identity and trusted identity scope;
- payload schema and data classification;
- correlation/causation policy;
- publication/outbox boundary;
- delivery semantics;
- consumer acknowledgement/completion boundary;
- retry/backoff/quarantine classification;
- inbox/idempotency/effect completion policy where duplicates matter;
- ordering/sequence/gap/replay profile where relevant;
- current placement/authorization behavior for delayed protected work;
- recovery/retention continuity;
- observability/audit requirements;
- compatibility/deprecation implications;
- realtime/webhook projection semantics where applicable;
- numeric limits or explicit OPEN items.

## What Phase 10 intentionally does not select

Phase 10 does not prematurely select:

- Kafka, NATS, SQS/SNS, RabbitMQ, Redis Streams, cloud pub/sub or another broker;
- partition count or queue topology;
- broker-specific acknowledgement modes;
- schema-registry vendor;
- exact wire serialization for every contract where logical semantics suffice;
- numeric retry/retention/backoff/dead-letter thresholds without evidence;
- deployment-specific topic/queue naming;
- service extraction boundaries not justified by the accepted architecture;
- new Product capabilities merely because an event architecture could support them.

These remain OPEN implementation/profile decisions unless a contract requires an exact external wire representation.

## Maximum-state evolution test

Before a Phase 10 contract is accepted, reviewers SHOULD ask whether it remains correct when:

- delivery is duplicated and reordered;
- producer and consumer versions differ during rolling deployment;
- a tenant relocates between cells while messages are in flight;
- a consumer is extracted to another service/region;
- broker technology is replaced;
- a message is replayed months later under a retained contract version;
- a consumer crashes after an external effect but before acknowledgement;
- a recovery restores local inbox/outbox state backward while external effects survive;
- realtime clients miss every message and must fully resynchronize;
- provider adapters change without changing platform event semantics;
- one workload grows 100x and requires independent partitioning/scaling.

If a consumer must understand physical topology, provider-native schemas or broker internals to remain correct, the contract is insufficiently decoupled.
