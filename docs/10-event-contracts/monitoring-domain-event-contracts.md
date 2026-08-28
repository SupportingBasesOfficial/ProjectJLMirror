# Monitoring Domain Event Contracts — Wave 4 Entry

**Status:** proposed baseline  
**Phase:** 10 contract instantiation for Wave 4 Monitoring  
**Owner/producer:** Monitoring  
**Traceability:** `CAP-MONITORING`, `FR-MON-001..006`, ADR-008, ADR-009, `message-envelope-and-classes.md`, `publication-outbox-and-producer-authority.md`, `security-tenant-context-and-data-classification.md`, `docs/03-domains/monitoring-domain-contract.md`

## Purpose

This document closes the Monitoring-specific asynchronous contracts that are already applicable to the first Wave 4 vertical. It prevents implementation from inventing event names, payload authority, generation semantics or invalidation behavior after API/data code already exists.

These contracts are deliberately **state-change/invalidation signals, not state replication**. A consumer that needs current protected Monitoring state re-establishes current tenant/placement/service authority and reads the owning Monitoring projection. Delayed/reordered events therefore cannot overwrite newer state merely because they arrived later.

Acceptance does **not**:

- select Kafka or any other broker/transport;
- force raw/high-volume `metric_observation` telemetry through the general integration-event broker;
- expose internal events to public webhooks or realtime automatically;
- create Alerting, ITSM or AIOps mutation authority;
- include metric values, provider payloads, endpoint URLs, credential references or secrets in these event payloads.

## Shared envelope/profile

All contracts inherit the Phase 10 canonical logical envelope.

Fixed shared fields/profile:

```text
message_class        integration_event
contract_version     1
producer             Monitoring
tenant_id             required, trusted owner-domain tenant identity
subject               contract-specific canonical JLMIRROR identity
occurred_at           authoritative local transition commit time
correlation_id        required
causation_id          nullable only for accepted root transition
data_classification   confidential_tenant
delivery              at-least-once
payload encoding      transport-independent; concrete serializer remains C2
```

`message_id` is the stable transition/outbox event identity produced by the authoritative transaction. Ordinary publish ambiguity/redelivery reuses the same logical `message_id`.

For consumer deduplication the trusted logical identity scope is at least:

```text
(tenant_id, contract_name)
```

A concrete consumer may include its own `consumer_contract` as required by the Phase 10 inbox law. Payload fields never choose a weaker tenant/message identity scope.

Same trusted scoped ID with non-equivalent immutable contract/version/subject/payload meaning is an integrity failure, not a duplicate. Equivalence-evidence mechanism remains C2 but the Phase 10 fail-closed invariant applies.

No `secret_or_credential` content is permitted. Canonical IDs/revisions are confidential tenant metadata and are not external bearer capabilities.

## Common invalidation/resync rule

These events tell consumers **that an authoritative Monitoring boundary changed**, not that the event payload is a complete current-state replica.

Consumer rules:

1. validate contract/version/producer/tenant/message identity and bounds;
2. deduplicate by accepted Phase 10 inbox/equivalence semantics;
3. do not trust broker arrival order as current-state order;
4. if current state/effect is required, resolve current tenant placement and current consumer authorization/service authority;
5. re-read or reconcile against current Monitoring owner state using canonical subject/revision information;
6. stale/retired generation messages may remain valid historical events but cannot restore current-source authority;
7. acknowledge only after the consumer's required durable local responsibility/effect boundary is established.

A consumer may coalesce multiple pending invalidations for the same subject because the required current-state action is resync/read-current, but it must preserve enough durable receipt/equivalence evidence to keep Phase 10 duplicate/integrity semantics correct.

## Contract 1 — `monitoring.source-generation.changed`

### Meaning

An authoritative source-instance cutover committed and changed which provider-instance generation owns current Monitoring authority for one logical source.

```text
contract_name   monitoring.source-generation.changed
subject_type    monitoring_source
subject_id      monitoring_source_id
```

### Authoritative trigger

The event exists **atomically with** the serialized replacement cutover that:

- fences the prior active generation;
- advances `active_source_instance_generation`;
- installs successor configuration/scope/credential references;
- advances source revisions;
- records audit/transition evidence;
- creates successor sync/reconciliation responsibility.

If the cutover transaction does not commit, this event does not exist. If the transaction commits but dispatch crashes, the durable event/outbox obligation survives.

### Payload v1

```text
monitoring_source_id
previous_source_instance_generation
active_source_instance_generation
configuration_revision
scope_revision
source_generation_transition_id
successor_sync_operation_id
reason = replacement_cutover
```

No provider-native ID, endpoint URL, credential reference, metric value or provider payload is included.

`source_generation_transition_id` is immutable and stable; it may be the canonical outbox `event_id/message_id` when the accepted implementation profile uses the same transition identity for publication.

### Producer-generation/currentness semantics

The fact that generation N was replaced by N+1 remains valid history after later cutovers. Delayed delivery is therefore not erased merely because another generation is now active.

However the payload is not current-source authority. Consumers that need current state compare/re-read the source's current `active_source_instance_generation` and revisions. A late N→N+1 event cannot move a consumer back from N+2.

### Required consumer effect

Current-view/read-model/cache/realtime-projection consumers that subscribe to this contract treat it as a **source-wide currentness invalidation/resync boundary**:

- prior-generation resources/metrics/problems/health/current values must no longer be treated as current merely because they remain retained;
- consumers resync current active-generation state rather than synthesizing per-object remove/resolve events;
- no O(number of prior objects) integration-event fanout is required by cutover.

### Ordering

No broker global/per-source order is trusted for correctness.

`configuration_revision` and generation fields are diagnostic/current-state comparison inputs only after re-reading trusted Monitoring source authority. Consumer correctness must survive reordered generation-change events.

## Contract 2 — `monitoring.source-scope.changed`

### Meaning

The configured provider scope revision for an active Monitoring source committed.

```text
contract_name   monitoring.source-scope.changed
subject_type    monitoring_source
subject_id      monitoring_source_id
```

### Authoritative trigger

The event exists atomically with a committed scope revision change that:

- installs the new canonical configured scope definition/reference;
- advances source `scope_revision`/configuration revision as applicable;
- records required audit/transition evidence;
- creates one bounded durable scope-reconciliation responsibility.

It does **not** mean the provider removed any resource/metric/problem.

A replacement cutover that installs a successor scope and advances the authoritative scope revision also creates this event for the newly active scope boundary when the effective scope revision changes.

### Payload v1

```text
monitoring_source_id
active_source_instance_generation
previous_scope_revision
scope_revision
configuration_revision
scope_transition_id
scope_reconciliation_operation_id
reason = scope_edit | replacement_cutover
```

The event intentionally omits actual host-group selectors/provider IDs. Consumers needing scope details re-read the authorized Monitoring source contract.

### Required consumer effect

Subscribers treat the event as a current-scope invalidation:

- old per-object `in_scope` projections cannot remain trusted solely from cache/read-model age;
- current reads/resync must honor the new source `scope_revision` and `scope_evidence_state`;
- the event cannot synthesize `removed`, `retired`, `resolved` or `healthy` for individual objects;
- consumers wait for/re-read bounded scope-reconciliation evidence rather than treating event arrival as proof that all child projections finished.

### Ordering

Broker order is not authority. A consumer re-reads current `scope_revision`; an older delayed event cannot regress a newer scope revision.

## Contract 3 — `monitoring.metric-current-state.changed`

### Meaning

A semantic current metric-state transition committed for one **active-generation** metric definition under current poll/source authority.

```text
contract_name   monitoring.metric-current-state.changed
subject_type    metric_definition
subject_id      metric_definition_id
```

The signal is intentionally minimal. It is not raw telemetry and is not the historical observation stream.

### Authoritative trigger

The event/outbox obligation exists atomically with the successful current-state advancement or with an equivalent durable advancement/transition record from which the exact event is deterministically recoverable.

It is emitted only for a **semantic current-state transition**. Merely acquiring a later poll generation, re-seeing the same canonical current observation/meaning, accepting a historical/backfill observation, or replaying an historical source generation does not create another logical `metric-current-state.changed` event.

### Payload v1

```text
monitoring_source_id
source_instance_generation
monitoring_resource_id
metric_definition_id
current_observation_id
projection_revision
current_state_transition_id
evidence_state
```

No metric `value`, unit, provider-native ID, raw log/text content, endpoint/configuration or credential reference is included.

`current_state_transition_id` is immutable and stable; it may be the canonical message identity under the accepted outbox profile.

### Current-source authority

The producer may create this event only while the metric's source-instance generation is still the source's active generation and the provider/current-state fence is authoritative.

Once a generation retires:

- delayed publication of a transition that genuinely committed while it was active remains historical event evidence;
- consumers cannot use that delayed event to restore current metric state;
- replay/backfill from the historical generation cannot create a new current-state transition merely because it executes later.

### Required consumer effect

Consumers requiring the latest metric state use this event as invalidation/resync and re-read `metric-current-states` under current authority. They do not apply the payload as a complete value update.

This property lets the event remain small/confidentiality-safe and prevents broker/realtime copies from becoming an alternative current-value authority.

### Ordering

Contract ordering profile is **unordered invalidation per metric subject**. Correctness does not rely on broker ordering.

A consumer that sees events in reverse order re-reads current owner state. `projection_revision` is an opaque revision/diagnostic join unless a future accepted contract explicitly gives it total ordering semantics; consumers SHALL NOT invent lexical/numeric ordering from its encoding.

## Why there is no raw observation event here

`metric_observation` durable acceptance/history projection is governed by the telemetry-plane and `OPEN-REL-030` profile. High-volume raw observations are explicitly not forced through the general event broker.

A selected C2 telemetry mechanism may use a durable journal/stream/transport internally, but that physical record is not automatically this Phase 10 integration contract and does not become externally subscribable merely because it exists.

## Problems/health and future consumers

Track A does not invent a public/cross-domain `problem.changed`, `health.changed`, Alerting event, AIOps event or webhook contract merely because Monitoring stores those projections.

When an accepted consumer/use case requires such cross-domain publication, it receives its own exact contract/schema/current-authority analysis. Until then, Monitoring problem/health state remains queryable through the accepted API and local owner-domain projection.

This does not weaken atomic owner-domain transition/audit requirements.

## Realtime boundary

These integration events are not the browser realtime protocol.

If/when `impl.realtime@1` is activated, a realtime projection contract may consume/coalesce these events and send authorized projection messages. It must still:

- inherit Phase 09 realtime admission/current authorization;
- handle gap/loss/reconnect with snapshot/resync;
- stop/fence delivery after authority removal/relocation;
- avoid assuming complete socket history;
- apply independent realtime protocol/version/backpressure bounds.

No internal event is automatically exposed over a socket.

## Outbound webhook boundary

No contract in this file is automatically an externally subscribable webhook event. External disclosure requires an explicit Product gate, subscription policy, payload-minimization/classification review and outbound webhook contract.

## Recovery / relocation

For all three contracts:

- event existence is tied to authoritative committed transition evidence, not in-memory worker success;
- `(R,F]` recovery reconciles owner state, transition identity, outbox publication and consumer receipt/effect evidence;
- missing restored outbox/receipt state does not mean the event never existed or was never processed;
- a stable message/transition identity is reused for ambiguous republish/recovery rather than inventing a second semantic event;
- old source/cell generation cannot regain current publication/effect authority from restored stale state;
- historical fact delivery remains allowed only where the contract says the historical occurrence remains valid;
- loss of message-equivalence evidence/historical verifier authority fails closed for duplicate/effect classification according to Phase 10.

## Capacity / backpressure

`source-generation.changed` and `source-scope.changed` are low-volume control/domain facts but remain bounded per tenant/source.

`metric-current-state.changed` may be high-rate. Therefore:

- payload is fixed/minimal and excludes metric value;
- producer/outbox/backlog is bounded/observable by tenant/source/workload;
- one noisy tenant/source cannot monopolize dispatcher/consumer capacity;
- consumers may coalesce invalidations while retaining correct message/equivalence evidence;
- a selected physical transport may be specialized and partitioned independently from other integration-event workloads;
- no contract wording forces a single global broker/topic/cluster.

Exact rates, partitions, backlog thresholds and transport topology remain evidence-driven C2/C3 decisions; unlimited backlog/memory is prohibited.

## Compatibility

For v1, compatibility-sensitive semantic fields include:

- `contract_name`/message class;
- tenant/producer authority;
- subject identity;
- generation/scope transition meaning;
- whether a payload is invalidation versus state authority;
- event trigger/transaction boundary;
- data classification;
- current/historical generation semantics;
- metric transition eligibility;
- message identity/equivalence scope.

Adding a field that changes authority, currentness, ordering, tenant scope or consumer effect is not treated as a harmless optional-schema addition merely because old JSON can parse it.

## Falsification matrix

1. Cutover commits but dispatcher crashes: exactly one durable `source-generation.changed` obligation remains discoverable.
2. Cutover rolls back: no generation-change event may publish as committed fact.
3. Two reordered generation-change events cannot move a consumer from current N+2 back to N+1.
4. One generation-change event invalidates/resyncs current views without emitting one remove/resolve event per old object.
5. Scope edit commits but child reconciliation is incomplete: `source-scope.changed` cannot claim children are reconciled.
6. Scope event cannot cause provider removal/metric retirement/problem resolution by itself.
7. Reordered scope events cannot regress current scope revision at a consumer.
8. Same metric observation/meaning under a later poll generation creates no duplicate logical current-state event.
9. Historical/backfill observation creates history but no current-state event merely from later delivery/event time.
10. Retired-generation poll/replay cannot create new current-state event.
11. Metric current-state event payload contains no metric value/log/text/provider payload/credential.
12. Reordered metric invalidations cannot regress current state because consumer re-reads owner projection.
13. Same trusted scoped event ID with changed immutable payload/contract meaning fails closed, not normal duplicate.
14. Broker publish-ack loss republishes same logical message identity.
15. Cross-tenant raw identical IDs cannot deduplicate or route into another tenant scope.
16. PITR restoring old source generation/outbox cannot make retired current-source authority valid again.
17. Broker/transport outage grows only bounded/observable durable backlog; one tenant cannot exhaust unrelated workload capacity.
18. Internal event existence does not make it a public webhook or browser realtime message.

## OPEN implementation choices preserved

- broker/job transport and topology;
- serializer/schema-registry product;
- message-equivalence evidence mechanism/KMS-historical verifier backend;
- exact dispatcher/partition/backlog/coalescing numerics;
- realtime projection/transport activation;
- external webhook Product/disclosure contracts.

These are implementation/profile decisions under existing Phase 10 C2/C3 governance. The three logical contracts above are the normative Monitoring semantics they must preserve.