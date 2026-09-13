# JLMirror Roadmap Dependency Graph

Status: canonical project-memory source

This roadmap is dependency-based, not percentage-based. A downstream capability must not be implemented merely because it is desirable; prerequisite authority and runtime truth must exist first.

## Current critical path

`Monitoring truth`
-> `Monitoring Problem/Health transitions`
-> `Monitoring->Alerting publication authorization (#146)`
-> `Monitoring->Alerting publication runtime (#148)`
-> `Alert Policy/Evaluation authorization`
-> `Alerting consumer + policy evaluator + Alert lifecycle runtime`
-> `Responsibility + JLMirror ACK authorization/runtime`
-> `Notification intent + delivery + authoritative visibility evidence`
-> `Response/waiting + approval workflows`
-> `Escalation + realtime`
-> `ITSM integration/runtime`
-> `Automation`
-> `AIOps / advanced operations`
-> `complete UI/reporting/production hardening`

## Why publication runtime precedes policy runtime
Alerting must have a durable, accepted path to learn that Monitoring truth changed, while still re-reading current owner state. #146 authorized that bridge; #148 implements it without creating Alert business state.

## Why policy authorization precedes automatic Alerts
The system must define, before runtime mutation:
- exact policy identity/version;
- enable/disable/effective version semantics;
- source family selection;
- resource/source selectors;
- Problem severity / Health predicates;
- grouping/dedupe/correlation rules;
- timing/debounce/confirmation rules where allowed;
- conflict/precedence semantics;
- open decision;
- resolve/recovery decision;
- historical-generation restrictions;
- currentness/fail-closed behavior;
- policy edit behavior for already-open Alerts;
- idempotency/replay laws.

Without those rules, automatic Alert creation/resolution remains blocked.

## Human-operations dependency chain
`Alert runtime`
-> `responsibility model`
-> `ACK model`
-> `notification intent`
-> `delivery evidence`
-> `authoritative view/read evidence`
-> `response/waiting state`
-> `approval workflow`
-> `next-action projection`
-> `escalation`
-> `ITSM workflow`

These are orthogonal state dimensions even when they appear in one operational timeline.

## Authoritative visibility requirement
Critical flows that require proof that a person/customer became aware of an operational item must not rely indefinitely on a channel that cannot provide authoritative read evidence. The admitted workflow must provide either:
- a channel with trustworthy read/interaction evidence; or
- a JLMirror-controlled authenticated confirmation surface reached from that channel.

## Parallel future tracks after core Alerting
- advanced device taxonomy/topology;
- metric-history product completion;
- Platform Management runtime expansion;
- Org & Access administration;
- public integration/webhook governance;
- FinOps;
- Commercial;
- richer reporting/NOC surfaces;
- deployment/HA/performance/DR/production readiness.

## Blocked-by rule
Every future project-memory update that changes this graph must state the newly satisfied dependency and the authority that satisfied it.
