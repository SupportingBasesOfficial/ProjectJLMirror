# G7 Alert Policy + Lifecycle — AI Task Packet

SLICE: `g7.alert-policy-lifecycle@1`

GOAL: Current canonical Monitoring Problem/Health truth is evaluated by one immutable bounded Alert policy version and can create or resolve a platform-owned Alert under the accepted `active | resolved` lifecycle.

## STOP CONDITIONS

Stop if implementation requires:
- ACK/unACK or suppression;
- responsibility/assignment/current-action ownership;
- notification/delivery/view/read/response/approval state;
- routing/escalation;
- ITSM/Automation/AIOps;
- arbitrary scripts/SQL/regex/unbounded policy DSL;
- direct provider calls;
- mutation of Monitoring business truth;
- production behavior.

## ALLOWED PATHS

```text
apps/g7-alert-policy-lifecycle/
contracts/g7-alert-policy-lifecycle/
implementation/g7-alert-policy-lifecycle/
tests/g7/
tools/g7/
sql/alerting/001_alert_policy_lifecycle.sql
.github/workflows/g7-alert-policy-lifecycle-runtime.yml
```

## IMPLEMENTATION CLAIM

```json
{"schema_version":1,"authorization_id":"g7.alert-policy-lifecycle@1","slice_id":"g7.alert-policy-lifecycle@1"}
```

Branch prefix: `impl/g7-alert-policy-lifecycle`  
Required label: `jlmirror-slice:g7-alert-policy-lifecycle`

## ADMITTED POLICY FAMILIES

Exactly:
- bounded current `monitoring_problem` condition;
- bounded current `monitoring_health_projection` condition.

Every effect requires current Monitoring reread and exact immutable `policy_id + policy_version`.

## LIFECYCLE

```text
NULL -> active
active -> resolved
resolved -> terminal for same alert_id
```

## BINDING SEMANTICS

```text
Event != Alert
event payload != current Monitoring state
current reread required before policy evaluation
policy id != policy version
historical generation != current Alert input
unknown currentness != match
resolved Alert ID != reopenable Alert ID
ACK != Alert lifecycle
responsibility != Alert lifecycle
delivery state != Alert lifecycle
Alert != ITSM incident
```

## REQUIRED TESTS

At minimum prove:
1. only two bounded source-condition families are admitted;
2. policy versions are immutable and effect evidence pins exact version;
3. disabled/superseded policy version cannot gain current effect authority;
4. current Problem match creates one Alert;
5. current Health match creates one Alert;
6. equivalent replay does not duplicate Alert or transition;
7. conflicting same decision identity fails closed;
8. current source recovery resolves active Alert under exact accepted policy semantics;
9. resolved `alert_id` never reopens;
10. later recurrence creates a new `alert_id`;
11. historical generation cannot create/keep current Alert;
12. stale/incomplete/unknown evidence cannot optimistically match;
13. reordered G6 delivery cannot regress lifecycle because current owner state is reread;
14. tenant isolation/RLS and least privilege hold;
15. no direct application persistence writes;
16. no G8+ ACK/responsibility/notification/ITSM state exists;
17. Alert list/detail API/BFF/UI browser E2E;
18. runtime/container proof;
19. trusted scope/readiness exact-head evidence.

```text
G7 != G8
POLICY EVALUATION != HUMAN ACK
ALERT LIFECYCLE != RESPONSIBILITY
ALERT LIFECYCLE != DELIVERY
READY_FOR_MERGE != AUTHORIZED_TO_MERGE
```
