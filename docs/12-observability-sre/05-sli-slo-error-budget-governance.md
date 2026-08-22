# Phase 12 — SLI, SLO and Error-Budget Governance

**Status:** proposed baseline  
**Phase:** 12 — Observability & SRE

## Purpose

This document fixes how JLMIRROR defines measurable service outcomes while keeping unsupported numeric promises OPEN.

## SLI definition contract

Every SLI SHALL declare:

```text
sli_id
capability_id
user_or_system_outcome being measured
population / eligibility denominator
successful outcome numerator or distribution
measurement boundary
excluded/not-applicable classes with evidence
required signal/profile versions
classification/cardinality constraints
missing-data behavior
late-data behavior
aggregation scope
known bias/sampling implications
owner
validation method
```

An SLI is invalid if its formula can improve merely because telemetry disappeared.

## Missing evidence

Missing telemetry is `unknown` unless the SLI contract explicitly proves another interpretation. It SHALL NOT be counted as success by default.

Telemetry outage therefore cannot improve an availability SLI or erase error-budget consumption.

## Initial capability SLI catalog

Phase 12 requires semantic SLIs, with numeric objectives remaining OPEN, for applicable classes including:

### API/BFF

- eligible-request successful outcome ratio;
- latency distribution by stable operation class;
- throttled/rejected/dependency-unavailable outcome distribution;
- long-running operation acceptance/terminal-convergence where relevant.

Authorization denial, invalid input and existence-concealment are classified according to endpoint semantics rather than blindly counted as platform failures.

### Async workers/events

- durable accepted-work age/lag;
- completion/convergence ratio;
- retry/quarantine/reconciliation pressure;
- publication-to-durable-responsibility latency where meaningful;
- duplicate-safe processing evidence.

### Provider integrations

- eligible provider operation completion ratio;
- provider latency distribution;
- normalized unavailable/throttled/ambiguous outcome ratio;
- reconciliation convergence for ambiguous effects.

### Realtime

- protected admission success for eligible clients;
- connection/subscription stability where meaningful;
- projection delivery lag;
- resync requirement/convergence.

### Outbound webhooks

Only when Product enables them: delivery obligation terminal-outcome/convergence, attempt latency and destination-isolated failure pressure. An ambiguous external outcome is not silently recorded as ordinary failure/success.

### Telemetry ingestion/current projections

- durable acceptance success/lag for customer monitoring observations;
- projection checkpoint lag;
- current-state advancement freshness using accepted ordering semantics.

These are distinct from observability-pipeline SLIs.

### Observability pipeline

- producer-to-observability-ingest/export health;
- signal drop/rejection/backpressure;
- trace propagation continuity for required synthetic paths;
- query/alert evaluation freshness where the selected implementation later supports it.

### Control Plane/cells

- accepted placement/admission operation outcome;
- cell readiness/degradation/quarantine exposure freshness;
- relocation/drain progress signals.

### Recovery/reconciliation

- recovery/reconciliation work progress/convergence;
- `(R,F]` evidence-gap population/age;
- blocked/quarantined scopes awaiting continuity evidence.

Recovery SLI improvement SHALL NOT imply authorization to resume.

## SLO governance

An SLO proposal requires:

- Product/business impact rationale;
- SLI semantic stability;
- baseline/runtime evidence;
- measurement bias/error analysis;
- capacity/cost consequence;
- tenant/plan applicability;
- exclusion/maintenance policy;
- review and revisit condition.

Numeric SLO targets, windows and percentiles are **OPEN** until this evidence exists.

A default copied from a vendor, framework or industry blog is not sufficient authority.

## Error budgets

An error budget is derived from an accepted SLO and its measured SLI. It is a governance/planning signal, not an autonomous deployment/retry/recovery/security authority.

Error-budget policy SHALL define before implementation:

- scope and SLO binding;
- accounting window;
- treatment of unknown/missing evidence;
- maintenance/exclusion rules;
- reset/recalculation behavior after SLI semantic changes;
- action/escalation classes;
- interaction with release governance in Phase 14.

No current numeric error-budget policy is fixed by Phase 12.

## Exclusions and gaming prevention

Exclusions SHALL be evidence-backed and semantically stable. The following are prohibited:

- excluding failed requests merely because they are inconvenient;
- treating telemetry loss as success;
- changing denominator population during an incident without versioned review;
- renaming an error class to remove it from the budget;
- discarding a tenant/workload from aggregate SLI solely because it is degraded;
- changing sampling in a way that makes SLI errors invisible without compatibility/governance review.

## Multi-tenant aggregation

Platform-level SLIs SHALL avoid hiding a severely affected small tenant behind high-volume healthy tenants. Applicable aggregate profiles declare whether they use request-weighted, tenant-weighted, worst-cohort, percentile/cohort or another evidence-backed method.

Exact aggregation policy remains OPEN per SLI until Product/operational evidence justifies it.

## Change classification

A change to SLI population, numerator, measurement boundary, unit, missing-data semantics, sampling dependence or aggregation can be semantically breaking even when dashboards still render.

Historical comparisons SHALL identify the profile version used; incompatible periods are not silently spliced.

## Validation obligations

Tests SHALL inject telemetry loss, denied/invalid requests, throttling, ambiguous effects, tenant skew and SLI profile changes to prove that metrics cannot be gamed into false success and that unsupported numerics remain OPEN.
