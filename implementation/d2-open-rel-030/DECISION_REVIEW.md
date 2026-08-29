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
11. authenticate the actual surviving post-R effect, bind every recovery grant to its effect digest, and permit local reconciliation only by applying verified recovery material;
12. make recovery single-winner authority a CAS on the governed recovery boundary, not arbitrary `grant_id`; equivalent valid grant IDs must converge to one winner;
13. lock the surviving singleton active-authority tuple before deriving the winner key and require every grant to match its exact domain/R/F/successor epoch/placement version/required receipt;
14. treat a valid grant signature as insufficient when successor epoch or placement differs from the active tuple; drifted grants must neither claim nor verify nor supply applicable recovery material;
15. bind the winner to authenticated principal plus restored-instance capability; reusable credentials alone are insufficient for retry identity;
16. preserve same-instance retry while rejecting independent restores and post-enrollment PGDATA clones that do not possess the winning effective proof;
17. require same-path positive control before treating a fail-closed clone negative as capability-rejection evidence;
18. keep recovery grant/effect/claim state unreadable to recovery principals and resolve signed facts inside surviving authority;
19. require caller-local established-response deadlines for recovery claim, verify and material-fetch calls; `connect_timeout` alone is insufficient;
20. require recovery-material fetch to lock/revalidate active authority, exact grant, canonical boundary claim and effect, hold signing state and revalidate the complete authority→claim→grant→effect binding before returning material;
21. fence locally reconciled state to the exact active successor epoch and placement as defense in depth;
22. prove the **effective hardened positive recovery path**, not verification-only behavior: after hardening is installed, reset the legitimate winner to `R` and successfully execute `claim → verify → fetch/apply → verify`;
23. require an actual established-session recovery network blackhole to fail closed under the local deadline without synchronous remote cancel/cleanup; production transport must provide independently bounded cleanup or equivalent session-retirement semantics;
24. apply the same established-response property to the separate post-enrollment clone claim/verify path, including a real blackhole before interpreting the positive control and governed negatives;
25. require deterministic versioned self-delimiting bytes before hash/MAC/signature and total/injective typed canonicalization over accepted domains;
26. select TimescaleDB Tier 2 only under the mediated shared-history profile proven by the C2 evidence;
27. classify `ts_automation_owner` as cross-tenant privileged infrastructure and exclude tenant/application authentication or role assumption in production;
28. reject direct pooled RLS assumptions for evaluated Timescale columnstore/CAGG combinations;
29. require genuine fresh-cluster role reconstruction and post-restore attack matrices;
30. lock source relocation authority before deriving `F` and require exact canonical source↔target coverage, never max-only completeness;
31. require target-owned authenticated sealed checkpoints over actual target state;
32. keep checkpoint signing/mint authority target-side; Tier 1 verifier must not possess equivalent mint capability;
33. keep verifier secrets in restricted authority-owned capability state and out of function source;
34. bound cross-authority verification at connection setup and established response, before local authority locks;
35. require the **effective final** relocation verifier timeout path to avoid synchronous cancel/disconnect; use independently bounded cleanup or equivalent one-shot session retirement;
36. exercise real established TCP response blackholes in both Tier1→Tier2 and Tier2→Tier1 verifier directions and require both to fail closed locally before downstream authority operations;
37. commit Tier 1 successor placement and the exact activation grant atomically;
38. require target `sealed → activated` to verify that exact committed Tier 1 grant; target automation cannot self-promote;
39. reject pre-activation target rows above `F`; after activation preserve existing history immutability and allow only new append `>F`;
40. preserve `OPEN-REL-020` as owner of production capacity/SLO/retention/cardinality/cost numerics;
41. treat database versions, image digests, evidence crypto, LOGIN roles, evidence-only external-to-PGDATA mount, `dblink`, one-shot session retirement, capability-store layout and laboratory deadlines as reproducibility dependencies rather than immutable production selections.

## Exact empirical anchor before governance mutation

```text
HEAD
f2a7f0c4cc1dedf02c64ed1129117f327d11931a

JLMIRROR Deterministic Assurance
run #2225
run id 33279609441
SUCCESS

JLMIRROR OPEN-REL-030 Conformance
run #180
run id 33279609464
SUCCESS
```

This anchor preserves the complete prior Tier1/history/Timescale/relocation/recovery package and closes classes #46–#48. It becomes provenance after this governance mutation; exact final package HEAD must independently rerun both gates.

## Owner-current history authority

`provider_authority` owns `authority_generation`, `provider_dataset_revision`, `current_snapshot_at`, `finality_floor` and `required_reconciliation_snapshot_at`. Only runs matching the locked current generation + dataset revision + required currentness contribute to contiguous coverage. Provider INSERT/UPDATE increments dataset revision and invalidates coverage in the same transaction. Identity rewrite, DELETE and statement-level TRUNCATE fail closed.

Already accepted stable identities are validated against owner-current canonical content independently of provider visibility timing. `became_visible_at` is an admission filter for previously unaccepted rows, never a way to suppress canonical-conflict validation.

The extended runner executes all five current hardening modules `004 → 005 → 006 → 007 → 008`, and workflow structure validation fails if an existing `00[4-9]_history_*.sql` module is orphaned.

## Physical PITR recovery authority

### Surviving effect authority and consistent material fetch

After committed `F`, the surviving control authority stores canonical authenticated `recovery_effect` evidence derived from the actual source post-R state. Every valid recovery grant includes the exact effect digest. Claim alone leaves the restored database at `R`; `fetch_claimed_recovery_material(...)` revalidates active authority, locks grant/boundary claim/effect, holds signing state and revalidates the complete authority→claim→grant→effect relationship. The restored side independently verifies the effect digest before atomically applying business state, receipt and successor authority.

Concurrent mutation tests prove the materialization locks are effective rather than merely visible in source text.

### Active surviving-authority binding — class #45

The surviving singleton owns the active tuple `(domain,R,F,successor_epoch,placement_version,required_receipt)`. `claim_grant(...)` locks it before deriving the winner key. Validly signed grants that drift successor epoch or placement are rejected, cannot create another boundary claim, cannot verify/apply and cannot change local successor authority. Verify/material-fetch revalidate the same active tuple.

### Effective hardened positive admission — class #46

The prior #45 evidence installed active-authority functions only after the base vector had already completed its successful recovery. Class #46 therefore requires a positive recovery under the **effective hardened definitions themselves**.

Exact #180 keeps the surviving active authority, grant, authenticated effect and canonical boundary winner durable, resets only the legitimate restored winner to exact `R`, and then replays:

```text
physical_pitr_active_authority_replay_reset_to_R=PASS
physical_pitr_active_authority_hardened_claim=PASS value=true
physical_pitr_active_authority_hardened_verify_before_apply=PASS value=true
physical_pitr_active_authority_hardened_claim_stays_at_R=PASS value=state_at_R|false|0
physical_pitr_active_authority_hardened_fetch_apply=PASS value=true
physical_pitr_active_authority_hardened_verify_after_apply=PASS value=true
physical_pitr_active_authority_hardened_boundary_single_claim=PASS value=1
physical_pitr_active_authority_hardened_clone_still_rejected=PASS value=false
physical_pitr_active_authority_end_to_end_replay=PASS
physical_pitr_active_authority_claim_fetch_apply_chain=PASS
```

The final state is the authenticated post-R business state at successor epoch/placement `6/8`; there remains exactly one boundary claim and the clone remains rejected. This proves the hardened `claim → fetch → apply` path itself is live and correct.

### Post-enrollment clone bounded response — class #47

The post-enrollment PGDATA clone keeps the copied database-visible identity but receives a distinct effective proof outside PGDATA. The helper path now uses asynchronous `dblink_send_query`/`dblink_is_busy` with a caller-local deadline. Timeout/send-error/uncertainty returns fail-closed without synchronous remote cleanup; the one-shot SQL backend is retired.

Exact #180 proves both cooperative and real-blackhole behavior before the authority negative:

```text
physical_pitr_post_enrollment_helpers_use_bounded_transport=PASS
physical_pitr_post_enrollment_deadline_path_has_no_synchronous_cleanup=PASS
physical_pitr_post_enrollment_stalled_peer_fails_closed=PASS
physical_pitr_post_enrollment_local_deadline=PASS elapsed_ms=564
physical_pitr_post_enrollment_real_blackhole_fails_closed=PASS
physical_pitr_post_enrollment_real_blackhole_local_deadline=PASS elapsed_ms=518
physical_pitr_post_enrollment_timeout_backend_retirement=PASS one_shot_sql_session=true
```

The same bounded path then successfully executes the clone probe claim/verify positive control and rejects the clone on the primary winning grant. Thus a false result cannot be counted merely because the RPC path is broken or unbounded.

## Timescale / relocation profile

The evaluated Timescale profile retains fixed-search-path mediation, no direct tenant-facing access to shared raw/CAGG/internal materialization, explicit privileged automation boundary, genuine fresh-cluster role reconstruction and post-restore/job attack matrices.

Relocation keeps source lock-before-F, total/injective canonical typed values, target-owned signing authority, verifier-without-mint separation, authenticated target sealing, atomic Tier 1 placement+activation-grant commit, target self-activation rejection and immutable history lifecycle after cutover.

### Effective verifier cleanup and real blackholes — class #48

Earlier relocation verifier polling enforced a local response deadline but performed synchronous `dblink_disconnect` when that deadline expired. Under a genuine response blackhole, cleanup itself could exceed the nominal deadline indefinitely.

An ordered final hardening module now replaces the **effective** Tier1 and Tier2 `bounded_remote_boolean(...)` before subsequent authority operations. Successful calls disconnect normally; timeout/send-error/uncertainty returns false without synchronous cancel/disconnect, and the one-shot SQL backend is retired.

Exact #180 proves:

```text
relocation_response_deadline_has_no_synchronous_timeout_cleanup=PASS
relocation_effective_verifier_transport_uses_session_retirement=PASS
relocation_target_verifier_real_blackhole_fails_closed=PASS value=false
relocation_target_verifier_real_blackhole_local_deadline=PASS elapsed_ms=506
relocation_tier1_verifier_real_blackhole_fails_closed=PASS value=false
relocation_tier1_verifier_real_blackhole_local_deadline=PASS elapsed_ms=520
relocation_timeout_backend_retirement=PASS one_shot_sql_session=true
```

All downstream target checkpoint, seal, exact completeness, placement+grant rollback/commit, activation and post-cutover vectors remain PASS after this effective transport replacement.

## Material finding classes closed by D2

The evidence program has repaired **48 material classes**, with panoramic review after each repair:

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
44. cooperative `pg_sleep` evidence failing to prove an established network blackhole, while synchronous cancel/disconnect could exceed the claimed local deadline;
45. validly signed grant reusing the same R/F/effect but drifting successor epoch or placement version could derive a second boundary fingerprint because active singleton authority was not checked before claim;
46. active-authority hardening was installed after the successful base recovery, leaving the hardened positive claim/fetch/apply path unproven;
47. post-enrollment clone claim/verify still used synchronous established-session `dblink` and could hang under a genuine response blackhole;
48. effective relocation verifier timeout cleanup synchronously disconnected the remote peer and could exceed the caller-local response deadline under a real blackhole.

## What acceptance would and would not mean

If the exact-final package is reviewed clean and Track B is explicitly accepted, `OPEN-REL-030` may be selected/conformed for the accepted mechanism/profile. Wave 4 implementation remains separately unauthorized.

Acceptance would **not** freeze production PostgreSQL/Timescale versions, KMS/HSM topology, database authentication/network/RPC topology, non-shareable recovery-instance mechanism, verifier secret-store mechanism, production timeout/cancellation numerics, capacity numerics, or the evidence encoding/`dblink`/one-shot-session mechanism.

## Review disposition

```text
Evidence completeness        COMPLETE
Executable empirical anchor  f2a7f0c4cc1dedf02c64ed1129117f327d11931a / #2225 / #180
Material finding classes     48
Inline review threads        0 unresolved at anchor review
Exact-final documentation CI REQUIRED AFTER THIS GOVERNANCE MUTATION
Fresh Codex exact-head       REQUIRED
Native Assurance exact-head  REQUIRED AGAIN
Track B acceptance           NOT GRANTED
Wave 4 implementation        NOT AUTHORIZED
Production authority         NONE
Merge                        NOT AUTHORIZED
```
