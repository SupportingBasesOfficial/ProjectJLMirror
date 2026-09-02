# D4-A — Kafka Candidate Evidence Execution Plan

**Status:** source-evidence plan only — no evidence credited, no Kafka selection, no D4/Wave 4/Product/production/C3 authority granted  
**Canonical D4 entry:** `main@b385e1b68162b2cf9bf4379011554a9cc4c2d5c4`  
**Track:** D4-A — broker transport, physical routing and anti-corruption boundary

## Purpose

This record converts the seven machine-owned D4-A proof obligations into an executable source-evidence program without weakening the separation between evidence generation and ledger promotion.

The first D4 evidence work starts with D4-A because Kafka is already the reviewed leading candidate and its canonical decision record contains explicit falsifiable closure conditions. This plan does not infer that Kafka is selected.

```text
PLAN != EVIDENCE
GREEN SOURCE RUN != LEDGER CREDIT
SEVEN SOURCE PROOFS != KAFKA ACCEPTANCE
KAFKA C2 CONFORMANCE != C3 PRODUCTION NUMERICS
D4-A CONFORMANCE != D4 ACCEPTANCE
D4 ACCEPTANCE != WAVE4 AUTHORITY
```

## Execution model

Evidence SHALL be generated in source PRs/runs first. A source run may emit immutable provenance for one or more D4-A evidence IDs, but SHALL NOT edit `evidence_completed` in the same run/PR merely because it passed. Ledger promotion is a later governed action after exact-run review.

Every candidate-dependent source run SHALL record:

- exact repository SHA;
- exact workflow run/job/probe identity;
- immutable Kafka/container/tool pins where applicable;
- bounded test profile and whether values are Baseline/Growth/Stress test values;
- positive result plus a negative control that demonstrates the harness detects the forbidden condition;
- explicit `current_run_auto_credit=false`;
- explicit preservation of D4/Wave4/Product/production/C3 non-authority.

## Seven proof packages

### D4-A1 — Capacity envelope

Run real Kafka candidate benchmarks against explicit Baseline/Growth/Stress **test** tiers covering tenant skew, event rate/cardinality, throughput, latency, backlog and recovery behavior. The test must expose a measured degradation/failure boundary rather than only a happy-path throughput number.

The benchmark values are evidence inputs. They do not become production partition counts, retention, lag SLOs or capacity commitments.

### D4-A2 — Broker-neutral anti-corruption swap

Exercise one logical producer/consumer port against Kafka and an alternate/stub transport implementation. The same contract test must prove that canonical message identity and business semantics do not depend on Kafka topic, partition, offset, consumer group, rebalance or transaction identity.

A fake alternate path that bypasses the real logical port is invalid evidence.

### D4-A3 — Regulated-payload erasure boundary

Prove the default profile rejects `sensitive_or_regulated` raw record-value bytes and uses an opaque governed reference when per-record erasure is required. Include a negative control that intentionally attempts raw regulated payload leakage and must be rejected.

The default remains reference-based erasure. If a later contract proposes an exception that places raw regulated content in Kafka record-value bytes, that exception is valid only when **all** binding controls from the Kafka decision record are satisfied together:

- the affected traffic uses a per-tenant topic or partition assignment that provides the required isolation granularity;
- a maximum Kafka segment-retention ceiling is explicitly bounded tightly enough to satisfy the accepted governed-erasure SLA for that data class;
- the exception receives explicit sign-off from the governance authority that owns the erasure-fencing model.

A generic “reviewed isolation/retention profile” is insufficient. Missing any one of those three controls keeps the raw-payload exception prohibited.

### D4-A4 — Exactly-once guardrail

Prove consumer registration fails without real inbox/dedup/effect protection even when Kafka idempotent producer or transactional settings are enabled. A valid protected consumer must pass the same registration path.

Kafka transactions may optimize Kafka-to-Kafka relay behavior but never satisfy business-effect exactly-once by themselves.

### D4-A5 — Ordering, partition ceiling and fallback

Map logical ordering scopes from trusted identity to partition keys and exercise a named key-level concurrency mechanism so unrelated logical scopes are not serialized globally or tenant-wide.

Benchmark a practical maximum partition ceiling for each bounded test tier and execute the tenant-cohort topic-sharding fallback when the modeled scope cardinality would exceed that ceiling. These are candidate-conformance values only; production partition counts remain C3.

### D4-A6 — Physical naming/routing/topology adapter

Prove physical topics, groups and cell placement remain replaceable transport mapping rather than logical contract identity. Tenant authorization must occur before physical mapping, and a replacement mapping must not require consumer semantic rewrite.

Production replica/partition/count numerics remain outside this proof.

### D4-A7 — Outbox/backlog drain and recovery

Under real candidate outage/recovery, prove committed outbox backlog survives, broker-ack ambiguity preserves the same logical message identity, and bounded priority-preserving drain does not starve protected/current work. Broker offset/ack progress must not be interpreted as business-effect truth.

Bounded test lag/drain values are evidence, not production lag/retention policy.

## Evidence-kind authority

Each of the seven evidence IDs has one exact allowed `evidence_kind` pinned by assurance tooling. A source PR cannot downgrade a real-candidate benchmark/recovery requirement to a synthetic probe, documentation-only check, or arbitrary substitute kind and remain conformant.

In particular, capacity, ordering/partition/concurrency, and outage/backlog/recovery claims require their declared real-candidate evidence classes. Unit/synthetic evidence may supplement them but cannot replace the source evidence kind owned by the plan.

## Evidence ordering

The preferred execution order is:

1. anti-corruption swap and exactly-once guardrail, because they establish the semantic harness used by later Kafka tests;
2. regulated-payload boundary and physical topology adapter, because they constrain what the benchmark is allowed to publish and map;
3. capacity + ordering/partition/fallback benchmark, because those tests need the accepted harness boundaries;
4. outage/backlog/recovery benchmark, because it exercises the candidate under the same logical identity and topology model after the earlier controls are proven.

Parallel execution is allowed only where evidence independence is explicit; shared harness changes require panoramic revalidation of all affected proof packages.

## Machine-owned plan

`implementation/d4-eventing-async/d4-a-evidence-plan.json` is the machine-owned source-evidence plan. `tools/assurance/validate_d4a_evidence_plan.py` independently pins all seven evidence IDs, **every declared `must_prove` assertion**, and the exact allowed evidence kind for each ID. Removing, substituting, duplicating, or weakening any declared assertion or evidence kind is invalid.

Negative controls reject inventory collapse, arbitrary/synthetic evidence-kind substitution, premature selection, auto-credit, production numeric escalation, loss of trusted-identity ordering, loss of tenant-cohort fallback, loss of topology pre-authorization, weakening of regulated-payload exception controls, loss of backlog-drain protection, treating broker progress as business-effect truth, and entry-ledger pre-credit.

## Exit from planning

This planning PR is complete only when exact-HEAD CI and adversarial review prove that the plan:

- covers exactly the seven D4-A evidence IDs already owned by the D4 entry ledger;
- preserves every declared binding proof assertion and all binding Kafka closure conditions;
- allow-lists the exact evidence kind for every proof package;
- makes real candidate evidence mandatory where the claim is about broker behavior/capacity/ordering/recovery;
- contains negative controls against the dangerous weakening modes;
- leaves D4-A evidence at 0/7 and Kafka unselected;
- grants no D4/Wave4/Product/production/C3 authority.

After this plan is accepted, the next PR SHALL implement the first source-evidence harness package. No ledger credit is implied by accepting the plan.
