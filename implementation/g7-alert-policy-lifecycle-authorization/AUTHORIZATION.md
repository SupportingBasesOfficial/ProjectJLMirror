# G7 Alert Policy + Lifecycle — Implementation Authorization

**Status:** proposed exact-scope authorization  
**Canonical base:** `main@fa5dcd48c87d6776b1e77e2bd643aecad8c47553`  
**Authorization ID:** `g7.alert-policy-lifecycle@1`

## Purpose

Authorize only the seventh AI-E2E product increment: one bounded Alerting policy/evaluation model that can convert **current canonical Monitoring truth** into Alerting-owned `active | resolved` lifecycle state under the already accepted Alert Core Model.

G7 closes the first effectful Alerting golden path:

```text
accepted G6 resync responsibility
 -> current Monitoring Problem/Health reread
 -> immutable enabled policy version
 -> bounded policy evaluation
 -> idempotent Alert create/resolve
 -> protected Alert list/detail API+BFF
 -> protected Alert UI
```

G7 does **not** authorize acknowledgement, suppression, responsibility/assignment, current-action ownership, notification/delivery/routing/escalation, ITSM, Automation, AIOps or production activation.

## Authorization on acceptance

```text
implementation_authority_before_merge = blocked
implementation_authority_after_merge = granted_for_exact_g7_alert_policy_lifecycle_only
merge_authorization = not_granted
```

## Dependencies

G7 depends on:
- canonical G1–G6 implementations;
- accepted Wave 4 Alerting Core Model authorization;
- accepted Monitoring Problem State and Health Projection authorities;
- accepted G6 transport/current-reread boundary;
- canonical future-design requirements in issue #149 as a **non-effectful successor constraint**.

## Policy v1 authority

G7 may introduce tenant-owned immutable policy identity/version persistence:

```text
policy_id
policy_version
enabled/effective state
source_kind = monitoring_problem | monitoring_health_projection
bounded condition family
bounded source/resource selectors
created_at / superseded_at
immutable version content hash/equivalence evidence
```

Exactly two source-condition families are admitted:

1. **Problem-source condition**
   - current canonical Problem only;
   - bounded predicate over canonical Problem lifecycle/severity/evidence fields explicitly admitted by the implementation contract;
   - historical/non-current generation cannot create or keep a current Alert active.

2. **Health-source condition**
   - current canonical Health Projection only;
   - bounded predicate over canonical `unknown | healthy | degraded | unhealthy`;
   - stale/incomplete/non-current evidence cannot be interpreted optimistically.

No arbitrary code, SQL, regex engine, expression language, user-supplied script, provider query, cross-tenant join or unbounded DSL is authorized.

## Alert lifecycle authority

The accepted Wave 4 lifecycle remains binding:

```text
active | resolved
```

Rules:
- create transition is `NULL -> active`;
- resolve transition is `active -> resolved`;
- `resolved` is terminal for the same `alert_id`;
- a later actionable occurrence gets a new `alert_id`;
- every effectful transition binds exact immutable `policy_id + policy_version`;
- same logical decision replay is idempotent;
- same decision identity with non-equivalent immutable meaning fails closed;
- Monitoring event arrival alone never creates/resolves an Alert;
- current Monitoring reread + current policy evaluation is mandatory;
- broker order/provider time is never lifecycle authority.

## Evaluation law

```text
EVENT != ALERT
EVENT_PAYLOAD != CURRENT_MONITORING_STATE
CURRENT_REREAD_REQUIRED_BEFORE_POLICY_EVALUATION
POLICY_ID != POLICY_VERSION
POLICY_VERSION_IMMUTABLE_AFTER_EFFECT
POLICY_MATCH != DUPLICATE_ALERT
RESOLVED_ALERT_ID != REOPENABLE_ALERT_ID
HISTORICAL_GENERATION != CURRENT_ALERT_INPUT
UNKNOWN_CURRENTNESS != MATCH
ACKNOWLEDGEMENT != ALERT_LIFECYCLE
RESPONSIBILITY != ALERT_LIFECYCLE
DELIVERY_STATE != ALERT_LIFECYCLE
ALERT != ITSM_INCIDENT
```

## Exact implementation path authority

Allowed prefixes:
- `apps/g7-alert-policy-lifecycle/`
- `contracts/g7-alert-policy-lifecycle/`
- `implementation/g7-alert-policy-lifecycle/`
- `tests/g7/`
- `tools/g7/`

Allowed exact paths:
- `sql/alerting/001_alert_policy_lifecycle.sql`
- `.github/workflows/g7-alert-policy-lifecycle-runtime.yml`

Required future implementation PR:
- branch prefix `impl/g7-alert-policy-lifecycle`;
- label `jlmirror-slice:g7-alert-policy-lifecycle`;
- claim file `implementation/g7-alert-policy-lifecycle/IMPLEMENTATION_CLAIM.json`;
- exact authorization ID `g7.alert-policy-lifecycle@1`;
- same repository;
- base equal to live default-branch tip when trusted evidence is produced.

Shared G1–G6, Wave 2, Wave 4 and Monitoring files remain read-only.

## Persistence boundary

The exact SQL migration may create only these G7-owned Alerting relations:

```text
alerting.alert_policy
alerting.alert_policy_version
alerting.alert_policy_effective_version
alerting.alert
alerting.alert_transition
alerting.alert_decision
```

Those relations are limited to:
- immutable policy identity/version;
- current policy activation/effective-version binding;
- canonical Alert projection;
- immutable Alert transition history;
- exact decision/idempotency evidence.

Guarded functions, roles, constraints, indexes and tenant RLS may support those relations, but no additional Alerting business-state relation is authorized.

It may not create ACK, responsibility, notification, delivery, view/read, response/waiting, approval, ITSM, Automation or AIOps state.

## Read/UI boundary

G7 may expose:
- bounded Alert list/detail;
- current lifecycle;
- source evidence summary;
- immutable policy identity/version;
- opened/resolved timestamps;
- bounded transition timeline limited to G7 Alert lifecycle facts.

The UI must not invent ACK/responsibility/delivery/view/response state.

## Required proof before implementation merge

- exact allowlist diff;
- bounded policy schema and immutable version proof;
- only the two admitted condition families;
- current Monitoring reread before every effectful decision;
- historical/stale/unknown currentness fails closed;
- idempotent create/resolve and conflicting-equivalence rejection;
- terminal resolved identity;
- no duplicate active Alert for same admitted logical policy/source occurrence;
- tenant isolation and FORCE RLS;
- least privilege/no application direct table writes;
- no G8+ state or behavior;
- list/detail API/BFF/UI browser E2E;
- runtime/container proof;
- exact-head CI green;
- trusted scope/readiness;
- panoramic/adversarial review;
- separate explicit owner merge authorization.

## Explicit non-authority

G7 does not authorize:
- acknowledgement or unacknowledgement;
- suppression;
- resource/alert responsibility or assignment;
- current-action ownership;
- notification intent;
- delivery attempt/state;
- view/read receipts;
- response/waiting state;
- approval/budget workflow;
- routing/escalation;
- ITSM incidents/tickets/tasks;
- Automation/AIOps mutation;
- provider write-back;
- public webhooks/browser realtime;
- arbitrary/unbounded policy DSL;
- production deployment/C3 numerics.

```text
G6_AUTHORIZED != G7_AUTHORIZED
G7_AUTHORIZED != G8_AUTHORIZED
POLICY_EVALUATION != HUMAN_ACK
ALERT_LIFECYCLE != RESPONSIBILITY
ALERT_LIFECYCLE != NOTIFICATION_DELIVERY
IMPLEMENTED != PRODUCTION_READY
GREEN_STATUS != MERGE_AUTHORIZATION
READY_FOR_MERGE != AUTHORIZED_TO_MERGE
```
