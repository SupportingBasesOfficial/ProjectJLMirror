# Ambiguity, Reconciliation and Recovery Continuity

**Status:** proposed baseline  
**Phase:** 11 — Reliability & Resilience

## Purpose

This document defines reliability behavior when outcome, identity equivalence, current authority or recovery continuity cannot be proven. It inherits ADR-018, Data Architecture and Phase 09/10 `(R,F]` semantics without turning recovery into ordinary retry. ADR-015 remains the separate authority for secrets and key management where cryptographic continuity is involved. The accepted Phase 10 message-equivalence correction additionally requires retained comparison evidence to remain interpretable under its historical canonical comparison profile/verifier authority.

## Universal rule

```text
uncertainty != absence
timeout != failure proof
lease expiry != effect absence
missing restored state != never executed/published/consumed/used
reachable copy != current authority
retained comparison bytes != proven equivalence when historical interpretation authority is unavailable
```

## Ambiguity classes

| Class | Example | Required owner behavior |
|---|---|---|
| `local_commit_unknown` | response/process lost around local commit | inspect authoritative transaction/result/idempotency state |
| `external_effect_unknown` | provider may have accepted request | reconcile stable operation identity/provider truth |
| `publication_unknown` | broker may have accepted while outbox state rolled back | republish same immutable logical message identity safely |
| `consumer_effect_unknown` | effect may have committed but inbox completion missing | reconcile effect/result authority before execution/duplicate classification |
| `identity_equivalence_unknown` | scoped message ID exists but comparison evidence is missing **or evidence exists while the required historical comparison profile/verifier authority is unavailable, retired, mismatched, rolled back or unknown** | classify the protected path as `recovery_continuity_blocked`; fail/reconciliation block; recover trusted comparison authority or complete an accepted equality-preserving migration |
| `authority_freshness_unknown` | auth/placement/generation state incomplete | deny protected admission until current authority proven |
| `governance_unknown` | erasure/hold status incomplete | no re-exposure; destructive deletion blocked |
| `delivery_unknown` | webhook/artifact bytes may have been disclosed | preserve identity/generation and reconcile; no retarget/re-release |
| `recovery_boundary_unknown` | `F` or continuity inventory incomplete | scope remains recovery-quarantined |

A compromised/untrusted comparison implementation, profile or verifier is not merely unavailable evidence. It is `compromised_or_untrusted` and fails closed under the affected comparison path until independently accountable authority establishes a trusted disposition.

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

For duplicate-sensitive message reconciliation, the record additionally preserves or references the accepted comparison evidence/profile generation required to prove historical semantic equality without exposing confidential comparison material as an operator oracle.

## Reconciliation authority

The owning domain/process decides business outcome. Generic infrastructure may collect evidence or pause work but SHALL NOT declare that an irreversible effect did/did not happen.

For message equivalence, a KMS/secret service can provide narrowly authorized historical verification material but does not decide duplicate/effect eligibility. The consumer/recovery contract decides eligibility from the accepted scoped identity plus verified comparison result.

AI-assisted diagnostics may propose hypotheses or identify evidence gaps only. Its output cannot grant, deny, score or determine retry, recovery, redrive, release, authorization or incident eligibility at any stage.

## Quarantine

Quarantine is durable responsibility, not successful completion and not a vendor DLQ synonym.

Quarantine SHALL preserve safe identity, owner, failure/ambiguity class, required evidence, current remediation state, data classification and retention. Full confidential payload retention is minimized and governed.

Message-equivalence quarantine may retain governed profile/generation references and safe failure reason classes but does not expose unrestricted fingerprints/MACs, conflicting confidential payloads or verifier material to ordinary operators.

Redrive requires current privileged authority, current placement/tenant scope, contract compatibility, duplicate/effect/content-equivalence reconciliation, current destination/source generation eligibility, audited decision and capacity admission.

## Recovery interval

For recovery point `R` and later authoritative boundary `F`:

```text
(R,F] = continuity interval
```

The recovery manifest separates rollback-subject business/domain state from continuity state that survives/reconciles forward.

Continuity state includes as applicable inbox/dedup and content-equivalence evidence; the canonical comparison-profile/version and non-secret historical verifier/key-generation reference required to interpret that evidence; narrowly authorized historical verification authority where the selected evidence form requires it; idempotency claims/results; outbox/publication identities; process/operation/external outcomes; webhook obligation/destination fences; producer/source/replay generations; immutable audit; revocations; placement generations; erasure/hold/crypto-erasure decisions; and artifact lifecycle/delivery/governance generations.

Retaining an uninterpretable fingerprint/MAC is not continuity. Restoring an obsolete verifier does not make it current authority for unrelated messages/scopes.

## Recovery quarantine and admission

A restored scope remains non-authoritative for protected/effectful work until:

1. `R` is known;
2. `F` is fenced or reconstructed from surviving durable authorities;
3. affected identities/effects/authorities in `(R,F]` are inventoried;
4. current authorization/placement/governance generations are proven non-regressed;
5. ambiguous effects are completed, compensated, quarantined or made retry-eligible by the owner;
6. duplicate/content-equivalence evidence covers the supported horizon **and the historical comparison profile/verifier authority required to interpret it is available/trusted or an accepted equality-preserving migration proves the same equality result**;
7. stale source/replay/destination/delivery generations are retired;
8. tenant isolation and cryptographic usability/erasure intent are validated without reviving obsolete verifier authority outside its historical evidence generation;
9. accepted customer-observation identities, acceptance/projection watermarks, monotonic current-state tokens and pending transition/signal intents are reconciled where the recovered scope includes customer telemetry;
10. explicit admission evidence is durably recorded.

Starting a database, passing schema checks, restoring an offset, restoring a key object or observing liveness is insufficient.

## Failover authority

Failover is an authority transition, not traffic redirection alone. It SHALL preserve one current writer/admission generation, stale-writer fencing, in-flight work classification, stable identities, placement consistency, current security/governance deny state, generation retirement and recovery quarantine where continuity cannot be proven.

Active-active, active-passive, quorum, consensus, fencing token and regional topology remain OPEN. No mechanism is acceptable if it permits split authoritative state.

## Relocation interaction

Normal and recovery-driven tenant relocation inherit accepted source fence/target admission semantics. Target effectful work starts only after required inbox/idempotency/process/security/governance continuity is present. Source realtime subscriptions and worker/scheduler authority tied to the retired placement generation stop within accepted evidence-driven bounds.

Where duplicate-sensitive inbox evidence moves or is restored across the transition, its canonical comparison-profile/version and required historical verifier authority remain bound to the evidence generation. Relocation cannot silently recompute old equality under a new profile.

After target accepts writes, rollback is not a pointer flip; use forward recovery or controlled reverse relocation.

## Stateful vs stateless recovery

Process memory is never durable truth. A stateless runtime may restart freely only because authoritative state, idempotency, leases/fences and process ownership survive elsewhere.

Stateful recovery classifies authoritative data, derived/rebuildable data, continuity evidence, ephemeral protection state, generation/leadership authority, encryption dependencies and admission state.

Rebuild of derived state uses isolated generation/target where production dedup or current projections could otherwise be corrupted.

## Convergence

Every reconciliation profile defines an evidence-based convergence criterion, unresolved cases, safe partial-resumption scope and full-admission blockers. Numeric objectives remain OPEN for Phase 12/Operations evidence.

For message-equivalence continuity, convergence means the same historical equality result can be established under the accepted retained profile/verifier authority (or a reviewed equality-preserving migration), not merely that a key service or evidence store is reachable.

## Required fault vectors

- crash before/after local commit and before response;
- provider acceptance with lost response;
- outbox publish accepted but local state rolled back;
- inbox effect survives but receipt/fingerprint rolls back;
- same scoped message ID conflicts after PITR;
- comparison evidence survives while its required historical comparison profile/verifier is unavailable, retired, mismatched or restored older;
- comparison-profile/key rotation crosses restore and historical equality must remain reproducible or the path remains reconciliation-blocked;
- restored obsolete verifier/profile is presented for unrelated current work and is rejected as authority;
- crafted duplicate identities attempt to create unbounded comparison/KMS work and remain bounded/tenant-scoped;
- stale producer/replay/destination generation restored;
- tenant/cell restore with post-`R` revocations and effects;
- failover while old writer remains reachable;
- relocation with active worker/realtime source authority;
- artifact delivery/erasure active across restore;
- legal hold or erasure decision after `R` missing from snapshot;
- incomplete `F` due to loss of prior authority.

`14-message-equivalence-reliability-continuity.md` makes the comparison-specific branches mandatory extensions of `FV-ASYNC-003` and binds them to existing blockers.

## Release blockers

Release/recovery is blocked if ambiguity expires into retry, failover permits two writers, recovery resumes before continuity reconciliation, missing/uninterpretable equivalence or historical comparison authority becomes duplicate success/effect eligibility, a restored obsolete verifier becomes unrelated current authority, deny/governance generations regress, or an old destination/source/delivery generation regains authority.
