# Telemetry Plane

**Status:** proposed baseline  
**Primary ADR:** ADR-006

## Purpose

Monitoring current state and high-volume historical telemetry have different performance/lifecycle requirements. Current operational reads must not degrade linearly as retained history grows. When those data classes use different persistence authorities, ingestion must remain crash-consistent.

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

## Canonical observation identity

An accepted observation/sample contract carries at least:

```text
observation_id / stable provider-derived dedup identity
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

## Durable acceptance boundary

Ingestion declares exactly one durable acceptance point before multiple persistence projections.

```text
Provider
  -> adapter validation/normalization
  -> derive observation_id / dedup identity
  -> DURABLE ACCEPTANCE
       |-> idempotent historical telemetry projection
       |-> idempotent current transactional-state projection when required
       |-> idempotent domain/integration signal projection
```

`DURABLE ACCEPTANCE` is an architectural contract, not a selected vendor. It may be:

- a durable telemetry ingress journal/log/stream with replay/checkpoints; or
- a transactional persistence record plus outbox when PostgreSQL is the accepted ingestion authority; or
- a specialized telemetry store only if it can provide the replay/checkpoint/reconciliation guarantees required to repair downstream projections.

The system does **not** acknowledge an observation as accepted after an uncoordinated write to one authority while another required write remains only in process memory.

## Projection and reconciliation semantics

Historical, current-state and signal writers consume the durable observation identity idempotently. Duplicate retries may reproduce delivery attempts but not duplicate the logical observation/effect.

Each projection tracks a durable checkpoint/watermark or equivalent reconciliation state. A crash between projections leaves recoverable lag, not ambiguous success. Operators can compare acceptance/projection watermarks and replay/reconcile incomplete work.

If a provider supports replay/resume tokens, those are tracked as source checkpoints but do not replace JLMIRROR's own accepted-observation identity.

## Unavailability/backpressure

If the durable acceptance boundary is unavailable, buffering is bounded and the source-specific backpressure/drop/retry policy is explicit. The transactional core is protected from unbounded telemetry backlog.

If a downstream projection store is unavailable after durable acceptance, ingestion may continue only within accepted backlog/storage budgets; the failed projection retries from durable accepted observations rather than inventing a second write path.

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

Current-state freshness includes projection watermark/observed-at semantics where operationally material.

## Downsampling/rollups

Long retention MAY use tiered resolution:

```text
raw -> short retention
fine rollup -> medium retention
coarse rollup -> long retention
```

Rollup algorithms and windows require product/query accuracy requirements and capacity benchmarks; they are not hard-coded at this stage.

## Tenant relocation

Telemetry is included in the relocation manifest. Large historical datasets may move asynchronously or via provider/storage-native transfer, but cutover must define which durable acceptance boundary is authoritative for new observations, transfer/replay watermarks, and how historical queries span/complete migration without split writes.

No observation may be durably accepted as new authoritative input in both source and target after the relocation fence.
