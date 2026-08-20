# Message Envelope and Classes

**Status:** proposed baseline  
**Phase:** 10 — Events / Async Contracts

## Purpose

This document defines the transport-independent logical envelope shared by JLMIRROR asynchronous contracts and the semantic distinction between facts, work commands, process signals, realtime projections and outbound delivery messages.

The envelope is a contract model, not a broker record layout. A concrete serializer may add framing metadata required by its transport, but it may not change the logical meaning defined here.

## Canonical logical envelope

Every Phase 10 message declares or inherits these logical fields:

```text
message_id
message_class
contract_name
contract_version
producer
producer_generation (when the producer authority can be retired/replaced)
tenant_id (required for tenant-scoped contracts; absent only for explicit global contracts)
subject (optional contract-defined logical resource/process reference)
occurred_at / created_at according to message class
correlation_id
causation_id (nullable only for an accepted root cause)
trace_context (optional, never authority)
ordering metadata (only when the contract defines it)
data_classification
payload
```

Exact JSON/Protobuf/Avro/CloudEvents-like encoding remains an implementation/profile choice until explicitly accepted. The field semantics do not.

## `message_id`

`message_id` is an opaque stable identity for one logical published message instance.

Properties:

- generated/assigned by the trusted producer boundary, not supplied as arbitrary payload authority;
- unique within the authoritative `message_identity_scope` required by each consumer contract;
- stable across ordinary broker redelivery of the same logical message;
- not reused for a semantically different message;
- not overloaded as tenant ID, aggregate revision, ordering sequence, correlation ID or operation ID.

For accepted event outbox records whose upstream schema names the identity `event_id`, that durable `event_id` is the canonical Phase 10 message identity for the published event; publication does not invent a second unrelated identity.

For jobs, the accepted durable `job_id` is the message identity of that work command unless a separately accepted wrapper contract needs another transport instance ID. Any such wrapper ID is operational metadata and cannot weaken job idempotency.

## `message_class`

Allowed semantic classes are intentionally small:

```text
domain_event
integration_event
job_command
process_signal
realtime_projection
outbound_webhook_delivery
```

A contract may define a narrower subtype under `contract_name`, but it does not invent a new top-level class without contract review.

## `contract_name`

`contract_name` is a stable platform-owned logical name.

Naming rules:

- provider-neutral;
- bounded-context/capability aligned;
- descriptive of a fact or work intent, not transport topology;
- does not include queue/topic/cell/database/region instance names;
- does not change when a module is extracted into a service.

Examples are illustrative only and do not create Product requirements:

```text
monitoring.observation-state.changed
alerting.alert.opened
organization.member-access.changed
platform.tenant-relocation.progressed
```

A concrete contract is added only when the owning Product/domain use case exists.

## `contract_version`

`contract_version` identifies the semantic contract version consumed by producers/consumers.

Phase 10 compatibility rules are defined in `schema-evolution-compatibility-and-governance.md`.

The version is not:

- deployment version;
- Git SHA;
- broker schema ID;
- provider API version;
- cell generation;
- database migration number.

A schema-registry vendor may map this logical version to its own ID, but that mapping is not the contract identity.

## `producer`

`producer` identifies the stable logical producing capability/bounded context, not a process instance.

Examples of acceptable meaning:

```text
Monitoring
Alerting
Organization & Access
Platform Management
```

A hostname, pod, function ID, broker publisher client ID or database schema name is observability metadata, not canonical producer identity.

## `producer_generation`

Some producer authorities can be retired or replaced, especially during tenant relocation, source failover, provider/source cutover or recovery.

When stale publication from an old source could be accepted incorrectly, the contract includes or derives a trusted `producer_generation` / source-generation dimension.

Rules:

- generated from trusted placement/source/control-plane authority;
- never selected by arbitrary payload text;
- consumers that require current-source semantics validate it against the applicable trusted authority;
- a retired generation cannot regain authority merely because delayed messages arrive later;
- exact encoding is OPEN.

Not every event requires an exposed generation field. A contract may bind generation in trusted transport/consumer context instead, provided the same security/correctness property is proven.

## Tenant/global scope

Tenant-scoped messages require a canonical `tenant_id` at envelope level.

`tenant_id`:

- comes from trusted producer `TenantContext`/owning state;
- is not inferred from a user/provider payload field at the consumer;
- participates in message identity scope and isolation where required;
- does not encode physical placement;
- remains the same logical tenant identity when the tenant relocates.

A global message may omit `tenant_id` only when the contract is explicitly global and its consumer semantics do not accidentally collapse tenant-scoped effects into a shared namespace.

Using `null`/absent tenant scope as a convenience for unknown tenant identity is prohibited.

## Subject

`subject` optionally identifies the logical resource, aggregate, operation or process the message concerns.

A subject is platform-owned logical identity such as:

```text
subject_type
subject_id
```

Provider-native IDs may appear only as explicit external references inside an adapter-owned payload where required; they do not replace platform subject identity.

`subject` is not authorization. Consumers still use current trusted tenant/resource policy when protected execution requires it.

## Time semantics

### Events

Events use `occurred_at` representing when the authoritative fact became true/committed according to the producer contract.

Publication/dispatch timestamps may exist as operational metadata but do not rewrite event occurrence time.

### Jobs/process signals

Jobs use `created_at` and may additionally define:

```text
not_before
deadline
```

where meaningful.

A deadline does not prove cancellation or that an external effect did not happen after timeout.

### Realtime projections

Realtime projection messages reference the authoritative event/state occurrence time where available. Socket send time is not authoritative business time.

## Correlation and causation

`correlation_id` groups a logical workflow/request/process across synchronous and asynchronous boundaries.

`causation_id` identifies the immediate logical cause when one exists.

Rules:

- tracing/correlation is not tenant or authorization authority;
- a caller-provided correlation value is validated/bounded before propagation;
- secrets and protected cursors are never used as correlation identifiers;
- a consumer producing a new message normally sets the consumed message/process identity as causation while preserving the broader correlation chain;
- recursive loops must be detectable through contract/process logic rather than relying only on correlation IDs.

## `trace_context`

Distributed tracing metadata may be propagated under the accepted tracing profile.

It is strictly observability metadata:

- not trusted tenant scope;
- not authorization;
- not idempotency identity;
- not ordering authority;
- redacted/validated according to data-classification policy.

Exact propagation standard remains OPEN until accepted.

## Data classification

Every contract declares an envelope/payload data classification sufficient to enforce logging, retention, replay and destination rules.

At minimum, contracts distinguish whether payload fields may contain:

- public data;
- internal operational data;
- confidential tenant data;
- regulated/sensitive data;
- secret/credential material.

Secret/credential material is prohibited from normal async payloads. Where a workflow requires a secret, messages carry an opaque secret reference/capability designed for the recipient and retrieve the secret through the accepted secret boundary.

## Payload

`payload` is contract-owned and versioned.

Rules:

- platform/domain language only;
- no ORM/database-row dumps as public async contracts;
- no provider-native payload promoted directly to domain consumers;
- unknown compatible fields follow the contract compatibility profile;
- payload is bounded in size/depth/item count by contract/profile;
- large binary/document content is referenced through artifact/resource identity, not embedded unbounded in messages;
- payload cannot override envelope tenant/producer/generation/identity authority.

## Domain events

A `domain_event` records a fact emitted by the owning domain.

Properties:

- past-tense/fact semantics;
- immutable historical meaning;
- emitted only after/with authoritative commit via the accepted outbox boundary when external consumption requires it;
- does not instruct an arbitrary consumer to perform a privileged action merely because it exists.

Internal-only domain events may remain module-local typed contracts and need not be broker-published unless a consumer/process boundary requires publication.

## Integration events

An `integration_event` is intentionally stable for consumers outside the producer's internal domain implementation.

It may:

- project one domain event into a stable external integration shape;
- combine information needed to avoid downstream database coupling;
- hide internal aggregate structure/provider details;
- evolve independently from internal implementation events.

A domain refactor does not require consumers to understand the refactor when the integration contract semantics remain stable.

## Job commands

A `job_command` means "attempt this accepted work under this durable operation identity".

It includes/derives as applicable:

```text
operation_id
job_type / contract_name
tenant_id
not_before / deadline
correlation_id
causation_id
payload
```

The worker does not infer that work has already happened merely because it received a job. It must establish current placement/authority and execute under the accepted idempotency/reconciliation contract.

## Process signals

A `process_signal` informs a persisted process manager of an event/condition/result.

It does not make queue order the process authority. The process manager loads its durable state, applies current transition rules and records the next stage/outbox atomically where applicable.

Duplicate/out-of-order process signals must be explicitly handled by process state/version/idempotency semantics.

## Realtime projections

A `realtime_projection` is non-authoritative acceleration.

The message may contain:

- stable contract identity/version;
- tenant/resource reference;
- `message_id`;
- occurred time;
- optional sequence/cursor where the channel supports replay;
- bounded projection payload.

Clients must be able to recover by authoritative snapshot/API resynchronization. A realtime message never substitutes for durable process/business state.

## Outbound webhook delivery messages

`outbound_webhook_delivery` is an internal delivery-work representation used by the webhook delivery adapter.

The external webhook payload has its own versioned contract. Internal delivery attempt fields such as destination, attempt count and next attempt time are not promoted into the business event contract.

## Identity versus ordering

The following identities SHALL remain conceptually separate:

```text
message_id       -> duplicate/redelivery identity
contract_name    -> semantic contract identity
subject identity -> logical resource/process identity
operation_id     -> durable effect/process identity
sequence/version -> ordering/freshness identity
correlation_id   -> workflow observability identity
causation_id     -> immediate causal linkage
```

Using one field as several authorities creates future collision and recovery ambiguity and is prohibited unless the contract proves equivalence explicitly.

## Message metadata integrity

Consumers SHALL treat envelope authority as trusted only when delivered through the accepted producer/broker boundary.

A consumer does not accept arbitrary internet/client/provider payloads as internal messages simply because they contain fields named `tenant_id`, `producer` or `contract_name`.

Provider callbacks are authenticated/normalized under Phase 09 before any internal event publication occurs.

## Size and complexity

Every contract/profile declares bounded:

- envelope/header size;
- payload bytes;
- object nesting/collection counts where structured;
- key/string lengths;
- batch count when batching is accepted.

Unlimited event bodies are not an accepted default. Large data sets use artifact/read-model/telemetry references appropriate to the accepted architecture.

## Batch envelopes

A broker may transport multiple messages in one protocol batch, but batching does not collapse logical identities.

Each logical message retains:

- independent `message_id`;
- independent contract validation;
- tenant scope;
- deduplication/effect semantics;
- per-message failure classification unless the contract explicitly defines atomic batch semantics.

A transport batch is not automatically one business transaction.

## Forbidden envelope practices

The following are prohibited:

- provider-native event type as the only platform contract identity;
- physical cell/database/queue/topic as logical resource identity;
- consumer trusting payload tenant fields over envelope/placement authority;
- access tokens/API keys/session secrets in payload;
- using broker offset as the only duplicate-effect identity;
- treating a correlation ID as idempotency or authorization;
- reusing one `message_id` for semantically different payloads;
- mutating the historical meaning of an already-published contract version.

## Required contract tests

Every implemented envelope profile tests as applicable:

- malformed/unknown contract identity/version rejection;
- payload cannot override trusted tenant/producer/generation context;
- same `message_id` + same trusted scope redelivers safely;
- same raw `message_id` from different authoritative scopes does not collide where IDs are not globally unique;
- secrets/forbidden data fail contract validation/redaction policy;
- oversized/deep payload rejected/quarantined before unbounded work;
- producer generation retirement prevents stale-source acceptance when the contract requires current source;
- correlation/trace metadata cannot alter authority.
