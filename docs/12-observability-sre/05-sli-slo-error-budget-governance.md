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

Canonical profiles: `sli.api.outcome@1`, `sli.api.latency@1`.

- eligible-request successful outcome ratio;
- latency distribution by stable operation class;
- throttled/rejected/dependency-unavailable outcome distribution;
- long-running operation acceptance/terminal-convergence where relevant.

Authorization denial, invalid input and existence-concealment are classified according to endpoint semantics rather than blindly counted as platform failures.

### Async workers/events

Canonical profile: `sli.async.progress@1`.

- durable accepted-work age/lag;
- completion/convergence ratio;
- retry/quarantine/reconciliation pressure;
- publication-to-durable-responsibility latency where meaningful;
- duplicate-safe processing evidence.

The SLI measures progress/outcome. It does not grant duplicate or effect eligibility.

### Provider integrations

Canonical profile: `sli.provider.outcome@1`.

- eligible provider operation completion ratio;
- provider latency distribution;
- normalized unavailable/throttled/ambiguous outcome ratio;
- reconciliation convergence for ambiguous effects.

### Realtime

Canonical profile: `sli.realtime.delivery@1`.

- protected admission success for eligible clients;
- connection/subscription stability where meaningful;
- projection delivery lag;
- resync requirement/convergence.

### Outbound webhooks

Candidate profile: `sli.webhook.convergence@1`.

`OPEN-OBS-037` owns whether accepted Product authority establishes the outbound-webhook capability as enabled, not enabled, or still unproven for this applicability decision. An unproven Product state remains OPEN; it is neither enablement nor `NO_APPLICABLE_CASE`.

After Product enablement is established, `OPEN-OBS-035` separately owns whether an enabled outbound-webhook capability requires the dedicated `sli.webhook.convergence@1` and corresponding alert commitment. Product enablement alone therefore does **not** activate a dedicated webhook SLI/SLO commitment.

Until the applicable OPEN decisions are closed by Product/SRE evidence:

- webhook diagnostic/health/security/recovery evidence remains required where the prepared capability profile applies;
- ordinary durable-progress/customer-impact evidence may still expose failures through applicable shared profiles;
- no dedicated webhook SLO/error-budget commitment is asserted by Phase 12;
- implementation/tool defaults SHALL NOT resolve either applicability OPEN implicitly.

If `OPEN-OBS-035` later activates the profile, its semantics cover delivery-obligation terminal convergence, attempt latency and destination-isolated failure pressure. An ambiguous external outcome is never silently recorded as ordinary failure/success.

### Telemetry ingestion/current projections

Canonical profile: `sli.customer-telemetry.acceptance@1`.

- durable acceptance success/lag for customer monitoring observations;
- projection checkpoint lag;
- current-state advancement freshness using accepted ordering semantics.

These are distinct from observability-pipeline SLIs.

### Observability pipeline

Canonical profile: `sli.observability.integrity@1`.

- producer-to-observability-ingest/export health;
- signal drop/rejection/backpressure;
- trace propagation continuity for required synthetic paths;
- query/alert evaluation freshness where the selected implementation later supports it.

### Control Plane/cells

Canonical profiles: `sli.control-plane.admission@1`, `sli.cell.admission@1`.

- accepted placement/configuration/lifecycle admission operation outcome;
- eligible cell admission outcome by stable workload class;
- cell readiness/degradation/quarantine exposure freshness;
- relocation/drain progress signals.

These SLIs observe accepted admission outcomes. They do not create placement/generation authority.

### Protected artifact delivery

Candidate profile when accepted Product authority exposes protected artifact delivery: `sli.artifact.delivery@1`.

`OPEN-OBS-037` also owns the Product applicability state for direct protected-artifact delivery exposure. Until accepted Product authority proves exposure or non-exposure, applicability remains OPEN. A proven non-exposed state may yield `NO_APPLICABLE_CASE`; an unproven state may not.

When applicable, the profile covers:

- eligible artifact lifecycle/delivery terminal outcome;
- delivery latency/disruption as permitted by the artifact contract;
- reconciliation/governance-blocked outcome classification.

The SLI SHALL NOT treat a stale delivery capability or ongoing older-generation stream as successful merely because bytes were served; accepted artifact delivery-generation/lease/erasure authority remains decisive.

### Recovery/reconciliation

Canonical profile: `sli.recovery.convergence@1`.

- recovery/reconciliation work progress/convergence;
- `(R,F]` evidence-gap population/age;
- blocked/quarantined scopes awaiting continuity evidence.

Recovery SLI improvement SHALL NOT imply authorization to resume.

## Hard-correctness authorities and direct SLI applicability

A direct service-level objective is `NO_APPLICABLE_CASE` when the property is a hard correctness/security authority whose failure cannot be tolerated through an error budget. This includes, as applicable:

- current authorization/revocation correctness;
- mandatory audit correctness/durable responsibility;
- duplicate-sensitive equivalence proof and replay/effect eligibility.

The `NO_APPLICABLE_CASE` applies only to the **direct correctness SLI**. Operational/customer impact remains measurable through consuming API, async or recovery SLIs. This disposition SHALL be explicit in `10-observability-semantic-manifest.md`; omission is invalid.

An availability SLI for an underlying dependency MAY be introduced later only if it does not imply an allowance to violate the hard correctness property.

Unknown/unproven Product applicability is not a hard-correctness `NO_APPLICABLE_CASE`; it remains owned by `OPEN-OBS-037` until accepted Product evidence closes it.

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

A candidate SLI whose activation is itself OPEN SHALL NOT receive a numeric SLO before the applicability OPEN is closed.

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

No error budget may authorize a violation of a hard correctness authority merely because availability objectives permit some failures.

## Exclusions and gaming prevention

Exclusions SHALL be evidence-backed and semantically stable. The following are prohibited:

- excluding failed requests merely because they are inconvenient;
- treating telemetry loss as success;
- changing denominator population during an incident without versioned review;
- renaming an error class to remove it from the budget;
- discarding a tenant/workload from aggregate SLI solely because it is degraded;
- changing sampling in a way that makes SLI errors invisible without compatibility/governance review;
- converting a hard correctness failure into an SLO exclusion to preserve reported compliance;
- converting unproven Product applicability into `NO_APPLICABLE_CASE` to avoid a future commitment decision.

## Multi-tenant aggregation

Platform-level SLIs SHALL avoid hiding a severely affected small tenant behind high-volume healthy tenants. Applicable aggregate profiles declare whether they use request-weighted, tenant-weighted, worst-cohort, percentile/cohort or another evidence-backed method.

Exact aggregation policy remains OPEN per SLI until Product/operational evidence justifies it.

## Change classification

A change to SLI population, numerator, measurement boundary, unit, missing-data semantics, sampling dependence or aggregation can be semantically breaking even when dashboards still render.

Historical comparisons SHALL identify the profile version used; incompatible periods are not silently spliced.

Changing an applicability decision between a direct SLI, an OPEN applicability owner and `NO_APPLICABLE_CASE` is semantic governance and requires review of the underlying authority rationale.

## Validation obligations

Tests SHALL inject telemetry loss, denied/invalid requests, throttling, ambiguous effects, tenant skew and SLI profile changes to prove that metrics cannot be gamed into false success and that unsupported numerics remain OPEN.

Validation SHALL also prove that direct hard-correctness `NO_APPLICABLE_CASE` decisions do not remove the consuming operational/customer-impact SLI and cannot be used to hide service degradation.

For Product-gated candidate profiles, validation SHALL prove that `product_state_unproven` remains bound to `OPEN-OBS-037`, is not treated as enablement/disablement or `NO_APPLICABLE_CASE`, and cannot be silently activated by implementation configuration. For enabled outbound webhooks, validation SHALL additionally prove that `OPEN-OBS-035` is not silently closed by implementation or tooling.