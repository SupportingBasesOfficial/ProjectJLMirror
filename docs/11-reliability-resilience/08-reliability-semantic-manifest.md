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
| `open_decisions` | applicable OPEN identifiers with owner, evidence, closure gate and non-default rule |

For `rel.consumer-inbox-effect@1` and duplicate-sensitive `rel.replay-consume-state@1`, the manifest additionally SHALL materialize the normalized Phase-10-derived dimensions defined in `14-message-equivalence-reliability-continuity.md`:

```text
message_equivalence_comparison_authority
message_equivalence_failure_binding
message_equivalence_security_capacity_policy
message_equivalence_recovery_continuity
message_equivalence_compatibility_policy
```

Where a keyed/authenticated evidence form is selected, `rel.secret-key-authority@1` SHALL materialize the historical-verifier generation scope and the rule that historical verification authority does not become unrelated current cryptographic/effect authority.

No required field may disappear. If a conditional subdimension has no applicable case, the manifest records `no_applicable_case` plus condition, accepted authority and reviewable evidence.

The canonical catalog MAY be normalized across multiple tables only when every table is keyed by the exact pair `reliability_profile_id` and `profile_version`. The join of those tables is one manifest record and SHALL materialize every required field exactly once for every key. `status` and applicable operation/contract/runtime-role classes SHALL be keyed profile data; document status or headings cannot supply them. Implicit defaults, narrative inheritance and unresolved policy references are forbidden. A named policy reference is valid only when its complete value is defined in the same accepted package and the profile row selects it explicitly.

For ordinary profiles, the base logical records are materialized in `07-capability-resilience-profiles.md`. For the exact duplicate-sensitive/profile-verifier dimensions above, the complete record is the same-key normalized join of `07` plus `14-message-equivalence-reliability-continuity.md`; `14` does not redefine unrelated `07` fields.

Deterministic derived fields are permitted only through the exact formulas defined in the normative Phase 11 catalog/normalized companions. `ALL-FAULT-VECTORS(profile_key)` SHALL include binding-, profile-, circuit- and cross-profile vectors, including mandatory `FV-ASYNC-003` equivalence-continuity branches from `14` for applicable profiles. `ALL-RELEASE-BLOCKERS(profile_key)` SHALL include the canonical blocker of every final vector. `ALL-OPEN-DECISIONS(profile_key)` SHALL include profile-specific and cross-profile OPENs plus `OPEN-REL-007` only through `CIRCUIT-OPEN(profile_key)` when the exact circuit selector has a non-empty applicable failure-class set. `evidence_requirements` SHALL cover the entire final vector set; a profile-specific seed list cannot replace these derived fields.

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

Message-equivalence verifier/profile problems do not create a new enum. For duplicate-sensitive effect/replay eligibility:

- a required historical verifier dependency that is temporarily unreachable while evidence/profile continuity remains intact is `unavailable` and maps to `reconciliation_blocked`;
- missing, rolled-back, mismatched, uninterpretable or retired-without-valid-migration comparison evidence/profile/verifier-generation continuity is `recovery_continuity_blocked` and maps to `reconciliation_blocked`;
- compromised/untrusted comparison authority is `compromised_or_untrusted` and maps to `fail_closed`.

Reachability restoration can clear only the `unavailable` condition after the same historical authority successfully proves equivalence; it does not by itself repair a continuity or trust defect.

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
- Every circuit policy uses only canonical failure-class/degradation enums, and each selecting profile materializes exact counted classes, exclusion of every other class, open mapping and fallback authority. Conditional prose such as “as applicable” is invalid. A profile with `no_applicable_case` SHALL select a dedicated negative-evidence branch, SHALL NOT inherit vectors whose trigger requires circuit open, half-open or probes, and SHALL NOT include `OPEN-REL-007` in its final `ALL-OPEN-DECISIONS`. A profile with a non-empty counted circuit-failure set SHALL include `OPEN-REL-007` through `CIRCUIT-OPEN(profile_key)` until that circuit implementation decision is validly closed.
- Each ambiguity class maps to a reconciliation owner and durable evidence.
- Each recovery profile maps continuity state to a resumption gate.
- Each security-sensitive profile maps relevant `SEC-*`/`TM-*` authorities.
- Each final OPEN reference exists in `12-phase-11-open-decisions-and-blockers.md`, is applicable to the selected profile state, and has accountable owner/evidence/closure gate. An OPEN cannot be inherited merely because a universal selector mentions its category.
- Each blocker reference exists in the validation matrix or global blocker registry.
- Each evidence record uses only `satisfied`, `open`, or evidence-backed `no_applicable_case` as its `blocker_disposition`. An applicable blocker remains `open` until accepted satisfaction evidence exists. `waived`, `override`, inferred pass and any equivalent unrecognized disposition are invalid unless a future accepted upstream governance change explicitly creates such a class; Phase 11 itself creates no waiver authority.
- Each compatibility-sensitive field maps to `10-compatibility-and-change-classification.md`.
- Each profile key materializes `status` and exact applicable operation/contract/runtime-role classes.
- Each final fault vector is present in all four evidence levels and contributes its canonical blocker to the final release-blocker set.
- Optional operational telemetry, durably accepted customer observations and mandatory audit use distinct profile keys; no loss, shedding or fallback rule may cross an acceptance boundary by data-plane naming alone.
- For Control Plane placement fallback, `placement_fallback_state` has exactly `verified_unexpired_lease_and_destination_admitted` and `fallback_ineligible`. Only the first permits `stale_tolerant` for bounded already-admitted traffic; missing, expired, unverifiable or contradicted lease/admission evidence yields `fallback_ineligible:fail_closed`.
- Every other state-qualified binding uses the closed selector/value sets materialized in `07-capability-resilience-profiles.md` for placement-cache fallback, Product-authorized stale reads/results, configuration last-known-good, outbox intent commitment, provider durable-path eligibility and privileged recovery reservation. A selector value missing accepted scoped authority evidence takes its explicitly restrictive branch; no unlisted/unknown value is permitted. Placement-cache fallback ineligibility is `fail_closed`. Privileged `inside_accepted_reservation` additionally requires an accepted `OPEN-REL-010` disposition for the same role/workload scope; otherwise only `outside_accepted_reservation` is valid.
- For durably accepted customer observations, `acceptance_state` has exactly `not_durably_accepted` and `durably_accepted`, derived from the canonical durable-acceptance record for the same scoped identity. Saturation before acceptance maps to `shed_or_reject` without acknowledgement; saturation after acceptance maps to `queued_or_deferred` for the bounded projection obligation and cannot discard or reject accepted work.
- Every materialized `deadline_timeout_policy` selects `OPEN-REL-005` through the exact cross-profile OPEN join; numeric deadlines cannot come from framework, provider or runtime defaults.
- A terminal trust or permanent-contract class SHALL NOT inherit ordinary circuit half-open probing or circuit-driven re-enablement. Any trust restoration is an independently authorized transition backed by accepted evidence.
- A profile whose physical durability mechanism remains OPEN SHALL select mechanism-neutral circuit/evidence records; topology-specific broker, outbox, journal, stream or store vectors become mandatory only after the owning OPEN closes that mechanism.
- Reliability admission and cost/budget classification SHALL inherit the exact accepted Phase 09/10 canonical interpretation. Unvalidated payload text, aliases, duplicate members, malformed encodings, caller-selected tenant/source fields, claimed operation names, or attacker-controlled cost hints SHALL NOT select a cheaper budget, another tenant scope, a privileged workload class, or broader admission authority. A conservative pre-validation claim may use only transport facts or already-trusted canonical metadata.
- When final canonical interpretation resolves a different resource/cost class from a provisional claim, the implementation SHALL atomically acquire/adjust to the authoritative budget or reject before expensive/effectful continuation. Continuing under an underpriced provisional claim, maintaining two semantic parsers, or using budget classification as authorization is prohibited.
- For `rel.consumer-inbox-effect@1` and duplicate-sensitive replay, a benign `duplicate` requires the trusted scoped identity plus proven equivalent immutable content under the accepted historical comparison profile. Temporary historical-verifier outage maps to `unavailable:reconciliation_blocked`; continuity loss maps to `recovery_continuity_blocked:reconciliation_blocked`; compromised comparison authority maps to `compromised_or_untrusted:fail_closed`.
- Message-equivalence comparison occurs only after trusted scoped identity derivation. Fingerprint/MAC/profile references SHALL NOT become authorization, routing, ordering, public identity, reverse lookup or cross-tenant/cross-consumer equality authority.
- Comparison/profile/KMS/migration work is bounded and attributable under `OPEN-REL-022`; mechanism selection remains `OPEN-REL-016` where keyed verifier material is required; evidence horizon remains `OPEN-REL-025`.

Dangling references, unknown enums, missing owners, inapplicable OPEN inheritance or retry without safety mapping are conformance failures.

## Canonical record location and serialization boundary

The complete logical records are materialized in `07-capability-resilience-profiles.md` plus the mandatory normalized companion `14-message-equivalence-reliability-continuity.md` for its explicitly applicable profile dimensions. A future YAML, JSON, schema or generated representation SHALL encode the complete normalized join for a profile key; a partial illustrative record is deliberately not normative and SHALL NOT be used as a template. Serialization/tool choice remains OPEN.

## Static governance checks

Future conformance tooling SHALL reject:

- retryable failure without identity/safety/budget;
- authority-critical profile with a permissive fallback;
- `stale_tolerant` without freshness authority/prohibited operations;
- queue/backlog without bound/overflow/owner;
- ambiguity without durable reconciliation state;
- failover without generation/fence and stale-writer rejection;
- recovery without `(R,F]` continuity/resumption gate;
- duplicate-sensitive effect/replay profile missing protected comparison evidence, stable comparison-profile/version, required historical verifier lifecycle or fail-closed unknown-equivalence behavior;
- temporary verifier outage, continuity loss and compromised verifier trust collapsed into one permissive retry/default class;
- duplicate classification based only on scoped identity when immutable semantic equality has not been proven;
- low-entropy confidential comparison evidence exposed through unsafe plain-digest logging/export, or any unrestricted cross-scope fingerprint/equality oracle;
- historical verifier/profile loss, retirement, rollback or mismatch becoming duplicate success, replay/effect eligibility or unrelated current authority;
- crafted duplicate/equality inputs creating unbounded comparison/KMS/secret-store/migration work;
- secret-bearing ordinary payload/telemetry/quarantine policy;
- missing tenant/provider/destination isolation;
- unsupported numeric literal replacing an OPEN decision;
- numeric deadline policy without exact `OPEN-REL-005` ownership;
- `no_applicable_case` circuit selector inheriting an open/half-open/probe vector or `OPEN-REL-007`;
- applicable non-empty circuit selector missing `OPEN-REL-007` from final `ALL-OPEN-DECISIONS`;
- final OPEN reference that lacks registry owner/evidence/gate or contradicts profile applicability;
- evidence with `blocker_disposition=waived`, an unknown disposition, an applicable blocker marked `no_applicable_case`, or a blocker marked `satisfied` without accepted attributable evidence;
- admission/budget scope or cost class derived from non-canonical or untrusted structured payload semantics, parser aliases/duplicates, caller-controlled tenant/source/operation claims, or an alternate normalization path;
- provisional pre-validation budget retained after canonical interpretation requires a different authoritative class, or expensive/effectful continuation before the authoritative claim is acquired;
- vendor/topology name as canonical contract identity;
- evidence claimed at a higher level than produced;
- acknowledged customer observation without durable scoped identity/responsibility, or optional-loss behavior applied after durable acceptance;
- AI output as protected decision authority, score, veto or eligibility condition.

## Change control

Changes to manifest semantics, enums, retry eligibility, degradation behavior, admission/cost-class derivation, authority/fence, retention/equivalence horizon, message-equivalence evidence confidentiality/domain separation, comparison-profile/version, historical verifier lifecycle, blocker-disposition semantics or resumption gates receive semantic compatibility review even when serialization shape is unchanged.

Generated artifacts are subordinate to the reviewed normative source. Tooling defaults cannot add a failure class, permissive fallback, blocker waiver or retry automatically.
