# Phase 11 — Reliability Compatibility and Change Classification

Status: proposed baseline  
Authority: Phase 11 — Reliability & Resilience  
Normative terms: `SHALL`, `SHALL NOT`, `SHOULD`, `MAY`

## 1. Purpose

Reliability behavior is part of the system contract. A change to failure classification, timeout or retry semantics, overload behavior, authority continuity, message-equivalence comparison authority or recovery convergence can be breaking even when API and event schemas are unchanged. This document defines the Phase 11 compatibility vocabulary and the evidence that downstream rollout governance SHALL consume.

## 2. Versioned reliability surfaces

The following surfaces SHALL be versioned or otherwise bound to an immutable semantic profile:

- capability and dependency criticality;
- failure and degradation classifications;
- deadline propagation, timeout truth, and cancellation behavior;
- retry eligibility, aggregate attempt budget, backoff, and ambiguity handling;
- circuit, bulkhead, concurrency, queue, and backpressure policy;
- canonical request/message interpretation used for admission scope and resource/cost classification;
- duplicate-sensitive message-equivalence comparison surface, canonical comparison-profile/version and historical verifier/key-generation lifecycle;
- equivalence-evidence confidentiality/domain-separation/anti-oracle behavior and comparison/KMS amplification bounds;
- admission, fairness, shedding, overflow, and backlog recovery behavior;
- tenant, cell, generation, provider, destination, and workload isolation;
- acknowledgement, lease, checkpoint, quarantine, redrive, and replay boundaries;
- authority lease, fencing, relocation, failover, and recovery semantics;
- `(R,F]` reconciliation and governance continuity;
- cache/staleness/monotonicity guarantees;
- capability resilience profiles and their required evidence.

Product/API/event identities SHALL remain independent of deployment topology and profile storage mechanisms.

## 3. Change classes

| Class | Definition | Default gate |
|---|---|---|
| `compatible_additive` | Adds a profile, failure detail, or enforcement that existing participants can safely ignore without weakening accepted behavior. | Contract and conformance review. |
| `compatible_stricter` | Narrows retry, authority, admission, or degradation in a way that preserves safety but may reduce availability. | Reliability plus Product/compatibility impact review. |
| `conditionally_compatible` | Safe only for declared version combinations, capabilities, workloads, tenants, or rollout states. | Mixed-version matrix and bounded rollout evidence. |
| `behavior_breaking` | Changes externally visible failure, availability, ordering, acknowledgement, retry, or degradation semantics. | New accepted contract and migration plan. |
| `security_breaking` | Broadens authority, weakens isolation/fencing/revocation, changes trust/equivalence evidence confidentiality, exposes cross-scope comparison, or creates a fail-open path. | Security authority approval; default release blocker. |
| `recovery_breaking` | Alters identity, ledger, generation, fencing, replay, retention, historical comparison authority or reconciliation such that old/new state cannot converge safely. | Forward-recovery/migration design; default rollback prohibition. |
| `capacity_risk` | Preserves semantics but changes resource amplification, queue growth, fairness, provider pressure, comparison/KMS work, tenant skew, or cost envelope materially. | Benchmark and capacity evidence. |
| `product_gated` | Introduces behavior whose correctness depends on a Product need not yet accepted. | Product authority before contract introduction. |
| `intentionally_deferred` | Describes a future capability excluded from the current implementation wave. | Must remain disabled and prevented from leaking through defaults. |

A change MAY have multiple classes. The strongest applicable gate SHALL control; a weaker label SHALL NOT erase a security, recovery, or Product dependency.

## 4. Compatibility dimensions

Every reliability change record SHALL answer:

1. Which capability, dependency, tenant/cell/generation, and workload profiles change?
2. Can old callers and new callees agree on deadline and cancellation semantics?
3. Can they agree on retry eligibility and stable operation/message/effect identity?
4. Can acknowledgement, lease, checkpoint, and quarantine boundaries coexist?
5. Can old and new canonical parsing/admission policies derive the same trusted tenant/workload/cost scope and coexist without feedback amplification or budget bypass?
6. For duplicate-sensitive messages, can every admitted version prove the same immutable-message equality under compatible canonical comparison profiles and historical verifier authority without weakening confidentiality/domain separation?
7. Does either version broaden authority or accept stale security/placement/comparison evidence?
8. Can failover, relocation, rollback, and `(R,F]` recovery converge across versions, including retained equivalence evidence/profile/verifier generations?
9. Are API/event schema compatibility classifications sufficient, or is behavior independently breaking?
10. What implementation, release, and runtime evidence is required?
11. Which OPEN decisions and release blockers apply?

## 5. Mixed-version matrix

For every participant pair that can coexist, the change SHALL declare a matrix entry:

| Dimension | Required declaration |
|---|---|
| producer/caller version | Exact semantic profile or supported range. |
| consumer/callee version | Exact semantic profile or supported range. |
| runtime/config version | Profile distribution and enforcement generation. |
| admitted combinations | Explicit list or mechanically evaluable constraint. |
| forbidden combinations | Combination and deterministic rejection behavior. |
| authority behavior | Lease, generation, fencing, revocation and historical verifier authority compatibility. |
| work identity | Operation, message, effect, attempt, and artifact identity continuity. |
| message-equivalence behavior | Canonical comparison surface/profile, evidence classification/domain separation, historical verifier generation, migration and unknown-equivalence behavior. |
| failure behavior | Timeout, retry, acknowledgement, degradation, and ambiguity outcome. |
| admission classification | Canonical interpretation, trusted scope/cost-class derivation, provisional-budget adjustment and rejection behavior. |
| capacity behavior | Amplification and isolation expectations, including comparison/KMS/migration work where applicable. |
| recovery behavior | Rollback safety or required forward recovery/reconciliation, including interpretability of retained equivalence evidence. |
| evidence | Conformance and fault vectors covering the combination. |

Silence SHALL mean unsupported, not compatible. A rollout mechanism SHALL NOT infer compatibility from matching API schemas alone.

## 6. Compatibility invariants

### 6.1 Deadline and retry

- A downstream version SHALL NOT extend an upstream end-to-end deadline without an accepted contract.
- Mixed versions SHALL NOT create nested retry multiplication beyond the aggregate attempt budget.
- A version that classifies an outcome as `external_outcome_ambiguous` SHALL NOT interoperate with a peer that blindly converts it to retryable absence.
- Retry-policy changes SHALL preserve stable operation and effect identity.

### 6.2 Authority and generations

- Older versions SHALL be fenced if they cannot recognize the current authority, placement, source, secret, comparison-profile/verifier, or recovery generation required by the affected contract.
- A rollout SHALL NOT create simultaneous authoritative writers because versions interpret leases differently.
- Cached older evidence SHALL NOT broaden authority accepted by a newer policy.
- A historical comparison verifier that remains usable for old evidence SHALL NOT become unrelated current cryptographic or effect authority merely because a mixed-version runtime can access it.

### 6.3 Async and acknowledgement

- Producer, broker adapter, consumer, inbox, and effect-ledger versions SHALL agree on immutable identity and content-conflict behavior.
- For duplicate-sensitive consumers, all admitted versions SHALL preserve the accepted Phase 10 rule that identity alone is not duplicate proof; historical equality must remain reproducible under the retained comparison profile/verifier authority or the affected path remains `recovery_continuity_blocked`/`reconciliation_blocked`.
- A version SHALL NOT replace confidentiality-safe/scoped comparison evidence with a low-entropy plain-digest or unrestricted equality lookup that leaks cross-tenant/cross-consumer information.
- Canonicalization/profile or verifier rotation SHALL preserve the same historical equality result or complete an accepted equality-preserving migration before old authority retirement.
- Acknowledgement SHALL remain after the accepted durable completion boundary across versions.
- Quarantine and redrive SHALL not rewrite identity or erase previous attempts.

### 6.4 Overload and backpressure

- New admission or queue policies SHALL not allow an old producer to bypass tenant/workload isolation.
- Coexisting versions SHALL derive admission scope and cost class from the same accepted canonical request/message interpretation. Aliases, duplicate fields, malformed encodings, caller-selected scope labels, or alternate normalization paths SHALL NOT cause the same logical input to enter a cheaper or different tenant/workload budget.
- A provisional pre-validation budget SHALL be upgraded to the final canonical authoritative class or rejected before expensive/effectful continuation; mixed versions SHALL NOT continue under the cheaper provisional claim.
- Duplicate/equality verification changes SHALL not create unbounded historical-profile, KMS/secret-store or migration work, nor move one tenant's crafted identity pressure into another tenant/consumer scope.
- Retry, circuit, batching, and drain changes SHALL be tested as a closed feedback system, not component by component only.
- Maintenance, replay, migration, and recovery work SHALL retain their class and checkpoint across versions.

### 6.5 Recovery

- Rollback SHALL be classified unsafe when it could resurrect authority, effects, revocations, erasures, or pre-reconciliation state.
- Recovery-breaking changes SHALL define forward migration and reconciliation before admission.
- `(R,F]` evidence SHALL remain interpretable by every version admitted during the recovery window.
- For duplicate-sensitive evidence, “interpretable” includes the canonical comparison-profile/version and required historical verifier authority; retained bytes alone are insufficient.
- Restoring an obsolete comparison verifier/profile SHALL NOT make it current authority for unrelated messages or scopes.

## 7. Example classifications

| Example | Minimum class | Reason |
|---|---|---|
| Add a new optional diagnostic failure detail while preserving the canonical class. | `compatible_additive` | Existing behavior remains mechanically interpretable. |
| Stop retrying a previously retryable ambiguous external effect. | `compatible_stricter` and possibly `behavior_breaking` | Safety improves, but Product-visible completion may change. |
| Change timeout ownership from caller to an independent callee budget. | `behavior_breaking` | Work may continue after caller expiry and create new ambiguity. |
| Allow stale authorization when the authority service is unavailable. | `security_breaking` | Missing evidence becomes permission. |
| Change canonical parsing or normalization so the same logical input can receive a cheaper or different tenant/workload budget before final validation. | `security_breaking` + `capacity_risk` | Admission and isolation semantics changed even if the API/event schema is unchanged. |
| Change message identity or inbox equivalence. | `recovery_breaking` | Old/new redelivery and reconciliation cannot be assumed to converge. |
| Change comparison canonicalization/profile so retained evidence may produce a different equality result. | `security_breaking` + `recovery_breaking` | Historical duplicate/effect eligibility may diverge without a proved migration. |
| Retire a historical verifier while affected identities remain replayable/deduplicable. | `recovery_breaking` and possibly `security_breaking` | Retained evidence becomes uninterpretable or unsafe fallback may appear. |
| Replace protected/scoped equivalence evidence with a low-entropy plain digest or global equality lookup. | `security_breaking` | Confidentiality and tenant/consumer isolation are weakened. |
| Increase comparison/KMS lookup work materially. | `capacity_risk` | Crafted duplicates can amplify shared secret-store/comparison cost. |
| Increase worker concurrency without changing schemas. | `capacity_risk` | Provider, database, queue, and tenant isolation may be destabilized. |
| Add outbound webhook behavior before Product approval. | `product_gated` | Reliability cannot invent the feature contract. |

## 8. Change record and workflow

Every proposed change SHALL include:

```text
change_id
affected_reliability_profiles
affected_api_event_data_contracts
classification[]
old_behavior
new_behavior
mixed_version_matrix
authority_and_security_delta
capacity_and_cost_delta
recovery_and_rollback_class
required_fault_vectors
open_decisions
release_blockers
approval_authorities
```

The workflow SHALL be:

1. identify the accepted profile and affected upstream contracts;
2. classify every applicable compatibility dimension;
3. update the semantic manifest and traceability;
4. define mixed-version, failure, security, capacity, and recovery evidence;
5. obtain the owning authorities without substituting AI-generated scores, votes, or vetoes;
6. let Phase 14 define the rollout, pause, abort, rollback, or forward-recovery mechanism;
7. let Phase 15 define operational execution and incident authority.

## 9. Release-blocking conditions

A reliability change is release-blocked when:

- an affected surface lacks a profile version or immutable binding;
- a mixed-version combination is possible but unclassified;
- API/event compatibility is green while reliability behavior is breaking and undeclared;
- authority, revocation, generation, fencing or historical comparison-authority behavior differs without deterministic rejection;
- retry, timeout, acknowledgement, ambiguity or message-equivalence semantics can produce duplicate/orphaned effects or duplicate success without proven equality;
- retained equivalence evidence can become uninterpretable while affected identities remain effect/replay eligible;
- evidence confidentiality/domain separation can regress into low-entropy disclosure, cross-scope equality or authority misuse;
- comparison/KMS/migration work can create unbounded or cross-tenant amplification without evidence;
- overload behavior can create feedback amplification or cross-tenant interference without evidence;
- canonical parsing/admission differences can classify the same logical request/message into different tenant/workload/cost budgets or let a provisional cheaper claim survive final canonical interpretation;
- rollback is claimed safe despite irreversible external effects or recovery/governance discontinuity;
- evidence is missing, weaker than claimed, or not attributable to exact versions;
- a Product-gated capability is introduced without accepted Product authority.

## 10. Downstream boundary

Phase 11 owns the semantic classification. Phase 12 defines the signals that prove behavior; Phase 13 selects and conforms runtime capabilities; Phase 14 owns build/promotion/rollout mechanics; Phase 15 owns operational execution. None may reclassify an accepted reliability-breaking change by tooling convenience.
