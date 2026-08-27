# OPEN-REL-030 Decision Record — Customer-Monitoring Durable Acceptance/Projection Mechanism

**Status:** proposed — mechanism selected; conformance evidence NOT YET EXECUTED (see "Evidence and validation required")
**Decision class:** C2 (`docs/16-implementation-readiness/03-consolidated-open-decision-register.md:102`) — "customer-monitoring durable acceptance/projection mechanism; specifically blocks `impl.customer-telemetry@1` until selected and conformed"
**Drivers:** `FR-MON-001..006`, `INV-ASYNC-001`, `rel.customer-telemetry-acceptance@1` (`docs/11-reliability-resilience/07-capability-resilience-profiles.md:31,252,359`)

This document follows the decision-quality checklist from `docs/00-foundation/decision-policy.md`. It is **not** a new ADR: it selects a physical mechanism inside architecture already accepted by ADR-008 (transactional outbox) and `docs/08-data/telemetry-plane.md` (durable-acceptance contract), which explicitly left the physical mechanism `OPEN` pending exactly this kind of decision — it does not redefine either.

## Context and problem

`docs/16-implementation-readiness/03-consolidated-open-decision-register.md`'s closure evidence rule states: "A C2 selection produces a bounded decision/spike record and conformance evidence before becoming canonical." This record supplies the selection and rationale half of that requirement. It does **not** by itself satisfy the rule — the conformance evidence (`FV-TEL-002`, covering crash, backlog, replay and relocation, per `docs/11-reliability-resilience/12-phase-11-open-decisions-and-blockers.md:56`) requires an explicitly governed bounded spike that has not yet been executed. Until that spike runs and its evidence is accepted, `impl.customer-telemetry@1` remains `bounded_evidence_spike_eligible`, not `eligible_for_implementation_authorization` (`docs/16-implementation-readiness/15-implementation-slice-readiness-manifest.md:36`).

`docs/08-data/telemetry-plane.md:86-90` defines the durable-acceptance contract generically and names three architecturally acceptable mechanism families without selecting one:

1. a durable telemetry ingress journal/log/stream with replay/checkpoints;
2. a transactional persistence record plus outbox when PostgreSQL is the accepted ingestion authority;
3. a specialized telemetry store, only if it can provide the same replay/checkpoint/reconciliation guarantees.

The same document separates two distinct concerns that a single mechanism choice must not conflate: the **durable acceptance boundary** (correctness-critical, per-observation, must be atomic and idempotent) and the **historical/current-state projection** (volume-critical, must support bounded time-range query, compression, retention/rollup, tenant isolation). Treating these as one undifferentiated storage decision is what this record explicitly avoids.

## Relevant requirements and quality attributes

- `FR-MON-001` — "The platform SHALL ingest monitoring data from one or more Monitoring Sources through provider adapters" (`docs/02-requirements/functional-requirements.md:41`) — the mechanism selected here is what makes ingestion durable.
- `FR-MON-003` — "The platform SHALL maintain efficient current-state views separately from high-volume historical telemetry where required for performance and scale" (`docs/02-requirements/functional-requirements.md:45`) — directly motivates this record's two-tier separation.
- `INV-ASYNC-001` (`docs/02-requirements/invariants.md:39`) — the async-correctness invariant ADR-008's atomic-claim/outbox pattern exists to satisfy; Tier 1 inherits it unchanged.
- `rel.customer-telemetry-acceptance@1` (`docs/11-reliability-resilience/07-capability-resilience-profiles.md:31,252,359`) — the accepted resilience profile whose fault-vector (`FV-TEL-002`) and OPEN set (including this decision) this record must satisfy.
- Quality attributes at stake: correctness/atomicity (Tier 1, non-negotiable — see "Alternatives considered" rejection of any mechanism that weakens it) and scale/query-performance/retention (Tier 2 — bounded time-range query, compression, tenant isolation, per `telemetry-plane.md:153-161`).

## Alternatives considered

**Alternative 1 — single specialized telemetry/time-series store for both acceptance and projection** (e.g. a dedicated ingestion pipeline in front of InfluxDB/Kafka+ksqlDB or similar). Rejected as the *sole* mechanism: `telemetry-plane.md:90` permits this only "if it can provide the replay/checkpoint/reconciliation guarantees required to repair downstream projections" — most time-series-optimized stores trade strict cross-record transactional atomicity for write throughput, which makes proving ADR-008's atomic accept-and-signal invariant (§"State-transition signal atomicity") harder to demonstrate than reusing a mechanism that already proves it. It would also introduce a new, unproven-in-this-codebase distributed system as day-one load-bearing infrastructure, which is exactly the premature-technology risk `docs/00-foundation/decision-policy.md`'s "Technology discipline" section warns against ("a technology is accepted only after the capability it serves is defined").

**Alternative 2 — durable telemetry ingress journal/log/stream** (e.g. Kafka/Kinesis-style log as the acceptance boundary itself). Rejected for the same reason as Alternative 1 for the acceptance boundary specifically: it requires `broker_or_job_transport` (Wave 2 residual C2, still unselected, `implementation/wave-2/IMPLEMENTATION_MANIFEST.json:33-42`) to already be chosen and would make Monitoring's first slice depend on resolving that vendor choice too, compounding two unresolved C2 decisions into one.

**Alternative 3 (chosen) — two-tier: PostgreSQL transactional acceptance (ADR-008 pattern) plus a PostgreSQL-native time-series extension for projection.**

## Chosen option

### Tier 1 — durable acceptance boundary: ADR-008's outbox/atomic-claim pattern, unchanged

The acceptance boundary reuses the exact mechanism ADR-008 already accepts and Wave 2 already schema-accepted at the SQL level (`sql/wave2/001_async_correctness.sql` and successors — primary-key/uniqueness constraints for the inbox/outbox identity pattern this tier depends on). No new mechanism is introduced for this tier. This reuse is **honest about what is and is not yet proven**: Wave 2's own `src/jlmirror_async/inbox.py`/`outbox.py` reference implementations (`InMemoryInboxLedger`, `InMemoryOutboxLedger`) are explicitly documented in that code as reference/falsification-oracle models, not production durability claims (`src/jlmirror_async/outbox.py:103-105`: "This is a falsification oracle, not a production durability claim. Production code must bind domain mutation, audit intent and outbox append in one accepted PostgreSQL transaction and use a reviewed durable claim implementation"), and `implementation/wave-2/KNOWN_DEFERRED_ITEMS.md:8-25` records outright that atomicity against a real multi-connection PostgreSQL deployment "is not demonstrated in this codebase." What is accepted and reusable today is the **schema and pattern** (unique constraints, transactional outbox shape, compare-and-set current-state advancement); what is *not* yet proven is that pattern's behavior under real concurrent PostgreSQL connections. Closing that gap is folded into this record's own required bounded spike below, rather than assumed already closed:

```text
BEGIN
  observation = atomic create-or-observe on (observation_identity_scope, observation_id)
  if newly accepted:
      persist canonical observation record
      append outbox intent for Tier 2 historical projection                  -- exactly once per logical
                                                                               -- accepted observation;
                                                                               -- independent of "latest"

  if this arrival is an owner-contract current-state candidate:
      validate current provider/source authority and accepted projection ordering token
      conditional compare-and-set current-state projection by ordering token  -- MAY execute even when
                                                                               -- observation already existed
      if advanced:
          persist stable transition identity
          append outbox intent for current-state-changed downstream signal
COMMIT
```

Two separations are deliberate and correctness-critical:

1. **Historical projection is coupled to first durable acceptance, not to current-state advancement.** Every newly accepted canonical observation gets its Tier 2 historical-projection intent even if it is stale/non-latest for current-state purposes.
2. **Current-state candidacy is not coupled to first acceptance.** The same canonical observation may have been accepted earlier through a historical/backfill path and only later be encountered through a provider-authoritative current-snapshot path, or may need its current projection re-attempted during replay/reconciliation. In those cases the create-or-observe result is "already exists," but the current-state CAS is still eligible under the owner contract's current authority + ordering token. Re-running that CAS is idempotent: an equal/older token does not advance, while a genuinely newer authorized token may advance and atomically creates its transition/signal obligation.

A provider timestamp/event-time value is **not automatically a current-state ordering token**. The owner/provider contract must supply an ordering authority that satisfies `telemetry-plane.md`'s monotonic-projection rule; that document explicitly says `observed_at` alone is insufficient because provider clocks can skew or move backwards. For the initial Zabbix profile, `docs/09-api-contracts/zabbix-monitoring-source-provider-contract.md` therefore uses a platform-owned fenced poll generation for current/latest snapshots, while `clock`/`ns` remain historical/freshness metadata. Historical `history.get` observations do not acquire current-state authority merely by having a larger event timestamp.

This directly satisfies `telemetry-plane.md:86-90`'s second option ("a transactional persistence record plus outbox when PostgreSQL is the accepted ingestion authority") and ADR-008's "State-transition signal atomicity" section without requiring a new *pattern* — the schema shape and the atomicity argument's structure already exist and were already adversarially reviewed for the structurally identical Wave 2 cross-authority operation/reconciliation pattern this reuses. What still requires new evidence, specific to this tier's real-database behavior, is listed in full under "Evidence and validation required" below.

### Tier 2 — historical telemetry projection: TimescaleDB (PostgreSQL extension)

Current-state remains Tier 1's responsibility (the compare-and-set projection inside the same accepted transaction boundary when a current-state candidate is evaluated, above) — Tier 2 covers only the high-volume historical side, matching `telemetry-plane.md`'s own separation of "Transactional current state in the cell" from "Historical telemetry through the telemetry port."

For the high-volume historical telemetry side (`metric_observation` history, per `telemetry-plane.md`'s "Historical telemetry through the telemetry port" section), the selected mechanism is **TimescaleDB**, a PostgreSQL extension providing hypertables (automatic time-partitioning), native compression, continuous aggregates (for rollups), and retention policies.

Rationale for TimescaleDB specifically over a non-Postgres specialized store:

- it satisfies every requirement `telemetry-plane.md:153-161` lists for the physical implementation (retention by data class/policy; compression/rollup; bounded time-range query; tenant isolation; export/recovery semantics; ingest/query observability; no per-tenant physical table requirement) natively, without hand-rolled partitioning logic;
- it speaks the PostgreSQL wire protocol and transaction model — the durable-acceptance write (Tier 1) and the historical projection write can share the same logical database technology and, where capacity permits, the same physical cluster, avoiding a second connection pool, a second backup/recovery story, and a second operational surface for on-call staff to learn;
- it is a mature, widely production-proven extension for exactly this workload shape (multi-tenant time-series telemetry), reducing the "unproven new distributed system" risk named in Alternative 1's rejection while still delivering genuine purpose-built time-series performance rather than settling for un-partitioned relational tables;
- `docs/08-data/recovery-retention-and-artifacts.md`'s accepted `(R,F]` recovery/reconciliation model, already implemented for Wave 2's transactional store, extends to a same-technology hypertable without a second, separately-designed recovery model.

TimescaleDB is a **C2 implementation choice**, not an architectural commitment: `telemetry-plane.md:151` explicitly keeps "the physical telemetry implementation... open until benchmark evidence," and this record does not close that door — if benchmark evidence from the bounded spike (see below) shows TimescaleDB cannot meet a specific bounded time-range query or ingest-rate requirement at accepted scale, this decision is revisited under this same record's "Conditions that would justify revisiting" section, not by amending ADR-008 or `telemetry-plane.md`.

## Consequences

### Positive

- reuses an already-accepted, already-adversarially-reviewed correctness *pattern and schema shape* for the highest-risk part (durable acceptance) instead of designing or reviewing a new one — only concurrent-PostgreSQL behavioral evidence remains outstanding, not a new architectural argument;
- historical acceptance and current-state candidacy are independent, so backfill/replay order cannot silently decide which observation is allowed to repair/advance current state;
- no new distributed system enters the platform's day-one operational surface;
- one database technology family (PostgreSQL + TimescaleDB) serves both current-state (Tier 1) and historical telemetry (Tier 2), simplifying backup/recovery/on-call;
- compression and continuous aggregates directly address the long-retention/rollup requirement `telemetry-plane.md:177-187` anticipates, without deferring that problem to a later rearchitecture;
- `broker_or_job_transport` (Wave 2 residual C2) is **not** a prerequisite for this decision — Tier 1's outbox *records* the intent to dispatch; the dispatch transport itself remains separately selectable without blocking durable acceptance correctness.

### Negative / cost

- TimescaleDB is an additional PostgreSQL extension to install/operate/upgrade, even though it is not a new database engine;
- current-state candidate evaluation needs an explicit owner/provider ordering authority in addition to canonical observation identity; event-time metadata cannot be promoted to that authority by convenience;
- hypertable chunk-interval, compression policy, and continuous-aggregate refresh cadence are new tuning surfaces requiring their own capacity evidence before production (`OPEN-REL-020`'s numeric envelopes, `docs/16-implementation-readiness/03-consolidated-open-decision-register.md:91`, remain separately open);
- at very large multi-tenant scale, a single shared PostgreSQL/TimescaleDB cluster may eventually require read-replica or sharding strategy work that a purpose-built distributed time-series store would have provided natively — accepted as a deferred, evidence-gated concern per the "Exit / revisit conditions" below, not a day-one requirement.

### Operational cost

New extension to install and monitor; new backup verification path (TimescaleDB chunks must be included in the accepted PITR/backup evidence, not merely the non-hypertable tables); no new credential/secret surface beyond the existing PostgreSQL access already governed by Wave 1/2.

### Security and tenant-isolation implications

Tenant isolation follows the same RLS/tenant-scoping model already accepted for the transactional store (`docs/08-data/tenant-isolation-and-rls.md`) — TimescaleDB hypertables are ordinary PostgreSQL tables from RLS's perspective and inherit the same policy mechanism without a new isolation model to design or review.

### Migration and rollback implications

Because Tier 1 (the correctness-critical acceptance boundary) is unchanged from the already-accepted ADR-008 pattern, rolling back Tier 2 alone (replacing TimescaleDB with a different projection store) would not require re-litigating acceptance correctness — only re-pointing the idempotent projection consumer at a different downstream store, which `telemetry-plane.md`'s own separation of acceptance from projection already anticipates as a safe seam.

## Evidence and validation required

Per the register's closure evidence rule, this record alone does not make the decision canonical. The following remain outstanding and SHALL be produced by an explicitly governed bounded spike (matching the `bounded_evidence_spike_eligible` state already assigned to `impl.customer-telemetry@1`) before this decision closes:

- `FV-TEL-002` conformance: crash injection around the Tier 1 atomic create-or-observe / historical-intent / current-state-CAS / transition-signal transaction, against a real concurrent PostgreSQL backend rather than the in-memory reference-model ledgers Wave 2's own tests currently exercise (per `implementation/wave-2/KNOWN_DEFERRED_ITEMS.md:8-25`) — mirroring the exact fault-injection discipline ADR-008 §"Validation" already requires, but proving it newly against real concurrent connections rather than assuming Wave 2's existing tests already cover it;
- backlog behavior: durable acceptance continuing to accept within bounded storage budget while a downstream TimescaleDB projection is temporarily unavailable, per `telemetry-plane.md`'s "Unavailability/backpressure" section;
- replay: out-of-order and duplicate observation delivery proven not to regress current-state projections or duplicate historical rows, per `telemetry-plane.md`'s "Identity validation" testing requirement;
- already-accepted/current-candidate independence: an observation first accepted through historical/backfill ingestion and later encountered as an authoritative current-state candidate can still attempt/advance the current projection under its valid ordering authority, without emitting a second historical-projection intent;
- event-time non-authority: a provider clock rollback or a numerically larger stale/backfill event timestamp cannot by itself advance/freeze current state when the owner/provider current-ordering authority says otherwise;
- unconditional historical dispatch: an accepted observation that does **not** advance current state (stale/non-latest at acceptance time) still reaches Tier 2 historical storage — proving the historical-projection outbox intent is genuinely unconditional on advancement, not accidentally coupled to the current-state-changed signal;
- relocation: tenant relocation continuity for both the Tier 1 acceptance record and Tier 2 hypertable data, per `telemetry-plane.md`'s "Tenant relocation" section and the accepted `(R,F]` recovery model;
- a first capacity benchmark proving TimescaleDB compression/continuous-aggregate behavior meets the bounded time-range query requirement at a representative multi-tenant sample scale (informs, but does not block, the separately-open `OPEN-REL-020` production numerics).

This spike is scoped, bounded, explicitly governed evidence generation — it does not constitute or imply authorization for `impl.customer-telemetry@1`'s full implementation, per `docs/16-implementation-readiness/01-implementation-readiness-overview.md:48`'s definition of `bounded_evidence_spike_eligible`.

## Conditions that would justify revisiting

- benchmark evidence from the spike above shows TimescaleDB cannot meet bounded time-range query or ingest-rate requirements at accepted production scale;
- `broker_or_job_transport` selection (Wave 2 residual C2) turns out to materially change the shape of Tier 1's outbox dispatch in a way that makes a unified journal/stream mechanism (Alternative 2) clearly preferable instead;
- production multi-tenant scale requires a sharding/read-replica strategy that TimescaleDB cannot provide natively, at which point Alternative 1 (specialized distributed store) is reconsidered specifically for Tier 2 while Tier 1 remains unchanged.