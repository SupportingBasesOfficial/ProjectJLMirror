# Wave 4 Monitoring — Metric History Authorization

**Status:** proposed bounded implementation authorization  
**Base:** `main@033222f023e09f0ab0339f8e0237bb2b8345ce08`  
**Authorization ID:** `wave4.monitoring-metric-history@1`

## Purpose

This record defines the exact next bounded Monitoring Data Plane implementation slice after accepted Metric Current State: project canonical historical metric observations from the durable acceptance boundary and from bounded authenticated Zabbix `history.get`, while maintaining independent checkpoint/reconciliation evidence that cannot silently manufacture completeness.

This authorization deliberately does not include Problems/Triggers/Events, Health, Alerting/ITSM/AIOps behavior, provider write-back, frontend behavior, production capacity numerics, irreversible selection of a specialized telemetry vendor, or any authority for History to mutate canonical Current State.

## Core product model

```text
CANONICAL METRIC DEFINITION / PROVIDER BINDING
  already accepted generation-scoped identity + owner tuple

DURABLE ACCEPTED OBSERVATION ENVELOPE
  canonical observation identity
  tenant/source/generation/resource/metric owner tuple
  provider occurrence time
  accepted-at / projection metadata
  canonical value + value kind
  history_projection_state = pending/projected/reconciliation_required

HISTORICAL METRIC OBSERVATION
  immutable canonical accepted sample
  observation_identity_scope
  observation_id
  tenant_id
  monitoring_resource_id
  metric_definition_id
  monitoring_source_id
  source_instance_generation
  provider_external_ref
  provider_clock/provider_ns
  observed_at
  accepted_at / projected_at
  value_kind
  canonical_value

HISTORY STREAM CHECKPOINT / RECONCILIATION STATE
  tenant/source/generation/item/value-type logical stream
  safe floor/window boundary
  provisional high-water mark
  overlap/reconciliation coverage
  gap/degraded/finalization evidence

CURRENT STATE
  NOT MUTATED BY THIS SLICE
```

Architectural invariants:

```text
HISTORY != CURRENT STATE
HISTORY != METRIC DEFINITION
HISTORY != HEALTH
HISTORICAL OBSERVATION IDENTITY != PROVIDER ITEM ID
PROVIDER EVENT TIME != APPEND POSITION
FAST HIGH-WATER MARK != COMPLETENESS
ONE FORWARD PASS != FINALIZATION
PAGE RETURNED != PAGE COMPLETE
CLOCK SECOND != SAFE CURSOR BY ITSELF
LATE ARRIVAL != DUPLICATE
REPLAY != NEW LOGICAL OBSERVATION
CURRENT PENDING HISTORY OBLIGATION != PROJECTED HISTORY
HISTORICAL GENERATION != CURRENT AUTHORITY
HISTORY CHECKPOINT AUTHORITY != CURRENT POLL AUTHORITY
HISTORY CHECKPOINT AUTHORITY != ITEM-DEFINITION POLL AUTHORITY
HISTORY CHECKPOINT AUTHORITY != HOST-INVENTORY POLL AUTHORITY
UNCERTAINTY != COMPLETE
RETENTION LOSS != SUCCESSFUL BACKFILL
```

## Authorized product behavior

1. **Read-only provider behavior.** The adapter may invoke authenticated bounded Zabbix `history.get` for canonical metric definitions/bindings and may batch compatible item IDs by native history value type. No provider write-back is authorized.
2. **`history.get` is historical authority; `item.get` is not.** `item.get lastvalue/lastclock/lastns` remains Current evidence and cannot be treated as historical-stream completeness.
3. **Canonical historical identity is scoped.** Every historical observation uses the trusted canonical observation identity scope, including tenant, source/provider and source-instance generation dimensions needed to prevent provider-ID collisions.
4. **History binds to canonical owner tuple.** A projected observation must resolve to the exact canonical tenant/resource/metric/source/source-generation ownership and accepted provider binding; raw `itemid` is external reference only.
5. **Historical generation is valid history.** A retained prior source generation may receive authorized replay/backfill for its own generation-scoped history when provider/recovery evidence permits it; this never restores Current authority.
6. **Current authority is independent.** Historical ingestion, replay or backfill MUST NOT advance, regress, refresh or otherwise mutate `metric_current_state` merely because a historical sample has a newer/equal provider timestamp.
7. **Single durable acceptance boundary.** A provider observation becomes a canonical accepted observation once. History projection consumes that identity idempotently rather than inventing a second deduplication namespace.
8. **Current-created obligations are first-class.** Every durable accepted observation with `history_projection_state=pending` is eligible for idempotent historical projection. It becomes projected only after the historical projection is durably committed/proven.
9. **Direct History acceptance and Current acceptance converge.** A sample first seen through `history.get` and the same sample later seen through Current, or vice versa, converges on one canonical accepted observation identity and one logical historical observation.
10. **History observations are immutable.** Once the canonical scoped observation identity is materialized, its owner tuple, provider occurrence identity/time, value kind and canonical value cannot be silently rewritten. Conflicting reuse is reconciliation/integrity failure.
11. **Per-stream checkpoint authority.** Completeness/reconciliation state is logical per `(tenant_id, monitoring_source_id, source_instance_generation, provider_external_ref/itemid, history_value_type)` even when physical requests batch compatible items.
12. **History owns its own recovery-safe authority.** Mutable history checkpoint/reconciliation state must not reuse Host Inventory, Item Definition or Current poll epoch/generation/admission state.
13. **Inclusive overlap is required.** Incremental polling re-reads a bounded overlap around the provisional high-water mark and deduplicates by canonical observation identity. A worker must not use `time_from = last_clock + 1` as its sole continuation rule.
14. **Same-second completeness is explicit.** Zabbix second-granularity query bounds plus row-level `ns` mean a boundary second cannot be advanced past until truncation/undiscovered same-second rows are ruled out for the logical stream.
15. **Page limit is not completeness.** Reaching a row/body/window limit without proving exhaustion is degraded/reconciliation/capacity evidence; it must not advance a safe checkpoint beyond the proven boundary.
16. **Provider event time is not append position.** A value may become query-visible after newer-clock rows due to proxy buffering or delayed delivery. A strict once-only forward timestamp cursor is forbidden.
17. **Late-arrival reconciliation is mandatory.** In addition to the fast incremental path, bounded background reconciliation repeatedly covers the still-supported late-arrival/history horizon in partitioned windows.
18. **Outage/gap widens reconciliation.** Provider/proxy outage, source recovery, detected gap or conditions that may exceed normal overlap widen/prioritize bounded reconciliation/backfill rather than silently continuing from the fast cursor.
19. **Finalization is evidence-bound.** A historical region may be called finalized only after the accepted provider lateness/retention contract makes further supported insertion impossible and reconciliation has covered the region after that boundary.
20. **Unbounded lateness means no false finality.** If the provider profile cannot support a finite lateness/finalization bound, the region remains explicitly incomplete/degraded or uses a stronger future provider-specific source; the platform must not claim final completeness.
21. **Retention loss becomes a visible gap.** If provider retention can no longer prove/recover a required interval, History records an explicit gap/incomplete state instead of fabricating samples or marking the interval complete.
22. **Checkpoint advancement is crash-safe.** Durable observations and safe checkpoint advancement must be ordered/atomic or otherwise recoverably journaled so a crash cannot advance the checkpoint past observations that were never durably projected.
23. **Replay is idempotent.** Recovery/reconciliation may replay windows and accepted obligations arbitrarily; canonical observation identity suppresses duplicates without suppressing equal provider-local IDs from different authoritative scopes.
24. **Bounded historical reads are authorized.** Backend history query contracts may read by canonical tenant/resource/metric identity over explicit bounded time ranges with deterministic pagination. Unbounded full-retention scans are not authorized by this slice.
25. **Physical storage remains behind the telemetry port.** This authorization fixes canonical history semantics and persistence obligations, not an irreversible production storage vendor. PostgreSQL may serve bounded implementation/conformance where repository contracts permit, but production specialization/capacity remains evidence-driven.
26. **No general broker requirement for raw history.** High-volume `metric_observation` rows are not forced through the general integration-event broker merely because they are historical telemetry.
27. **Tenant isolation is mandatory.** Historical persistence, checkpoint state and reads remain tenant-bound and cannot use provider-local IDs as cross-tenant keys.
28. **Recovery/relocation remains generation-aware.** Replay after relocation/PITR/failover preserves canonical observation scope, source generation and accepted safe checkpoint/floor; stale placement cannot manufacture newer history authority.
29. **No frontend implication.** Backend/domain/data support for historical metrics creates no frontend route/navigation authority.

## Checkpoint and completeness semantics

For each logical history stream, the implementation maintains distinct concepts:

```text
provisional_high_water_mark
  optimization for fast incremental polling

safe_checkpoint / safe_floor
  highest boundary proven durable without skipping still-discoverable rows

reconciliation_coverage
  bounded windows already swept under current provider retention/lateness evidence

finalized_through
  optional; exists only when provider lateness/retention contract proves finality

gap/degraded evidence
  explicit inability to prove or recover required coverage
```

Rules:

- `clock/ns` is provider event-time identity/evidence, not a provider append offset;
- physical requests may batch item IDs, but checkpoint ownership remains per logical item/value-type stream;
- every request window is bounded and deterministic;
- overlap windows are inclusive and safe under exact observation deduplication;
- truncation, timeout, unknown coverage or provider visibility uncertainty blocks unsafe checkpoint advancement;
- background sweep and fast-path overlap are complementary, not substitutes;
- numeric overlap, sweep cadence, row/body/window limits and finalization horizon remain evidence-driven OPEN numerics; implementation may enforce hard safety ceilings without claiming production sizing authority.

## Durable projection semantics

A history projector consumes the canonical durable acceptance boundary:

```text
accepted observation
  -> validate exact owner/provenance tuple
  -> idempotent metric_observation projection
  -> mark/reconcile history projection obligation
  -> advance only the independently proven history checkpoint/coverage state
```

A crash may leave `pending` projection lag, but it must not produce either of these impossible states:

- checkpoint says the observation/window is durably complete while required observation projection is missing;
- obligation says `projected` while the canonical historical observation is absent or owner/provenance-incompatible.

History projection of a sample that was already accepted by Current does not create a Current transition. History ingestion of a late/backfill sample does not acquire Current authority.

## Explicitly outside this slice

This authorization does not permit:

- deriving or mutating `metric_current_state` from `history.get`;
- treating provider timestamps as Current ordering authority;
- using `item.get` latest values as proof of historical completeness;
- strict `clock + 1` continuation as the sole History cursor;
- one-pass/high-water-mark-only completeness;
- checkpoint advancement after truncated/uncertain pages;
- global checkpoint shared across independent item/value-type streams;
- declaring final completeness without provider lateness/retention evidence;
- fabricating observations for missing history;
- hiding provider-retention gaps;
- rewriting immutable accepted historical observations in place;
- collapsing observation identity across tenant/source/generation boundaries;
- raw-provider payload replication as canonical history;
- unbounded history API scans;
- irreversible production telemetry-store selection without benchmark/capacity evidence;
- Problems/Triggers/Events ingestion;
- Health projection;
- Alerting/ITSM/AIOps behavior;
- provider write-back;
- frontend route/navigation creation;
- production deployment.

## Acceptance boundary

This authorization becomes implementation authority only after its exact HEAD passes deterministic validation and panoramic/adversarial review and is separately squash-merged into `main`. Until then, implementation of Metric History remains blocked.
