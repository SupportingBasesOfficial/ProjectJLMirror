# D2 / OPEN-REL-030 Evidence State

**State:** EVIDENCE COMPLETE — READY FOR EXACT-HEAD DECISION REVIEW  
**Production authority:** none  
**Track B acceptance authorization:** not granted  
**Wave 4 implementation authorization:** not granted  
**Production versions/numerics:** not selected; capacity envelopes remain `OPEN-REL-020` C3

## Current recommendation

Recommend C2 Track B acceptance only if the complete invariant set below remains preserved together and the exact final governance HEAD passes deterministic assurance, OPEN-REL-030 conformance, Native Assurance and a fresh adversarial Codex review.

### Tier 1 — transactional and history authority

- canonical observation identity/content is immutable;
- active source generation, poll epoch and durable `live` poll claim come from owner-controlled state inside the acceptance transaction;
- current-state CAS uses platform authority, never provider event time;
- reconciliation coverage is contiguous from `supported_history_floor` and bound to exact owner `authority_generation`, exact `provider_dataset_revision` and required snapshot currentness;
- owner-visible provider mutation invalidates current coverage atomically; stable identity rewrite, DELETE and TRUNCATE fail closed;
- accepted stable identities are compared with owner-current canonical content before coverage publication whenever either side intersects the requested window, independently of current `became_visible_at`;
- a retained durable `finalized_through=T2` is historical authority, not reusable coverage: after dataset invalidation, any later finalization request for `T1<T2` must still prove current-revision contiguous coverage through T2 before the stream may return to `complete`;
- partial current-revision revalidation below a retained watermark leaves `state=reconciliation_required` and preserves the historical watermark without advertising it as currently complete;
- `try_finalize(..., p_finalize_through)` rejects `NULL` cutoff with SQLSTATE `22004` before any completeness decision;
- provider mutation, sweep and finalization use one explicit authority-row lock order: `provider_authority → stream_state`; the pre-lock internal sweep/finalize entry points are not executable by the reconciliation worker;
- real concurrent mutation×finalization and mutation×sweep vectors must complete without deadlock/lock abort;
- every ordered history hardening module is executed by the extended runner and structurally guarded against orphaning; the current set is `004–010`.

### Physical PITR recovery authority

Recovery admission remains a surviving, authenticated, effect-bound, active-authority-bound, boundary-single-winner authority:

1. committed R precedes a real committed `(R,F]` effect;
2. surviving authority outside the restored database stores authenticated effect evidence derived from actual post-R source state;
3. every recovery grant binds that exact effect digest;
4. the surviving singleton active tuple `(domain,R,F,successor_epoch,placement_version,required_receipt)` is locked before winner-key derivation;
5. validly signed epoch/placement drift grants fail closed and cannot create another claim;
6. equivalent valid grant IDs converge to one canonical recovery-boundary claim;
7. the winner is bound to authenticated principal plus restored-instance capability; reusable credentials alone are insufficient;
8. post-enrollment PGDATA clone does not copy the effective instance proof, and clone rejection is accepted only after a same-path positive control;
9. claim alone leaves local truth at R; only verified surviving recovery material may atomically apply post-R state and exact successor authority;
10. recovery material fetch locks and revalidates active authority, grant, boundary claim, effect and signing state against in-flight substitution;
11. the hardened positive path itself is replayed after hardening installation through `claim → verify → fetch/apply → verify`;
12. established-response deadlines are caller-local and asynchronous; timeout/uncertainty has no synchronous remote cancel/disconnect and one-shot SQL session retirement closes abandoned evidence connections;
13. real established TCP response blackholes are exercised directly.

### Tier 2 / relocation

- Timescale shared history remains acceptable only under the mediated profile; tenant/application principals have no direct shared raw/CAGG/internal-materialization authority;
- `ts_automation_owner` remains privileged cross-tenant infrastructure, not an application/tenant principal;
- fresh-cluster role reconstruction and post-restore/job attack matrices remain mandatory evidence;
- relocation typed canonicalization is total/injective over evaluated `timestamptz` and `numeric` domains;
- target checkpoint measurement/signing authority originates inside Tier 2; Tier 1 verifies but cannot mint;
- verifier capability secrets remain restricted and absent from function source;
- the effective final verifier transport uses caller-local asynchronous deadlines and no synchronous timeout cleanup;
- real established response blackholes are exercised in both Tier1→Tier2 and Tier2→Tier1 directions;
- source authority is locked before F; target completeness is canonical-set completeness, never max-only;
- Tier 1 successor placement + exact activation grant commit atomically;
- target remains sealed until verifying that committed grant; existing history is immutable after activation and only new append `>F` is eligible.

## Exact empirical mechanism anchor before this governance mutation

```text
HEAD
51cddbca4258a78ed8f4a3254ff54a01a332e933

JLMIRROR Deterministic Assurance
run #2261
run id 33283602526
SUCCESS

JLMIRROR OPEN-REL-030 Conformance
run #198
run id 33283602532
SUCCESS
```

Exact #198 checked out and verified that SHA, executed all seven history hardening modules (`004–010`), the complete PITR/recovery package, post-enrollment clone, Timescale restore/jobs and Tier1↔Tier2 relocation, then ended with `open_rel_030_extended_conformance=PASS` while retaining `closure_claim=false`.

### Class #51 empirical proof

The Codex finding identified a lock-order cycle under ordinary concurrency: the prior effective finalizer acquired `stream_state → provider_authority`, while provider-visible mutation invalidation acquired `provider_authority → stream_state`. A mutation and finalization for the same stream could therefore deadlock and force PostgreSQL to abort one operation. Panoramic review also found that sweep previously relied on a joint `FOR UPDATE OF s,a` rather than an explicit global order.

The effective worker-facing `sweep(...)` and `try_finalize(...)` are now authority-order wrappers. Each acquires `provider_authority` first and `stream_state` second before delegating to the already-proven internal implementation. Those internal pre-lock entry points are owner-only and not executable by `history_reconcile_worker`, so the canonical order cannot be bypassed by the governed worker path. The #50 NULL cutoff remains rejected before authority work.

Exact #198 proves:

```text
history_lock_order_wrappers_installed=PASS
history_internal_entrypoints_not_worker_callable=PASS
history_null_finalize_guard_preserved_after_lock_order=PASS
history_finalization_lock_order_concurrency=PASS
history_sweep_lock_order_concurrency=PASS
history_authority_lock_order=provider_authority_then_stream_state=PASS
history_null_finalize_cutoff_rejected=PASS
history_retained_finalized_watermark_requires_revalidation=PASS
history_retained_finalized_watermark_recovers_after_full_revalidation=PASS
open_rel_030_extended_conformance=PASS
```

The concurrent vectors deliberately hold `provider_authority`, then race provider dataset invalidation against finalization and sweep. Both sessions complete without deadlock, timeout or lock abort under the canonical order.

## Material classes #38–#51

- **#38:** post-enrollment PGDATA clone authority — effective proof moved outside PGDATA clone domain.
- **#39:** clone-negative false pass — same-path positive control required first.
- **#40:** grant-id scoped winner — canonical recovery-boundary single-winner CAS.
- **#41:** unauthenticated post-R reconciliation — authenticated surviving effect + grant digest binding.
- **#42:** unbounded physical-recovery established response — asynchronous caller-local deadlines.
- **#43:** recovery-material fetch TOCTOU — consistent locked snapshot and full binding revalidation.
- **#44:** cooperative-delay false confidence — real TCP blackhole + no synchronous timeout cleanup + session retirement.
- **#45:** validly signed drifted successor authority — locked active singleton tuple before winner derivation and verify/fetch revalidation.
- **#46:** hardened positive-path gap — successful reset-to-R recovery replay under installed hardening.
- **#47:** post-enrollment clone unbounded response — bounded async transport, real blackhole and backend retirement.
- **#48:** relocation timeout cleanup outside deadline — effective final transport override with two-direction real blackholes and one-shot retirement.
- **#49:** retained finalized watermark stale resurrection — current-revision coverage must revalidate through the retained historical watermark before `complete` can be restored.
- **#50:** NULL finalization watermark — malformed NULL cutoff is rejected before three-valued logic can mint `complete` with a NULL finalized watermark.
- **#51:** inconsistent history authority lock order — provider mutation, sweep and finalization now acquire `provider_authority → stream_state`, with worker bypass removed and concurrent deadlock vectors required.

Classes #1–#37 remain part of the same evidence lineage and are enumerated in `DECISION_REVIEW.md`; no prior closure is superseded by #51.

## Acceptance boundary

```text
Evidence package             COMPLETE
Executable empirical anchor  51cddbca4258a78ed8f4a3254ff54a01a332e933 / #2261 / #198
Material finding classes     51
History hardening modules    7 (004–010)
Inline review threads        0 unresolved after #51 evidence reply
Exact-final-HEAD CI          REQUIRED AGAIN AFTER THIS GOVERNANCE MUTATION
Fresh Codex exact-head       REQUIRED
Native Assurance exact-head  REQUIRED AGAIN
Track B acceptance           EXPLICIT AUTHORIZATION REQUIRED
Wave 4 implementation        SEPARATE EXPLICIT AUTHORIZATION REQUIRED
Production authority         NONE
Merge                        NOT AUTHORIZED
```

Evidence completion, CI success, mergeability or reviewer cleanliness do not themselves accept `OPEN-REL-030`, authorize Wave 4, choose production topology/numerics, or authorize merge. `READY_FOR_MERGE != AUTHORIZED_TO_MERGE`.
