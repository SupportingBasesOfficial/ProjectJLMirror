# OPEN-EVT-001 / OPEN-REL-012 Decision Record — Kafka as Async Event/Message Transport

**Status:** proposed — NOT YET closing `OPEN-EVT-001`/`OPEN-REL-012.A` as canonical; four binding closure conditions below (capacity evidence + anti-corruption layer, erasure-granularity mandate, exactly-once guardrail, ordering/partitioning component) are required before Kafka may be treated as selected
**Decision class:** C2 (`docs/16-implementation-readiness/03-consolidated-open-decision-register.md:49,81` — `OPEN-EVT-001..005` and `OPEN-REL-012.A`)
**Drivers:** `docs/10-event-contracts/event-contracts-overview.md`, `docs/10-event-contracts/phase-10-open-decisions.md` (`OPEN-EVT-001,005,006,011,026`), `docs/04-quality/capacity-envelope.md`, `docs/10-event-contracts/security-tenant-context-and-data-classification.md`, `docs/10-event-contracts/ordering-sequencing-and-replay.md`, `docs/10-event-contracts/delivery-ack-retry-and-quarantine.md`, `docs/11-reliability-resilience/05-overload-backlog-and-workload-isolation.md`

This document follows the decision-quality checklist from `docs/00-foundation/decision-policy.md`. It is **not** a new ADR: broker/queue technology is explicitly the question `OPEN-EVT-001` leaves open, inside architecture (broker-neutral logical contracts, at-least-once default, outbox/inbox invariants) already fixed by Phase 10. It was produced from an adversarial multi-round red/blue-team review. **Kafka is not safe to accept as closing `OPEN-EVT-001`/`OPEN-REL-012.A` as originally framed** — all four findings below were independently re-verified against the repository and confirmed (one narrowed from "infeasible" to "requires a named component," one narrowed from "critical" to "high" because the platform already prohibits the failure mode by name).

## Context and problem

`OPEN-EVT-001` (`docs/10-event-contracts/phase-10-open-decisions.md:12-25`) already fixes that logical contracts are broker-neutral, default delivery is at-least-once, a broker's EOS/transaction feature alone does not prove business exactly-once, and identity does not depend on physical topic/partition IDs. It leaves the concrete transport product open. `OPEN-REL-012` (Phase 11) separately requires broker product/topology/partition/retention/lag/outbox/drain mechanisms to be selected with conformance plus backlog/recovery benchmarks. This record evaluates Kafka against both.

## Decision

Kafka is selected as the async transport mechanism, conditioned on the four closure requirements below. None of the four is Kafka-specific in the sense of ruling Kafka out; each is a guardrail this ADR-level record makes explicit before Kafka's selection is canonical.

### Closure condition 1 — capacity-envelope evidence + enforced anti-corruption layer (binding, high severity)

`docs/04-quality/capacity-envelope.md:8` requires: "before a later decision selects or materially specializes... queue/event transport... on capacity grounds, that decision SHALL be tested against a stated workload envelope and the resulting evidence recorded." Its Measurements status is literally `OPEN` — no tenant/throughput numbers exist yet. `OPEN-EVT-005` (`phase-10-open-decisions.md:77`) requires "service extraction/broker replacement must not require consumer semantic rewrite." Without an enforced abstraction layer, Kafka-native primitives (offsets, consumer-group rebalance, transactional API) will leak into Phase 10 outbox/inbox/consumer code by default — the platform's own `OPEN` discipline (`phase-10-open-decisions.md:381-391`) explicitly refuses to let "a broker feature is convenient" or "an SDK generates a schema" close an OPEN item, anticipating exactly this failure mode. This gate applies to any broker choice, not uniquely Kafka.

**Requirement:** before `OPEN-REL-012.A`/`OPEN-EVT-001` close: (1) run capacity-envelope evidence against the Baseline/Growth/Stress tiers for the tenant/device/event-rate dimensions `capacity-envelope.md` requires; (2) specify an anti-corruption layer so outbox/inbox/consumer code depends only on the broker-neutral logical contract — never Kafka offsets, consumer-group semantics, or the transactional API directly — verified by a compatibility test that swaps in a stub/alternate broker; (3) record both the evidence and the enforced abstraction boundary explicitly in this record before it is treated as closed.

### Closure condition 2 — erasure-granularity mandate for regulated payloads (binding, high severity)

`docs/08-data/recovery-retention-and-artifacts.md:313`: "garbage collection is governed, not blind TTL deletion." `OPEN-EVT-026` (`phase-10-open-decisions.md:355`) names "legal hold/erasure governance overrides ordinary broker cleanup" — targeting broker-resident data directly, not by analogy. `docs/10-event-contracts/security-tenant-context-and-data-classification.md` lists `confidential_tenant` and `sensitive_or_regulated` as valid, expected message classes (only `secret_or_credential` is prohibited outright), and its payload-minimization guidance uses discretionary "avoid"/"may" language, not a hard MUST-NOT for regulated payload bytes specifically. Kafka's only native deletion primitives are segment-based time/size retention (deletes a whole segment only once every record in it ages out) and log compaction (asynchronous, best-effort, no wall-clock deletion guarantee) — neither can target one tenant's one record inside a segment/partition shared with other tenants.

**Requirement:** no `sensitive_or_regulated`-classified payload field is stored as Kafka record value bytes — only an opaque reference into a governed store with per-record cryptographic-erasure capability, so erasure is satisfied by destroying the referenced ciphertext/key rather than the Kafka record. Where raw regulated content must transit Kafka for specific contracts, require per-tenant topic/partition assignment plus a maximum segment-retention ceiling short enough to make "wait for natural expiry" an acceptable governed-erasure SLA, signed off by the governance authority owning the `recovery-retention-and-artifacts.md` erasure-fencing model.

### Closure condition 3 — exactly-once guardrail as enforced tooling, not a reminder (binding, high severity — downgraded from critical)

`docs/10-event-contracts/event-contracts-overview.md:185` already contains an explicit, specific textual prohibition: "exactly-once wording is prohibited unless the owning business effect proves exactly-once semantics end-to-end. A broker's exactly-once/transaction feature by itself does not satisfy that requirement." Selecting Kafka does not itself contradict this — the document already defends against exactly this reasoning. The residual risk is that Kafka's idempotent-producer/transactional API is the one mainstream broker feature literally named "exactly-once," which measurably raises the probability an implementer relaxes investment in the mandated `OPEN-EVT-011` inbox/dedup store believing the seam is already covered. Kafka transactions cannot span the seam between the authoritative DB commit and a separate Kafka-transaction commit, nor cover consumers whose effect is an external HTTP call, different datastore write, or webhook dispatch — most of this platform's declared consumer population.

**Requirement:** the ADR records, as an enforced implementation guardrail rather than a restated reminder, that Kafka's idempotent-producer/transactional-API configuration is permitted only for internal Kafka-to-Kafka relay hops and is explicitly barred from being cited (in code, contract docs, or incident postmortems) as satisfying `OPEN-EVT-011`. An automated contract-conformance check (extending `event-contract-validation-matrix.md` tooling) fails any consumer registration lacking a real inbox/dedup implementation regardless of producer-side transactional configuration, running in CI before a consumer can be registered against a Kafka topic.

### Closure condition 4 — named consumer-side ordering component (binding, medium severity — downgraded from high)

`docs/10-event-contracts/ordering-sequencing-and-replay.md:147-149` requires serializing "only that required scope rather than one entire tenant/domain/global stream"; `delivery-ack-retry-and-quarantine.md:310`: "broker-wide head-of-line blocking is not a contract requirement." Kafka's only native ordering/parallelism unit is the partition; at this platform's scale, fine-grained ordering scopes multiplied across thousands of tenants can exceed practical per-cluster partition counts, forcing many unrelated scopes onto shared partitions where one slow-but-valid message blocks all of them. This is not a structural impossibility — a known, widely-adopted pattern (consumer-side key-level virtual sequencing / bounded per-key concurrency, e.g. the open-source "Parallel Consumer" pattern) already resolves it by decoupling logical ordering-scope cardinality from physical partition count — but it must be a named, deliberate architectural component, not discovered under incident pressure.

**Requirement:** a documented mapping from every declared ordering-scope class to a partitioning-key strategy validated against `capacity-envelope.md`'s tenant/device cardinality tiers; a named consumer-side key-level concurrency component required explicitly in this record (cited so it is adopted deliberately); a benchmarked maximum partition-count ceiling per topic/cluster tier with a documented fallback (tenant-cohort topic sharding).

## Consequences

### Positive
- mature, widely-operated broker technology with a large operational knowledge base;
- the four guardrails above are broker-choice-agnostic in three of four cases (capacity evidence, erasure granularity, ordering component would apply to any broker) — the actual Kafka-specific risk is narrowly the exactly-once-feature temptation, which is now enforced by tooling rather than left to discipline.

### Negative / cost
- an anti-corruption layer, ordering-scope-to-partition-key mapping, and CI conformance check are all new implementation surface beyond adopting Kafka's SDK directly;
- the erasure-granularity mandate forecloses storing raw regulated payloads directly in Kafka records for the affected message classes.

## Validation

Before production eligibility, conformance evidence SHALL prove:
- capacity-envelope evidence exists for Baseline/Growth/Stress tiers and the anti-corruption layer passes a stub-broker swap test;
- no `sensitive_or_regulated` payload field appears as Kafka record value bytes in any registered contract;
- the CI conformance check rejects a consumer registration lacking a real inbox/dedup implementation regardless of Kafka transactional config;
- a benchmarked partition-count ceiling exists per topic/cluster tier with a working key-level concurrency component and documented fallback.

## Exit / revisit conditions

Revisit if capacity evidence shows Kafka cannot meet the measured envelope, if the anti-corruption layer proves unenforceable in practice, or if a future broker-neutral generalization of the ordering/erasure guardrails is adopted platform-wide.
