# OPEN-REL-030 Decision Record — Customer-Monitoring Durable Acceptance/Projection Mechanism

**Status:** proposed — Tier 1 mechanism selected; Tier 2 TimescaleDB is a leading candidate pending mandatory tenant-isolation/capacity conformance; C2 closure NOT YET ACHIEVED
**Decision class:** C2 (`docs/16-implementation-readiness/03-consolidated-open-decision-register.md:102`) — "customer-monitoring durable acceptance/projection mechanism; specifically blocks `impl.customer-telemetry@1` until selected and conformed"
**Drivers:** `FR-MON-001..006`, `INV-ASYNC-001`, `rel.customer-telemetry-acceptance@1` (`docs/11-reliability-resilience/07-capability-resilience-profiles.md:31,252,359`)

This document follows the decision-quality checklist from `docs/00-foundation/decision-policy.md`. It is **not** a new ADR: it evaluates/selects physical mechanisms inside architecture already accepted by ADR-008 (transactional outbox) and `docs/08-data/telemetry-plane.md` (durable-acceptance contract), which explicitly left the physical mechanism `OPEN` pending exactly this kind of decision — it does not redefine either.

## Context and problem

`docs/16-implementation-readiness/03-consolidated-open-decision-register.md`'s closure evidence rule states: "A C2 selection produces a bounded decision/spike record and conformance evidence before becoming canonical." This record supplies the Tier 1 selection/rationale and identifies the leading Tier 2 candidate. It does **not** by itself satisfy the rule — the conformance evidence (`FV-TEL-002`, covering crash, backlog, replay and relocation, per `docs/11-reliability-resilience/12-phase-11-open-decisions-and-blockers.md:56`) plus the Tier 2 tenant-isolation/capacity evidence below requires an explicitly governed bounded spike that has not yet been executed. Until that spike runs and its evidence is accepted, `impl.customer-telemetry@1` remains `bounded_evidence_spike_eligible`, not `eligible_for_implementation_authorization` (`docs/16-implementation-readiness/15-implementation-slice-readiness-manifest.md:36`).

`docs/08-data/telemetry-plane.md:86-90` defines the durable-acceptance contract generically and names three architecturally acceptable mechanism families without selecting one:

1. a durable telemetry ingress journal/log/stream with replay/checkpoints;
2. a transactional persistence record plus outbox when PostgreSQL is the accepted ingestion authority;
3. a specialized telemetry store, only if it can provide the same replay/checkpoint/reconciliation guarantees.

The same document separates two distinct concerns that a single mechanism choice must not conflate: the **durable acceptance boundary** (correctness-critical, per-observation, must be atomic and idempotent) and the **historical/current-state projection** (volume-critical, must support bounded time-range query, compression, retention/rollup, tenant isolation). Treating these as one undifferentiated storage decision is what this record explicitly avoids.

## Relevant requirements and quality attributes

- `FR-MON-001` — "The platform SHALL ingest monitoring data from one or more Monitoring Sources through provider adapters" (`docs/02-requirements/functional-requirements.md:41`) — the mechanism selected here is what makes ingestion durable.
- `FR-MON-003` — "The platform SHALL maintain efficient current-state views separately from high-volume historical telemetry where required for performance and scale" (`docs/02-requirements/functional-requirements.md:45`) — directly motivates this record's two-tier separation.
- `INV-ASYNC-001` (`docs/02-requirements/invariants.md:39`) — the async-correctness invariant ADR-008's atomic-claim/outbox pattern exists to satisfy; Tier 1 inherits it unchanged.
- `docs/08-data/tenant-isolation-and-rls.md` — pooled protected tenant data uses defense in depth including trusted tenant binding, PostgreSQL RLS/data policy, role/function hardening and automated cross-tenant isolation tests; a single leaked row is a release blocker.
- `rel.customer-telemetry-acceptance@1` (`docs/11-reliability-resilience/07-capability-resilience-profiles.md:31,252,359`) — the accepted resilience profile whose fault-vector (`FV-TEL-002`) and OPEN set (including this decision) this record must satisfy.
- Quality attributes at stake: correctness/atomicity (Tier 1, non-negotiable), tenant isolation/security (non-negotiable on every pooled Tier 2 path), and scale/query-performance/retention (Tier 2 — bounded time-range query, compression, tenant isolation, per `telemetry-plane.md:153-161`).

## Alternatives considered

**Alternative 1 — single specialized telemetry/time-series store for both acceptance and projection** (e.g. a dedicated ingestion pipeline in front of a specialized distributed telemetry store or log-backed processor). Rejected as the *sole* mechanism for Tier 1: `telemetry-plane.md:90` permits a specialized acceptance store only if it can provide the replay/checkpoint/reconciliation guarantees required to repair downstream projections. Introducing a new distributed acceptance authority would require a fresh correctness proof rather than reusing ADR-008's transactional pattern.

**Alternative 2 — durable telemetry ingress journal/log/stream** (e.g. Kafka/Kinesis-style log as the acceptance boundary itself). Rejected for the acceptance boundary specifically at this stage: it requires `broker_or_job_transport` (Wave 2 residual C2, still unselected, `implementation/wave-2/IMPLEMENTATION_MANIFEST.json:33-42`) to already be chosen and would make Monitoring's first evidence slice depend on resolving that separate C2 choice too.

**Alternative 3 (Tier 1 selected; Tier 2 leading candidate) — two-tier: PostgreSQL transactional acceptance (ADR-008 pattern) plus TimescaleDB/PostgreSQL-extension historical projection if and only if its actual feature profile can preserve the accepted tenant-isolation contract.**

## Tier 1 selected mechanism — durable acceptance boundary: ADR-008 PostgreSQL pattern

The acceptance boundary reuses the exact mechanism ADR-008 already accepts and Wave 2 already schema-accepted at the SQL level (`sql/wave2/001_async_correctness.sql` and successors — primary-key/uniqueness constraints for the inbox/outbox identity pattern this tier depends on). No new mechanism is introduced for this tier. This reuse is **honest about what is and is not yet proven**: Wave 2's own `src/jlmirror_async/inbox.py`/`outbox.py` reference implementations (`InMemoryInboxLedger`, `InMemoryOutboxLedger`) are explicitly documented in that code as reference/falsification-oracle models, not production durability claims, and `implementation/wave-2/KNOWN_DEFERRED_ITEMS.md:8-25` records that atomicity against a real multi-connection PostgreSQL deployment is not yet demonstrated. What is accepted and reusable today is the **schema and pattern**; what remains to be proven is its real concurrent PostgreSQL behavior under the telemetry workload.

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
      if current projection already references the same canonical observation identity:
          no semantic current-state transition                               -- idempotent repeat/current snapshot
      else:
          conditional compare-and-set current-state projection by ordering token
          if advanced:
              persist stable transition identity
              append outbox intent for current-state-changed downstream signal
COMMIT
```

Three separations are deliberate and correctness-critical:

1. **Historical projection is coupled to first durable acceptance, not to current-state advancement.** Every newly accepted canonical observation gets its Tier 2 historical-projection intent even if it is stale/non-latest for current-state purposes.
2. **Current-state candidacy is not coupled to first acceptance.** The same canonical observation may have been accepted earlier through a historical/backfill path and only later be encountered through a provider-authoritative current-snapshot path, or may need its current projection re-attempted during replay/reconciliation. In those cases the create-or-observe result is "already exists," but the current-state CAS remains eligible under the owner contract's current authority + ordering token when the current projection does not already reference that observation.
3. **Ordering/fencing progress is not itself a semantic state change.** A later poll/worker generation proves which candidate is eligible to win; it does not manufacture a new current observation. Re-reading the same canonical observation identity is idempotent and does not emit another `current-state-changed` signal merely because the poll generation advanced. A genuinely different canonical current observation may advance even when its provider event timestamp moved backwards, provided the owner/provider ordering authority says the candidate is current.

A provider timestamp/event-time value is **not automatically a current-state ordering token**. The owner/provider contract must supply an ordering authority that satisfies `telemetry-plane.md`'s monotonic-projection rule; that document explicitly says `observed_at` alone is insufficient because provider clocks can skew or move backwards. For the initial Zabbix profile, `docs/09-api-contracts/zabbix-monitoring-source-provider-contract.md` uses a platform-owned fenced poll epoch/generation for current/latest snapshots, while `clock`/`ns` remain historical/freshness metadata. That poll epoch additionally inherits placement/recovery fencing so PITR/relocation cannot make a restored lower poll sequence authoritative.

This satisfies `telemetry-plane.md:86-90`'s second mechanism family ("a transactional persistence record plus outbox when PostgreSQL is the accepted ingestion authority") and ADR-008's "State-transition signal atomicity" structure without inventing a second correctness model. The real-database proof remains part of the bounded spike below.

## Tier 2 leading candidate — TimescaleDB, security conformance required before selection completes

Current-state remains Tier 1's responsibility. Tier 2 covers only the high-volume historical side, matching `telemetry-plane.md`'s separation of "Transactional current state in the cell" from "Historical telemetry through the telemetry port."

TimescaleDB remains the leading Tier 2 candidate because its hypertable/time-partitioning, columnar/compression, retention and continuous-aggregate capabilities directly target JLMIRROR's historical telemetry workload while remaining in the PostgreSQL ecosystem. That makes it attractive for operations, SQL/tool compatibility and migration from Tier 1.

**Those capabilities are not themselves proof that TimescaleDB satisfies JLMIRROR's pooled multi-tenant isolation contract.** In particular, the performance features that make TimescaleDB attractive must be evaluated in their actual supported combinations with PostgreSQL RLS/data policy, continuous aggregates/materialization, background refresh/compression jobs and application/read roles. JLMIRROR SHALL NOT infer that an RLS policy on an uncompressed/raw hypertable automatically protects every compressed/columnar chunk, continuous-aggregate relation, materialized backing object or privileged maintenance path produced by the selected Timescale feature profile.

Therefore TimescaleDB is **not yet a completed Tier 2 selection** under this C2 record. It becomes selected/canonical only if the bounded spike proves an accepted tenant-isolation profile **and** capacity/query fitness. If the features required to satisfy retention/compression/rollup cannot coexist with the accepted tenant-isolation contract, the TimescaleDB candidate fails and another Tier 2 mechanism is selected without weakening tenant isolation.

### Allowed isolation solution classes for the spike

The spike may falsify/compare implementation classes, but none is accepted merely because it works functionally:

- a Timescale profile in which every protected relation directly reachable by normal application/worker/read roles retains enforceable database-level tenant isolation under the actual storage/compression/aggregate features used;
- a mediated projection/query profile in which normal tenant-facing roles have **no direct privilege** on a shared relation that cannot enforce the accepted tenant boundary, and the mediation mechanism itself is reviewed against `tenant-isolation-and-rls.md` (including role escalation, `SECURITY DEFINER`, search-path and caller-controlled tenant-context attacks);
- stronger physical segmentation, such as telemetry separated by cell/isolation class, where that is required to preserve the accepted boundary;
- a different telemetry store/product whose native isolation and retention/rollup semantics satisfy the same logical contract.

An application `WHERE tenant_id = ...` convention by itself is not an accepted substitute for the repository's defense-in-depth tenant-isolation model. Nor may a privileged background job, continuous-aggregate owner, compression role, migration role or reporting role become an undocumented cross-tenant bypass.

## Consequences

### Positive

- Tier 1 reuses an already-accepted correctness pattern/schema shape instead of designing a new acceptance authority;
- historical acceptance and current-state candidacy are independent, so backfill/replay order cannot silently decide which observation is allowed to repair/advance current state;
- repeated observation of the already-current canonical observation is idempotent even when the poll/worker ordering generation advances;
- Tier 2 remains replaceable behind the telemetry projection seam;
- TimescaleDB can still win on its real strengths, but only after the exact security/performance profile is proven rather than assumed;
- `broker_or_job_transport` (Wave 2 residual C2) is **not** a prerequisite for Tier 1 durable acceptance — Tier 1's outbox records the dispatch obligation while transport remains separately selectable.

### Negative / cost

- Tier 1 still requires real concurrent PostgreSQL fault/concurrency proof;
- TimescaleDB adds an extension and operational/tuning surface if selected;
- current-state candidate evaluation needs both a stable canonical observation identity and an explicit owner/provider ordering authority; event-time metadata cannot be promoted to that authority by convenience;
- TimescaleDB's attractive compression/columnar/continuous-aggregate features cannot be assumed usable on pooled protected data until their isolation profile is proven, which may force a different query topology, physical segmentation or different store;
- hypertable/chunk, compression/columnstore, aggregate refresh and retention settings remain capacity evidence decisions before production (`OPEN-REL-020`);
- at very large multi-tenant scale, Tier 2 may still require read scaling/sharding/segmentation beyond one cluster.

### Operational cost

If TimescaleDB passes the spike, its extension lifecycle, background jobs, backup/PITR verification, storage/retention behavior and role model become production operational obligations. "Same PostgreSQL protocol" does not mean "same failure/security surface"; extension-specific objects/jobs are included in observability, backup/restore and permission review.

### Security and tenant-isolation implications

`docs/08-data/tenant-isolation-and-rls.md` remains authoritative. Pooled protected telemetry keeps non-null immutable `tenant_id`, trusted tenant context, least-privilege roles, database-level isolation appropriate to the query trust class, tenant-safe relationships/indexes where applicable, and automated cross-tenant tests. A single leaked row remains a release blocker.

The earlier assumption that TimescaleDB's entire Tier 2 feature set would simply "inherit the same RLS mechanism" is **rejected**. The spike must enumerate every database object and principal created/used by the chosen Timescale profile and prove that no normal tenant-facing/application/worker/reporting path can cross the tenant boundary, including after compression/columnar conversion, aggregate refresh, retention work, backup/restore and role changes. Where a selected Timescale feature cannot preserve that property on a pooled shared relation, that feature/profile is ineligible for that relation unless a separately reviewed stronger isolation/mediation design removes direct tenant-facing access to the unsafe surface.

### Migration and rollback implications

Tier 1 acceptance correctness remains independent of Tier 2. If TimescaleDB fails the spike, no canonical customer-telemetry implementation has yet been authorized, so Tier 2 can be replaced before load-bearing adoption. If a later accepted Tier 2 store is replaced, canonical observation identity, historical-projection idempotency, watermarks/reconciliation and tenant-isolation evidence must migrate intact.

## Evidence and validation required

Per the register's closure evidence rule, this record alone does not make the C2 decision canonical. The bounded spike SHALL produce at least:

- `FV-TEL-002` conformance: crash injection around the Tier 1 atomic create-or-observe / historical-intent / current-state-CAS / transition-signal transaction against a real concurrent PostgreSQL backend rather than only in-memory reference ledgers;
- backlog behavior: durable acceptance continuing within a bounded storage budget while the Tier 2 projector is unavailable, without acknowledging beyond durable responsibility;
- replay: out-of-order and duplicate observation delivery proven not to regress current-state projections or duplicate historical rows;
- already-accepted/current-candidate independence: an observation first accepted through historical/backfill ingestion and later encountered as an authoritative current-state candidate can still attempt/advance the current projection without emitting a second historical-projection intent;
- repeated-current idempotence: repeated authoritative snapshots that reference the same canonical observation identity do not create a second current-state transition/signal merely because the poll/worker ordering generation advanced;
- event-time non-authority: provider clock rollback or a numerically larger stale/backfill timestamp cannot by itself advance/freeze current state when the owner/provider ordering authority says otherwise;
- poll-authority recovery continuity for the initial Zabbix profile: restore/PITR/relocation cannot reuse a stale/lower poll sequence as current authority; existing epoch continuity is proven or a successor epoch is admitted only after stale-placement fencing and `(R,F]` reconciliation;
- unconditional historical dispatch: an accepted observation that does **not** advance current state still reaches Tier 2 historical storage;
- late-history reconciliation: delayed older provider history, including a delay beyond the ordinary overlap after a provider/proxy outage, is either recovered by bounded reconciliation or produces an explicit durable incomplete/gap state rather than a false complete watermark;
- relocation: tenant relocation continuity for Tier 1 acceptance/current-state evidence and the Tier 2 candidate data, preserving one authoritative acceptance path and reconciled projection watermarks;
- **Timescale tenant-isolation matrix:** known Tenant B identifiers/rows are attacked from Tenant A context across raw hypertables, every compression/columnar state actually used, continuous-aggregate/query surfaces, backing/materialization objects reachable by platform roles, reporting/read paths, projection workers, background refresh/compression/retention jobs, migration/DDL roles, backup/restore/recovery roles and any mediated functions/views; no normal tenant path may read/write cross-tenant data or assume an RLS-bypass owner/role;
- role/function hardening: attempts using `SET`, `set_config`, `SET ROLE`, session authorization, search-path manipulation, helper functions and `SECURITY DEFINER`/owner privilege paths are exercised wherever applicable to the chosen Tier 2 profile;
- backup/PITR test: restoring the Tier 2 candidate cannot reintroduce a broader role/policy/object state or expose a relation/materialization that bypasses the current tenant-isolation profile;
- capacity benchmark under the **same isolation profile that passed security testing**, proving representative multi-tenant ingest, bounded time-range queries, retention/compression/rollup behavior and background-job load. A benchmark obtained by disabling the required isolation controls is invalid evidence.

The spike is scoped, bounded, explicitly governed evidence generation — it does not constitute or imply authorization for `impl.customer-telemetry@1`'s full implementation. Tier 2 candidate code/data created during the spike cannot become canonical merely because it exists.

## Conditions that would justify revisiting / rejecting the Tier 2 candidate

- TimescaleDB cannot preserve the accepted pooled tenant-isolation contract while enabling the storage/query features required to meet the historical telemetry workload;
- the only way to meet the performance target requires ordinary application/reporting roles to reach a shared surface without an accepted database/physical isolation boundary;
- benchmark evidence shows the passing isolation profile cannot meet bounded time-range query or ingest requirements at representative scale;
- extension/background-job/backup/recovery behavior cannot satisfy the accepted recovery and least-privilege contracts;
- `broker_or_job_transport` selection materially changes Tier 1 dispatch in a way that makes a unified journal/stream acceptance mechanism clearly preferable under equivalent correctness evidence;
- production multi-tenant scale requires a sharding/segmentation strategy better served by another specialized Tier 2 store.
