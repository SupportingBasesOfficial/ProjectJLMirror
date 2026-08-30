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
Material finding classes    51
History hardening modules   7 (004–010)
Merge                       not authorized
```

## Exact empirical anchor

The current mechanism anchor before the latest governance-only promotion is:

```text
51cddbca4258a78ed8f4a3254ff54a01a332e933
Deterministic Assurance #2261 — SUCCESS — run id 33283602526
OPEN-REL-030 Conformance #198 — SUCCESS — run id 33283602532
```

#198 verifies the exact SHA, executes all mandatory vectors, all seven history hardening modules, physical PITR/recovery, the post-enrollment clone vector, Timescale restore/jobs and Tier1↔Tier2 relocation, then ends with `open_rel_030_extended_conformance=PASS` and `closure_claim=false`.

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
- `try_finalize(..., NULL)` is malformed authority input and fails closed with SQLSTATE `22004`;
- provider mutation, worker sweep and worker finalization all acquire `provider_authority → stream_state` in that order;
- the pre-lock internal sweep/finalize entry points are owner-only and unavailable to the governed worker;
- concurrent mutation×finalization and mutation×sweep vectors must complete without deadlock or lock abort;
- the exact ordered module set `004–010` must be present in the extended runner and structural guard.

The current ordered history chain is:

```text
004_history_reconciliation.sql
005_history_identity_window_hardening.sql
006_history_dataset_revision_hardening.sql
007_history_dataset_revision_edge_hardening.sql
008_history_visibility_correction_hardening.sql
009_history_retained_finalized_watermark_hardening.sql
010_history_lock_order_hardening.sql
```

### #49 — retained finalized watermark

After a stream has historically finalized through T2, a later provider dataset mutation may invalidate current coverage while preserving the durable T2 watermark. The finalizer never uses a shorter T1 request to restore `complete` unless current-revision coverage again reaches T2.

### #50 — NULL finalization cutoff

The effective finalizer rejects a NULL requested cutoff with SQLSTATE `22004` before completeness processing, so SQL three-valued logic cannot mint `complete` with a NULL watermark.

### #51 — canonical history lock order

Provider mutation already used `provider_authority → stream_state`; the former finalizer used the reverse order, creating a real deadlock cycle. The final worker-facing `sweep(...)` and `try_finalize(...)` now acquire the canonical order before calling their owner-only internal implementations. Exact #198 proves:

```text
history_lock_order_wrappers_installed=PASS
history_internal_entrypoints_not_worker_callable=PASS
history_null_finalize_guard_preserved_after_lock_order=PASS
history_finalization_lock_order_concurrency=PASS
history_sweep_lock_order_concurrency=PASS
history_authority_lock_order=provider_authority_then_stream_state=PASS
```

The same run preserves both #49 regression markers and #50 NULL rejection.

### Physical PITR / restored authority

The recovery vector preserves the full recovery authority chain: effective per-instance proof outside PGDATA; same-path clone positive controls; one winner per canonical recovery boundary; authenticated surviving post-R effect; claim-at-R until verified material application; consistent locked recovery-material fetch; active-authority binding; hardened positive replay; caller-local deadlines; real TCP blackholes; and one-shot backend retirement on timeout/uncertainty.

### Post-enrollment PGDATA clone

The clone vector proves PGDATA copying alone cannot duplicate recovery authority even when the copied database-visible identity and external credential are reused. It exercises bounded asynchronous claim/verify, cooperative stall, a real established response blackhole, a same-path positive control, then the governed main-grant clone rejection.

### Timescale / Tier 2

The evaluated Tier 2 candidate is the mediated shared-history profile. Tenant/application principals do not directly read shared raw history, CAGG or internal materialization. Privileged automation ownership is a separate cross-tenant trust boundary. Fresh-cluster restore reconstructs roles and reruns tenant/escalation/job attack matrices.

### Relocation

Relocation preserves total/injective typed canonicalization, target-originated checkpoint signing authority, verifier-without-mint separation, restricted verifier capability state, source lock-before-F, exact target completeness, authenticated sealing, atomic Tier 1 placement+activation-grant commit and target activation only after exact grant verification. The effective verifier transport has asynchronous caller-local deadlines, no synchronous timeout cleanup, one-shot session retirement and real TCP response-blackhole tests in both directions.

## Files

- `STATE.md` — current governed evidence state and acceptance boundary.
- `DECISION_REVIEW.md` — normative decision-review record and all 51 material finding classes.
- `EVIDENCE_MANIFEST.json` — machine-readable evidence classification and guard facts.
- `sql/d2-open-rel-030/*` — executable Tier 1 / history / Timescale evidence modules.
- `tools/open_rel_030/*` — orchestration, recovery, clone, restore and concurrency falsification harnesses.
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
