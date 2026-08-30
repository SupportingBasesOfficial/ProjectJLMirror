# D2 / OPEN-REL-030 — Bounded Conformance Evidence

This directory contains the governed C2 evidence package for `OPEN-REL-030`.

It is an **evidence-generating implementation decision**, not the Monitoring production implementation. It does not grant production authority, accept/close the OPEN, authorize Wave 4, select production capacity numerics, select production identity/KMS/HSM, or freeze a production cross-authority transport/database-authentication topology.

## Governed state

```text
Evidence state              complete_ready_for_decision_review
Closure claim               false
Track B acceptance          not_granted
Wave 4 authorization        not_granted
Production authority        none
Production versions         not selected
Production capacity         OPEN-REL-020
Material finding classes    50
History hardening modules   6 (004–009)
Merge                       not authorized
```

## Exact empirical anchor

The current mechanism anchor before the latest governance-only promotion is:

```text
68938d0f02efaf1cc6ee23a288beedeae8d14214
Deterministic Assurance #2237 — SUCCESS — run id 33282676657
OPEN-REL-030 Conformance #186 — SUCCESS — run id 33282676651
```

#186 verifies the exact SHA, executes all mandatory vectors, all six history hardening modules, physical PITR/recovery, the post-enrollment clone vector, Timescale restore/jobs and Tier1↔Tier2 relocation, then ends with `open_rel_030_extended_conformance=PASS` and `closure_claim=false`.

## Evidence architecture

### Tier 1 transactional acceptance

Tier 1 proves immutable canonical observation identity/content, owner-controlled active source generation and poll authority, durable live poll claim, and current-state CAS based on platform ordering authority.

### Owner-current history / late data

History reconciliation is intentionally fail-closed:

- coverage is contiguous from `supported_history_floor`;
- only runs matching the exact current `authority_generation`, exact `provider_dataset_revision` and owner-required snapshot currentness count;
- provider-visible INSERT/UPDATE advances dataset revision and invalidates current coverage atomically;
- stable identity rewrite, DELETE and TRUNCATE fail closed;
- accepted stable identities are checked against owner-current canonical content independently of current `became_visible_at`;
- retained `finalized_through` is historical authority and must be revalidated under the current dataset revision before `complete` can return;
- `try_finalize(..., NULL)` is malformed authority input and fails closed with SQLSTATE `22004`; it cannot mint `complete` or a NULL completeness watermark;
- all existing `00[4-9]_history_*.sql` modules must be present in the extended runner.

The current ordered history chain is:

```text
004_history_reconciliation.sql
005_history_identity_window_hardening.sql
006_history_dataset_revision_hardening.sql
007_history_dataset_revision_edge_hardening.sql
008_history_visibility_correction_hardening.sql
009_history_retained_finalized_watermark_hardening.sql
```

### #49 — retained finalized watermark

After a stream has historically finalized through T2, a later provider dataset mutation may invalidate current coverage while preserving the durable T2 watermark. The finalizer never uses a shorter T1 request to restore `complete` unless current-revision coverage again reaches T2.

```text
required_through = max(requested_finalize_through, existing_finalized_through)
complete only if current revision/generation/snapshot coverage reaches required_through
```

### #50 — NULL finalization cutoff

A never-finalized stream formerly allowed `try_finalize(stream_id,NULL)` to produce `v_required_through=NULL`; SQL three-valued comparisons could skip the fail-closed branch and permit `complete` with `finalized_through=NULL`.

The effective finalizer now rejects the NULL cutoff before completeness processing. Exact #186 proves:

```text
history_null_finalize_cutoff_rejected=PASS
history_null_finalize_preserves_noncomplete_state=PASS
history_retained_finalized_watermark_requires_revalidation=PASS
history_retained_finalized_watermark_recovers_after_full_revalidation=PASS
```

### Physical PITR / restored authority

The recovery vector preserves the full recovery authority chain:

- effective per-instance proof is outside PGDATA clone state;
- clone negatives require same-path positive controls;
- recovery ownership is one winner per canonical recovery boundary, not per arbitrary grant ID;
- surviving post-R effect evidence is authenticated and grant-bound;
- claim alone leaves restored truth at R;
- material fetch locks and revalidates active authority, grant, boundary claim, effect and signing state;
- validly signed successor epoch/placement drift grants fail closed;
- a real successful claim→verify→fetch/apply→verify is replayed after hardening installation;
- established response deadlines are caller-local and real TCP response blackholes are exercised;
- timeout/uncertainty uses one-shot backend retirement rather than synchronous remote cleanup.

### Post-enrollment PGDATA clone

The clone vector proves PGDATA copying alone cannot duplicate recovery authority even when the copied database-visible identity and external credential are reused. It exercises bounded asynchronous claim/verify, cooperative stall, a real established response blackhole, a same-path positive control, then the governed main-grant clone rejection.

### Timescale / Tier 2

The evaluated Tier 2 candidate is the mediated shared-history profile. Tenant/application principals do not directly read shared raw history, CAGG or internal materialization. Privileged automation ownership is a separate cross-tenant trust boundary. Fresh-cluster restore reconstructs roles and reruns tenant/escalation/job attack matrices.

### Relocation

Relocation preserves total/injective typed canonicalization, target-originated checkpoint signing authority, verifier-without-mint separation, restricted verifier capability state, source lock-before-F, exact target completeness, authenticated sealing, atomic Tier 1 placement+activation-grant commit and target activation only after exact grant verification.

The effective final verifier transport has asynchronous caller-local deadlines, no synchronous timeout cancel/disconnect, one-shot session retirement, and real TCP response-blackhole tests in both directions.

## Files

- `STATE.md` — current governed evidence state and acceptance boundary.
- `DECISION_REVIEW.md` — normative decision-review record and all 50 material finding classes.
- `EVIDENCE_MANIFEST.json` — machine-readable evidence classification and guard facts.
- `sql/d2-open-rel-030/*` — executable Tier 1 / history / Timescale evidence modules.
- `tools/open_rel_030/*` — orchestration, recovery, clone, restore and relocation falsification harnesses.
- `.github/workflows/open-rel-030-conformance.yml` — exact-HEAD structural + empirical conformance gate.

## Final-gate rule

The empirical anchor is provenance after a governance mutation. The **exact final governance HEAD** must independently pass:

1. JLMIRROR Deterministic Assurance;
2. JLMIRROR OPEN-REL-030 Conformance;
3. Native Assurance with P0/P1/P2 all zero;
4. a fresh adversarial Codex review on that exact stationary SHA;
5. zero unresolved review threads.

Only then may the package be presented for **explicit Track B acceptance**. Wave 4 implementation authorization is separate. Merge authorization is separate. Production selections are separate.

`READY_FOR_MERGE != AUTHORIZED_TO_MERGE`.
