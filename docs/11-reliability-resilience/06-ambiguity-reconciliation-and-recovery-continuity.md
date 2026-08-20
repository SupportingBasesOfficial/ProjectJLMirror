# Ambiguity, Reconciliation and Recovery Continuity

**Status:** proposed baseline  
**Phase:** 11 — Reliability & Resilience

## Purpose

This document defines reliability behavior when outcome, identity equivalence, current authority or recovery continuity cannot be proven. It inherits ADR-018, Data Architecture and Phase 09/10 `(R,F]` semantics without turning recovery into ordinary retry. ADR-015 remains the separate authority for secrets and key management where cryptographic continuity is involved.

## Universal rule

```text
uncertainty != absence
timeout != failure proof
lease expiry != effect absence
missing restored state != never executed/published/consumed/used
reachable copy != current authority
```

## Ambiguity classes

| Class | Example | Required owner behavior |
|---|---|---|
| `local_commit_unknown` | response/process lost around local commit | inspect authoritative transaction/result/idempotency state |
| `external_effect_unknown` | provider may have accepted request | reconcile stable operation identity/provider truth |
| `publication_unknown` | broker may have accepted while outbox state rolled back | republish same immutable logical message identity safely |
| `consumer_effect_unknown` | effect may have committed but inbox completion missing | reconcile effect/result authority before execution/duplicate classification |
| `identity_equivalence_unknown` | scoped message ID exists but comparison evidence missing | fail closed; recover fingerprint/original/equivalent evidence |
| `authority_freshness_unknown` | auth/placement/generation state incomplete | deny protected admission until current authority proven |
| `governance_unknown` | erasure/hold status incomplete | no re-exposure; destructive deletion blocked |
| `delivery_unknown` | webhook/artifact bytes may have been disclosed | preserve identity/generation and reconcile; no retarget/re-release |
| `recovery_boundary_unknown` | `F` or continuity inventory incomplete | scope remains recovery-quarantined |

## Ambiguity state machine

Every effectful ambiguous operation uses durable state equivalent to:

```text
attempt_eligible
  -> attempting
  -> completed | failed_terminal
  -> ambiguity_detected
       -> reconciling
       -> completed | attempt_eligible | compensated | quarantined
```

No time-based transition from `ambiguity_detected` to `attempt_eligible` is allowed without authoritative reconciliation evidence. State names are implementation choices; the eligibility constraint is fixed.

## Stable operation identity

External/cross-authority effects SHALL establish a stable platform `operation_id` or equivalent before the ambiguous boundary. Provider-side idempotency identity may support reconciliation but does not replace platform identity.

Reconciliation records owner and tenant scope, original operation/message/delivery identity, immutable semantic request evidence, target authority/generation, attempt evidence, authoritative receipts, decision, retry/compensation eligibility, current authorization/governance context and audit/correlation.

## Reconciliation authority

The owning domain/process decides business outcome. Generic infrastructure may collect evidence or pause work but SHALL NOT declare that an irreversible effect did/did not happen.

AI-assisted diagnostics may propose hypotheses or identify evidence gaps only. Its output cannot grant, deny, score or determine retry, recovery, redrive, release, authorization or incident eligibility at any stage.

## Quarantine

Quarantine is durable responsibility, not successful completion and not a vendor DLQ synonym.

Quarantine SHALL preserve safe identity, owner, failure/ambiguity class, required evidence, current remediation state, data classification and retention. Full confidential payload retention is minimized and governed.

Redrive requires current privileged authority, current placement/tenant scope, contract compatibility, duplicate/effect/content-equivalence reconciliation, current destination/source generation eligibility, audited decision and capacity admission.

## Recovery interval

For recovery point `R` and later authoritative boundary `F`:

```text
(R,F] = continuity interval
```

The recovery manifest separates rollback-subject business/domain state from continuity state that survives/reconciles forward.

Continuity state includes as applicable inbox/dedup and content-equivalence evidence; idempotency claims/results; outbox/publication identities; process/operation/external outcomes; webhook obligation/destination fences; producer/source/replay generations; immutable audit; revocations; placement generations; erasure/hold/crypto-erasure decisions; and artifact lifecycle/delivery/governance generations.

## Recovery quarantine and admission

A restored scope remains non-authoritative for protected/effectful work until:

1. `R` is known;
2. `F` is fenced or reconstructed from surviving durable authorities;
3. affected identities/effects/authorities in `(R,F]` are inventoried;
4. current authorization/placement/governance generations are proven non-regressed;
5. ambiguous effects are completed, compensated, quarantined or made retry-eligible by the owner;
6. duplicate/content-equivalence evidence covers the supported horizon;
7. stale source/replay/destination/delivery generations are retired;
8. tenant isolation and cryptographic usability/erasure intent are validated;
9. accepted customer-observation identities, acceptance/projection watermarks, monotonic current-state tokens and pending transition/signal intents are reconciled where the recovered scope includes customer telemetry;
10. explicit admission evidence is durably recorded.

Starting a database, passing schema checks, restoring an offset or observing liveness is insufficient.

## Failover authority

Failover is an authority transition, not traffic redirection alone. It SHALL preserve one current writer/admission generation, stale-writer fencing, in-flight work classification, stable identities, placement consistency, current security/governance deny state, generation retirement and recovery quarantine where continuity cannot be proven.

Active-active, active-passive, quorum, consensus, fencing token and regional topology remain OPEN. No mechanism is acceptable if it permits split authoritative state.

## Relocation interaction

Normal and recovery-driven tenant relocation inherit accepted source fence/target admission semantics. Target effectful work starts only after required inbox/idempotency/process/security/governance continuity is present. Source realtime subscriptions and worker/scheduler authority tied to the retired placement generation stop within accepted evidence-driven bounds.

After target accepts writes, rollback is not a pointer flip; use forward recovery or controlled reverse relocation.

## Stateful vs stateless recovery

Process memory is never durable truth. A stateless runtime may restart freely only because authoritative state, idempotency, leases/fences and process ownership survive elsewhere.

Stateful recovery classifies authoritative data, derived/rebuildable data, continuity evidence, ephemeral protection state, generation/leadership authority, encryption dependencies and admission state.

Rebuild of derived state uses isolated generation/target where production dedup or current projections could otherwise be corrupted.

## Convergence

Every reconciliation profile defines an evidence-based convergence criterion, unresolved cases, safe partial-resumption scope and full-admission blockers. Numeric objectives remain OPEN for Phase 12/Operations evidence.

## Required fault vectors

- crash before/after local commit and before response;
- provider acceptance with lost response;
- outbox publish accepted but local state rolled back;
- inbox effect survives but receipt/fingerprint rolls back;
- same scoped message ID conflicts after PITR;
- stale producer/replay/destination generation restored;
- tenant/cell restore with post-`R` revocations and effects;
- failover while old writer remains reachable;
- relocation with active worker/realtime source authority;
- artifact delivery/erasure active across restore;
- legal hold or erasure decision after `R` missing from snapshot;
- incomplete `F` due to loss of prior authority.

## Release blockers

Release/recovery is blocked if ambiguity expires into retry, failover permits two writers, recovery resumes before continuity reconciliation, missing equivalence becomes duplicate success, deny/governance generations regress, or an old destination/source/delivery generation regains authority.
