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
worker concurrency by workload class
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

Every runtime/workload profile declares:

- resource dimensions it consumes;
- admission/concurrency controls;
- saturation/queueing signals;
- tenant/workload/destination isolation dimensions;
- degradation/shedding behavior inherited from Phase 11;
- Phase 12 health/SLI/alert bindings;
- evidence required to raise/lower limits;
- scale-up/scale-out/relocation triggers as OPEN numerics until benchmark/runtime evidence exists.

## Noisy-neighbor isolation

A tenant, provider, destination, report, parser, migration, recovery job or workload class SHALL NOT have an unbounded path to unrelated shared capacity.

Isolation mechanisms MAY be implemented through separate queues/pools/quotas/runtime groups/cells or other reviewed mechanisms. The mechanism remains replaceable; the boundedness property does not.

## Scaling classes

Phase 13 distinguishes:

### Replica scaling

Adds/removes interchangeable stateless runtime instances within a stable runtime/cell authority. Replica churn must not change logical tenant/resource identity or lose durable responsibility.

### Workload-pool scaling

Changes capacity for one worker/realtime/automation/parser class while preserving bulkheads and durable-work semantics.

### Stateful-port scaling

Expands/reconfigures a storage/broker/cache/telemetry/object dependency while preserving its port authority, compatibility, fencing and recovery semantics.

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
- process-local cache loss cannot resurrect stale authority.

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
- capacity profile published before placement.

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

Relocation capacity must account for temporary dual footprint, copy/backfill/reconciliation load and control-plane pressure.

## Recovery and scaling interaction

Autoscaling/replacement during recovery cannot erase quarantine or spawn many replicas of stale authority. Recovery-state/current-generation admission gates apply before new replicas process protected/effectful work.

## Cost attribution

Phase 13 requires cost/usage evidence to be attributable at least to runtime/workload/cell and, where safe/useful, tenant/integration classes without creating unsafe high-cardinality telemetry.

Cost controls SHALL detect runaway retry/backlog/query/parser/provider/recovery work. Exact prices/budgets remain OPEN.

## Scaling and rearchitecture triggers

Distributed service extraction or dedicated runtime/cell isolation requires evidence such as sustained independent scale, failure containment, security/runtime specialization, release cadence or ownership need. Load alone does not force premature service decomposition.

## Validation obligations

Conformance/runtime evidence later SHALL include:

- stateless replica replacement;
- scale-down during in-flight requests/jobs/realtime;
- stale leader after failover;
- one tenant/provider/destination/workload saturation;
- second-cell provisioning and rejection of wrong-placement tenant;
- relocation source/target fencing;
- temporary relocation double-load;
- recovery plus autoscaling interaction;
- migration/backfill pressure against serving workloads;
- capacity/cost measurement across multiple dimensions.

Exact replica/node/cell/region/autoscaling/partition numerics remain OPEN.