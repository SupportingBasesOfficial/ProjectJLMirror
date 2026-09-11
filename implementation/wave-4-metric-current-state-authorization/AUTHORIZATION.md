# Wave 4 Monitoring — Metric Current State Authorization

**Status:** proposed bounded implementation authorization  
**Base:** `main@84e9111dadaaca5823b8e696efc1c0764596e269`  
**Authorization ID:** `wave4.monitoring-metric-current-state@1`

## Purpose

This record defines the exact next bounded Monitoring Data Plane implementation slice after accepted Metric Definitions + Bindings: durably accept bounded authenticated Zabbix current-value evidence, maintain canonical `metric_current_state`, and persist the historical-projection obligation required by the accepted Telemetry Plane.

This authorization deliberately does not include `history.get`, materialization of durable `metric_observation` history/backfill, triggers/problems/events, health projection, provider write-back or frontend behavior.

## Core product model

```text
METRIC DEFINITION / BINDING
  already accepted identity + provider mapping

DURABLE ACCEPTED OBSERVATION ENVELOPE
  observation_identity_scope
  observation_id
  metric_definition_id
  source_instance_generation
  observed_at
  accepted_at
  canonical value/value_kind
  current projection ordering token
  historical projection obligation = pending/projectable

CURRENT METRIC PROJECTION
  metric_definition_id
  monitoring_resource_id
  monitoring_source_id
  source_instance_generation
  current_observation_id
  observed_at
  accepted_at
  value_kind
  value
  evidence_state
  projection_revision
  last_changed_at

HISTORICAL METRIC OBSERVATION MATERIALIZATION
  NOT AUTHORIZED BY THIS SLICE
```

Architectural invariants:

```text
CURRENT STATE != METRIC DEFINITION
CURRENT STATE != HISTORY
CURRENT STATE != HEALTH
DURABLE OBSERVATION ACCEPTANCE != CURRENT-STATE ADVANCEMENT
NEW ACCEPTED OBSERVATION => HISTORICAL PROJECTION OBLIGATION
SAME VALUE != SAME OBSERVATION
PROVIDER EVENT TIME != CURRENT-STATE ORDERING AUTHORITY
ACCEPTANCE TIME != PROVIDER EVENT TIME
LATER POLL GENERATION != SEMANTIC VALUE CHANGE
POSITIVE PER-OBJECT EVIDENCE != GLOBAL SNAPSHOT COMPLETENESS
OMISSION != NEGATIVE AUTHORITY WITHOUT KNOWN COVERAGE
LAST-KNOWN VALUE != CURRENT EVIDENCE
UNCERTAINTY != NULL/ABSENT VALUE
CURRENT-STATE POLL AUTHORITY != ITEM-DEFINITION POLL AUTHORITY
CURRENT-STATE POLL AUTHORITY != HOST-INVENTORY POLL AUTHORITY
HISTORICAL GENERATION != CURRENTLY MONITORED
STALE SCOPE != CURRENT AUTHORITY
```

## Authorized product behavior

1. **Read-only provider behavior.** The adapter may use bounded authenticated Zabbix `item.get` current-value fields (`lastvalue`, `lastclock`, `lastns`) only for metric definitions/bindings already accepted by the canonical Monitoring domain. No provider write-back is authorized.
2. **One current projection per accepted metric definition.** `metric_current_state` is keyed by canonical metric identity, never by raw `itemid` alone.
3. **Canonical ownership required.** Current evidence is accepted only when the metric definition and provider binding resolve within the same tenant/source/source-instance generation and owning canonical Monitoring resource.
4. **Active-generation only current authority.** A prior-generation metric may retain last-known current evidence for historical/last-known reads, but it cannot participate in current monitoring or receive new current-state authority.
5. **Current scope required.** A metric may be represented as freshly current only when its scope projection is proven against the source's current `scope_revision`; stale/reconciliation-required scope fails closed.
6. **Definition/binding compatibility required.** `definition_state=active`, compatible canonical `value_kind`, and non-reconciliation binding/definition evidence are required before provider value may become current canonical state.
7. **Independent current-state poll authority.** Current polling owns its own recovery-safe poll epoch, generation and volatile admission state. It may reuse accepted recovery/fencing laws and trusted recovery authority patterns, but it must not reuse Host Inventory or Item Definition mutable stream state.
8. **Poll generation is precedence/fence authority.** A later valid current-state poll may supersede an earlier in-flight poll. Provider `observed_at`, Zabbix `clock/ns`, and platform `accepted_at` do not independently override the current poll fence.
9. **Provider event time is evidence, not universal ordering.** A genuinely different current observation may be accepted under a later valid fenced poll even when provider event time is equal to or earlier than the previously stored event time, provided all other authority/compatibility checks succeed.
10. **Current observation identity is explicit.** The projection records an opaque/canonical `current_observation_id` bound to the durable accepted observation identity/evidence. Provider-local identity is always scoped by trusted tenant/source/generation context.
11. **Value normalization is canonical.** The accepted provider value must parse according to the already accepted metric `value_kind`. Invalid, lossy or incompatible conversion fails closed and degrades/reconciles evidence rather than mutating canonical type.
12. **No implicit boolean inference.** Generic integer `0/1` remains integer unless the metric definition already has an explicitly accepted boolean semantic mapping.
13. **Semantic no-op does not become a current transition.** A newly accepted observation whose canonical value/meaning equals the current value may refresh current evidence bookkeeping, but does not advance `last_changed_at` and does not create a duplicate current-state-changed obligation.
14. **Same value may still be a new observation.** A distinct provider observation identity/time carrying the same canonical value is durably accepted once and retains its historical-projection obligation even though it is a no-op for current-value transition semantics.
15. **Value change is distinct from evidence refresh.** `last_changed_at` advances only for a genuine canonical current-value transition, not because a poll generation, `accepted_at`, provider clock or evidence freshness changed.
16. **Last-known survives uncertainty without masquerading as current.** If provider evidence becomes `stale`, `incomplete`, `reconciliation_required` or `unavailable`, the prior value may remain stored/visible as last-known with a non-current `evidence_state`; it must not be presented as freshly current truth.
17. **Missing/invalid provider value is not a fabricated canonical value.** The implementation must not manufacture `0`, empty string, `false` or `null` as current value merely because provider evidence is missing, disabled, unsupported, stale or malformed.
18. **Disabled/unsupported definition semantics remain separate.** Provider disabled/unsupported state does not retire the metric definition. It may prevent fresh current evidence and degrade current-state evidence according to bounded provider semantics.
19. **Current state is not reconstructed from history per read.** The canonical projection is maintained directly; user reads do not query the historical store for a latest-row scan.
20. **Single durable acceptance boundary.** Every newly accepted provider observation is durably recorded exactly once under canonical scoped observation identity before/with required projections. The current row is not itself the sole acceptance record when doing so would lose the independent historical-projection obligation.
21. **Historical projection obligation is durable but history storage remains blocked.** Every newly accepted observation owns one idempotent durable obligation for the later History slice. This slice may persist that obligation/acceptance envelope, but it must not materialize `metric_observation`, expose history queries, or claim historical completeness.
22. **Current advancement and signal intent are atomic.** When a newly accepted observation genuinely advances current value, the current projection change and stable current-state transition/outbox obligation are persisted atomically, or an equivalent durable advancement record makes publication recoverable after crash/replay.
23. **No-op acceptance has no duplicate current transition.** Exact redelivery deduplicates at observation acceptance; a distinct newly accepted observation with the same canonical value may create a historical obligation but no `current-state-changed` obligation.
24. **Recovery fails closed.** PITR/failover/relocation cannot restore volatile current-state admission or allow stale pre-recovery claims to regain current authority.
25. **No frontend implication.** Backend/domain/data support for current state creates no frontend route/navigation authority.
26. **Positive per-object evidence is independently admissible.** A successfully returned, authority-valid item may be durably accepted and refresh its own current projection even if another bounded page/partition in the same broader cycle fails. Global snapshot completeness is not required for trustworthy positive evidence about that specific item.
27. **Omission has no authority without proven coverage.** A missing item/value in an incomplete, truncated, timed-out or otherwise uncertain cycle cannot clear the stored value or invent a negative current-state transition. It may degrade evidence only when the implementation can prove the metric belonged to the attempted coverage domain; otherwise prior last-known state is preserved without fabricated inference.
28. **Provider sample time must be structurally valid.** When Zabbix `lastclock/lastns` contributes to accepted observation identity/evidence, `lastclock` must represent a valid provider sample time and `lastns` must be a valid nanosecond component. Missing/zero/invalid sample-time evidence cannot be promoted to fresh current truth merely because a `lastvalue` string is present.

## Durable acceptance / projection semantics

The accepted Telemetry Plane requires one durable acceptance point before multiple projections. For this bounded slice:

- canonical observation identity is scoped by trusted tenant/source/provider/source-generation authority;
- exact redelivery of the same canonical observation is idempotent and does not create another acceptance row, history obligation or current transition;
- every newly accepted observation persists one later-history projection obligation, regardless of whether it changes current value;
- current-state advancement uses a deterministic monotonic ordering token derived from the accepted current poll authority/acceptance contract, not provider timestamp alone;
- current-state advancement that changes value atomically persists stable transition identity/outbox intent;
- a crash after durable observation acceptance but before all downstream projection work leaves recoverable lag, not ambiguous success;
- this slice does not project the historical observation itself. The later History slice consumes/reconciles the durable obligation under its own authorization.

## Evidence-state semantics

Canonical current-state evidence uses the accepted Monitoring operational evidence classes:

```text
current
stale
incomplete
reconciliation_required
unavailable
```

Rules:

- `current` requires active generation, current scope, compatible active definition/binding, current poll authority/admission and valid bounded provider value evidence;
- positive object-specific evidence may become current without requiring unrelated partitions to complete, provided that object's request/evidence and authority are individually trustworthy;
- omitted objects in incomplete/uncertain coverage do not acquire negative authority and their values are not cleared;
- stale/incomplete/unavailable provider execution never fabricates a fresh value;
- reconciliation-required definition/binding/scope prevents fresh current authority;
- historical generation has no current authority even if the stored projection's last accepted evidence had once been `current`;
- evidence degradation may update evidence classification without advancing `last_changed_at` when the canonical value itself did not change;
- invalid/missing provider sample time cannot be represented as freshly current observation evidence.

## Ordering / idempotency semantics

Current-state mutation is fenced by the endpoint-specific current-state poll stream.

A completion must bind at least:

```text
tenant_id
monitoring_source_id
source_instance_generation
configuration_revision
scope_revision
current_state_poll_epoch
current_state_poll_generation
runtime admission / placement authority
metric_definition_id
provider binding identity
canonical observation identity
```

The implementation must reject/retire stale or superseded completions before they mutate current state.

Replays of the same accepted observation are idempotent. A newer poll that accepts a distinct observation with the same canonical value may update `current_observation_id`/evidence bookkeeping according to the implementation contract while preserving `last_changed_at` and emitting no duplicate current-state change. A newer valid poll with a different canonical value may advance current state even if provider event time moved backwards; the monotonic platform ordering token determines write precedence, while provider time remains evidence.

## Explicitly outside this slice

This authorization does not permit:

- `history.get`;
- materializing durable `metric_observation` rows;
- history checkpoints/backfill/replay/finalization;
- claiming that pending historical projection obligation equals completed history;
- treating current-state rows as historical completeness;
- deriving current by querying historical latest-per-metric on each request;
- trigger/problem/event ingestion;
- health projection;
- Alerting/ITSM/AIOps behavior;
- provider write-back;
- raw provider payload replication;
- cross-generation current-state identity merging;
- current writes for historical generations;
- accepting stale scope as current authority;
- reusing Host Inventory or Item Definition poll epoch/generation/admission state for Current;
- provider timestamp as sole ordering authority;
- `accepted_at` as provider occurrence time;
- duplicate transition publication for same-value/no-op refresh;
- dropping the historical projection obligation because current value did not change;
- implicit current value from missing/invalid evidence;
- clearing current value from incomplete/unproven omission;
- treating global snapshot completeness as prerequisite for accepting trustworthy positive per-object current evidence;
- production polling/retry/capacity numerics beyond hard safety bounds;
- frontend route or navigation creation;
- production deployment.

## Acceptance boundary

This authorization becomes implementation authority only after its exact HEAD passes deterministic validation and panoramic/adversarial review and is separately squash-merged into `main`. Until then, implementation of Metric Current State remains blocked.
