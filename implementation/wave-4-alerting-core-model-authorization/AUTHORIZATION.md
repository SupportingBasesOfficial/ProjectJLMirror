# Wave 4 Alerting — Core Model Authorization

**Status:** proposed bounded implementation authorization  
**Base:** `main@e7cb9512846926f01429d3fbc4c6d6b0a2a9db71`  
**Authorization ID:** `wave4.alerting-core-model@1`

## Purpose

Authorize the canonical **Alerting-owned alert model and lifecycle semantics** required after the accepted Monitoring -> Alerting invalidation bridge, without yet authorizing alert-policy evaluation, automatic alert creation, acknowledgement, suppression, routing, notification delivery, escalation, realtime, ITSM mutation, AIOps mutation, Automation actions, provider write-back, frontend behavior or production deployment.

This slice closes the state model that future Alerting policy/runtime work must preserve. It deliberately does not let Monitoring events create alerts by themselves.

## Ownership boundary

Alerting owns:

- canonical `alert_id`;
- alert lifecycle state;
- immutable source-evidence linkage to Monitoring canonical identities/revisions;
- immutable alert transition history;
- current alert projection/read semantics.

Monitoring remains owner of Monitoring resources, problems, health and their currentness. An Alert never becomes a copy or alternate owner of Monitoring state.

```text
MONITORING PROBLEM != ALERT
MONITORING HEALTH != ALERT
MONITORING EVENT != ALERT
ALERT != ITSM INCIDENT
ALERT != NOTIFICATION DELIVERY
ALERT != AIOPS FINDING
PROVIDER ID != ALERT ID
EVENT ARRIVAL != ALERT CREATION AUTHORITY
POLICY VERSION != MUTABLE LOOKUP AT EXECUTION TIME
```

## Canonical identity

1. `alert_id` is an opaque platform-owned Alerting identity, tenant-scoped and independent from `problem_id`, `monitoring_resource_id`, provider IDs, event IDs, policy IDs and human-readable labels.
2. Provider-native IDs never become alert identity.
3. Monitoring `problem_id` and/or `monitoring_resource_id` may be retained as source references, not identity aliases.
4. An alert is always owned by exactly one tenant. Cross-tenant correlation into one alert is prohibited.
5. Human-readable display numbers, if introduced later, remain lookup/display attributes and never replace `alert_id`.

## Lifecycle v1

The canonical lifecycle state is exactly:

```text
active | resolved
```

Rules:

1. `active` means Alerting currently retains one actionable alert occurrence under its own accepted policy authority.
2. `resolved` is terminal for that `alert_id`.
3. A resolved `alert_id` never reopens. A future distinct actionable occurrence requires a new `alert_id` unless a separately accepted future lifecycle version explicitly introduces another semantic model.
4. Re-observing equivalent evidence for an already-active alert is idempotent and must not create another logical alert or transition.
5. Resolution requires an Alerting-owned decision made from current authorized source/policy evidence. Monitoring problem resolution, Health becoming healthy, event absence, timeout or consumer retry do not themselves mutate Alert state without the separately authorized policy/evaluation boundary.
6. Provider acknowledgement has zero Alert lifecycle authority.
7. Broker arrival order has zero Alert lifecycle authority.
8. Historical Monitoring generations may remain source evidence but cannot create or resolve a current alert merely by delayed delivery.

## Lifecycle fields

The canonical Alert projection may contain only bounded, platform-owned semantics such as:

```text
tenant_id
alert_id
lifecycle_state = active | resolved
source_kind = monitoring_problem | monitoring_health_projection
monitoring_source_id
source_instance_generation
monitoring_resource_id nullable by source kind
problem_id nullable by source kind
source_projection_revision
source_transition_id
policy_id
policy_version
opened_at
resolved_at nullable
last_confirmed_at
projection_revision
created_by_transition_id
last_transition_id
```

The source discriminant is closed:

- `monitoring_problem` requires `problem_id`; `monitoring_resource_id` may also be retained when the accepted Monitoring problem association proves it;
- `monitoring_health_projection` requires `monitoring_resource_id` and MUST NOT carry `problem_id` as if Health were a Problem occurrence;
- one Alert occurrence has exactly one source evidence family; Problem and Health evidence are never merged into an ambiguous source tuple.

`policy_id` and immutable `policy_version` are required on every v1 effectful lifecycle transition once policy evaluation is separately authorized. There is no policy-less create/resolve path in this lifecycle version.

## Source evidence law

1. Alerting consumes only canonical Monitoring identities/state through the accepted Monitoring -> Alerting invalidation/resync bridge and current-authority Monitoring rereads.
2. Event payload is not current-state authority.
3. Before any future effectful Alerting decision, the consumer must re-establish current tenant/placement/service authority and reread the relevant Monitoring owner projection.
4. Source evidence retained on an Alert is evidence of the decision that was accepted; it is not a writable mirror of Monitoring.
5. A later Monitoring change does not rewrite historical Alert transition evidence.
6. If source currentness cannot be proven, future policy/evaluation logic must fail closed or defer; this core-model authorization does not permit optimistic creation/resolution.
7. Source family, canonical source identity, source generation, source transition/revision, `policy_id` and immutable `policy_version` are part of the accepted decision evidence and cannot be silently rewritten after the transition commits.

## Transition model

Every semantic lifecycle change has one immutable transition record.

```text
alert_transition_id
alert_id
from_state nullable for create
to_state
transition_reason
source_kind
source_transition_id/source_projection_revision
policy_id
policy_version
occurred_at = authoritative Alerting commit time
correlation_id
causation_id nullable only for accepted root transition
```

Rules:

1. create `NULL -> active` and resolve `active -> resolved` are the only lifecycle transitions in v1;
2. replay of the same accepted transition identity is idempotent;
3. same trusted transition identity with different immutable meaning is an integrity failure;
4. `opened_at` is immutable after creation;
5. `resolved_at` is null while active and required when resolved;
6. `resolved_at >= opened_at`;
7. `projection_revision` advances exactly once for each accepted semantic Alert projection change;
8. transition history is immutable/append-only;
9. platform commit/acceptance time governs lifecycle ordering, not provider event time;
10. every create/resolve transition requires the exact immutable policy identity/version whose separately authorized evaluation produced the decision;
11. a later edit/new version of a policy cannot retroactively change the meaning of a committed Alert transition.

## Policy boundary

This authorization intentionally does **not** define or activate alert-policy evaluation.

A separate accepted authorization is required before runtime may decide:

- which Monitoring Problem/Health conditions are actionable;
- severity/class predicates;
- resource/source selectors;
- grouping/correlation/deduplication keys beyond transition replay;
- policy precedence/conflict resolution;
- policy enable/disable/effective-version semantics;
- whether a current condition opens a new Alert;
- whether source recovery resolves an Alert.

Until that gate is accepted, there is **no automatic Alert creation or resolution authority** and therefore no valid runtime producer of the required `policy_id/policy_version` lifecycle evidence.

## Acknowledgement and suppression

Acknowledgement and suppression are explicitly separate concerns from lifecycle.

This slice does not authorize:

- `acknowledged` as a lifecycle state;
- `suppressed` as a lifecycle state;
- acknowledgement commands;
- suppression windows/reasons;
- provider acknowledgement mapping;
- using ACK/suppression to resolve an alert.

Their ownership/semantics require later independent contracts.

## Read boundary

The reserved API family remains:

```text
GET /api/v1/tenants/{tenant_id}/alerts
GET /api/v1/tenants/{tenant_id}/alerts/{alert_id}
```

A future implementation under this authorization may provide bounded Alert reads only after defining the exact permission/action profile consistent with Phase 09 authorization laws.

Required read invariants:

- tenant isolation;
- opaque `alert_id` anchor/identity;
- authorization re-established for every protected read/page;
- cursor possession grants no authority;
- deterministic pagination;
- finite row and serialized-response byte bounds;
- no provider payloads, credentials, unrestricted tags/text or notification secrets in broad list responses.

This authorization does not invent an action string if one is not already accepted elsewhere; runtime API activation must bind to an accepted permission vocabulary first.

## Persistence and isolation

Any future implementation of this authorized model must provide:

- tenant-owned Alert projection;
- immutable transition history;
- FORCE RLS/tenant isolation consistent with accepted pooled-tenant laws;
- least-privilege execution roles;
- immutable tenant/alert identity ownership;
- bounded source/policy references;
- exact source-kind integrity constraints;
- immutable policy identity/version evidence on lifecycle transitions;
- no direct Alerting mutation authority over Monitoring tables;
- no direct Monitoring mutation authority over Alerting tables.

## Recovery and idempotency

1. Durable Alert transitions are business truth; in-memory consumer progress is not.
2. At-least-once/redelivery ambiguity must not duplicate Alert transitions.
3. Recovery must reconcile Alert projection and transition evidence under accepted `(R,F]` laws.
4. Missing restored consumer metadata cannot be treated as proof that an Alert transition never committed.
5. Stale restored Monitoring generation/event evidence cannot regain current Alerting decision authority.
6. Same logical transition is represented by one stable transition identity across ambiguous retry/recovery.
7. Recovery must retain the exact source-kind/source evidence and policy identity/version that authorized the original transition; it cannot reevaluate historical transitions under a newer policy version and call them equivalent.

## Explicitly outside this slice

- alert-policy/rule DSL or evaluation runtime;
- automatic Alert creation/resolution from Monitoring events;
- policy-less or ad-hoc Alert create/resolve;
- acknowledgement;
- suppression;
- routing;
- notification intent/channel selection;
- notification delivery/retry/history;
- escalation policy/execution;
- realtime delivery;
- public webhooks;
- ITSM incident/ticket creation or mutation;
- AIOps findings/correlation;
- Automation actions;
- provider acknowledgement/write-back;
- provider-native identities as Alert identity;
- frontend implementation;
- production deployment/topology/C3 sizing.

## Acceptance boundary

This record grants no runtime Alert mutation authority until its exact HEAD passes deterministic CI plus panoramic/adversarial review and is separately squash-merged into `main`.

Even after merge, **automatic alert creation/resolution remains blocked** until a separately accepted Alert Policy/Evaluation authorization exists. This authorization closes the canonical Alert core model only.
