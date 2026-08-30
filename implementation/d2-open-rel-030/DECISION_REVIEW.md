# D2 / OPEN-REL-030 — Decision Review Record

**Decision:** `OPEN-REL-030` — customer-monitoring durable acceptance/projection mechanism  
**Class:** C2 bounded evidence-generating implementation decision  
**Canonical spike base:** `main@5f031ae4bacc0c441eeee16f9c67d272e39d6b0b`  
**Current disposition:** evidence complete; recommendation ready for exact-HEAD review; not yet accepted  
**Production authority:** none  
**Track B acceptance authorization:** not granted  
**Wave 4 implementation authorization:** not granted

## Recommendation

Subject to exact-final-HEAD CI, clean Native Assurance, a fresh adversarial Codex review and explicit Track B acceptance, select the bounded C2 mechanism/profile only with these coupled guarantees:

1. immutable canonical Tier 1 observation identity/content;
2. owner-controlled source generation, poll epoch and durable live poll claim inside transactional acceptance;
3. platform ordering authority for current-state CAS, never provider event time;
4. owner-derived reconciliation finality/currentness;
5. reconciliation coverage bound to exact authority generation, provider dataset revision and required snapshot currentness;
6. provider mutation invalidates current coverage atomically; stable identity rewrite, DELETE and TRUNCATE fail closed;
7. stable accepted identities are validated independently of current `became_visible_at` whenever either side intersects the sweep window;
8. a retained historical `finalized_through` watermark can never be re-advertised as current completeness after invalidation unless current-revision coverage has again reached that watermark;
9. a requested finalization cutoff is mandatory authority input; `NULL` is rejected with SQLSTATE `22004` before completeness logic;
10. provider mutation, sweep and finalization share the explicit authority lock order `provider_authority → stream_state`, and worker-facing paths cannot bypass it;
11. real mutation×finalize and mutation×sweep races must complete without deadlock/lock abort;
12. all current history hardening modules `004–010` execute under an anti-orphan workflow guard;
13. physical PITR admission derives from authenticated surviving authority external to restored state;
14. actual post-R effect evidence is authenticated, grant-bound and locally applied only after verified material fetch;
15. one canonical recovery-boundary winner exists across equivalent grant IDs;
16. the surviving active authority tuple is locked before winner derivation and revalidated by claim/verify/fetch;
17. the winner is bound to authenticated principal plus non-PGDATA effective restored-instance proof;
18. clone rejection requires same-path positive control;
19. recovery material fetch uses a consistent locked authority→grant→claim→effect/signing snapshot;
20. the hardened positive recovery path is exercised after hardening installation;
21. established recovery/clone response deadlines are caller-local, asynchronous and fail closed without synchronous timeout cleanup;
22. real established TCP blackholes are directly falsified;
23. deterministic versioned self-delimiting serialization and total/injective typed canonicalization precede hashes/MACs/signatures;
24. Timescale Tier 2 is selected only under the mediated shared-history profile proven by C2 evidence;
25. `ts_automation_owner` remains cross-tenant privileged infrastructure, excluded from tenant/application auth;
26. fresh-cluster role reconstruction and post-restore/job attack matrices are mandatory;
27. source relocation authority is locked before F and target completeness is canonical-set completeness, never max-only;
28. target checkpoint measurement/signing authority originates target-side; Tier 1 verifies but cannot mint;
29. verifier credentials remain restricted capability state, absent from function source;
30. effective final cross-authority verifier transport has caller-local response deadlines and no synchronous timeout cancel/disconnect;
31. real response blackholes are exercised in both relocation directions;
32. Tier 1 successor placement and exact activation grant commit atomically;
33. target `sealed → activated` requires that exact committed Tier 1 grant;
34. pre-activation future rows are rejected; activated existing history is immutable and only new append `>F` is eligible;
35. `OPEN-REL-020` remains owner of production capacity/SLO/retention/cardinality/cost numerics;
36. evaluation database versions, image digests, evidence HMACs, LOGIN roles, external-to-PGDATA mount, `dblink`, one-shot session retirement and laboratory deadlines remain reproducibility dependencies, not frozen production selections.

## Exact empirical mechanism anchor before governance mutation

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

Exact #198 verifies the anchor SHA, executes seven history hardening modules and preserves the complete prior recovery/clone/Timescale/relocation package while adding class #51 proof:

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
closure_claim=false governed Track B acceptance still required; production/Wave4/merge authorization not granted
```

## Class #51 — canonical history authority lock order

### Finding

The effective finalizer acquired `stream_state` before `provider_authority`, while provider-visible history mutation invalidation acquired `provider_authority` before `stream_state`. Under ordinary same-stream mutation/finalization concurrency, each transaction could hold one row and wait on the other, producing a PostgreSQL deadlock and aborting ingestion or finalization. Panoramic review also found that sweep used a joint row-lock query rather than an explicit global order.

### Closure

The effective worker-facing `sweep(...)` and `try_finalize(...)` now acquire `provider_authority` first and `stream_state` second before delegating to their already-proven internal implementations. The renamed pre-lock implementations are owner-only and are not executable by `history_reconcile_worker`, so the governed worker cannot bypass the canonical order. `try_finalize(...,NULL)` continues to fail with SQLSTATE `22004` before authority work.

The dedicated concurrency harness creates same-stream races in which provider authority is already held and provider-dataset invalidation competes with finalization or sweep. Both races must complete without `deadlock detected`, statement/lock timeout or process abort. Exact #198 proves both concurrent paths and all prior history regressions.

This closes Codex P2 thread `PRRT_kwDOT7x07M6ddqA2` at the mechanism/evidence layer. Governance promotion and fresh exact-final-head review are separate gates.

## Class #50 — NULL finalization watermark rejection

A requested finalization cutoff is mandatory authority input. The effective finalizer rejects `p_finalize_through IS NULL` with SQLSTATE `22004` before state/completeness processing, preventing SQL three-valued logic from minting `complete` with a NULL watermark. Exact #198 preserves the #50 rejection markers after the #51 wrapper is installed.

## Class #49 — retained finalized watermark revalidation

A durable historical T2 watermark cannot be restored to current `complete` after provider-dataset invalidation using only shorter T1 coverage. The finalizer requires current generation + dataset revision + required snapshot contiguous coverage through `max(requested_finalize_through, existing_finalized_through)`. Exact #198 preserves both #49 regression markers.

## Material finding classes closed by D2

The evidence program has repaired **51 material classes**, with panoramic review after each repair:

1. conflicting observation content under stable Tier 1 acceptance identity;
2. caller-asserted source/poll authority;
3. same-cluster restore falsely implying role reconstruction;
4. relocation F derived before authority lock;
5. max-only target completeness;
6. disjoint/max-only history reconciliation completeness;
7. target receipt not bound to actual target state;
8. observation digest omitting immutable payload;
9. target seal not serialized with DML;
10. cross-tenant freeze/owner hardening;
11. Timescale LOGIN automation-owner trust ambiguity;
12. restored authority self-minting recovery evidence;
13. history worker self-asserting currentness/finality;
14. uncheckpointed target `>F` surviving cutover;
15. delimiter-framed unrestricted observation text;
16. delimiter-framed structured recovery grants;
17. checkpoint HMAC relying on ambiguous concatenation;
18. Tier 1 holding target checkpoint HMAC key/mint capability;
19. target automation leaving `sealed` before Tier 1 grant;
20. placement/grant lacking explicit all-or-nothing failure evidence;
21. signing key generated/provisioned by cross-database controller instead of target authority;
22. verifier connection secrets embedded in SQL function source;
23. reconciliation coverage reusable across authority-generation changes with same timestamps;
24. owner-current provider conflict silently treated as duplicate;
25. surviving recovery grant reusable across multiple restored authorities;
26. established relocation `dblink` verification lacking caller-local response deadline;
27. recovery single-winner binding relying on caller-copyable target identifier;
28. recovery principals needing direct grant read/caller-supplied signed facts;
29. stable identity correction escaping validation when `observed_at` crosses sweep boundary;
30. timestamp canonicalization non-injective across BC/AD;
31. provider dataset mutation leaving coverage reusable without dataset-revision change;
32. reviewer-critical history module present but not executed by runner;
33. non-finite `timestamptz` disappearing under finite-only formatting;
34. statement-level TRUNCATE bypassing row mutation fencing;
35. numeric `NaN`/`Infinity`/`-Infinity` lacking total cross-store canonicalization;
36. accepted stable-identity conflict hidden by owner correction moving `became_visible_at` beyond current snapshot;
37. duplicate independent physical restore accepted as same-principal retry when recovery credential is reused;
38. post-enrollment physical PGDATA clone inheriting database-resident instance capability;
39. post-enrollment clone rejection able to false-pass because helper/transport failure looked like capability rejection;
40. recovery single-winner scoped to arbitrary `grant_id`;
41. restored authority able to claim reconciliation without authenticating/applying actual surviving `(R,F]` effect;
42. physical-recovery claim/verify/material-fetch using unbounded synchronous established-session response semantics;
43. recovery-material fetch verify-then-unlocked-reread allowing in-flight grant/effect substitution;
44. cooperative delay failing to prove real network blackhole while synchronous cleanup could exceed deadline;
45. validly signed grant drifting successor epoch or placement version without active singleton check;
46. active-authority hardening installed after the successful base recovery, leaving hardened positive path unproven;
47. post-enrollment clone claim/verify retaining synchronous established-session response behavior;
48. effective relocation verifier timeout cleanup synchronously disconnecting under a real blackhole;
49. retained historical `finalized_through` being re-advertised as complete after dataset invalidation using only shorter current-revision coverage;
50. NULL requested finalization cutoff exploiting SQL three-valued logic to mint `complete` with a NULL finalized watermark;
51. inconsistent provider/history authority lock acquisition allowing mutation-versus-finalization deadlock under normal concurrency.

## What acceptance would and would not mean

If the exact-final package is reviewed clean and Track B is explicitly accepted, `OPEN-REL-030` may be selected/conformed for the accepted mechanism/profile. Wave 4 implementation remains separately unauthorized.

Acceptance would **not** freeze production PostgreSQL/Timescale versions, KMS/HSM topology, database authentication/network/RPC topology, workload/instance identity mechanism, verifier secret-store mechanism, production timeout/cancellation numerics, capacity numerics, or the evidence `dblink`/one-shot-session mechanism.

## Review disposition

```text
Evidence completeness        COMPLETE
Executable empirical anchor  51cddbca4258a78ed8f4a3254ff54a01a332e933 / #2261 / #198
Material finding classes     51
History hardening modules    7 (004–010)
Inline review threads        0 unresolved after #51 evidence closure
Exact-final documentation CI REQUIRED AFTER THIS GOVERNANCE MUTATION
Fresh Codex exact-head       REQUIRED
Native Assurance exact-head  REQUIRED AGAIN
Track B acceptance           NOT GRANTED
Wave 4 implementation        NOT AUTHORIZED
Production authority         NONE
Merge                        NOT AUTHORIZED
```
