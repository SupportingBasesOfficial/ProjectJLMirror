# Phase 11 — OPEN Decisions and Blockers

Status: proposed baseline  
Authority: Phase 11 — Reliability & Resilience  
Normative terms: `SHALL`, `SHALL NOT`, `SHOULD`, `MAY`

## 1. Purpose

This register preserves decisions that Phase 11 cannot responsibly close without Product, measurement, implementation, runtime, vendor, or downstream-phase evidence. It also defines the conditions that block Phase 11 acceptance, implementation readiness, release, or production eligibility.

## 2. Closure classes

Every OPEN SHALL use exactly one primary class from the accepted roadmap:

1. `must_close_before_implementation` — structural semantics, authority, ownership, or trust boundary required to write correct code;
2. `evidence_generating_implementation_decision` — mechanism/product choice that may be evaluated without changing accepted contracts;
3. `must_close_before_production_eligibility` — numeric targets, limits, staffing, RPO/RTO/SLO, capacity, retention, or operational thresholds;
4. `product_gated` — behavior cannot exist until an accepted Product need defines it;
5. `intentionally_deferred_future_capability` — outside the initial wave and prevented from leaking through defaults.

An OPEN SHALL include an accountable authority, evidence requirement, and closure gate. “TBD” without those fields is a blocker.

## 3. Phase 11 OPEN register

| OPEN | Fixed normative property | Decision intentionally OPEN | Primary class, owner, evidence and gate |
|---|---|---|---|
| `OPEN-REL-001` | Cells require bounded continuity during Control Plane impairment without authority expansion. | Concrete continuity mechanism, lease distribution, and cached-authority implementation. | `2`; Phase 13 with Security; partition/fencing conformance; close before implementation mechanism is selected and conformed. |
| `OPEN-REL-002` | Control-plane staleness and contradiction are explicit and generation-bound. | Numeric freshness/lease horizons and availability topology. | `3`; Phase 12/13/15 plus Product/business; partition measurement and recovery rehearsal; close before production eligibility. |
| `OPEN-REL-003` | A cell has one authoritative writer generation and deterministic failover fencing. | Database product, HA topology, election/fencing mechanism, replica counts. | `2`; Phase 13/Data; failover and stale-writer fault evidence; mechanism before implementation, numerics/topology before production as separately classified decisions. |
| `OPEN-REL-004` | Region loss SHALL not create dual authority or violate residency/placement. | Region topology, active/passive policy, failover geography and capacity. | `3`; Product/Data/Phase 13/15; capacity, residency and recovery evidence; before production eligibility. |
| `OPEN-REL-005` | End-to-end deadlines are propagated and timeout never invents completion truth. | Numeric deadline profiles by operation/capability. | `3`; Product/Phase 12 with measured latency; load and fault distributions; before production eligibility. |
| `OPEN-REL-006` | Retries require semantic eligibility, stable identity, aggregate budgets, backoff and jitter. | Attempt counts, elapsed budgets, delay curves and jitter ranges. | `3`; Reliability/Phase 12 with provider/runtime evidence; amplification tests; before production eligibility. |
| `OPEN-REL-007` | Where a profile's exact circuit selector has a non-empty applicable failure-class set, circuits isolate unhealthy dependencies and use bounded recovery probes; a `no_applicable_case` profile has no circuit-open/half-open/probe implementation obligation and retains negative circuit evidence only. | Algorithm, state thresholds, windows and probe budgets **only for profiles with an applicable circuit selector**. | `2`; Phase 13 implementation owner; fault/load comparison on the exact applicable profile scope; select before implementation of that circuit-bearing adapter/profile, tune before production. `no_applicable_case` does not select or close an algorithm branch. |
| `OPEN-REL-008` | Bulkheads and concurrency preserve tenant, workload and dependency isolation. | Pool mapping, concurrency/reservation sizes and adaptive-control mechanism. | `2`; Phase 13 with Capacity overlay; skew and saturation benchmarks; mechanism before implementation, numbers before production. |
| `OPEN-REL-009` | Backlogs are bounded, attributable, age-aware and have explicit overflow behavior. | Queue/buffer sizes, age limits, storage pressure thresholds and spill mechanism. | `3`; Phase 12/13/15 with capacity evidence; burst, outage and drain benchmarks; before production eligibility. |
| `OPEN-REL-010` | Fairness protects unrelated tenants and critical live/recovery work. | Scheduling algorithm, priority weights, reserved recovery capacity, premium Product tiers if any. | `2`; Product plus Phase 13; adversarial tenant-skew and starvation evidence; Product terms before differentiated behavior, mechanism before implementation. |
| `OPEN-REL-011` | Provider calls use provider-scoped deadlines, retry eligibility, circuits, concurrency and ambiguity handling. | Provider-specific numeric profiles and inquiry/reconciliation capabilities. | `3`; Integration owner with Product; sandbox/fault evidence and provider contracts; before each provider is production-eligible. |
| `OPEN-REL-012` | Accepted async work is durable; broker failure is absorbed only within bounded capacity; drain preserves priorities. | Broker product/topology, partitions, retention, lag thresholds, outbox publication and drain mechanisms. | `2`; Phase 13/14 with Data; conformance plus backlog/recovery benchmarks; mechanism before implementation, numbers before production. |
| `OPEN-REL-013` | Failover, relocation and recovery use monotonic generations and fence stale actors. | Concrete lease/fence token mechanism and propagation implementation. | `1`; System/Data/Phase 13; stale-writer and delayed-message proofs; must close before writing authoritative failover paths. |
| `OPEN-REL-014` | Ambiguous operations and `(R,F]` recovery require authoritative inquiry/reconciliation or remain blocked. | Reconciliation orchestration/tooling and automation degree. | `2`; Phase 13/15; ambiguity and incomplete-fact rehearsals; mechanism before implementation of recovery tooling. |
| `OPEN-REL-015` | Cache and replay are derived, generation-aware and unable to broaden authority. | Cache product/topology, invalidation transport, replay window and epoch implementation. | `2`; Phase 13 with Data; loss/staleness/relocation conformance; before the derived-state implementation is selected. |
| `OPEN-REL-016` | Secret/key bootstrap and rotation use verified generations and bounded leases; secrets never enter ordinary state. Where keyed/authenticated message-equivalence evidence is selected, historical verifier material remains secret-bound and generation-scoped, and its availability does not itself grant duplicate/effect eligibility. | Secret/KMS product, lease horizon, rotation overlap, emergency-recovery mechanism, and concrete historical-verifier implementation for keyed message-equivalence evidence. | `2`; Security/Phase 13/15; bootstrap, rotation, historical-verifier loss/restore and recovery rehearsal; mechanism before implementation, numeric horizon before production. |
| `OPEN-REL-017` | Realtime is non-authoritative, placement/auth generation-bound, overload-aware and resynchronizable. | Session limits, buffer/drop policy, reconnect budget and runtime transport. | `3`; Product/Phase 12/13; disconnect, revocation, skew and resync benchmarks; before production eligibility. |
| `OPEN-REL-018` | Webhook delivery, if Product-approved, requires immutable delivery identity, destination isolation, ambiguity and bounded retry. | Whether/families of outbound webhooks, destination semantics, retry horizons and limits. | `4`; Product authority; accepted feature contract plus adversarial destination evidence; no implementation before Product gate. |
| `OPEN-REL-019` | Artifacts are integrity-verified, tenant/generation-bound, and governed by revocation/erasure/quarantine. | Object-store product/topology, capability mechanism, streaming continuation and availability profile. | `2`; Data/Security/Phase 13; mismatch, outage and governance-race tests; mechanism before implementation, numerics before production. |
| `OPEN-REL-020` | Optional operational telemetry cannot become business authority and its loss is explicit; customer monitoring observations acknowledged after their separate durable acceptance boundary remain recoverable and project monotonically; mandatory audit boundaries fail according to Security/Data policy. | Optional/customer/audit telemetry products and numeric buffer, loss-tolerance, checkpoint-lag, retention, cardinality and storage/cost envelopes; the customer durable-acceptance/projection mechanism is owned separately by `OPEN-REL-030`. | `3`; Phase 12/Security/Data; optional-loss, durable-acceptance/projection, overload, relocation and confidentiality evidence; before production eligibility. |
| `OPEN-REL-021` | Fault evidence SHALL be bounded, reproducible, attributable, isolated and cleanup-safe. | Fault/chaos tooling, execution environments and production-like rehearsal policy. | `2`; Verification overlay with Phase 14/15; tool conformance and safe rehearsal; before executable fault program. |
| `OPEN-REL-022` | Capacity is multi-dimensional and includes tenant skew, retry amplification, recovery, message-equivalence comparison/KMS/migration work and cost. | Numeric envelopes and rearchitecture triggers. | `3`; Product/business plus Capacity overlay; representative benchmarks, crafted-duplicate amplification tests and cost evidence; before production eligibility. |
| `OPEN-REL-023` | Availability and recovery claims require accepted objectives and measurement semantics. | SLOs, error budgets, RPO/RTO and convergence targets. | `3`; Product/business with Phase 12/15; measured baseline and recovery drills; before production eligibility. |
| `OPEN-REL-024` | Specialized/privileged roles require separate trust, isolation, lifecycle and capacity envelopes. | Mapping to processes/nodes/sandboxes/runtimes and extraction sequence. | `2`; Phase 13 with Security; privilege, egress, saturation and portability tests; before role implementation. |
| `OPEN-REL-025` | Idempotency, inbox/outbox, quarantine, replay and recovery evidence remain available for their accepted semantic horizons; duplicate-sensitive equivalence evidence remains interpretable under its required canonical comparison-profile/version and historical verifier authority for the same supported horizon or an equality-preserving governed migration safely replaces it. | Numeric retention horizons, physical storage lifecycle and retained historical comparison-authority lifecycle implementation. | `3`; Product/Data with Phase 09/10 owners; redelivery/recovery/equivalence horizon evidence and cost; before production eligibility. |
| `OPEN-REL-026` | Every reliability transition and blocker has evidence requirements consumable by Observability. | Signal names, telemetry schema, health/readiness semantics, alert and SLI mapping. | `1`; Phase 12; trace from failure state to evidence and negative tests; must close before implementation instrumentation contracts. |
| `OPEN-REL-027` | Critical capabilities, incidents, ambiguity, quarantine, recovery and break-glass need accountable operational ownership. | Named owners, staffing, runbooks, escalation and communications platform. | `1`; Phase 15 for ownership semantics, `3` for staffing numerics; table-top/rehearsal evidence; ownership before implementation readiness, staffing before production. |
| `OPEN-REL-028` | Reliability-breaking changes require compatible rollout, pause/abort and rollback/forward-recovery behavior. | Deployment tooling, wave sizes, health gates, pause/abort thresholds and emergency mechanism. | `2`; Phase 14; mixed-version, rollout and recovery evidence; mechanism before implementation readiness, numerics before production. |
| `OPEN-REL-029` | Configuration authority is schema-valid, scope-bound, generation-monotonic, compatibly distributed and recovery-aware independently of secret material. | Configuration store/distribution product, schema tooling, rollout mechanism, last-known-good horizon and convergence targets. | `2`; configuration-owning capability with Phase 13/14 and Security; malformed/partial/restore fault evidence; authority/schema semantics before implementation, mechanism through Phase 13/14, numerics before production. |
| `OPEN-REL-030` | Customer monitoring observations are acknowledged only after canonical scoped identity and durable acceptance responsibility exist; accepted observations remain replayable into idempotent historical, monotonic current-state and durable transition/signal projections across restart, recovery and relocation. | Concrete durable acceptance authority/mechanism, projection persistence/transport, checkpoint implementation and reconciliation orchestration. | `2`; Data/monitoring owner with Phase 13/14; `FV-TEL-002` conformance including crash, backlog, replay and relocation; select and conform the mechanism before implementing the customer-telemetry ingestion/projection path. |
| `OPEN-REL-031` | `rel.security-session-authority` fails closed for unavailable/stale/compromised authority (`07-capability-resilience-profiles.md:18,45`) with no stale-tolerant escape hatch analogous to Control Plane data (ADR-017); that stricter posture makes an untracked HA/topology blast radius for its own backing store less tolerable, not more, yet no OPEN item currently tracks it the way `OPEN-REL-003`/`004` track cell/region database HA. | Identity/session-authority durable-store topology (single global primary vs. per-region/per-cell-group primaries), RPO/RTO and failover-mechanism selection, and whether the store is Control-Plane-owned or its own tier. | `2` for topology/mechanism, `3` for RPO/RTO numerics; Security/Data with Phase 13; failover and stale-writer fault evidence mirroring `OPEN-REL-003.A/B`; mechanism/ownership decision before implementation, numerics before production. |

Where a row contains sub-decisions with different gates, downstream owners SHALL split them into separate records before closure rather than close the entire OPEN with partial evidence.

OPEN applicability is part of conformance. `OPEN-REL-007` SHALL enter a profile's final `open_decisions` only through the exact `CIRCUIT-OPEN(profile_key)` branch in `07-capability-resilience-profiles.md`. A non-empty counted circuit-failure set imports `OPEN-REL-007`; `no_applicable_case` imports no circuit implementation OPEN and keeps only its dedicated negative evidence. Tooling SHALL reject both an applicable circuit profile missing `OPEN-REL-007` and a no-circuit profile carrying it as an implementation obligation.

## 4. Decisions Phase 11 closes

Phase 11 closes the following semantic decisions within roadmap authority:

- capability/dependency criticality vocabulary and required profile fields;
- failure and degradation vocabulary, including `external_outcome_ambiguous`, `recovery_continuity_blocked`, and explicit staleness;
- fail-closed boundaries for uncertain authority, revocation, generations, and sensitive operations;
- deadline propagation and the rule that timeout is not completion truth;
- retry eligibility, stable identity, aggregate-budget, circuit, bulkhead, backpressure, and bounded-backlog requirements;
- canonical Phase 09/10 interpretation remains the authority for admission tenant/workload/cost classification; provisional pre-validation resource claims are conservative and must be upgraded or rejected before effect;
- confidentiality-safe scoped message-equivalence comparison, deterministic temporary-verifier-outage vs continuity-loss vs compromised-trust failure classes, historical comparison-profile/verifier continuity and anti-oracle/capacity obligations without selecting their implementation mechanism;
- noisy-neighbor, maintenance/replay/recovery isolation requirements;
- quarantine, redrive, fencing, reconciliation, and `(R,F]` recovery continuity;
- reliability compatibility/change classification;
- fault-vector, evidence-level, and release-blocker semantics.

It does not close products, vendors, concrete topology, numeric objectives/thresholds, staffing, Product-gated behavior, or downstream execution mechanisms.

## 5. Phase 11 acceptance blockers

Phase 11 SHALL NOT be accepted while any of the following is true:

- a roadmap-required artifact or overlay is missing or optionalized;
- a critical capability lacks authority, dependencies, failure/degradation behavior, isolation, recovery, evidence, or owner handoff;
- stable Control Plane impairment can be interpreted as fail-open or unlimited autonomy;
- missing trust/recovery evidence can be interpreted as absence or permission;
- duplicate-sensitive message equivalence can be accepted from scoped identity alone, from uninterpretable evidence, from a temporarily unavailable historical verifier without blocking, or from compromised/untrusted comparison authority;
- low-entropy/cross-scope equivalence evidence can become an offline/equality oracle, authority token or unbounded comparison/KMS amplification path;
- ambiguous external effects can receive blind retry;
- retry/backlog/concurrency is unbounded or lacks tenant/workload isolation;
- non-canonical/untrusted structured request or message semantics can select tenant/workload/cost admission class, or a cheaper provisional budget can survive the final canonical classification into expensive/effectful continuation;
- recovery can restore authority before `(R,F]`, revocation, erasure, hold, audit, historical comparison-profile/verifier continuity and generation reconciliation;
- physical topology leaks into public API/event identity;
- an OPEN lacks a class, owner, evidence requirement, gate or applicable profile scope;
- a profile's final OPEN set contradicts its exact circuit applicability branch;
- a vendor, topology, numeric target, Product behavior, or downstream mechanism is canonized without authority/evidence;
- AI output is used as approval, waiver, score, vote, veto, or intermediate normative authority;
- fault vectors lack deterministic expected/forbidden outcomes and blocker mappings;
- the exact-final-HEAD Native Assurance Gate is not complete under the accepted Review and Assurance Governance package;
- P0/P1/P2 findings or review threads remain unresolved at final merge authorization;
- the reviewed HEAD, PR HEAD, or accepted base does not match the exact gate record.

External reviewer/model absence, quota or outage is neither a clean signal nor a blocker by itself. Independence SHALL be claimed only when provenance demonstrates it.

## 6. Implementation-readiness blockers inherited from Phase 11

Even after Phase 11 merge, implementation remains blocked until downstream phases close at least:

- `OPEN-REL-013`, `OPEN-REL-026`, and the ownership-semantic portion of `OPEN-REL-027`;
- `OPEN-REL-030` before any customer-telemetry durable acceptance/projection path is implemented;
- runtime responsibility, isolation, identity, secrets, historical verifier lifecycle where keyed comparison is selected, lifecycle, cell and fencing mechanisms from Phase 13;
- build/release authority, artifact trust, compatibility rollout and recovery change classes from Phase 14;
- operational ownership, recovery admission, runbook/break-glass and incident authority from Phase 15;
- the full Implementation Readiness traceability and blocker gate.

Implementation work that exists solely to generate evidence for a class-2 decision is not authorized merely by this document; it requires the later Implementation Readiness governance and bounded spike authority.

## 7. Release and production blockers

The blockers `RB-REL-001` through `RB-REL-026` in the fault matrix apply to their respective evidence gates. Additionally:

- production eligibility is blocked while applicable class-3 OPENs lack accepted numbers and runtime evidence;
- a Product-gated capability is blocked until Product authority and its full contract exist;
- an intentionally deferred capability SHALL be disabled and SHALL NOT leak through framework/runtime defaults;
- a release SHALL be blocked when mixed-version reliability behavior is unsupported or when rollback would violate security, recovery, audit, revocation, erasure, message-equivalence/historical-verifier continuity or external-effect continuity;
- production readiness SHALL not be inferred from document acceptance, implementation conformance, or release-candidate testing alone.

## 8. OPEN update protocol

An OPEN closure proposal SHALL include:

```text
open_id
proposed_decision
authority_and_owner
evidence
affected_contracts_and_profiles
security_privacy_delta
capacity_performance_cost_delta
compatibility_and_recovery_delta
fault_vectors_and_blockers
closure_class_and_gate
review_assurance_provenance
```

`review_assurance_provenance` records the exact review/assurance evidence actually used. It SHALL identify the reviewed SHA and provenance sufficient to support any independence claim. It does not require a named external reviewer/model and SHALL NOT turn reviewer quota, latency or outage into a progression dependency. Native Assurance remains the repository-default exact-HEAD gate unless accepted governance later changes that rule.

Closing an OPEN SHALL update the semantic manifest, compatibility classification, fault/evidence matrix, and traceability in the same accepted change. A convenient implementation default SHALL never count as evidence.

## 9. Phase handoff

On Phase 11 acceptance:

- the Phase 11 reliability semantics become inherited authority;
- Phase 12 becomes unblocked and SHALL consume the failure/evidence vocabulary;
- Phase 13–15 remain blocked from normative start until their predecessors pass;
- implementation remains blocked by the accepted roadmap and the Implementation Readiness Gate;
- Phase 11 itself is not merged without separate explicit authorization on the exact reviewed HEAD.
