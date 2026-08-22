# Phase 12 — Health, Readiness and Degradation Contract

**Status:** proposed baseline  
**Phase:** 12 — Observability & SRE

## Purpose

This document defines health meanings that expose Phase 11 behavior without collapsing fundamentally different states into a single green/red bit.

## Core dimensions

### Liveness

Whether the runtime process/agent is executing enough to be restarted or diagnosed. Liveness SHALL NOT require every external dependency to be healthy; otherwise a shared dependency outage can cause destructive restart loops.

Liveness is not authorization, readiness or correctness proof.

### Readiness

Whether a runtime/capability instance is currently eligible to accept a defined class of new work under its accepted lifecycle/generation/configuration prerequisites.

Readiness is workload/profile-specific. A runtime may be ready for read-only public health while not ready for tenant mutations, provider work or recovery-sensitive work.

Readiness SHALL NOT become an alternate authorization authority. It summarizes prerequisites established by owning authorities.

### Degradation

Whether the capability is intentionally operating with reduced freshness, throughput or optional features under an accepted Phase 11 degradation mode while preserving invariants.

A degraded state SHALL identify the affected capability/workload and degradation class. `degraded` is not synonymous with `down`.

### Draining

Whether the runtime/cell/workload is refusing new admission while completing, fencing, transferring or terminating accepted work according to lifecycle policy.

Draining state SHALL make outstanding work/lease/backlog visibility available where safe so termination cannot masquerade as clean completion.

### Saturation

Whether a bounded resource dimension is approaching/exceeding an accepted operating envelope. Saturation is evidence for admission/backpressure/degradation decisions owned elsewhere; it is not itself permission to shed protected work contrary to its profile.

### Recovery quarantine

Whether a tenant/cell/capability is intentionally non-authoritative or non-executable for protected/effectful work pending recovery/reconciliation evidence such as `(R,F]`, current security/governance state, comparison-verifier continuity or external-effect reconciliation.

Recovery quarantine SHALL be distinguishable from ordinary dependency outage. A generic restart or health probe cannot clear it.

## Composite health model

Health SHOULD be represented as dimensions/reasons, for example:

```text
capability_id
workload_class
liveness
readiness
readiness_reason_class
degradation_mode
saturation_class
draining_state
recovery_quarantine_state
trust_state_summary
config_generation_reference
runtime_generation_reference
observed_at
```

Exact wire representation belongs to implementation, but semantic meaning is fixed here.

## Required reason classes

Health evidence SHALL be able to distinguish, where applicable:

```text
healthy_or_eligible
dependency_unavailable
dependency_slow_or_saturated
throttled_or_shed
configuration_unavailable_or_stale
current_authority_unprovable
compromised_or_untrusted
reconciliation_required
recovery_continuity_blocked
draining
startup_or_warmup
internal_failure
```

These reason classes map to accepted Phase 11 behavior; they do not replace its failure taxonomy.

## Dependency health

A dependency being reachable is not enough to declare it healthy/trusted. Probes distinguish protocol reachability from semantic eligibility and trust where necessary.

Trust/security failures SHALL NOT heal merely because an ordinary circuit-breaker probe succeeds. A compromised/untrusted dependency remains blocked until the owning trust authority/evidence re-establishes eligibility.

## Duplicate-sensitive comparison health

Duplicate-sensitive inbox/replay paths SHALL expose three independent dimensions rather than one generic dependency state:

```text
comparison_dependency_availability
historical_comparison_continuity
comparison_trust_state
```

They SHALL preserve the owning Phase 11 boundary semantics:

- a temporary comparison dependency outage may be an availability condition;
- missing, rolled-back, mismatched or uninterpretable historical comparison authority is a continuity condition;
- compromised/untrusted comparison authority is a trust condition.

The health profile records the Phase 11 failure class and degradation mode selected by the owning profile. It does not independently decide admission, duplicate status, replay eligibility or effect safety.

Returning network/service reachability may clear only the temporary availability dimension after the owning authority can again establish the required proof. It SHALL NOT clear a historical-continuity or trust failure.

Comparison-health detail is privileged. Public health surfaces SHALL NOT expose protected comparison references or enable equality/correlation across tenant/consumer scopes.

## Control Plane and cells

Health for Control Plane/cells SHALL expose separately:

- control-plane reachability/currentness where relevant;
- cell admission state;
- placement/generation freshness;
- draining/relocation state;
- recovery quarantine;
- workload-specific dependency degradation.

A cell being reachable does not authorize placement or protected admission.

## Async/workers

Worker health SHALL expose progress-oriented evidence such as accepted work age/backlog, lease progress, retry/quarantine/reconciliation pressure and dependency saturation. A process heartbeat without durable progress is insufficient evidence of healthy async processing.

For duplicate-sensitive workers, process/queue health SHALL NOT mask `health.message-equivalence@1`; a worker can be alive while effect/replay admission remains reconciliation-blocked or fail-closed.

## Telemetry pipeline health

Observability pipeline health is self-observed through bounded independent signals such as exporter backlog/drop/error counters and last-success evidence. The design SHALL avoid recursive dependence where the only proof that telemetry is working is telemetry that requires the same failed path.

Exact secondary/self-observation mechanism remains OPEN.

## Public vs privileged health

Externally/publicly exposed health endpoints SHALL reveal only the minimum safe state needed for their purpose. Internal dependency names, tenant identifiers, topology, provider details, security/recovery state and vulnerable component information are privileged diagnostic data unless an accepted public contract says otherwise.

## Probe behavior

Health probes SHALL be bounded in time/work and SHALL NOT:

- mutate business state;
- consume one-time capabilities;
- perform expensive full scans;
- create provider side effects;
- bypass tenant/security boundaries;
- clear quarantine/trust state;
- depend on unbounded telemetry queries.

## Validation obligations

Tests SHALL prove distinctions among liveness/readiness/degradation/draining/saturation/recovery quarantine; dependency outage without restart storm; trust failure that remains blocked after reachability returns; recovery quarantine that cannot be cleared by a probe; and worker heartbeat without progress not being reported as healthy durable progress.

Duplicate-sensitive validation SHALL additionally prove that temporary comparison unavailability, historical comparison continuity loss and compromised comparison trust remain distinguishable and cannot be cleared by the wrong recovery predicate.
