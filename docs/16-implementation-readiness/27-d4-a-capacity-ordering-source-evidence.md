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
QUOTA THROTTLING BOUNDARY != PRODUCTION CAPACITY LIMIT
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
- **broker-observed backlog from Kafka end offsets** before consumer drain;
- backlog drain duration;
- drain messages/second;
- per-tenant/event-rate skew exercised through real keyed Kafka records;
- a real producer-performance probe for every bounded partition count in the tier;
- the target messages/second for that same tier and the observed fraction of that target achieved by each probe;
- whether each partition probe satisfies the tier-specific target-relative throughput admission and maximum average-latency admission;
- the highest tested partition count satisfying that bounded admission.

The partition ceiling is therefore not inferred from successful topic creation or a fixed low throughput floor. Every partition-count probe executes the **full message count for its tier** and must sustain at least **70% of that same tier's configured target messages/second**, while also satisfying the bounded latency admission. The highest admitted tested count is source evidence for this ephemeral environment only; it is not an absolute Kafka limit and cannot become a production partition count.

### Real degradation/failure-boundary probe

Backlog existence alone is not treated as evidence of a degradation boundary. After the B/G/S runs, the harness executes a dedicated real Kafka throttling experiment using Kafka's client producer-byte-rate quota for a dedicated `client.id`.

The same stress-sized producer probe runs first without that quota and then with a bounded source-test quota. The evidence fails unless the throttled run exhibits at least the declared minimum throughput-drop fraction. The quota is removed immediately after the probe.

This deliberately creates a controlled, observable broker-side degradation mechanism instead of labeling an ordinary consumer pause as degradation. The quota byte-rate and observed threshold remain source-test values only and grant no production/C3 authority.

### Backlog drain scope

The B/G/S backlog drain proves only that a measured committed broker backlog can be consumed and its drain rate/duration observed while Kafka remains available. It does **not** claim:

- broker outage survival;
- broker restart recovery;
- outbox survival while Kafka is unavailable;
- acknowledgement ambiguity handling;
- priority-preserving recovery under simultaneous protected/current work.

Those remain exclusively D4-A7.

## Ordering-scope coverage

The benchmark profile enumerates every ordering class accepted by Phase 10:

- `unordered`;
- `causal_only`;
- `per_subject_ordered`;
- `per_process_ordered`;
- `per_source_ordered`;
- `custom_bounded_order`.

Each class has an explicit mapping from trusted logical identity to partition-key strategy. The source validator fails if a mapping uses physical `topic`, `partition`, `offset`, consumer-group or cell identity as the logical partition-key authority.

The live benchmark does not merely inspect these mappings. It runs a broker exercise for **all six profiles**. `unordered` and `causal_only` prove ordinary broker passage without claiming key serialization. Every ordered profile uses real keyed Kafka records and then passes the consumed work through the canonical named consumer-side component.

## Named consumer-side concurrency component

The source package names and implements **JLMIRROR KeySerialExecutor** at `tools/assurance/d4a_capacity_ordering/key_serial_executor.py`, following the consumer-side key-level virtual sequencing / bounded per-key concurrency pattern required by the Kafka candidate decision record.

For every ordered Phase 10 profile, the live source probe exercises the same implementation. The evidence fails unless:

- same-key sequence is preserved;
- independent keys overlap in processing time;
- serialization is not global or tenant-wide.

A deterministic negative-control suite additionally blocks a one-worker/global-serialization substitute. This is deliberately a platform-owned logical component rather than reliance on Kafka partition-wide head-of-line blocking.

## Partition ceiling and tenant-cohort fallback

Every bounded tier probes multiple partition counts against the real Kafka candidate and runs producer-performance work at each count. A probe is admitted only when it satisfies the **same tier's** bounded target-relative throughput and maximum average-latency conditions. The highest admitted tested count is persisted as the **bounded test partition ceiling** for that source environment.

The tenant-cohort fallback is not allowed to claim success from a fabricated `ceiling + 1` scalar. After the Stress tested ceiling is known, the harness creates **more distinct trusted logical scopes than that ceiling**, routes every one of those scopes through the stable tenant-to-cohort mapping, and sends the records through real Kafka cohort topics. The evidence fails unless the number of distinct scopes actually observed after round-trip remains greater than the single-topic test ceiling and at least two cohort topics are exercised.

Each cohort topic remains at or below the bounded single-topic test ceiling. The physical cohort changes transport placement only; logical contract identity remains unchanged, and tenant/cohort/topic identity does not become consumer semantic identity.

## Machine-owned package

Manifest:

`implementation/d4-eventing-async/source-evidence/capacity-ordering/source-evidence-manifest.json`

Benchmark profile:

`implementation/d4-eventing-async/source-evidence/capacity-ordering/benchmark-profile.json`

Assurance tooling:

- `tools/assurance/d4a_capacity_ordering/key_serial_executor.py`;
- `tools/assurance/d4a_capacity_ordering/test_key_serial_executor.py`;
- `tools/assurance/d4a_capacity_ordering/run_live_kafka_benchmark.py`;
- `tools/assurance/d4a_capacity_ordering/validate_source_evidence.py`;
- `tools/assurance/d4a_capacity_ordering/test_validate_source_evidence.py`;
- `tools/assurance/d4a_capacity_ordering/emit_source_provenance.py`.

The source-validator negative controls fail on mutable Kafka pins, physical ordering-key leakage, missing ordering-profile coverage, global serialization, synthetic degradation substitution, weakened/non-tier-relative partition admission, partition-ceiling policy detached from the same-tier target, fake model-only fallback triggers, fallback that does not route an actual over-ceiling workload, semantic identity changes in fallback, source auto-credit, an unauthorized fifth global credit, and D4-A7 recovery overclaim.

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
- an absolute Kafka partition ceiling;
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
- throughput/latency and broker-observed backlog/drain measurements persisted;
- a real Kafka quota produces the declared bounded degradation boundary;
- every partition producer-performance probe is tied to the same tier's target and admitted only after satisfying the pinned 70% target fraction plus latency bound;
- the tested partition ceiling per tier is derived only from admitted real-load probes;
- all six ordering classes are individually exercised through Kafka;
- every ordered profile uses the canonical `JLMIRROR KeySerialExecutor`, preserving same-key order while independent keys overlap;
- source negative controls reject physical-key, profile-loss, quota-weakening, tier-admission weakening, fake fallback and source-credit escapes;
- tenant-cohort fallback routes an actually exercised number of distinct logical scopes greater than the bounded single-topic test ceiling through real cohort topics without semantic identity change;
- Phase 10 and D4 validators remain green;
- D4-A remains 4/7 and this run grants zero ledger credit;
- Kafka remains not selected and all authorities remain ungranted/unselected.
