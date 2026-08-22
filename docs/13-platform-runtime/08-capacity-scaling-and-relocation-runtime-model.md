# Phase 13 — Capacity, Scaling and Relocation Runtime Model

**Status:** proposed baseline  
**Phase:** 13 — Platform & Runtime

## Purpose

This document defines the evidence-generating multidimensional runtime capacity model and the portable capabilities required for scale, cell expansion, replacement and tenant relocation.

It does not set unsupported replica counts, cell counts, node sizes, autoscaling thresholds, regions or partition counts.

## Capacity dimensions

Capacity SHALL be evaluated across at least the applicable dimensions below:

```text
tenant count and tenant skew
request concurrency / operation mix
worker_specialization_id concurrency and queue ownership
durable backlog age and volume
provider/destination concurrency
realtime connection/fanout pressure
transactional database connections/CPU/IO/storage
customer telemetry ingest/history pressure
object/artifact throughput/storage
cache/coordination/reliability-state pressure
observability ingest/query/export pressure
control-plane lifecycle/placement pressure
migration/backfill/recovery work
secret/key/config authority request pressure
network/egress throughput and destination skew
```

One scalar such as CPU, tenant count or queue depth is not a complete capacity model.

## Capacity envelope

Every runtime profile and every selected `worker_specialization_id` declares:

- resource dimensions it consumes;
- admission/concurrency controls;
- queue/transport ownership where applicable;
- saturation/queueing signals;
- tenant/workload/destination isolation dimensions;
- state-port/connection pressure it can create;
- degradation/shedding behavior inherited from Phase 11;
- Phase 12 health/SLI/alert bindings;
- evidence required to raise/lower limits;
- scale-up/scale-out/relocation triggers as OPEN numerics until benchmark/runtime evidence exists.

A generic `runtime.worker@1` pool cannot be capacity-modeled without its exact selected worker specializations.

## Worker-specialization bulkheads

The initial prepared worker specializations are separately accountable for queue/concurrency/resource pressure:

```text
worker.outbox-publication@1
worker.async-consumer@1
worker.provider-integration@1
worker.webhook-delivery@1
worker.reporting-export@1
worker.customer-telemetry@1
worker.artifact-lifecycle@1
worker.reconciliation@1
```

Physical co-location MAY share compute only when per-specialization admission/concurrency/backlog and state/egress pressure remain attributable and bounded. Shared process/host placement is not evidence of a safe shared budget.

`PRTV-037` applies to privilege/resource coupling created by co-location; `PRTV-030` applies to noisy-neighbor saturation; `PRTV-043` applies if the implementation omits the specialization/resource binding.

## Noisy-neighbor isolation

A tenant, provider, destination, report, parser, migration, recovery job or worker specialization SHALL NOT have an unbounded path to unrelated shared capacity.

Isolation mechanisms MAY be implemented through separate queues/pools/quotas/runtime groups/cells or other reviewed mechanisms. The mechanism remains replaceable; the boundedness property does not.

## Scaling classes

Phase 13 distinguishes:

### Replica scaling

Adds/removes interchangeable stateless runtime instances within a stable runtime/cell authority. Replica churn must not change logical tenant/resource identity or lose durable responsibility.

### Workload-pool scaling

Changes capacity for one exact worker specialization, realtime, automation or parser workload while preserving bulkheads and durable-work semantics. Scaling one worker specialization cannot implicitly expand another specialization's principal/secret/state/egress envelope.

### Stateful-port scaling

Expands/reconfigures a storage/broker/cache/telemetry/object dependency while preserving its logical port authority, compatibility, fencing and recovery semantics. Physical scale/co-location cannot trigger `PRTV-039` authority collapse.

### Cell expansion

Creates a new data-plane cell as a new failure/capacity unit. New cell admission requires validation before tenant placement.

### Tenant relocation

Moves a logical tenant between cells through accepted placement authority. Relocation is not ordinary load balancing and cannot be inferred from a saturated process alone.

## Stateless runtime scaling

Serving replicas SHOULD be replaceable without process-local authoritative state.

Scale-down/drain SHALL ensure:

- no new work claimed/admitted beyond drain policy;
- in-flight requests reach bounded safe outcome;
- durable job leases/outcomes remain discoverable;
- realtime clients resync/reconnect where required;
- process-local cache loss cannot resurrect stale authority;
- worker specialization identity and durable responsibility remain discoverable across replica churn.

## Coordination and leadership

Where a workload requires a single active coordinator/leader/lease holder, the design SHALL use fenced, failure-detectable coordination rather than immortal singleton assumptions.

Requirements:

- leadership identity/epoch is distinguishable across failover;
- stale leader work is rejected where duplicate concurrent authority is unsafe;
- lease expiry/process death does not imply external effect absence;
- durable business/recovery truth is not kept only in leader memory;
- coordination loss maps to accepted degradation profile.

Exact lease/election product/primitive remains OPEN.

## Cell expansion

Second/new cell provisioning must prove:

- same logical API/event/runtime contracts;
- expected state-port capability/profile versions;
- workload identities and secret/config references scoped to the new cell;
- tenant isolation and placement admission;
- health/observability coverage;
- ability to reject a tenant/version not assigned to the cell;
- runtime and worker-specialization capacity profiles published before placement.

A new cell cannot require customer-visible tenant ID/resource ID changes.

## Tenant relocation runtime support

Runtime support includes:

1. target cell provisioned/validated/admitted;
2. placement operation obtains accepted source/target generations;
3. source admission transitions according to relocation state;
4. data/evidence transfer/reconciliation follows accepted System/Data contracts;
5. target becomes authoritative only through Control Plane placement transition;
6. stale source requests/workers/sockets are rejected/fenced/resynced;
7. post-cutover `(R,F]`/ambiguous effects are reconciled before unsafe replay/resume;
8. old physical resources are retired only after governance/recovery obligations permit it.

Relocation capacity must account for temporary dual footprint, copy/backfill/reconciliation load, worker-specialization backlog and control-plane pressure.

## Recovery and scaling interaction

Autoscaling/replacement during recovery cannot erase quarantine or spawn many replicas of stale authority. Recovery-state/current-generation admission gates apply before new replicas process protected/effectful work.

Scaling a recovery/reconciliation worker does not grant broader recovery authority; exact worker/runtime profile and affected scope remain authoritative.

## Cost attribution

Phase 13 requires cost/usage evidence to be attributable at least to runtime profile, worker specialization, cell and, where safe/useful, tenant/integration classes without creating unsafe high-cardinality telemetry.

Cost controls SHALL detect runaway retry/backlog/query/parser/provider/recovery work. Exact prices/budgets remain OPEN.

## Scaling and rearchitecture triggers

Distributed service extraction or dedicated runtime/cell isolation requires evidence such as sustained independent scale, failure containment, security/runtime specialization, release cadence or ownership need. Load alone does not force premature service decomposition.

## Validation obligations

Conformance/runtime evidence later SHALL include:

- stateless replica replacement;
- scale-down during in-flight requests/jobs/realtime;
- per-worker-specialization saturation and bulkhead isolation;
- stale leader after failover;
- one tenant/provider/destination/workload saturation;
- second-cell provisioning and rejection of wrong-placement tenant;
- relocation source/target fencing;
- temporary relocation double-load;
- recovery plus autoscaling interaction;
- migration/backfill pressure against serving workloads;
- capacity/cost measurement across multiple dimensions;
- manifest completeness for worker specialization/resource bindings under `PRTV-043`.

Exact replica/node/cell/region/autoscaling/partition numerics remain OPEN.