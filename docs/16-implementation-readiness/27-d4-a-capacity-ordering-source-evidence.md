# D4-A — Live Kafka Capacity + Ordering Source Evidence

**Status:** source-evidence package only — no ledger credit, no Kafka selection, no D4/Wave 4/Product/production/C3 authority granted  
**Canonical base:** `main@32a35e9d9d695e9a37ed4ea3499b5598b0005a1e`  
**Track:** D4-A — broker transport, physical routing and anti-corruption boundary

## Purpose

This package implements the next preferred D4-A source-evidence block after the governed ledger reached 4/7. It generates live-candidate evidence for exactly two still-open obligations:

- `capacity_envelope_baseline_growth_stress`;
- `ordering_scope_partition_mapping_ceiling_tenant_cohort_fallback_and_key_level_concurrency`.

The package intentionally leaves `broker_outbox_dispatch_priority_preserving_backlog_drain_recovery_benchmark` for the later failure/recovery source package. A successful source run does not edit the D4-A ledger.

```text
LIVE KAFKA RUN != KAFKA SELECTION
TEST NUMERICS != C3 PRODUCTION NUMERICS
GREEN SOURCE RUN != LEDGER CREDIT
PARTITION TEST CEILING != PRODUCTION PARTITION COUNT
BACKLOG DRAIN UNDER LOAD != BROKER OUTAGE/RECOVERY PROOF
```

## Candidate runtime

The source package uses Kafka 4.3.1 through an immutable multi-architecture image reference pinned to index digest `sha256:77e3df9054047a88b520d0cc46e16696d3b22022e1d580aeccd2632df6532837`. The Linux/amd64 child manifest is independently pinned to `sha256:ccd1314e47ec76909e01f86308b4dcf2064f19f7c89759234322314b0e319e26`.

The workflow pulls the digest-qualified image and mechanically verifies that the index contains exactly the expected Linux/amd64 manifest before starting the broker. Both digests are persisted in immutable source-run provenance. These pins authorize only this bounded C2 candidate test; they do not select Kafka or create a production image/version authority.

This package treats Kafka only as the current leading candidate. Passing this benchmark does not select Kafka because one D4-A source obligation remains open and separate ledger promotion/acceptance gates still apply.

## Capacity evidence

`benchmark-profile.json` defines three bounded test tiers:

- **Baseline**;
- **Growth**;
- **Stress**.

For each tier the live-broker harness records:

- producer messages/second;
- average producer latency;
- maximum producer latency;
- bounded backlog before drain;
- backlog drain duration;
- recovery/drain messages/second;
- topic creation elapsed time across a bounded partition-count probe set;
- explicit per-tenant/event-rate skew exercised through keyed Kafka records.

The Stress tier is deliberately run with a longer consumer pause so backlog degradation is observed rather than reporting only a happy-path throughput number. Recovery here means bounded backlog drain while the broker remains available; it is **not** the later outage/restart/ack-ambiguity proof owned by D4-A7.

All counts, rates, record sizes, pauses and partition values are marked `test_values_only_not_production`. They do not grant retention, lag, partition, replica, topology, capacity or scaling authority.

## Ordering-scope coverage

The benchmark profile enumerates every ordering class accepted by Phase 10:

- `unordered`;
- `causal_only`;
- `per_subject_ordered`;
- `per_process_ordered`;
- `per_source_ordered`;
- `custom_bounded_order`.

Each class has an explicit mapping from trusted logical identity to partition-key strategy. Broker partition IDs remain physical implementation details rather than canonical ordering identity.

## Named consumer-side concurrency component

The source package names and implements **JLMIRROR KeySerialExecutor** at `tools/assurance/d4a_capacity_ordering/key_serial_executor.py`, following the consumer-side key-level virtual sequencing / bounded per-key concurrency pattern required by the Kafka candidate decision record. The live Kafka probe consumes records carrying several independent trusted logical keys and passes every record through this same component.

The evidence fails unless:

- same-key sequence is preserved;
- independent keys overlap in processing time;
- serialization is not global or tenant-wide.

This is deliberately a platform-owned logical component rather than reliance on Kafka partition-wide head-of-line blocking.

## Partition ceiling and tenant-cohort fallback

Every bounded tier probes multiple partition counts against a real broker and records elapsed topic-creation evidence. The highest successful count in that tier is persisted only as a **bounded test partition ceiling**.

The harness separately exercises tenant-cohort sharding using a stable hash of trusted tenant identity across two test cohorts. The physical cohort changes transport placement only; logical contract identity remains unchanged.

This fallback is evidence that physical sharding can be introduced when modeled ordering-scope cardinality exceeds a bounded test ceiling without converting tenant cohort/topic identity into consumer semantics.

## Machine-owned package

Manifest:

`implementation/d4-eventing-async/source-evidence/capacity-ordering/source-evidence-manifest.json`

Benchmark profile:

`implementation/d4-eventing-async/source-evidence/capacity-ordering/benchmark-profile.json`

Assurance tooling:

- `tools/assurance/d4a_capacity_ordering/key_serial_executor.py`;
- `tools/assurance/d4a_capacity_ordering/run_live_kafka_benchmark.py`;
- `tools/assurance/d4a_capacity_ordering/validate_source_evidence.py`;
- `tools/assurance/d4a_capacity_ordering/emit_source_provenance.py`.

CI workflow:

`.github/workflows/d4-a-capacity-ordering-source-evidence.yml`

The artifact contains both `benchmark-results.json` and immutable source-run provenance with exact HEAD SHA, run/attempt, job ID/name, Kafka version, immutable index digest, Linux/amd64 manifest digest, and SHA-256 digests for source manifest, benchmark profile and benchmark results.

## Source/ledger separation

This PR preserves:

- `current_run_auto_credit=false`;
- `ledger_credit=[]`;
- D4-A global ledger at exactly 4/7;
- both new evidence IDs still in `evidence_remaining`;
- Kafka `not_selected`;
- D4 `scoped`;
- transport/Product/Wave 4/production/C3 authority unchanged.

A later promotion PR may credit these IDs only after the exact source HEAD/run/job/artifact is reviewed.

## Non-claims

This package does not claim:

- production performance or SLO numerics;
- production partition/topic/cluster topology;
- production Kafka image/version selection;
- Kafka selection/acceptance;
- broker outage/restart recovery;
- outbox survival across broker outage;
- ack-ambiguity recovery;
- final D4-A acceptance;
- D4 transport, Product, Wave 4, production or C3 authority.

## Exit gate

This source PR is eligible for final review only when the exact HEAD proves:

- real Kafka candidate execution from the exact index-pinned image and exact Linux/amd64 child manifest;
- all Baseline/Growth/Stress tiers executed;
- tenant skew exercised;
- throughput/latency/backlog/drain measurements persisted;
- bounded degradation/recovery observed in every tier;
- all six ordering classes mapped;
- the canonical `JLMIRROR KeySerialExecutor` preserves same-key order while independent keys overlap;
- bounded partition probes executed per tier;
- tenant-cohort fallback exercised without semantic identity change;
- Phase 10 and D4 validators remain green;
- D4-A remains 4/7 and this run grants zero ledger credit;
- Kafka remains not selected and all authorities remain ungranted/unselected.
