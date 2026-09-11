# Wave 4 Monitoring — Problem State Authorization

**Status:** proposed bounded implementation authorization  
**Base:** `main@4908e5124f2d182146d0366030c1dd64c778a423`  
**Authorization ID:** `wave4.monitoring-problem-state@1`

## Purpose

Authorize the next bounded Monitoring Data Plane slice after canonical Metric History: read-only Zabbix problem/event evidence -> canonical tenant-owned Monitoring problem identity and lifecycle state, without activating Health, Alerting, ITSM, provider write-back or frontend behavior.

This authorization consumes the already accepted Monitoring domain/API contracts, Zabbix provider contract and Zabbix canonical normalization profile. It does not redefine those semantics.

## Canonical model

```text
PROVIDER EVIDENCE
  problem.get  -> current active-problem evidence
  event.get    -> explicit recovery/closure + bounded reconciliation evidence
  trigger.get  -> bounded trigger/problem association metadata only

CANONICAL PROBLEM
  problem_id
  tenant_id
  monitoring_source_id
  source_instance_generation
  monitoring_resource_id
  provider_profile = zabbix
  provider_external_ref = scoped problem-class eventid
  problem_state = active | resolved
  severity_class = unknown | informational | warning | degraded | critical
  summary / bounded provider metadata
  opened_at
  resolved_at nullable
  last_confirmed_at
  evidence_state
  projection_revision
```

Architectural invariants:

```text
PROVIDER EVENT ID != CANONICAL PROBLEM ID
PROVIDER ACKNOWLEDGED != JLMIRROR ACKNOWLEDGEMENT
PROVIDER SEVERITY != HEALTH ENUM
TRIGGER METADATA != PROBLEM LIFECYCLE AUTHORITY
ABSENCE FROM INCOMPLETE problem.get != RESOLVED
HISTORICAL GENERATION != CURRENT PROBLEM AUTHORITY
PROBLEM STATE != HEALTH PROJECTION
PROBLEM STATE != ALERTING STATE
PROBLEM STATE != ITSM STATE
```

## Authorized behavior

1. The Zabbix adapter may perform authenticated, bounded, read-only `problem.get`, `event.get`, and only the bounded `trigger.get` metadata needed to safely associate provider evidence with canonical resources/problems.
2. Canonical `problem_id` is platform identity. Zabbix `eventid` is an external reference scoped by tenant, monitoring source, provider profile and source-instance generation.
3. The same provider numeric ID in another tenant/source/generation is unrelated. Cross-generation identity equality is never inferred from matching provider IDs.
4. `problem.get` positive evidence may create or confirm an `active` canonical problem when exact current source/scope/resource association authority is proven.
5. A missing problem from an incomplete, truncated, stale, visibility-degraded or otherwise uncertain `problem.get` result has no resolution authority.
6. Resolution requires either explicit accepted recovery/closure evidence from `event.get` (or an already accepted equivalent provider read) bound to the same scoped provider event identity, or a complete authoritative negative reconciliation that satisfies the provider contract.
7. Historical-generation problem evidence remains historical. It cannot participate in current operational problem authority after source generation replacement.
8. Canonical severity mapping is fixed by the accepted normalization profile: Not classified -> `unknown`; Information -> `informational`; Warning -> `warning`; Average -> `degraded`; High/Disaster -> `critical`.
9. Provider-native severity may be retained only as bounded provider metadata/provenance. It does not become the canonical health enum.
10. Zabbix `acknowledged` and acknowledgement records are provider metadata only. They cannot acknowledge, resolve, suppress or close JLMIRROR Monitoring, Alerting or ITSM state.
11. Provider tags and text are untrusted bounded data. They cannot select tenant, authorization, placement, canonical identity, alert policy or unrestricted observability labels.
12. Provider problem/trigger text may populate bounded canonical summary/diagnostic metadata only after canonical string handling, size bounds and safe output encoding.
13. Resource association must resolve through current canonical provider/resource mappings under the same tenant/source/generation. Unresolved or ambiguous association becomes reconciliation-required evidence rather than fabricated linkage.
14. Problem transitions are revisioned and atomic with their durable transition/audit intent according to the already accepted Monitoring/ADR-008 atomicity law. This authorization does not introduce a second event/outbox substrate.
15. Exact replay/redelivery of the same provider evidence is idempotent. It must not generate duplicate logical problem transitions.
16. A provider problem changing canonical severity while remaining active is a problem-state transition, but it is not a new canonical problem identity.
17. Provider timestamps are evidence, not tenant/auth/current-generation authority. Current authority remains fenced by platform source/generation/configuration/scope admission.
18. Problem ingestion owns an independent recovery-safe poll epoch/generation/admission stream. It must not reuse Host Inventory, Metric Definitions, Metric Current State or Metric History mutable poll authority.
19. Current active-problem polling and historical/recovery reconciliation are distinct concerns. Fast `problem.get` polling cannot replace bounded `event.get` reconciliation where explicit recovery evidence is required.
20. Bounded reconciliation windows, page sizes, body limits and provider text/tag limits must be finite safety bounds. Production sizing remains evidence-driven and does not become C3 authority here.
21. Tenant isolation is mandatory for problem persistence, provider identity mapping, transitions and reads.
22. Problems list/detail follow the accepted API anchor cursor profile using `problem_id`, with `opened_at` tie position derived from authoritative state; every continuation re-establishes current auth/tenant/filter/generation eligibility.
23. Problems responses are `no_store`.
24. No Health projection is authorized by this slice. Problem severity becomes available as an input for a later separately authorized Health slice only.
25. No Alerting, ITSM, Automation or AIOps lifecycle behavior is authorized.
26. No provider write-back is authorized.
27. No frontend route/navigation implication is authorized.

## Completeness / reconciliation rules

```text
positive active evidence
  -> may establish/confirm active state per object

complete authoritative negative evidence
  -> may resolve only when provider contract proves the object should have been visible

explicit recovery event
  -> may resolve the matching scoped problem identity

incomplete/truncated/unavailable/stale evidence
  -> no negative authority; preserve last known state with degraded evidence_state
```

A complete provider request is not automatically a globally complete problem universe. Completeness remains bounded to the exact authorized source/scope/object class and provider query semantics.

## Explicitly outside this slice

- deriving Health projection or `healthy/degraded/unhealthy/unknown` resource state;
- Alert creation, acknowledgement, suppression, notification or escalation;
- ITSM ticket/incident behavior;
- Zabbix acknowledgement/write-back;
- automatic policy from arbitrary provider tags;
- cross-tenant or cross-generation provider-ID identity collapse;
- using incomplete omission as problem resolution;
- treating `trigger.get` definitions as lifecycle authority;
- unbounded provider scans;
- provider credentials/raw payload replication;
- frontend implementation;
- production deployment or C3 numerics.

## Acceptance boundary

This record grants no runtime authority until its exact HEAD passes deterministic CI plus panoramic/adversarial review and is separately squash-merged into `main`. Implementation of Problem State remains blocked until then.
