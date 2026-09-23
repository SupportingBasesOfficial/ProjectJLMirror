# G6 Monitoring → Alerting Transport — AI Task Packet

SLICE: `g6.monitoring-alerting-transport@1`

GOAL: Accepted Monitoring Problem/Health transition events reach a durable Alerting consumer inbox, are deduplicated/reconciled, force a current Monitoring reread, and complete only a resync responsibility. No Alert is created.

## STOP CONDITIONS

Stop if implementation requires:

- Alert projection or transition persistence;
- any Alert create/resolve/reopen behavior;
- Alert policy/rule identity or evaluation;
- ACK/suppression/notification/ITSM behavior;
- a new broker/outbox/inbox substrate;
- modifying shared Wave 2 or Monitoring business tables;
- direct provider calls;
- production behavior.

## ALLOWED PATHS

```text
apps/g6-monitoring-alerting-transport/
contracts/g6-monitoring-alerting-transport/
implementation/g6-monitoring-alerting-transport/
tests/g6/
tools/g6/
sql/integration/002_monitoring_alerting_consumer.sql
.github/workflows/g6-monitoring-alerting-transport-runtime.yml
```

The SQL file is exact-path authority for composition only. It may bind least-privilege execution/functions to the existing Wave 2 inbox and canonical Monitoring rereads. It may not create Alert business state or a parallel async substrate.

## IMPLEMENTATION CLAIM

```json
{"schema_version":1,"authorization_id":"g6.monitoring-alerting-transport@1","slice_id":"g6.monitoring-alerting-transport@1"}
```

Branch prefix: `impl/g6-monitoring-alerting-transport`  
Required label: `jlmirror-slice:g6-monitoring-alerting-transport`

## CONTRACTS

Exactly:

```text
monitoring.problem-state.changed
monitoring.health-projection.changed
```

## BINDING SEMANTICS

```text
Monitoring event != Alert
event arrival != Alert creation authority
event payload != current Monitoring state
broker order != owner-domain order
inbox receipt != Alert
inbox completed != Alert created
duplicate delivery != duplicate resync responsibility
historical generation != current Alerting input authority
current Monitoring reread required before completion
unknown currentness != optimistic effect
```

## CONSUMER FLOW

```text
validate
 -> create-or-observe system.async_consumer_inbox
 -> dedup/equivalence check
 -> claim
 -> current tenant/service authority
 -> current Problem/Health reread
 -> current-vs-historical disposition
 -> durable resync completion
 -> stop
```

## REQUIRED TESTS

At minimum prove:

1. only the two accepted Monitoring contracts are admitted;
2. malformed/wrong-version/wrong-producer/wrong-tenant envelope fails closed;
3. duplicate equivalent redelivery creates one inbox identity/responsibility;
4. conflicting same identity fails closed;
5. claim/restart does not duplicate completion;
6. ambiguous claim/effect requires reconciliation;
7. Problem event causes current canonical Problem reread;
8. Health event causes current canonical Health reread;
9. delayed historical-generation event cannot gain current input authority;
10. reordered delivery cannot regress current disposition;
11. no Alert table/projection/transition/policy row is created;
12. no policy identity/evaluation path exists;
13. accepted publication runtime conformance still passes;
14. Wave 2 inbox constraints are reused;
15. runtime/container proof;
16. trusted scope/readiness exact-head evidence.

```text
G6 != G7
TRANSPORT != ALERT LIFECYCLE
INBOX COMPLETION != ALERT CREATION
READY_FOR_MERGE != AUTHORIZED_TO_MERGE
```
