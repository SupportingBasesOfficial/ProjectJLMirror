# Phase 12 — Observability Compatibility and Change Classification

**Status:** proposed baseline  
**Phase:** 12 — Observability & SRE

## Purpose

Observability compatibility is semantic. Dashboards rendering and parsers accepting fields do not prove that health, SLI, alert or diagnostic meaning stayed compatible.

## Change classes

### OBS-COMP-A — Additive non-semantic

Examples: optional diagnostic field with bounded classification/cardinality; new signal not consumed by existing SLI/alert contracts.

Requires ordinary review and evidence that no existing consumer meaning changes.

### OBS-COMP-B — Additive consumer-relevant

Examples: new bounded dimension, new health reason, new correlation edge or new optional outcome class consumed by queries/alerts.

Requires consumer compatibility review, mixed-version behavior and cardinality/cost analysis.

### OBS-COMP-C — Semantic breaking

Includes changes to:

- signal meaning under same identity;
- unit or aggregation semantics;
- metric label meaning/cardinality class;
- missing-vs-zero semantics;
- health/readiness/degradation meaning;
- SLI numerator/denominator/population/aggregation;
- SLI/alert applicability or `NO_APPLICABLE_CASE` disposition;
- SLO/error-budget accounting semantics;
- alert trigger/clear/suppression semantics;
- classification/redaction/retention requirements;
- sampling behavior that materially changes evidence validity;
- correlation identity role or trust assumptions;
- telemetry-pipeline failure/degradation behavior;
- tenant query/isolation semantics;
- Product-gated observability applicability moving among OPEN, applicable and proven non-applicable states.

These require explicit profile/version/governance review as applicable and cannot silently roll through under an unchanged semantic identity.

### OBS-COMP-D — Security/recovery authority-sensitive

A subset of breaking changes affecting tenant isolation, secret/protected-data handling, recovery quarantine, current authority visibility, ambiguity/reconciliation evidence, comparison continuity/trust, audit separation or a change that would make observability more permissive than an accepted upstream correctness authority.

These are release-blocking until the owning Security/Recovery authority and Phase 12 consumers prove the new semantics safe.

## Product applicability compatibility

Product-gated observability profiles have an explicit authority lifecycle:

```text
OPEN-OBS-037 / product_state_unproven
        -> accepted Product evidence
        -> applicable OR proven non-applicable
```

Rules:

- implementation configuration, feature flags, absence of deployed code or current UI/runtime behavior SHALL NOT perform this transition;
- `product_state_unproven` is not compatible with silently treating the capability as absent or enabled;
- moving to proven non-applicable requires accepted Product evidence before `NO_APPLICABLE_CASE` may be recorded;
- moving to applicable activates only the profiles whose separate applicability/commitment decisions are already closed;
- for outbound webhooks, proven Product enablement does not close `OPEN-OBS-035`;
- reopening/superseding accepted Product applicability requires ordinary upstream governance and downstream Phase 12 compatibility review.

A change may therefore be semantically breaking without changing any telemetry schema or implementation code.

## Mixed-version rules

Rolling deployments may temporarily emit multiple profile versions. The accepted migration declares:

- producer versions in flight;
- consumer versions/read compatibility;
- whether dual emission is allowed;
- how metrics with different units/label meaning are prevented from unsafe aggregation;
- alert/SLI behavior during the window;
- retirement criteria;
- rollback semantics.

A backend's ability to store both schemas does not prove semantic compatibility.

## Metric identity

A metric name/profile identity SHALL NOT retain the same semantic identity across incompatible unit, aggregation, denominator or label-meaning changes.

Removing a label can be breaking when it collapses scopes. Adding a label can be breaking when it changes cardinality/aggregation or alert queries.

## Health compatibility

Changing what `ready`, `degraded`, `draining` or `recovery_quarantine` means is a correctness/security change. Old and new instances SHALL NOT present the same health identity with conflicting admission meaning.

Phase 13 runtime implementation later maps these semantics to concrete probes; it cannot redefine them.

Changing comparison-health semantics so that temporary availability, historical continuity loss or compromised trust become indistinguishable is security/recovery breaking.

## SLI/SLO compatibility

Historical SLI/SLO comparisons identify the semantic profile used. When numerator/denominator/population/missing-data semantics change incompatibly:

- historical periods are not silently concatenated;
- error-budget accounting resets/rebases only through accepted governance;
- release/incident analysis records the boundary.

Activating/deactivating a candidate SLI or changing a direct SLI between OPEN, applicable and `NO_APPLICABLE_CASE` is a semantic compatibility change even if no metric name changes.

## Correlation compatibility

Changing propagation/identity semantics requires review of every producer/consumer boundary. A field cannot change from “diagnostic only” to “routing/authority” through implementation; such authority change belongs upstream and is forbidden by Phase 12 alone.

## Security/privacy compatibility

A change that emits previously excluded data, increases retention/searchability, broadens query access, weakens redaction or increases cross-tenant correlation is security/privacy breaking even if storage schema is unchanged.

## Sampling/retention compatibility

Sampling/retention numeric tuning may be operationally reversible, but becomes semantic-breaking when it invalidates SLI, security, recovery or diagnostic evidence obligations.

Exact numbers remain OPEN; compatibility obligations do not.

## Rollback

Rollback SHALL NOT resurrect a telemetry profile that:

- leaks fields prohibited by current security policy;
- interprets current health/recovery state more permissively;
- collapses tenant scopes;
- uses retired SLI meaning as if current;
- restores obsolete secret/protected-data logging;
- treats an unresolved/reopened Product applicability decision as proven enabled or non-applicable.

If downgrade cannot safely interpret current evidence, observability consumers fail closed/unknown rather than fabricate compatible meaning.

## Evidence

Compatibility evidence includes schema/profile diff, semantic diff, Product-applicability authority diff where relevant, mixed-version tests, old/new consumer tests, SLI/alert applicability/query tests, cardinality/cost analysis, security/privacy review and rollback rehearsal where material.
