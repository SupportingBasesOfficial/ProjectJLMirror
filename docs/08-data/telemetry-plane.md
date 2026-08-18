# Telemetry Plane

**Status:** proposed baseline  
**Primary ADR:** ADR-006

## Purpose

Monitoring current state and high-volume historical telemetry have different performance/lifecycle requirements. Current operational reads must not degrade linearly as retained history grows. When those data classes use different persistence authorities, ingestion must remain crash-consistent and current-state projections must not regress when accepted observations are replayed or delivered out of order.

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
projection_order_key / source generation semantics when required
```

Provider-native IDs do not replace stable JLMIRROR resource/metric identity.

`observed_at` is event time and is not, by itself, a sufficient monotonic authority for latest-state updates because provider clocks can skew or move backwards.

## Durable acceptance boundary

Ingestion declares exactly one durable acceptance point before multiple persistence projections.

```text
Provider
  -> adapter validation/normalization
  -> derive observation_id / dedup identity
  -> derive/validate projection ordering metadata
  -> DURABLE ACCEPTANCE
       |-> idempotent historical telemetry projection
       |-> monotonic current transactional-state projection when required
       |-> idempotent domain/integration signal projection
```

`DURABLE ACCEPTANCE` is an architectural contract, not a selected vendor. It may be:

- a durable telemetry ingress journal/log/stream with replay/checkpoints; or
- a transactional persistence record plus outbox when PostgreSQL is the accepted ingestion authority; or
- a specialized telemetry store only if it can provide the replay/checkpoint/reconciliation guarantees required to repair downstream projections.

The system does **not** acknowledge an observation as accepted after an uncoordinated write to one authority while another required write remains only in process memory.

## Projection ordering and monotonic current state

Idempotency prevents the same observation from being applied twice; it does not by itself prevent an older distinct observation from arriving after a newer one. Every current/latest-state projection therefore defines a deterministic ordering contract for its projection key, such as `(tenant_id, source_id, resource_id, metric_definition_id)` or another owner-domain key.

The ordering contract MUST use an ordering token that can be compared monotonically for that projection key. Preferred inputs are:

- a provider-native monotonic sequence/version when its semantics are reliable;
- a provider sequence combined with an explicit source generation/epoch when the provider can reset counters;
- or a platform-assigned acceptance ordinal/version established at the durable acceptance boundary when provider ordering is insufficient.

A current-state writer performs a conditional compare-and-set/update: the incoming observation may replace current state only when its ordering token is strictly newer than the stored projection token, or when an explicitly defined deterministic tie-break rule says it wins. A stale/out-of-order observation remains valid historical telemetry but MUST NOT regress `metric_latest_state`, `resource_current_state` or equivalent current projections.

Signals whose meaning is "current/latest state changed" are emitted only from an observation that successfully advances the corresponding current-state projection. Historical/event-time analytics may process late observations under their own explicit window/watermark semantics, but they do not masquerade as a newer current-state transition.

Ordering semantics are source-aware. A reconnect, provider reset, tenant relocation or source reconfiguration that can invalidate sequence comparison introduces a new generation/epoch or equivalent boundary rather than reusing an ambiguous counter domain.

## Projection and reconciliation semantics

Historical, current-state and signal writers consume the durable observation identity idempotently. Duplicate retries may reproduce delivery attempts but not duplicate the logical observation/effect.

Each projection tracks a durable checkpoint/watermark or equivalent reconciliation state. A crash between projections leaves recoverable lag, not ambiguous success. Operators can compare acceptance/projection watermarks and replay/reconcile incomplete work.

Reconciliation may replay observations in arbitrary delivery order; monotonic current-state compare-and-set semantics ensure replay cannot move latest state backwards.

If a provider supports replay/resume tokens, those are tracked as source checkpoints but do not replace JLMIRROR's own accepted-observation identity or projection ordering contract.

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

Current-state records include enough ordering/freshness metadata to prove why a value is considered current and to reject stale replay.

## Downsampling/rollups

Long retention MAY use tiered resolution:

```text
raw -> short retention
fine rollup -> medium retention
coarse rollup -> long retention
```

Rollup algorithms and windows require product/query accuracy requirements and capacity benchmarks; they are not hard-coded at this stage.

## Tenant relocation

Telemetry is included in the relocation manifest. Large historical datasets may move asynchronously or via provider/storage-native transfer, but cutover must define which durable acceptance boundary is authoritative for new observations, transfer/replay watermarks, source generation/order-token continuity, and how historical queries span/complete migration without split writes.

No observation may be durably accepted as new authoritative input in both source and target after the relocation fence.
