# Wave 4 Monitoring — Health Projection Authorization

**Status:** proposed bounded implementation authorization  
**Base:** `main@1da4350cb860d759549b6302e575a02af6f07b09`  
**Authorization ID:** `wave4.monitoring-health-projection@1`

## Purpose

Authorize the next bounded Monitoring Data Plane slice after canonical Problem State: derive a canonical tenant-owned Monitoring `health_projection` for each eligible Monitoring resource from already-canonical Monitoring evidence, without introducing a new provider polling authority and without activating Alerting, ITSM, Automation, AIOps, provider write-back, frontend behavior or public/cross-domain health events.

This authorization consumes the already accepted Monitoring domain/API contracts, Problem State implementation, generation/scope semantics and Monitoring event-contract boundary. It does not redefine those semantics.

## Canonical model

```text
CANONICAL INPUTS
  monitoring_resource
  monitoring_source + active_source_instance_generation
  resource scope/presence/current evidence
  active canonical Monitoring problems
  canonical problem severity/evidence

CANONICAL HEALTH PROJECTION
  tenant_id
  monitoring_resource_id
  monitoring_source_id
  source_instance_generation
  health_class = unknown | healthy | degraded | unhealthy
  evidence_state = current | stale | incomplete | reconciliation_required | unavailable
  projection_revision
  last_changed_at
  last_evidence_at
  bounded problem/reason references
```

`generation_state = active_generation | historical_generation` remains derived at read/use time by comparing the projection generation with the source's current active generation.

Architectural invariants:

```text
PROVIDER SEVERITY != HEALTH CLASS
PROBLEM STATE != HEALTH PROJECTION
HEALTH PROJECTION != ALERTING STATE
HEALTH PROJECTION != ITSM STATE
HEALTH PROJECTION != AIOPS FINDING
HISTORICAL GENERATION != CURRENT HEALTH AUTHORITY
STALE/INCOMPLETE EVIDENCE != PROVEN HEALTHY
SCOPE EXCLUSION != HEALTHY
PROVIDER ACKNOWLEDGED != HEALTH AUTHORITY
HEALTH DERIVATION != PROVIDER POLLING AUTHORITY
```

## Authorized behavior

1. Health is a Monitoring-owned **derived projection**. This slice authorizes no new Zabbix/provider API read, poll epoch, poll generation or provider runtime-admission stream.
2. Projection inputs are canonical Monitoring state already accepted under current tenant/source/generation/scope authority. Raw provider payloads, provider tags, provider acknowledgement and provider-native IDs are not direct health authority.
3. A projection belongs to one canonical `monitoring_resource_id`, source and source-instance generation. Cross-tenant, cross-source or cross-generation aggregation is prohibited.
4. Current-health derivation for an active-generation resource requires current source authority and current authoritative scope evidence for that resource. A stale scope projection cannot prove current health.
5. Historical-generation health may remain retained as historical/last-known evidence, but it cannot participate in current Monitoring health, Alerting input or current dashboard authority.
6. Canonical `health_class` is exactly `unknown | healthy | degraded | unhealthy`.
7. With current complete authoritative evidence and no active health-affecting canonical problem, the resource may project `healthy`.
8. One or more active `warning` or `degraded` problems require health to be at least `degraded`.
9. Any active `critical` problem requires `unhealthy`.
10. An active `unknown`-severity problem prevents the resource from being proven `healthy`. In the absence of a stronger active health effect, the canonical class is `unknown`.
11. Active `informational` problems alone do not force degradation. With otherwise complete current authoritative evidence, informational-only active problems may coexist with `healthy`.
12. Multiple active current-generation problems combine by strongest canonical health effect: `unhealthy > degraded > unknown > healthy` for derivation purposes. This precedence is a derivation rule, not a provider severity ordering contract.
13. Only canonical `problem_state=active` rows with current authority for the same tenant/resource/source/generation may contribute to current health. Resolved problems do not contribute to current health.
14. Provider acknowledgement metadata does not change health derivation.
15. Provider timestamps do not choose current health ordering. Platform current authority, canonical projection revision and durable transition acceptance govern projection advancement.
16. No trustworthy current evidence yields `unknown` or preserves a last-known class with a non-current `evidence_state`; it must not fabricate `healthy`.
17. Incomplete, stale, reconciliation-required or unavailable problem/source/scope evidence cannot be upgraded to `current` merely because no active critical/warning problem is visible.
18. Scope exclusion never means healthy. An `out_of_scope` resource may retain historical/last-known health evidence but has no freshly proven current-health authority.
19. Resource removal does not fabricate `healthy`. Retained health is historical/last-known evidence governed by current generation/scope/presence semantics.
20. Health projection advancement is idempotent. Re-evaluating the same canonical class/evidence/reason meaning must not create a duplicate logical transition or advance `last_changed_at` merely because a worker ran again.
21. A semantic `health_class` change advances `projection_revision` and `last_changed_at`. A pure evidence freshness/currentness change may advance projection/evidence metadata while preserving `last_changed_at` when the canonical health class is unchanged.
22. `last_evidence_at` is platform acceptance/projection evidence time, not provider event time.
23. Bounded problem/reason references may identify the canonical causes used in the projection, but they cannot contain unbounded provider text, arbitrary tags, secrets, endpoint details or credential references.
24. Projection write and any local Monitoring transition/audit intent required by the accepted owner-domain atomicity law must commit atomically or be deterministically recoverable from one durable authoritative transition record. This authorization creates no second outbox/event substrate.
25. Track A still does not authorize a public/cross-domain `health.changed` integration event. Health remains queryable through the accepted Monitoring API/local owner-domain projection until a separately accepted consumer contract exists.
26. Health list/detail reads use action `monitoring.health.read`, re-establish current auth/tenant/placement/filter/generation eligibility on every page/read and default collections to `active_generation`.
27. Health list pagination follows the accepted anchor profile using `monitoring_resource_id` in ascending deterministic order. Cursor possession grants no authority and carries no hidden protected continuation state.
28. Health API representations use the accepted `private_revalidate` cache class. Revalidation must recompute/validate current authorization, generation and scope currentness; cache age/possession is never authority.
29. All collection/read outputs remain finitely bounded by row count and serialized response-byte budget. Production numeric sizing remains evidence-driven and is not C3 authority here.
30. Tenant isolation is mandatory for health persistence, derivation, transition evidence and reads.

## Conservative derivation matrix

```text
current authoritative evidence + active critical
  -> unhealthy / current

current authoritative evidence + active warning or degraded, no critical
  -> degraded / current

current authoritative evidence + active unknown only (plus optional informational)
  -> unknown / current

current authoritative evidence + informational-only or no active health-affecting problem
  -> healthy / current

stale/incomplete/reconciliation-required/unavailable authority
  -> never newly prove healthy;
     project unknown or preserve bounded last-known class with matching non-current evidence_state

historical generation
  -> retained historical/last-known health only; never current health authority
```

## Read contract

Accepted API surfaces remain:

```text
GET /api/v1/tenants/{tenant_id}/health-projections
GET /api/v1/tenants/{tenant_id}/health-projections/{monitoring_resource_id}

action      monitoring.health.read
cache       private_revalidate
ordering    monitoring_resource_id ASC
default     generation_state=active_generation
```

Representations expose canonical health/evidence/generation semantics and bounded reason/problem references only. Provider payloads and unrestricted provider metadata remain excluded.

## Explicitly outside this slice

- any new Zabbix/provider polling or direct raw-provider health derivation;
- Alert creation, acknowledgement, suppression, notification, escalation or routing;
- ITSM ticket/incident lifecycle;
- AIOps finding/recommendation lifecycle;
- Automation actions;
- Zabbix acknowledgement/write-back;
- public/cross-domain `problem.changed` or `health.changed` integration events;
- policy/routing from arbitrary provider tags;
- frontend route/navigation implementation;
- production deployment or C3 numeric sizing authority;
- treating stale/incomplete omission as proof of health;
- treating historical-generation health as current;
- using cache/cursor possession as authorization.

## Acceptance boundary

This record grants no runtime authority until its exact HEAD passes deterministic CI plus panoramic/adversarial review and is separately squash-merged into `main`. Implementation of Health Projection remains blocked until then.
