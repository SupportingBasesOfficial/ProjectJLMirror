# Telemetry Plane

**Status:** accepted  
**Primary ADRs:** ADR-006, ADR-008

## Purpose

Monitoring current state and high-volume historical telemetry have different performance/lifecycle requirements. Current operational reads must not degrade linearly as retained history grows. When those data classes use different persistence authorities, ingestion must remain crash-consistent, accepted-observation identity must remain collision-safe across tenants/providers/sources, and current-state projections must not regress when accepted observations are replayed or delivered out of order.

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
observation_identity_scope   non-null canonical trusted namespace
observation_id               stable identity unique within that scope
tenant_id
resource_id
metric_definition_id
source_id
observed_at
ingested_at
value + value_type/unit semantics
quality/status metadata when applicable
provider observation/event/sequence identity when available
projection_order_key / source generation semantics when required
```

The canonical deduplication identity is conceptually:

```text
UNIQUE(observation_identity_scope, observation_id)
```

`observation_identity_scope` is derived from trusted platform/integration context and includes every dimension required to make the source identity unambiguous, such as tenant/global boundary, provider/integration/source identity and source generation/stream when applicable. Provider payload text or caller-controlled fields do not get to select a weaker namespace.

A provider-native observation/event/sequence ID MAY supply `observation_id` only inside that authoritative scope. The same provider-local value emitted by a different tenant, integration, source or generation is a different accepted observation and MUST NOT be suppressed. A constant/global scope is permitted only when the producing contract explicitly proves the ID is globally unique across every producer capable of reaching the acceptance boundary for the full deduplication retention window.

When no safe provider-native stable identity exists, the platform assigns/persists an accepted-observation identity according to the ingestion contract; downstream projections consume the persisted canonical identity rather than inventing independent dedup keys.

Provider-native IDs do not replace stable JLMIRROR resource/metric identity, and deduplication identity is distinct from projection ordering identity.

`observed_at` is event time and is not, by itself, a sufficient monotonic authority for latest-state updates because provider clocks can skew or move backwards.

## Durable acceptance boundary

Ingestion declares exactly one durable acceptance point before multiple persistence projections.

```text
Provider
  -> adapter validation/normalization
  -> derive trusted observation_identity_scope + observation_id
  -> derive/validate projection ordering metadata
  -> DURABLE ACCEPTANCE
       |-> idempotent historical telemetry projection
       |-> monotonic current transactional-state projection when required
       |-> durable transition/signal intent for successful current-state advances
```

`DURABLE ACCEPTANCE` is an architectural contract, not a selected vendor. It may be:

- a durable telemetry ingress journal/log/stream with replay/checkpoints; or
- a transactional persistence record plus outbox when PostgreSQL is the accepted ingestion authority; or
- a specialized telemetry store only if it can provide the replay/checkpoint/reconciliation guarantees required to repair downstream projections.

The durable acceptance authority enforces or otherwise proves uniqueness of the canonical scoped observation identity for the accepted deduplication window. A provider-local ID alone is not treated as globally unique unless the provider/source contract proves that property.

The system does **not** acknowledge an observation as accepted after an uncoordinated write to one authority while another required write remains only in process memory.

## Projection ordering and monotonic current state

Idempotency prevents the same canonical accepted observation from being applied twice; it does not by itself prevent an older distinct observation from arriving after a newer one. Every current/latest-state projection therefore defines a deterministic ordering contract for its projection key, such as `(tenant_id, source_id, resource_id, metric_definition_id)` or another owner-domain key.

The ordering contract MUST use an ordering token that can be compared monotonically for that projection key. Preferred inputs are:

- a provider-native monotonic sequence/version when its semantics are reliable;
- a provider sequence combined with an explicit source generation/epoch when the provider can reset counters;
- or a platform-assigned acceptance ordinal/version established at the durable acceptance boundary when provider ordering is insufficient.

A current-state writer performs a conditional compare-and-set/update: the incoming observation may replace current state only when its ordering token is strictly newer than the stored projection token, or when an explicitly defined deterministic tie-break rule says it wins. A stale/out-of-order observation remains valid historical telemetry but MUST NOT regress `metric_latest_state`, `resource_current_state` or equivalent current projections.

Ordering semantics are source-aware. A reconnect, provider reset, tenant relocation or source reconfiguration that can invalidate sequence comparison introduces a new generation/epoch or equivalent boundary rather than reusing an ambiguous counter domain.

## Atomic current-state advancement and signal intent

A signal whose meaning is **"current/latest state changed"** is part of the successful state transition, not best-effort code after it.

When an observation successfully advances a current-state projection, the system MUST durably persist a stable transition identity and the required signal/outbox intent atomically with that advancement, or persist an equivalent durable advancement record from which the signal can be produced after crash/replay.

Preferred PostgreSQL-owned pattern:

```text
BEGIN
  compare-and-set current projection by ordering token
  if advanced:
      persist transition_id / from_token / to_token
      append current-state-changed outbox intent
COMMIT
```

If the current-state projection lives in another persistence authority, that authority must atomically retain an advancement record/checkpoint that an idempotent signal projector can consume. The transient result `CAS updated 1 row` held only in worker memory is not sufficient.

Therefore a crash after state advancement but before ordinary worker code continues leaves a durable signal obligation. Replay encountering an equal already-stored ordering token can discover the prior transition record/intent and complete publication without trying to move the state again.

Historical/event-time analytics may process late observations under their own explicit window/watermark semantics, but stale observations do not masquerade as a newer current-state transition and do not create a second transition signal.

## Projection and reconciliation semantics

Historical, current-state and signal writers consume canonical scoped observation/transition identities idempotently. Duplicate retries within the same authoritative observation scope may reproduce delivery attempts but not duplicate the logical observation, state transition or effect. An equal raw provider ID from a different trusted scope remains independently processable.

Each projection tracks a durable checkpoint/watermark or equivalent reconciliation state. A crash between projections leaves recoverable lag, not ambiguous success. Operators can compare acceptance/projection watermarks and replay/reconcile incomplete work.

Reconciliation may replay observations in arbitrary delivery order; monotonic current-state compare-and-set semantics ensure replay cannot move latest state backwards, while durable transition identities ensure a previously committed advance cannot lose its required signal.

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

Current-state records include enough ordering/freshness metadata to prove why a value is considered current and to reject stale replay. Transition records/intents include enough identity to recover required downstream signals without making the current row mutable history.

## Downsampling/rollups

Long retention MAY use tiered resolution:

```text
raw -> short retention
fine rollup -> medium retention
coarse rollup -> long retention
```

Rollup algorithms and windows require product/query accuracy requirements and capacity benchmarks; they are not hard-coded at this stage.

## Identity validation

Tests MUST feed the same raw provider-local observation/event ID from different authoritative tenant/source/generation scopes and prove both observations are accepted and projected independently. Exact redelivery of the same canonical scoped identity must deduplicate. Untrusted/provider payload fields must not be able to forge another scope or collapse two authoritative sources into one deduplication identity.

## Tenant relocation

Telemetry is included in the relocation manifest. Large historical datasets may move asynchronously or via provider/storage-native transfer, but cutover must define which durable acceptance boundary is authoritative for new observations, transfer/replay watermarks, canonical observation identity scope/source-generation continuity, pending transition/signal intent continuity, and how historical queries span/complete migration without split writes.

No observation may be durably accepted as new authoritative input in both source and target after the relocation fence.
