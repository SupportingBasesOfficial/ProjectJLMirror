# Telemetry Plane

**Status:** proposed baseline  
**Primary ADR:** ADR-006

## Purpose

Monitoring current state and high-volume historical telemetry have different performance/lifecycle requirements. Current operational reads must not degrade linearly as retained history grows.

## Separation

### Transactional current state in the cell

Examples:

- monitoring source configuration/reference;
- stable resources/devices;
- external provider mappings;
- metric definitions;
- resource/device current health/state;
- active problems;
- synchronization/checkpoint state;
- latest operational values required for fast UI/policy evaluation.

### Historical telemetry through the telemetry port

Examples:

- metric samples;
- observation/event history;
- capacity samples;
- high-volume operational measurements.

Logs/traces used for platform observability are operational telemetry and need not share the same physical store as customer monitoring metrics.

## Canonical sample dimensions

A metric sample contract carries at least:

```text
tenant_id
resource_id
metric_definition_id
source_id
observed_at
ingested_at
value + value_type/unit semantics
quality/status metadata when applicable
provider sequence/external identity when available
```

Provider-native IDs do not replace stable JLMIRROR resource/metric identity.

## Ingestion flow

```text
Provider
  -> adapter validation/normalization
  -> deduplication/reconciliation where possible
  -> update current transactional state if required
  -> append historical telemetry
  -> committed domain/integration signal
```

The flow must define what happens if telemetry persistence is temporarily unavailable; buffering is bounded and backpressure/data-loss policy is explicit.

## Partitioning and specialization

The physical telemetry implementation remains open until benchmark evidence. Candidate strategies may partition by time, tenant/hash dimension, metric/resource dimension or use a specialized time-series/columnar engine.

The design MUST support:

- retention by data class/plan/policy;
- compression/rollup where appropriate;
- bounded time-range query;
- tenant isolation;
- export/recovery semantics;
- ingest/query observability;
- no per-tenant physical table requirement by default.

## Current-state projection

Expensive current-state questions are answered from bounded projections, not by repeatedly scanning history for `latest`.

Examples:

- `resource_current_state`;
- `metric_latest_state` where product use requires it;
- `active_problem` projection.

Exact table names/models are determined with domain/API contract design.

## Downsampling/rollups

Long retention MAY use tiered resolution:

```text
raw -> short retention
fine rollup -> medium retention
coarse rollup -> long retention
```

Rollup algorithms and windows require product/query accuracy requirements and capacity benchmarks; they are not hard-coded at this stage.

## Tenant relocation

Telemetry is included in the relocation manifest. Large historical datasets may move asynchronously or via provider/storage-native transfer, but cutover must define which store is authoritative for new samples and how historical queries span/complete migration without split writes.
