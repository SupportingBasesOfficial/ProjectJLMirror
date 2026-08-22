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
- SLO/error-budget accounting semantics;
- alert trigger/clear/suppression semantics;
- classification/redaction/retention requirements;
- sampling behavior that materially changes evidence validity;
- correlation identity role or trust assumptions;
- telemetry-pipeline failure/degradation behavior;
- tenant query/isolation semantics.

These require explicit profile versioning/migration and cannot silently roll through under an unchanged semantic identity.

### OBS-COMP-D — Security/recovery authority-sensitive

A subset of breaking changes affecting tenant isolation, secret/protected-data handling, recovery quarantine, current authority visibility, ambiguity/reconciliation evidence or audit separation.

These are release-blocking until the owning Security/Recovery authority and Phase 12 consumers prove the new semantics safe.

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

## SLI/SLO compatibility

Historical SLI/SLO comparisons identify the semantic profile used. When numerator/denominator/population/missing-data semantics change incompatibly:

- historical periods are not silently concatenated;
- error-budget accounting resets/rebases only through accepted governance;
- release/incident analysis records the boundary.

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
- restores obsolete secret/protected-data logging.

If downgrade cannot safely interpret current evidence, observability consumers fail closed/unknown rather than fabricate compatible meaning.

## Evidence

Compatibility evidence includes schema/profile diff, semantic diff, mixed-version tests, old/new consumer tests, SLI/alert query tests, cardinality/cost analysis, security/privacy review and rollback rehearsal where material.
