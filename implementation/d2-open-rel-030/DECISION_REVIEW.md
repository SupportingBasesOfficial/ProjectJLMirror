# D2 / OPEN-REL-030 — Decision Review Record

**Decision:** `OPEN-REL-030` — customer-monitoring durable acceptance/projection mechanism  
**Class:** C2 bounded evidence-generating implementation decision  
**Canonical spike base:** `main@5f031ae4bacc0c441eeee16f9c67d272e39d6b0b`  
**Current disposition:** evidence complete; recommendation ready for exact-HEAD review; not yet accepted  
**Production authority:** none  
**Track B acceptance authorization:** not granted  
**Wave 4 implementation authorization:** not granted

## Recommendation

Subject to exact-final-HEAD CI, fresh adversarial Codex review, clean Native Assurance and explicit Track B acceptance:

1. use PostgreSQL transactional acceptance only with immutable canonical observation content and owner-controlled source/poll authority;
2. require a durable exact `live` poll claim and current-state CAS by platform ordering authority, never provider event time;
3. derive late-history finality/currentness from durable provider-owner state, not worker timestamps;
4. bind reconciliation coverage to exact `authority_generation`, `provider_dataset_revision` and owner-required snapshot currentness;
5. invalidate coverage atomically on owner-visible provider mutation and serialize mutation/sweep on the owner row;
6. reject stable identity rewrite and fail closed on destructive DELETE/TRUNCATE without a separately governed gap path;
7. keep reconciliation workers out of provider mutation, owner membership and trigger administration;
8. require every current history hardening module to be wired into the extended runner under an anti-orphan CI guard;
9. validate stable accepted identities against owner-current canonical content before coverage publication whenever either side's `observed_at` intersects the sweep window, independently of current `became_visible_at`;
10. require physical PITR admission from surviving authenticated `(R,F]` authority outside the restored database;
11. authenticate the **actual surviving post-R effect**, bind every recovery grant to its effect digest, and permit local reconciliation only by applying verified recovery material;
12. make recovery single-winner authority a CAS on the **governed recovery boundary**, not an arbitrary grant id; multiple valid grant IDs for one boundary must converge to one winner;
13. bind that winner to authenticated principal plus restored-instance capability; reusable credentials alone are insufficient for retry identity;
14. preserve same-instance retry while rejecting independent restores and post-enrollment PGDATA clones that do not possess the winning effective proof;
15. require same-path positive control before treating a fail-closed clone negative as capability-rejection evidence;
16. keep recovery grant/effect/claim state unreadable to recovery principals and resolve signed facts inside surviving authority;
17. require caller-local established-response deadlines for recovery claim, verify and material-fetch calls; `connect_timeout` alone is insufficient;
18. require recovery-material fetch to lock the exact grant, canonical boundary claim and effect, hold signing state and revalidate the full claim→grant→effect binding before returning material;
19. require an actual established-session network blackhole to fail closed under the local deadline without synchronous remote cancel/cleanup; production transport must provide independently bounded cleanup or equivalent session-retirement semantics;
20. require deterministic versioned self-delimiting bytes before hash/MAC/signature and total/injective typed canonicalization over accepted domains;
21. select TimescaleDB Tier 2 only under the mediated shared-history profile proven by the C2 evidence;
22. classify `ts_automation_owner` as cross-tenant privileged infrastructure and exclude tenant/application authentication or role assumption in production;
23. reject direct pooled RLS assumptions for evaluated Timescale columnstore/CAGG combinations;
24. require genuine fresh-cluster role reconstruction and post-restore attack matrices;
25. lock source relocation authority before deriving `F` and require exact canonical source↔target coverage, never max-only completeness;
26. require target-owned authenticated sealed checkpoints over actual target state;
27. keep checkpoint signing/mint authority target-side; Tier 1 verifier must not possess equivalent mint capability;
28. keep verifier secrets in restricted authority-owned capability state and out of function source;
29. bound cross-authority verification at connection setup and established response, before local authority locks;
30. commit Tier 1 successor placement and the exact activation grant atomically;
31. require target `sealed → activated` to verify that exact committed Tier 1 grant; target automation cannot self-promote;
32. reject pre-activation target rows above `F`; after activation preserve existing history immutability and allow only new append `>F`;
33. preserve `OPEN-REL-020` as owner of production capacity/SLO/retention/cardinality/cost numerics;
34. treat database versions, image digests, evidence crypto, LOGIN roles, evidence-only external-to-PGDATA mount, `dblink`, one-shot session retirement, capability-store layout and laboratory deadlines as reproducibility dependencies rather than immutable production selections.

## Exact empirical anchor before governance mutation

```text
HEAD
b162ff5ace52cee09610ebcff2e8d142a4822160

JLMIRROR Deterministic Assurance
run #2211
run id 33275135337
SUCCESS

JLMIRROR OPEN-REL-030 Conformance
run #173
run id 33275135328
SUCCESS
```

This anchor preserves the complete prior Tier1/history/Timescale/relocation/recovery package and closes the two latest recovery findings. It becomes provenance after this governance mutation; exact final package HEAD must independently rerun both gates.

## Owner-current history authority

`provider_authority` owns `authority_generation`, `provider_dataset_revision`, `current_snapshot_at`, `finality_floor` and `required_reconciliation_snapshot_at`. Only runs matching the locked current generation + dataset revision + required currentness contribute to contiguous coverage. Provider INSERT/UPDATE increments dataset revision and invalidates coverage in the same transaction. Identity rewrite, DELETE and statement-level TRUNCATE fail closed.

Already accepted stable identities are validated against owner-current canonical content independently of provider visibility timing. `became_visible_at` is an admission filter for previously unaccepted rows, never a way to suppress canonical-conflict validation.

The extended runner executes all five current hardening modules `004 → 005 → 006 → 007 → 008`, and workflow structure validation fails if an existing `00[4-9]_history_*.sql` module is orphaned.

## Physical PITR recovery authority

### Surviving effect authority and consistent material fetch

The C2 recovery model distinguishes **authorization to recover** from **proof of what must be recovered**. After committed `F`, the surviving control authority stores a canonical `recovery_effect` derived from the actual source post-R business state and receipt, computes its SHA-256 digest and authenticates the canonical payload with surviving-authority HMAC. Every valid recovery grant includes that exact `effect_digest` and cannot validate if the effect evidence is absent, altered or mismatched.

The winning restored database remains exactly at `R` after claim. `reconciled_through_f` is not set by claim or by a locally recreated receipt. `fetch_claimed_recovery_material(...)` now materializes recovery truth only from a consistent authority snapshot: it locks the exact grant, locks the canonical boundary claim, locks the referenced effect, holds signing-key state, revalidates every claim/grant authority dimension plus the exact effect digest and effect/grant R/F/domain/receipt binding, then revalidates the stored HMAC-backed effect and grant. Only that material can be returned to the restored side, which independently recomputes the canonical effect digest before atomically applying the post-R business state, receipt and successor authority.

Exact #173 proves:

```text
physical_pitr_surviving_effect_source_state=PASS
physical_pitr_surviving_effect_evidence_published=PASS
physical_pitr_recovery_effect_digest_binding=PASS
physical_pitr_recovery_fetch_locks_grant=PASS
physical_pitr_recovery_fetch_locks_effect=PASS
physical_pitr_recovery_fetch_locks_boundary_claim=PASS
physical_pitr_recovery_fetch_consistent_locked_snapshot=PASS
physical_pitr_recovery_fetch_revalidates_claim_grant_effect_binding=PASS
physical_pitr_claim_without_effect_application_stays_at_R=PASS value=state_at_R|false|0
physical_pitr_authenticated_effect_application=PASS value=true
physical_pitr_reconciled_from_authenticated_surviving_effect=PASS
physical_pitr_local_reconciled_state=PASS
```

The lock proof is not source-string evidence alone: a test-only hold wrapper keeps the final fetch transaction live while independent owner mutations target the grant, effect and boundary claim. Each mutation is required to hit `lock_timeout` rather than substitute authority state in flight.

### Boundary-level single winner

A grant id is not the recovery event identity. Surviving authority derives a canonical `boundary_fingerprint` from `(domain, R, F, successor_epoch, placement_version, required_receipt)` and uses it as the primary key of `recovery_boundary_claim`. The first valid authenticated principal+instance capability wins that boundary. Another grant id for the same boundary cannot establish a second authority; the same winning instance may converge through an equivalent grant, while a rival instance is rejected.

A separate concurrent vector races **two different grant IDs** for one synthetic recovery boundary and requires exactly one winner and exactly one boundary-claim row.

Exact #173 proves:

```text
physical_pitr_duplicate_grants_same_boundary=PASS
physical_pitr_recovery_cross_grant_boundary_single_winner_race=PASS
physical_pitr_recovery_boundary_claim_rows_after_cross_grant_race=PASS value=1
physical_pitr_recovery_duplicate_grant_same_winner_retry=PASS value=true
physical_pitr_recovery_duplicate_grant_clone_rejected=PASS value=false
physical_pitr_recovery_main_boundary_single_claim=PASS value=1
physical_pitr_recovery_single_winner_per_boundary_across_grant_ids=PASS
```

### Bounded recovery RPC and real blackhole

`pitr_local_claim_external`, `pitr_local_verify_external` and `pitr_local_apply_external` all route through the same `pitr_bounded_remote_text` primitive. It separates connection setup from response time: `connect_timeout` bounds setup; `dblink_send_query` + `dblink_is_busy` polling enforces a caller-local deadline after connection establishment.

On timeout/uncertainty the C2 helper returns fail-closed without invoking synchronous `dblink_cancel_query` or synchronous remote disconnect on the deadline path. The harness invokes it from a one-shot SQL backend/session, so the abandoned connection is retired with that local session. This is an evidence mechanism, not a production transport choice; production must independently bound cancellation/cleanup or use equivalent session-retirement semantics.

Two independent negatives are required. A cooperative authenticated five-second server delay is cut off locally in ~573 ms. More importantly, a real established authenticated query is observed active and then server→client TCP responses are dropped. The same caller-local bound fails closed in ~517 ms, while an outer five-second watchdog only protects the evidence harness from hanging if the claim regresses.

Exact #173 proves:

```text
physical_pitr_recovery_helpers_use_bounded_transport=PASS
physical_pitr_recovery_deadline_path_has_no_synchronous_cancel=PASS
physical_pitr_recovery_stalled_peer_fails_closed=PASS
physical_pitr_recovery_local_deadline=PASS elapsed_ms=573
physical_pitr_recovery_real_blackhole_fails_closed=PASS
physical_pitr_recovery_real_blackhole_local_deadline=PASS elapsed_ms=517
physical_pitr_recovery_timeout_backend_retirement=PASS one_shot_sql_session=true
```

### Clone authority and evidence quality

Class #38 remains closed by keeping the effective post-enrollment C2 proof outside the physical `PGDATA` clone domain. Class #39 remains closed by making the already-cloned PostgreSQL successfully claim+verify a separate probe grant through the same helper/transport/credential path and requiring surviving-authority fingerprint equality with the clone-local capability fingerprint before interpreting rejection on the primary-winning grant.

These laboratory mechanisms do not select the production workload identity, KMS/HSM/TPM/TEE, secret store, database authentication or RPC topology. Production must preserve the stronger semantic properties: non-shareable per-instance authority, one winner per recovery boundary, surviving authenticated effect evidence, consistent claim→grant→effect materialization and bounded fail-closed cross-authority verification/cleanup.

## Timescale / relocation profile

The evaluated Timescale profile retains fixed-search-path mediation, no direct tenant-facing access to shared raw/CAGG/internal materialization, explicit privileged automation boundary, genuine fresh-cluster role reconstruction and attack matrices.

Relocation keeps source lock-before-F, total/injective canonical typed values, target-owned signing authority, verifier-without-mint separation, bounded verifier response, authenticated target sealing, atomic Tier 1 placement+activation-grant commit, target self-activation rejection and immutable history lifecycle after cutover.

## Material finding classes closed by D2

The evidence program has repaired **44 material classes**, with panoramic review after each repair:

1. conflicting observation content under stable Tier 1 acceptance identity;
2. caller-asserted source/poll authority;
3. same-cluster restore falsely implying role reconstruction;
4. relocation `F` derived before authority lock;
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
38. post-enrollment physical PGDATA clone inheriting database-resident instance capability and being accepted as same-instance retry;
39. post-enrollment clone rejection able to false-pass because fail-closed helper/transport failure was indistinguishable from capability rejection;
40. recovery single-winner scoped to arbitrary `grant_id`, allowing multiple valid grants for one recovery boundary to authorize multiple instances;
41. restored authority able to claim reconciliation without authenticating and applying the actual surviving `(R,F]` business effect;
42. physical-recovery claim/verify/material-fetch using unbounded synchronous established-session `dblink` response semantics;
43. recovery-material fetch using verify-then-unlocked-reread, allowing a re-signed grant/effect substitution to race the previously authorized boundary claim;
44. cooperative `pg_sleep` evidence failing to prove an established network blackhole, while synchronous cancel/disconnect could exceed the claimed local deadline.

## What acceptance would and would not mean

If the exact-final package is reviewed clean and Track B is explicitly accepted, `OPEN-REL-030` may be selected/conformed for the accepted mechanism/profile. Wave 4 implementation remains separately unauthorized.

Acceptance would **not** freeze production PostgreSQL/Timescale versions, KMS/HSM topology, database authentication/network/RPC topology, non-shareable recovery-instance mechanism, verifier secret-store mechanism, production timeout/cancellation numerics, capacity numerics, or the evidence encoding/`dblink`/one-shot-session mechanism.

## Review disposition

```text
Evidence completeness        COMPLETE
Executable empirical anchor  b162ff5ace52cee09610ebcff2e8d142a4822160 / #2211 / #173
Material finding classes     44
Inline review threads        0 unresolved at anchor review
Exact-final documentation CI REQUIRED AFTER THIS GOVERNANCE MUTATION
Fresh Codex exact-head       REQUIRED
Native Assurance exact-head  REQUIRED AGAIN
Track B acceptance           NOT GRANTED
Wave 4 implementation        NOT AUTHORIZED
Production authority         NONE
Merge                        NOT AUTHORIZED
```
