# Wave 4 Monitoring — Alerting Publication Bridge Authorization

**Status:** proposed bounded implementation authorization  
**Base:** `main@193883f0b3ddfd3531ceb54e0849c2f6e04744bc`  
**Authorization ID:** `wave4.monitoring-alerting-publication@1`

## Purpose

Authorize the next bounded cross-domain slice after canonical Monitoring Health Projection: publish minimal Monitoring-owned integration-event invalidations for canonical Problem State and Health Projection transitions so a future Alerting consumer can durably detect that protected Monitoring state changed and re-read current owner state.

This authorization does **not** create Alerting lifecycle/mutation authority. It does not create alerts, acknowledgement, suppression, routing, notification, escalation, incidents, ITSM tickets, AIOps findings, Automation actions, provider write-back, browser realtime messages or public webhooks.

## Canonical contracts

Two exact logical contracts are authorized:

```text
monitoring.problem-state.changed
monitoring.health-projection.changed
```

Both are `integration_event` class, contract version `1`, producer `Monitoring`, tenant-confidential, at-least-once, and **invalidation/resync signals rather than state replication**.

They inherit the accepted Phase 10 logical envelope without weakening or redefining it:

```text
message_class        integration_event
contract_version     1
producer             Monitoring
tenant_id             required trusted tenant identity
subject               contract-specific canonical JLMIRROR subject
message_id            stable immutable logical event identity
occurred_at           authoritative local transition commit time
correlation_id        required
causation_id          nullable only for accepted root transition
data_classification   confidential_tenant
delivery              at-least-once
```

Publish ambiguity, dispatcher retry and redelivery MUST reuse the same logical `message_id`. Same trusted scoped `message_id` with non-equivalent immutable contract/version/subject/payload meaning is an integrity failure, never a normal duplicate.

Shared invariants:

```text
MONITORING EVENT != ALERT STATE
EVENT ARRIVAL != CURRENT STATE AUTHORITY
BROKER ORDER != OWNER-DOMAIN ORDER
PROVIDER ID != EVENT SUBJECT ID
PROVIDER TIME != EVENT CURRENTNESS AUTHORITY
OUTBOX DELIVERY != BUSINESS TRANSITION COMMIT
PUBLIC WEBHOOK != INTERNAL INTEGRATION EVENT
BROWSER REALTIME != INTERNAL INTEGRATION EVENT
HISTORICAL GENERATION != CURRENT ALERTING INPUT AUTHORITY
EVENT PAYLOAD != CURRENT PROBLEM/HEALTH STATE REPLICA
```

## Contract A — `monitoring.problem-state.changed`

### Meaning

One durable canonical Monitoring Problem State transition committed for one tenant-owned `problem_id`.

```text
contract_name   monitoring.problem-state.changed
subject_type    monitoring_problem
subject_id      problem_id
```

### Authorized trigger

The event/outbox obligation may exist only when the corresponding durable canonical Problem State transition record commits, including:

- problem creation/activation from accepted current provider evidence;
- canonical severity-class transition;
- explicit provider recovery accepted for the exact provider event binding;
- authoritative complete-negative resolution.

`problem_transition_id` MUST reference that exact immutable Monitoring transition record. A pure re-confirmation, evidence refresh, stale/incomplete marking, metadata refresh or projection update that does not create a canonical Problem State transition record creates **no** `monitoring.problem-state.changed` event under v1.

Replay of the same canonical transition does not create a second logical event. A poll that re-confirms the same meaning without a canonical transition creates no new logical publication.

### Payload v1

```text
problem_id
monitoring_source_id
source_instance_generation
monitoring_resource_id
projection_revision
problem_transition_id
```

The payload deliberately omits `problem_state` and `severity_class`. It MUST NOT include provider-native event/trigger IDs, provider acknowledgement, summary/free text, tags, endpoint URLs, credentials, provider payloads or metric values.

The payload is intentionally insufficient to decide Alerting side effects. A consumer needing protected current state re-establishes current tenant/placement/service authority and reads Monitoring using the canonical subject.

## Contract B — `monitoring.health-projection.changed`

### Meaning

One semantic canonical Monitoring Health Projection class/evidence transition committed for one tenant-owned Monitoring resource.

```text
contract_name   monitoring.health-projection.changed
subject_type    monitoring_resource
subject_id      monitoring_resource_id
```

### Authorized trigger

The event/outbox obligation may exist only when a durable Health Projection transition commits. `health_transition_id` MUST reference that exact immutable Monitoring transition record. Re-evaluating the same canonical class/evidence/snapshot/reason meaning is idempotent and creates no second logical event.

A semantic class transition always qualifies. An evidence/currentness transition may qualify only when the canonical Health implementation created a durable transition record for that revision. Merely observing a later wall-clock time or rerunning derivation with equivalent canonical meaning does not qualify.

### Payload v1

```text
monitoring_source_id
source_instance_generation
monitoring_resource_id
projection_revision
health_transition_id
```

The payload deliberately omits `health_class` and `health_evidence_state`. It MUST NOT include problem summaries, provider IDs, raw provider severity, provider acknowledgement, reason text/tags, endpoint/configuration details, credentials or raw telemetry.

## Producer authority and atomicity

1. Monitoring remains the sole semantic owner/producer of both contracts.
2. Event existence is tied to the already-authoritative immutable Monitoring transition, not to worker memory, broker acknowledgement or consumer state.
3. Publication obligation is atomic with the owning transition or deterministically recoverable from that exact durable authoritative transition record under the accepted outbox/recovery law.
4. Publish ambiguity/redelivery reuses the same stable logical `message_id`; it never invents a second semantic event.
5. Same trusted scoped event identity with different immutable contract/version/subject/payload meaning is an integrity failure, not a normal duplicate.
6. No new broker, outbox substrate or telemetry stream is authorized by this record. Implementation reuses the already accepted Phase 10 publication/outbox authority.

## Currentness and generation semantics

- Events are durable historical facts about committed Monitoring transitions.
- A delayed event from a retired source generation remains valid historical evidence of that past transition but has **zero authority to restore current state**.
- Consumers MUST compare/re-read current Monitoring owner state before protected effects.
- Broker ordering is not authoritative. Reordered events cannot regress Alerting or any other consumer.
- Cursor/message possession grants no tenant or resource authority.

## Alerting consumer boundary

This authorization exists to make a future Alerting consumer possible, but Alerting mutation remains blocked.

A future Alerting slice must separately define and authorize:

- alert identity and lifecycle;
- which Monitoring conditions are actionable;
- alert rule/policy identity/versioning;
- deduplication/correlation keys;
- open/close/reopen semantics;
- acknowledgement/suppression ownership;
- routing/notification/escalation policy;
- notification delivery history/retry;
- realtime projection;
- ITSM handoff.

No consumer may infer any of those semantics from event arrival alone.

## Consumer effect profile authorized here

The only consumer effect authorized by this record is a bounded, durable **invalidation/resync responsibility**:

1. validate envelope/contract/version/producer/tenant/message identity and bounds;
2. deduplicate under accepted Phase 10 inbox/equivalence rules;
3. record durable receipt/resync responsibility as required;
4. re-establish current tenant/placement/service authority;
5. re-read current Monitoring owner state for the canonical subject;
6. stop without creating Alerting/ITSM/AIOps/Automation business state.

## Delivery and recovery

- delivery is at-least-once;
- dispatcher/consumer retry is bounded and observable;
- one tenant/source cannot monopolize shared backlog/capacity;
- recovery follows accepted `(R,F]` owner-state/outbox/inbox reconciliation laws;
- missing restored dispatch metadata does not prove an event never existed;
- stale restored producer generation cannot regain current publication authority;
- lost equivalence/verifier authority fails closed for duplicate classification.

## Explicitly outside this slice

- Alert creation/open/close/reopen;
- Alert acknowledgement or suppression;
- notification intent, channel selection, delivery or retry;
- escalation/routing policies;
- ITSM ticket/incident creation or mutation;
- AIOps findings/correlation;
- Automation execution;
- provider acknowledgement/write-back;
- provider-native IDs in event payloads;
- problem/health semantic state values in event payloads;
- raw monitoring observations/metric values;
- browser realtime publication;
- public webhooks or SDK exposure;
- frontend behavior;
- production deployment/topology/C3 numeric sizing;
- treating event arrival/order as current Monitoring state;
- synthesizing publication from a Problem/Health refresh that has no durable canonical transition record.

## Acceptance boundary

This record grants no runtime publication authority until its exact HEAD passes deterministic CI plus panoramic/adversarial review and is separately squash-merged into `main`. Runtime publication implementation and all Alerting business behavior remain blocked until their own accepted gates.
