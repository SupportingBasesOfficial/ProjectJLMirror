# Phase 15 — Dependency Failure and Degraded Operations

**Status:** proposed baseline

## Purpose

Map accepted Phase 11 failure/degradation behavior to operational ownership and procedures without redefining resilience semantics.

## Operational mapping

Every critical dependency/capability records:

```text
accepted_reliability_profile
failure/degradation class
automatic handling profile
operational owner
incident class trigger conditions
manual runbook class
security/recovery blockers
capacity/backlog implications
recovery/resumption evidence
```

If Phase 11 already defines automatic bounded handling, operators observe/escalate rather than replace it with ad hoc behavior.

## Control Plane impairment

Operators may stabilize traffic and freeze unsafe changes according to accepted profiles. They cannot derive tenant placement or authorization from cached operational dashboards when current authority is required.

## Cell degradation

Cell draining/degradation preserves Phase 13 lifecycle, placement and generation semantics. Operational evacuation/relocation uses accepted placement authority; deployment tooling or manual routing does not move tenants incidentally.

## External/provider outage

Provider failure uses accepted adapter/reliability semantics. Operators may pause, isolate, reconcile or switch an accepted provider profile only where Product/domain authority permits. Provider-native success/failure does not redefine platform outcome.

## Async/backlog overload

Operators use accepted admission, shedding, backpressure, quarantine and capacity profiles. Increasing concurrency, redriving queues or disabling deduplication is not an operational shortcut.

## Observability degradation

Loss of telemetry is itself an operational degraded state under Phase 12. Lack of alerts/logs cannot be interpreted as service health. Critical protected operations requiring evidence may remain blocked where observability evidence is a required admission input.

## Security/crypto dependency outage

When current authorization, key/verifier or cryptographic authority cannot be proven, protected operations fail closed according to accepted Security/Phase 11 profiles. Operators cannot substitute manually copied material or stale verifier policy.

## Release/deployment dependency outage

A failed CI/CD/orchestrator/controller does not make deployment effect absent. Active `deployment_operation_id` and target-state evidence remain authoritative and must reconcile before a new release operation.

## Vendor/dependency status

Vendor dashboards/status pages are evidence only. They do not prove JLMIRROR recovery, effect absence, current authority or incident closure.

## Evidence

Operational evidence records accepted degradation mode, automatic/manual path, scope, capacity/backlog state, authority blockers, actions and resumption basis.