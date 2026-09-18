# G6 Monitoring → Alerting Transport — Implementation Authorization

**Status:** proposed exact-scope authorization  
**Canonical base:** `main@edaa73b4b1752ab7bd9d4e8b73fd6e60976364c4`  
**Authorization ID:** `g6.monitoring-alerting-transport@1`

## Purpose

Authorize only the sixth AI-E2E product increment: complete the already-authorized Monitoring → Alerting invalidation/resync transport by adding the bounded Alerting consumer side.

The accepted producer side already exists in `main`:

- Monitoring Problem/Health transition-bound publication;
- immutable Phase 10 outbox obligation;
- stable message identity;
- at-least-once delivery semantics;
- publication recovery.

G6 adds only:

1. contract/envelope validation for the two accepted Monitoring integration events;
2. durable create-or-observe receipt in the accepted Wave 2 consumer inbox;
3. duplicate/equivalence handling under the accepted inbox law;
4. bounded claim/retry/reconciliation ownership;
5. current-authority re-read of canonical Monitoring Problem/Health owner state;
6. durable completion of the resync responsibility;
7. operational diagnostics/proof.

G6 MUST NOT create, resolve, reopen, acknowledge, suppress, route or notify any Alert. It MUST NOT evaluate Alert policy. It MUST NOT create a parallel broker/outbox/inbox substrate.

## Authorization on acceptance

```text
implementation_authority_before_merge = blocked
implementation_authority_after_merge = granted_for_exact_g6_monitoring_alerting_transport_only
```

Authorized slice:

```text
g6.monitoring-alerting-transport@1
```

`merge_authorization = not_granted` remains separate.

## Dependency boundary

G6 depends on:

- canonical G1–G5 implementations;
- accepted Wave 2 async/outbox/inbox correctness substrate;
- accepted Monitoring event contracts;
- accepted Wave 4 Monitoring→Alerting publication authorization;
- accepted Monitoring→Alerting publication runtime;
- accepted Alerting Core Model authority only as a **non-effectful boundary reference**.

The Alerting Core Model does not authorize G6 to create Alert state. Policy/evaluation remains separately blocked for G7.

## Implementation path authority

Allowed prefixes:

- `apps/g6-monitoring-alerting-transport/`;
- `contracts/g6-monitoring-alerting-transport/`;
- `implementation/g6-monitoring-alerting-transport/`;
- `tests/g6/`;
- `tools/g6/`.

Allowed exact paths:

- `sql/integration/002_monitoring_alerting_consumer.sql`;
- `.github/workflows/g6-monitoring-alerting-transport-runtime.yml`.

Required future implementation PR identity:

- branch prefix `impl/g6-monitoring-alerting-transport`;
- label `jlmirror-slice:g6-monitoring-alerting-transport`;
- claim file `implementation/g6-monitoring-alerting-transport/IMPLEMENTATION_CLAIM.json`;
- authorization ID `g6.monitoring-alerting-transport@1`;
- same repository;
- base equal to the live default-branch tip when trusted evidence is produced.

Shared Wave 2/Wave 4/Monitoring/Alerting files remain read-only. The exact integration migration is the only authorized persistence/privilege composition path.

## Contracts admitted

Exactly:

```text
monitoring.problem-state.changed
monitoring.health-projection.changed
```

Both remain:

```text
message_class        integration_event
contract_version     1
producer             Monitoring
delivery             at-least-once
data_classification  confidential_tenant
meaning              invalidation/resync only
```

No semantic Problem state, Health class, provider payload or metric value may be trusted from the event payload.

## Consumer effect authorized

The only consumer effect is:

```text
durable_invalidation_resync_responsibility
```

Sequence:

```text
receive accepted Monitoring integration event
 -> validate envelope/contract/version/producer/tenant/message bounds
 -> create-or-observe Wave 2 inbox receipt
 -> classify duplicate/equivalence fail-closed
 -> claim under current execution/placement authority
 -> re-establish current tenant/service authority
 -> re-read canonical Monitoring owner state
 -> verify generation/currentness
 -> durably complete resync responsibility
 -> stop
```

There is no Alert mutation step.

## Binding semantics

```text
MONITORING_EVENT != ALERT
EVENT_ARRIVAL != ALERT_CREATION_AUTHORITY
EVENT_PAYLOAD != CURRENT_MONITORING_STATE
BROKER_ORDER != OWNER_DOMAIN_ORDER
OUTBOX_DELIVERY != BUSINESS_TRANSITION_COMMIT
MESSAGE_ID != BUSINESS_EFFECT_ID
INBOX_RECEIPT != ALERT
INBOX_COMPLETED != ALERT_CREATED
DUPLICATE_DELIVERY != DUPLICATE_RESPONSIBILITY
HISTORICAL_GENERATION != CURRENT_ALERTING_INPUT_AUTHORITY
PROBLEM_EVENT != PROBLEM_STATE_REPLICA
HEALTH_EVENT != HEALTH_STATE_REPLICA
CURRENT_REREAD_REQUIRED_BEFORE_RESYNC_COMPLETION
CURRENTNESS_UNKNOWN != OPTIMISTIC_EFFECT
```

## Durable consumer boundary

The future exact SQL migration may only compose accepted substrate to support this G6 consumer. It may:

- create a dedicated NOLOGIN/least-privilege G6 consumer execution capability;
- bind exact EXECUTE/SELECT privileges required for the accepted worker flow;
- create bounded SECURITY DEFINER functions owned by that capability where needed;
- create no new generic inbox/outbox/broker substrate;
- use `system.async_consumer_inbox` as canonical receipt/dedup/reconciliation state;
- reuse accepted cross-authority operation/reconciliation records only where the Wave 2 law requires them;
- enforce tenant/contract/message identity binding and immutable equivalence evidence;
- expose only bounded diagnostics required for proof.

It MUST NOT create Alert projection/lifecycle/policy tables.

## Current Monitoring re-read boundary

For `monitoring.problem-state.changed`:

- use canonical `problem_id` / source generation references;
- re-read current canonical Problem owner state;
- historical generation is valid historical event evidence but not current Alerting input.

For `monitoring.health-projection.changed`:

- use canonical `monitoring_resource_id` / source generation references;
- re-read current canonical Health owner projection;
- historical generation is not current Alerting input.

Payload state values are not accepted because v1 deliberately does not carry them.

## Duplicate / redelivery / restart

Required behavior:

- same scoped `message_id` + equivalent immutable meaning creates one inbox identity;
- duplicate/redelivery never creates a second resync responsibility;
- same scoped `message_id` + non-equivalent immutable meaning fails closed/quarantines per accepted law;
- worker restart/claim expiry does not invent effect absence;
- ambiguous completion enters accepted reconciliation rather than blind retry;
- replay preserves the same logical consumer identity;
- current Monitoring reread decides currentness, not broker sequence.

## Operational diagnostics authority

G6 may expose internal/test diagnostics for:

- admitted / duplicate / processing / completed / reconciliation-required / quarantined receipt state;
- contract/message/tenant identity in bounded canonical form;
- current reread outcome class;
- current-vs-historical generation disposition;
- retry/reconciliation proof;
- lag/count evidence required by runtime proof.

No tenant-facing Alert UI/API is authorized by G6.

## Explicit non-authority

G6 does not authorize:

- Alert projection persistence;
- Alert transition persistence;
- Alert creation/resolution/reopen;
- Alert policy/rule identity, DSL, selectors or evaluation;
- `policy_id` / `policy_version` effectful use;
- Alert lifecycle state mutation;
- Alert acknowledgement/suppression;
- responsibility/action ownership;
- notification intent/delivery/routing/escalation;
- ITSM incidents/tickets/tasks;
- Automation/AIOps mutation;
- provider write-back;
- browser realtime/public webhooks;
- new broker/outbox/inbox substrate;
- direct provider calls;
- mutation of Monitoring business truth;
- production deployment/C3 numerics.

## Required proof before later implementation merge

- exact allowlist diff;
- exact integration migration only;
- Wave 2 inbox reuse and no parallel inbox;
- accepted publication runtime conformance reused;
- event contract validation tests;
- duplicate/redelivery/restart falsification;
- conflicting-equivalence fail-closed proof;
- tenant/message/contract scope binding;
- current Monitoring Problem re-read proof;
- current Monitoring Health re-read proof;
- historical generation ignored as current input;
- reordered delivery cannot regress current disposition;
- inbox claim/reconciliation proof;
- no Alert tables/rows/transitions created;
- no policy/evaluation path;
- runtime/container proof;
- exact-head CI green;
- trusted scope/readiness;
- panoramic/adversarial review;
- separate explicit owner merge authorization.

```text
G5_AUTHORIZED != G6_AUTHORIZED
G6_AUTHORIZED != G7_AUTHORIZED
TRANSPORT_READY != ALERT_POLICY_AUTHORIZED
MONITORING_EVENT != ALERT
INBOX_COMPLETION != ALERT_LIFECYCLE_TRANSITION
IMPLEMENTED != PRODUCTION_READY
GREEN_STATUS != MERGE_AUTHORIZATION
READY_FOR_MERGE != AUTHORIZED_TO_MERGE
```
