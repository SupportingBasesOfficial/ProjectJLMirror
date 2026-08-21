# Reliability Semantic Manifest

**Status:** proposed baseline  
**Phase:** 11 — Reliability & Resilience

## Purpose

This document defines mandatory machine/enforcement-oriented metadata for every implementable reliability profile. A future YAML/JSON/catalog representation MAY implement it; field semantics are normative and vendor-neutral.

## Manifest identity

Every profile has stable identity:

```text
reliability_profile_id
profile_version
owning_capability
applicable operation/contract/runtime-role classes
tenant/global scope
authority references
status: proposed | accepted | superseded
```

Runtime instance, queue, topic, cell, region, provider product or deployment name is not canonical profile identity.

## Required fields

| Field | Requirement |
|---|---|
| `owning_capability` | logical accountable capability; named operational ownership remains Phase 15 |
| `scope` | tenant/cell/provider/destination/workload/global dimensions governed by the record |
| `authority_refs` | accepted Product/INV/QA/SEC/TM/ADR/System/Data/API/Event references |
| `truth_authority` | durable/current authority proving state/effect/eligibility |
| `criticality` | authority/correctness/confidentiality/durability/blast-radius/recovery dimensions |
| `dependency_set` | hard, async, optional, authority and continuity dependencies |
| `failure_classes` | canonical Phase 11 classes accepted by the profile |
| `degradation_mode` | allowed behavior per failure class |
| `prohibited_fallbacks` | explicit unsafe behavior |
| `identity_policy` | operation/message/delivery/lease/generation identity under retry/failover |
| `deadline_timeout_policy` | stage/overall semantics and ambiguity behavior |
| `retry_policy` | eligibility/safety, aggregate attempt/elapsed/concurrency/bytes/cost budget, backoff, jitter and terminal path |
| `circuit_policy` | protected scope, counted/excluded failures, open behavior, probe concurrency, retry/backlog interaction, state-loss behavior, fallback authority, evidence and numeric OPENs |
| `bulkhead_policy` | tenant/workload/provider/destination/cell/privilege isolation |
| `backpressure_policy` | admission, bound, overflow, fairness and drain behavior |
| `ambiguity_policy` | durable states, owner/evidence and retry gate |
| `recovery_policy` | continuity state, `(R,F]`, quarantine/resumption gate |
| `security_privacy` | auth/tenant/secrets/classification/abuse/governance constraints |
| `capacity_cost` | resource dimensions, amplification, evidence-driven bounds and exact OPEN owner for every unresolved numeric envelope/trigger |
| `evidence_requirements` | design, implementation, release and runtime evidence separately |
| `fault_vectors` | deterministic/concurrency/chaos/load/recovery cases |
| `compatibility_class` | consequences of changing semantics |
| `release_blockers` | specific blocker identifiers |
| `open_decisions` | owner, evidence, closure gate and non-default rule |

No required field may disappear. If a conditional subdimension has no applicable case, the manifest records `no_applicable_case` plus condition, accepted authority and reviewable evidence.

The canonical catalog MAY be normalized across multiple tables only when every table is keyed by the exact pair `reliability_profile_id` and `profile_version`. The join of those tables is one manifest record and SHALL materialize every required field exactly once for every key. `status` and applicable operation/contract/runtime-role classes SHALL be keyed profile data; document status or headings cannot supply them. Implicit defaults, narrative inheritance and unresolved policy references are forbidden. A named policy reference is valid only when its complete value is defined in the same accepted package and the profile row selects it explicitly.

Deterministic derived fields are permitted only through the exact formulas defined in `07-capability-resilience-profiles.md`. `ALL-FAULT-VECTORS(profile_key)` SHALL include binding-, profile-, circuit- and cross-profile vectors. `ALL-RELEASE-BLOCKERS(profile_key)` SHALL include the canonical blocker of every final vector. `evidence_requirements` SHALL cover the entire final vector set; a profile-specific seed list cannot replace these derived fields.

## Canonical enums

### Failure classes

```text
unavailable
slow_or_timed_out
throttled
saturated
partitioned
stale
duplicate
identity_conflict
out_of_order_or_gap
contract_permanent
policy_denied
poison_or_unknown
external_outcome_ambiguous
recovery_continuity_blocked
compromised_or_untrusted
governance_blocked
```

### Degradation modes

```text
fail_closed
fail_fast
stale_tolerant
queued_or_deferred
shed_or_reject
reconciliation_blocked
resync_required
capability_unavailable
```

### Evidence levels

```text
design_acceptance
implementation_conformance
release_evidence
runtime_evidence
```

These are the single canonical evidence-level enums for the Phase 11 package and are defined semantically in `09-reliability-validation-and-fault-matrix.md`. Document acceptance supplies only `design_acceptance` evidence.

## Referential rules

- Each capability/dependency map row references at least one manifest profile.
- Each failure-class binding maps to exactly one allowed mode and at least one fault vector for every materialized operation state. If an accepted boundary changes the mode, the profile SHALL name a closed, machine-evaluable state selector and one exact mode for every selector value; prose conditions or implementation-local state are invalid.
- Each retryable class maps to stable identity, safety mechanism and aggregate budget.
- Every retry policy materializes attempts, elapsed time, concurrency, queued count, bytes and attributable cost; it also records speculation and redrive as bounded or as `no_applicable_case` with a condition. Bare `OPEN` aliases are invalid: every unresolved numeric/backoff/jitter value names its exact `OPEN-REL-*` owner.
- Every circuit policy uses only canonical failure-class/degradation enums, and each selecting profile materializes exact counted classes, exclusion of every other class, open mapping and fallback authority. Conditional prose such as “as applicable” is invalid. A profile with `no_applicable_case` SHALL select a dedicated negative-evidence branch and SHALL NOT inherit vectors whose trigger requires circuit open, half-open or probes.
- Each ambiguity class maps to a reconciliation owner and durable evidence.
- Each recovery profile maps continuity state to a resumption gate.
- Each security-sensitive profile maps relevant `SEC-*`/`TM-*` authorities.
- Each OPEN reference exists in `12-phase-11-open-decisions-and-blockers.md`.
- Each blocker reference exists in the validation matrix or global blocker registry.
- Each compatibility-sensitive field maps to `10-compatibility-and-change-classification.md`.
- Each profile key materializes `status` and exact applicable operation/contract/runtime-role classes.
- Each final fault vector is present in all four evidence levels and contributes its canonical blocker to the final release-blocker set.
- Optional operational telemetry, durably accepted customer observations and mandatory audit use distinct profile keys; no loss, shedding or fallback rule may cross an acceptance boundary by data-plane naming alone.
- For Control Plane placement fallback, `placement_fallback_state` has exactly `verified_unexpired_lease_and_destination_admitted` and `fallback_ineligible`. Only the first permits `stale_tolerant` for bounded already-admitted traffic; missing, expired, unverifiable or contradicted lease/admission evidence yields `fallback_ineligible:fail_closed`.
- Every other state-qualified binding uses the closed selector/value sets materialized in `07-capability-resilience-profiles.md` for placement-cache fallback, Product-authorized stale reads/results, configuration last-known-good, outbox intent commitment, provider durable-path eligibility and privileged recovery reservation. A selector value missing accepted scoped authority evidence takes its explicitly restrictive branch; no unlisted/unknown value is permitted.
- For durably accepted customer observations, `acceptance_state` has exactly `not_durably_accepted` and `durably_accepted`, derived from the canonical durable-acceptance record for the same scoped identity. Saturation before acceptance maps to `shed_or_reject` without acknowledgement; saturation after acceptance maps to `queued_or_deferred` for the bounded projection obligation and cannot discard or reject accepted work.
- Every materialized `deadline_timeout_policy` selects `OPEN-REL-005` through the exact cross-profile OPEN join; numeric deadlines cannot come from framework, provider or runtime defaults.
- A terminal trust or permanent-contract class SHALL NOT inherit ordinary circuit half-open probing or circuit-driven re-enablement. Any trust restoration is an independently authorized transition backed by accepted evidence.
- A profile whose physical durability mechanism remains OPEN SHALL select mechanism-neutral circuit/evidence records; topology-specific broker, outbox, journal, stream or store vectors become mandatory only after the owning OPEN closes that mechanism.

Dangling references, unknown enums, missing owners or retry without safety mapping are conformance failures.

## Canonical record location and serialization boundary

The complete logical records are materialized in `07-capability-resilience-profiles.md`. A future YAML, JSON, schema or generated representation SHALL encode the complete normalized join for a profile key; a partial illustrative record is deliberately not normative and SHALL NOT be used as a template. Serialization/tool choice remains OPEN.

## Static governance checks

Future conformance tooling SHALL reject:

- retryable failure without identity/safety/budget;
- authority-critical profile with a permissive fallback;
- `stale_tolerant` without freshness authority/prohibited operations;
- queue/backlog without bound/overflow/owner;
- ambiguity without durable reconciliation state;
- failover without generation/fence and stale-writer rejection;
- recovery without `(R,F]` continuity/resumption gate;
- secret-bearing ordinary payload/telemetry/quarantine policy;
- missing tenant/provider/destination isolation;
- unsupported numeric literal replacing an OPEN decision;
- numeric deadline policy without exact `OPEN-REL-005` ownership;
- `no_applicable_case` circuit selector inheriting an open/half-open/probe vector;
- vendor/topology name as canonical contract identity;
- evidence claimed at a higher level than produced;
- acknowledged customer observation without durable scoped identity/responsibility, or optional-loss behavior applied after durable acceptance;
- AI output as protected decision authority, score, veto or eligibility condition.

## Change control

Changes to manifest semantics, enums, retry eligibility, degradation behavior, authority/fence, retention/equivalence horizon or resumption gates receive semantic compatibility review even when serialization shape is unchanged.

Generated artifacts are subordinate to the reviewed normative source. Tooling defaults cannot add a failure class, permissive fallback or retry automatically.
