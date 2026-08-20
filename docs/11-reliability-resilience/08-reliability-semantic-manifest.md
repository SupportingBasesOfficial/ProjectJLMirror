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
| `authority_refs` | accepted Product/INV/QA/SEC/TM/ADR/System/Data/API/Event references |
| `truth_authority` | durable/current authority proving state/effect/eligibility |
| `criticality` | authority/correctness/confidentiality/durability/blast-radius/recovery dimensions |
| `dependency_set` | hard, async, optional, authority and continuity dependencies |
| `failure_classes` | canonical Phase 11 classes accepted by the profile |
| `degradation_mode` | allowed behavior per failure class |
| `prohibited_fallbacks` | explicit unsafe behavior |
| `identity_policy` | operation/message/delivery/lease/generation identity under retry/failover |
| `deadline_timeout_policy` | stage/overall semantics and ambiguity behavior |
| `retry_policy` | eligibility, aggregate budget, backoff/jitter and terminal path |
| `circuit_policy` | scope, counted failures, open/probe and state-loss behavior |
| `bulkhead_policy` | tenant/workload/provider/destination/cell/privilege isolation |
| `backpressure_policy` | admission, bound, overflow, fairness and drain behavior |
| `ambiguity_policy` | durable states, owner/evidence and retry gate |
| `recovery_policy` | continuity state, `(R,F]`, quarantine/resumption gate |
| `security_privacy` | auth/tenant/secrets/classification/abuse/governance constraints |
| `capacity_cost` | resource dimensions, amplification and evidence-driven bounds |
| `evidence_requirements` | design, implementation, release and runtime evidence separately |
| `fault_vectors` | deterministic/concurrency/chaos/load/recovery cases |
| `compatibility_class` | consequences of changing semantics |
| `release_blockers` | specific blocker identifiers |
| `open_decisions` | owner, evidence, closure gate and non-default rule |

No required field may disappear. If a conditional subdimension has no applicable case, the manifest records `no_applicable_case` plus condition, accepted authority and reviewable evidence.

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
- Each failure class maps to one allowed mode and fault vector.
- Each retryable class maps to stable identity, safety mechanism and aggregate budget.
- Each ambiguity class maps to a reconciliation owner and durable evidence.
- Each recovery profile maps continuity state to a resumption gate.
- Each security-sensitive profile maps relevant `SEC-*`/`TM-*` authorities.
- Each OPEN reference exists in `12-phase-11-open-decisions-and-blockers.md`.
- Each blocker reference exists in the validation matrix or global blocker registry.
- Each compatibility-sensitive field maps to `10-compatibility-and-change-classification.md`.

Dangling references, unknown enums, missing owners or retry without safety mapping are conformance failures.

## Example logical profile

```yaml
reliability_profile_id: provider_call.effectful
profile_version: 1
owning_capability: accepted owning application process
scope: tenant_integration
authority_refs: [QA-AVAIL-001, QA-BULK-001, ADR-013, ADR-017]
truth_authority: stable platform operation plus provider reconciliation authority
failure_classes:
  slow_or_timed_out: reconciliation_blocked
  throttled: queued_or_deferred
  contract_permanent: capability_unavailable
identity_policy: preserve stable operation_id across attempts
retry_policy:
  eligibility: only after classified safe outcome
  aggregate_budget: OPEN-REL-006
bulkhead_policy:
  dimensions: [tenant, integration, provider, operation_class]
recovery_policy:
  continuity: operation outcomes and acknowledgements in (R,F]
  admission: fail_closed_until_reconciled
fault_vectors: [FV-EXT-002]
release_blockers: [RB-REL-008]
```

This is illustrative syntax, not a selected serialization/tool.

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
- vendor/topology name as canonical contract identity;
- evidence claimed at a higher level than produced;
- AI output as protected decision authority, score, veto or eligibility condition.

## Change control

Changes to manifest semantics, enums, retry eligibility, degradation behavior, authority/fence, retention/equivalence horizon or resumption gates receive semantic compatibility review even when serialization shape is unchanged.

Generated artifacts are subordinate to the reviewed normative source. Tooling defaults cannot add a failure class, permissive fallback or retry automatically.
