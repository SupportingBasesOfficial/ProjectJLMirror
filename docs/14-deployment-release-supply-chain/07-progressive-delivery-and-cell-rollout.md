# Phase 14 — Progressive Delivery and Cell Rollout

**Status:** proposed baseline

## Purpose

This document defines rollout semantics over Phase 13 cells/runtime profiles without selecting orchestrator, deployment controller or rollout product.

## Rollout principle

Production rollout is bounded, observable and interruptible. A release cannot require all cells/tenants to change simultaneously merely because tooling defaults to global deployment.

## Canonical rollout sequence

For ordinary releases whose behavior can be established without a cell-specific reference deployment:

```text
environment.validation@1 / validation.general@1
 -> production canary scope
 -> bounded production wave(s)
 -> remaining eligible production scope
 -> completion / retirement of old generation when safe
```

For cell/runtime/schema changes covered by the accepted Data staged-rollout rule:

```text
environment.validation@1 / validation.general@1
 -> environment.validation@1 / validation.reference-cell@1
 -> production canary cell(s)
 -> bounded production wave(s)
 -> remaining eligible production cells
 -> completion / retirement of old generation when safe
```

`validation.reference-cell@1` is a rollout/evidence scope inside the accepted logical validation environment, not a fifth Phase 13 environment class.

Exact wave sizes/durations remain OPEN.

## Deployment object

A `release.deployment@1` identifies:

```text
deployment_id
promotion_id
artifact_id
configuration identity
target environment
validation scope/evidence class
cell/target scope
expected_release_target_state_version
resulting_release_target_state_version_or_pending
runtime profiles
old/new runtime generations
schema/contract compatibility state
cell compatibility metadata version/evidence where applicable
wave identity
admission gate profile
pause/abort state
runtime-observed artifact identity/equivalent
runtime verification result
terminal/reconciliation state
```

`deployment_id` is the stable logical operation identity. Retrying the same logical deployment reuses that identity and observes its durable state/outcome rather than inventing a second executor.

`release_target_state_version` is release-control state for one target scope. It does not replace Phase 13 runtime generation, placement version, tenant placement authority or cell admission authority.

## Deployment create-or-observe

Before an effectful deployment starts, the release control plane atomically creates-or-observes the durable deployment operation and verifies the expected target release state/version.

For incompatible concurrent deployments targeting the same protected scope:

- one compatible transition wins admission under a fenced/atomic equivalent;
- a stale operation observing a newer target release state cannot continue effectful advancement;
- same `deployment_id` with conflicting immutable artifact/config/target semantics is an integrity conflict, not a retry;
- different operation IDs do not permit two incompatible target states to become current concurrently.

The concrete coordination store/lease/CAS mechanism remains `OPEN-RLS-027`; the single-current-transition property is not OPEN.

## Ambiguous deployment outcome

Timeout, controller crash, runner loss or lost API response after an effectful release command creates ambiguity, not absence.

The release system SHALL:

1. preserve the same `deployment_id` and requested immutable target semantics;
2. inspect durable release-controller and target/runtime evidence;
3. classify the operation as completed, still in progress, safely not started, or `reconciliation_required`;
4. retry effectful work only when the owning operation/fence semantics establish eligibility.

Blindly issuing a new deployment operation because the previous call timed out is prohibited when the earlier effect may have occurred.

## Pre-admission gates

Before protected serving admission, applicable gates re-establish:

- artifact integrity/provenance;
- target promotion authority;
- current deployment operation/fence and target release state;
- applicable validation scope completion on the same immutable artifact;
- Phase 13 runtime/environment conformance;
- independently observed running artifact identity/equivalence;
- configuration/network/workload-credential currentness;
- schema/API/event mixed-version compatibility;
- current Control Plane cell compatibility metadata sufficient for placement/cutover safety where applicable;
- required Phase 11 reliability state;
- Phase 12 health/security/recovery admission semantics;
- migration/backfill preconditions.

## Reference-cell validation

A cell-affecting release SHALL NOT skip from general validation directly to production canary merely because the deployment product has no staging concept.

The reference-cell stage proves the exact artifact/config/runtime/schema combination on a bounded production-like cell profile while remaining non-production authority. It cannot receive production placement authority, credentials or tenant traffic merely to increase fidelity.

If a specific release truly has no applicable reference-cell case, the release manifest records evidence-backed `NO_APPLICABLE_CASE`; omission/tool limitation is not sufficient.

## Cell compatibility metadata

The rollout consumes the accepted Control Plane cell metadata that records current/target schema/runtime compatibility sufficient for placement and rollout safety.

Release tooling may propose/update the intended target compatibility state only through the owning trusted Control Plane/release mechanism. It cannot route or cut over a tenant to a cell whose current admitted runtime/schema combination is outside the release compatibility matrix.

Stale or caller-controlled compatibility metadata cannot override destination-cell admission.

## Canary

Canary scope is selected by release authority, never caller/tenant input. Canary evidence cannot be generalized to incompatible runtime/profile/cell/environment states without explicit equivalence.

For cell-affecting releases, production canary begins only after required reference-cell evidence is satisfied.

## Pause

Rollout enters `paused` when an accepted gate cannot prove safe continuation. Pause preserves durable obligations, deployment operation identity/fences and does not imply rollback eligibility.

## Abort

Abort stops new rollout advancement. Already-mutated state/external effects remain authoritative and are handled under rollback/forward-recovery classification.

Abort of an operation with uncertain target effect records `reconciliation_required`; it does not reset the target state version or make a new deployment automatically eligible.

## Cell awareness

Cell rollout preserves placement authority and source/target fencing. Deployment cannot move tenants between cells as an incidental rollout shortcut; relocation remains Control Plane authority.

Release-target fencing and placement fencing are separate authorities and both apply where needed.

## Old/new coexistence

Rolling deployment declares supported old/new runtime, schema, API/event and configuration combinations. An old runtime unable to interpret current authority/evidence is drained/quarantined before incompatible state becomes authoritative.

## Runtime artifact verification

Each rollout scope verifies that the actually running workload corresponds to the approved immutable artifact identity or reviewed equivalent identity mapping. Deployment-controller success, desired-state equality or mutable tag equality is insufficient.

## Signals

Admission/pause/abort uses accepted Phase 12 signal/health semantics. Vendor-native green/ready is adapter evidence only and cannot override recovery/security quarantine or release-target fencing.

## Capacity

Rollout accounts for temporary double footprint, reference-cell capacity, surge replicas, migration/backfill work, cache warmup, realtime reconnects, worker backlog, observability load and ambiguous/retried release-controller work. Absence of numeric thresholds does not permit unbounded rollout amplification.