# Phase 12 — Capacity, Cost and Observability Pipeline Resilience

**Status:** proposed baseline  
**Phase:** 12 — Observability & SRE

## Purpose

Observability consumes CPU, memory, network, storage, index/query capacity and operator attention. This document ensures the evidence plane cannot become an unbounded outage/cost amplifier while preserving evidence required by accepted authority.

## Resource dimensions

Capacity models SHALL include, as applicable:

```text
signals_per_second
bytes_per_second
log event bytes
trace spans per operation
metric series cardinality
metric samples per second
active tenants
active resources/providers/destinations
indexed high-cardinality fields
collector/exporter concurrency
buffer/backlog bytes and age
retry work
query concurrency/scan bytes
alert evaluation volume
alert notification fanout
retained raw/derived bytes
synthetic journey volume
cross-tenant/global diagnostic query cost
comparison-verification calls and latency
comparison-verification concurrency
comparison outcome signal volume
```

No single scalar “telemetry volume” is sufficient.

## Producer budgets

Producing capabilities SHALL have bounded emission behavior. An error loop SHALL NOT generate unbounded logs/traces faster than the system can contain them.

Profiles MAY use rate limiting, aggregation, deduplication, sampling or bounded diagnostic escalation when this does not violate mandatory evidence semantics.

Untrusted input SHALL NOT select a more expensive telemetry profile without bounded authorization/policy.

## Duplicate-sensitive comparison budgets

Duplicate-sensitive inbox/replay observability SHALL be budgeted together with the comparison work it observes so crafted candidates cannot create a hidden two-plane amplification path.

Required bounded dimensions include, as applicable:

- comparison attempts by owning reliability profile/workload class;
- comparison dependency latency and concurrency;
- temporary-unavailability/reconciliation-blocked outcome counts;
- historical-continuity-blocked outcome counts;
- compromised/untrusted outcome counts;
- quarantine/reconciliation backlog age/count;
- telemetry emitted per comparison attempt;
- diagnostic query/export work over those outcomes.

Message IDs, protected content, comparison-derived equality values and arbitrary source fields SHALL NOT become metric-series dimensions or attacker-selected cost buckets.

A duplicate/equality storm SHALL NOT be able to consume unrelated global comparison-service or observability capacity. Tenant, consumer contract, workload and privileged-recovery isolation apply as accepted upstream.

Exact numeric limits remain owned by accepted Phase 11 capacity OPENs plus `OPEN-OBS-008`, `OPEN-OBS-026` and applicable runtime evidence. Phase 12 does not invent their numbers.

## Cardinality budgets

Metric cardinality is governed by semantic label sets plus evidence-driven numeric budgets. New dimensions require cardinality/cost review.

When a bounded dimension exceeds its accepted domain, the pipeline uses an explicit overflow/rejection/aggregation behavior; it SHALL NOT silently create arbitrary new series.

High-cardinality diagnostic identities are primarily logs/traces and may be non-indexed/limited according to profile.

Comparison outcome metrics use fixed semantic classes and owning profile/workload classes, not per-message/per-content series.

## Buffering and backpressure

Operational observability buffers are bounded by bytes/items/age and workload isolation. When downstream is unavailable, each signal class defines an outcome such as:

```text
bounded_buffer_then_drop
sample_or_aggregate
local_spool_with_bound
reject_optional_diagnostic_enrichment
mark_evidence_unknown
```

Exact mechanism/numerics remain OPEN.

The chosen behavior SHALL NOT:

- block authoritative transactions indefinitely;
- create infinite retry;
- consume unbounded disk/memory;
- cause one tenant/provider to evict unrelated critical evidence without policy;
- weaken mandatory audit or customer-telemetry durable-acceptance contracts;
- turn dropped comparison telemetry into duplicate/replay/effect eligibility.

## Signal criticality

Operational signals SHOULD be classified by diagnostic importance, for example:

- **required_integrity_signal** — needed to detect observability blind spots/security/recovery state;
- **service_level_signal** — required by an accepted SLI/alert profile;
- **diagnostic_standard** — useful routine diagnosis;
- **diagnostic_verbose** — optional high-volume detail.

These are observability delivery priorities only, not business authority classes. Exact storage/sampling policy remains profile-driven.

Comparison continuity/trust outcome evidence needed to diagnose a blocked duplicate-sensitive path is an integrity/security diagnostic obligation, but telemetry delivery priority does not make it the authoritative comparison evidence.

## Pipeline failure behavior

The observability pipeline itself has Phase 11-style failure handling:

- `unavailable` — bounded buffering/degradation; evidence completeness may become unknown;
- `slow/timed_out` — producer/export deadlines bounded; no ordinary business timeout inherits from telemetry;
- `throttled/saturated` — shed/sample/aggregate according to signal criticality and tenant/workload budgets;
- `stale` — query/alert freshness exposed explicitly;
- `compromised_or_untrusted` — stop trusting affected evidence path; do not auto-heal through reachability alone;
- `recovery_blocked` — restored pipeline/query state cannot be treated current until applicable governance/security continuity is proven.

Exact mechanisms belong to Phase 13/implementation.

Observability-pipeline failure SHALL NOT be mapped back into a more permissive comparison/effect state. If comparison telemetry is unavailable, the owning Phase 10/11 authority still decides duplicate/effect/replay eligibility from its durable evidence.

## Self-observation without recursion

JLMIRROR SHALL be able to distinguish “no failures observed” from “observability path not working.”

Required properties:

- exporter/collector success/failure/drop/backlog evidence;
- last-known successful evidence age/freshness where useful;
- bounded source-side counters/health that do not require the same failed downstream query path to exist;
- explicit `unknown` when integrity cannot be proven.

The exact secondary/out-of-band mechanism is `OPEN-OBS-025`.

## Tenant/workload isolation

Budgets and failure containment consider tenant, capability, provider, destination, runtime/workload and signal class. One noisy tenant/provider/destination SHALL NOT consume all telemetry or alert capacity.

Global signals are protected from tenant-controlled cardinality amplification.

Duplicate-sensitive comparison workloads additionally isolate by consumer/replay workload scope required upstream; observability aggregation SHALL NOT collapse those scopes into an unsafe global equality surface.

## Query cost

Observability queries/exports SHALL have:

- bounded time range/default limits;
- result/byte limits;
- concurrency/resource budgets;
- tenant/current authorization scope;
- protection from pathological regex/query expressions or unrestricted scans where the selected backend exposes them;
- cancellation/deadline behavior that does not imply data absence.

Exact query language/backend controls remain OPEN.

Queries over duplicate-sensitive diagnostics SHALL operate on bounded outcome/profile/time dimensions and SHALL NOT expose unrestricted cross-scope equality search semantics.

## Alert cost/fanout

Alert evaluation and notifications are bounded by dedup/grouping, tenant/provider/workload isolation and actionability profiles. Suppression reduces notification fanout but does not delete underlying evidence/SLI accounting.

## Synthetic cost

Synthetic journeys are bounded workloads with explicit credentials/scope, frequency, target and cost budgets. They SHALL NOT create privileged side effects merely to test observability. Side-effecting synthetic flows require dedicated reversible/test identities and later Phase 13/15 authority.

## Cost attribution

Implementation SHALL expose enough evidence to attribute major observability cost drivers by safe bounded dimensions such as signal family, capability, environment class and workload cohort. Per-tenant attribution is used only when privacy/cardinality/cost evidence supports it.

Comparison-related cost attribution uses safe profile/workload classes; it does not expose protected comparison identities or source-derived equality values.

## Scaling/rearchitecture triggers

Exact thresholds are OPEN, but implementation evidence SHALL identify triggers such as:

- cardinality growth exceeding safe series/index envelope;
- ingestion backlog/drop increasing materially;
- query latency/scan cost preventing incident diagnosis;
- telemetry resource use affecting core workload isolation;
- one tenant/cohort dominating cost despite accepted isolation;
- retention growth exceeding cost/compliance assumptions;
- duplicate/equality storms causing comparison or telemetry amplification despite accepted isolation.

These triggers justify capacity action; they do not select a vendor automatically.

## Validation obligations

Load/fault testing SHALL exercise tenant skew, provider error storms, high-cardinality attacks, collector outage, slow backend, retry storm, storage pressure, expensive query/export and alert fanout while proving bounded resource use and preservation of critical evidence semantics.

Tests SHALL additionally exercise duplicate/equality storms and prove bounded comparison dependency work, bounded observability emission/cardinality, correct isolation and no transformation of telemetry loss/saturation into effect or replay eligibility.
