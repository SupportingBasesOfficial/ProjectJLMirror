# D2 / OPEN-REL-030 — Decision Review Record

**Decision:** `OPEN-REL-030` — customer-monitoring durable acceptance/projection mechanism  
**Class:** C2 bounded evidence-generating implementation decision  
**Canonical spike base:** `main@5f031ae4bacc0c441eeee16f9c67d272e39d6b0b`  
**Current disposition:** evidence complete; recommendation ready for exact-HEAD review; not yet accepted  
**Production authority:** none  
**Track B acceptance authorization:** not granted  
**Wave 4 implementation authorization:** not granted

## Recommendation

Subject to exact-final-HEAD CI, fresh adversarial review, clean Native Assurance and explicit Track B acceptance:

1. select the ADR-008 PostgreSQL transactional acceptance pattern as Tier 1 only with immutable canonical observation content, owner-controlled active source/poll authority, durable live poll claims and current-state CAS by platform ordering authority;
2. require late-history finality/currentness from durable provider-owner authority, never worker/caller timestamps;
3. bind every late-history coverage run to exact owner `authority_generation`, exact current `provider_dataset_revision` and owner-required snapshot currentness;
4. invalidate materialized reconciliation coverage whenever owner authority generation or owner-visible provider dataset changes;
5. serialize provider mutation and sweep on the same owner authority row;
6. prohibit stable provider identity rewrite and require DELETE/TRUNCATE to fail closed absent a separate governed gap/authority path;
7. keep reconciliation worker out of direct provider-history INSERT/UPDATE/DELETE/TRUNCATE, provider-owner membership and trigger administration;
8. require every `00[4-9]_history_*.sql` hardening module to be wired into the extended conformance runner and structurally guarded against orphaning;
9. reject conflicting canonical content under an already accepted stable identity before recording coverage;
10. validate accepted stable identities whenever either accepted or owner-current `observed_at` intersects the requested sweep window, **independently of current provider `became_visible_at`**;
11. use `became_visible_at <= current_snapshot_at` only to decide admission of previously unaccepted provider rows, never to suppress conflict validation for accepted identities;
12. require physical PITR recovery admission from authenticated surviving `(R,F]` evidence external to the restored authority;
13. require surviving recovery-grant consumption to be atomic single-winner authority;
14. treat authenticated principal/session identity as necessary but insufficient for idempotent recovery retry when credentials can be copied across restores;
15. bind recovery admission to authenticated principal plus a fresh post-R restored-instance capability, with same-instance retry convergence and same-principal/different-instance rejection;
16. keep grant facts and HMAC verification inside surviving authority; recovery principals must not read grant state directly or provide signed grant facts/principal identity as authority;
17. require deterministic versioned self-delimiting structured bytes before hash/MAC/signature;
18. require canonical typed values to be total/injective over the full accepted domain: PostgreSQL `timestamptz` preserves UTC time, microseconds, AD/BC and exact `±infinity`; unconstrained `numeric` preserves normalized finite values and exact `NaN`, `Infinity`, `-Infinity`;
19. select TimescaleDB as Tier 2 historical projection only under the mediated shared-history profile proven by this spike;
20. classify `ts_automation_owner` as LOGIN cross-tenant privileged infrastructure and require production admission controls to exclude tenant/application use;
21. reject direct pooled RLS assumptions for Timescale columnstore/CAGG on the evaluated profile;
22. require genuine fresh-cluster reconstruction of database-global role topology;
23. require source relocation placement authority to be locked before deriving `F`;
24. require target-owned authenticated sealed canonical-payload checkpoints before Tier 1 can authorize target placement;
25. require target checkpoint signing/mint authority exclusively on the target side and effective signing key generation inside target authority;
26. require Tier 1 verifier capability to exclude target signing key/equivalent mint capability;
27. require cross-authority verifier secrets to remain restricted authority-owned state, not embedded in function source;
28. require cross-authority verification to be bounded/fail-closed at both connection establishment and established response, outside local authority-lock windows;
29. require Tier 1 successor placement and exact durable activation grant to commit atomically, bound to tenant, `F`, checkpoint id/generation, target attestation and successor placement version;
30. require target `sealed → activated` to verify that exact committed Tier 1 grant; target automation cannot self-promote;
31. reject target data above `F` before activation unless explicitly covered by target lifecycle;
32. preserve `OPEN-REL-020` as owner of production capacity/SLO/retention/cardinality/cost numerics;
33. treat database versions, image digests, evidence crypto, recovery/verifier LOGIN mechanisms, restored-instance secret mechanism, verifier transport, capability-store layout, deadlines and concrete canonical encoding as reproducibility dependencies rather than immutable production selections.

## Exact empirical anchor before reviewer-document mutation

```text
HEAD
ce6f04c1192aae68f305d0b9f5fcaefd4964f8fb

JLMIRROR Deterministic Assurance
run #2155
run id 33255911094
SUCCESS

JLMIRROR OPEN-REL-030 Conformance
run #145
run id 33255911080
SUCCESS
```

This anchor executes all five history hardening modules (`004–008`), closes visibility-shift conflict evasion, proves recovery single-winner authority against a second physical restore reusing the exact same external credential, and preserves all prior Tier1/Timescale/relocation/canonicalization vectors. It becomes provenance after reviewer-document mutation; exact final package HEAD must independently rerun both gates.

## Tier 1 acceptance and owner-current history authority

The PostgreSQL harness establishes independent-session atomic create-or-observe, immutable canonical identity/content, owner source generation and poll epoch, durable live poll claims, current-state CAS independent from provider event time, historical obligation/outbox atomicity, crash rollback and post-COMMIT ambiguity convergence.

Durable `provider_authority` owns `authority_generation`, `provider_dataset_revision`, `current_snapshot_at`, `finality_floor` and `required_reconciliation_snapshot_at`. Coverage is valid only for exact current generation + dataset revision + owner-required snapshot currentness. `advance_provider_authority(...)` clears coverage; owner-visible provider INSERT/UPDATE increments dataset revision and invalidates coverage in the same transaction. Provider mutation and `sweep(...)` serialize on the same authority row.

Stable provider identity cannot be rewritten. DELETE is rejected and statement-level TRUNCATE has a separate fail-closed guard. Reconciliation worker has no direct provider DML/TRUNCATE privilege, provider-owner membership or trigger-administration path.

### Visibility-shift hardening

The final `sweep(...)` compares an already accepted stable identity against owner-current provider canonical content whenever either side's `observed_at` intersects the requested window. That comparison intentionally does **not** require the provider row to satisfy current visibility time. `became_visible_at` filters only insertion of previously unaccepted rows.

The dedicated vector begins with accepted/provider content at 11:58, finalizes coverage, then performs an owner correction to the same stable identity with `observed_at=12:01`, `became_visible_at=12:30` while the current snapshot remains 12:00, and changed numeric content. Dataset revision invalidation fires, a fresh 11:00..12:00 sweep rejects the immutable-content conflict before a new run can be minted, and accepted canonical content remains unchanged.

Exact #145:

```text
history_modules=5
history_conflicting_observation_rejected=PASS
history_cross_window_identity_conflict_rejected=PASS
history_generation_bound_coverage=PASS
history_owner_currentness_authority=PASS
history_provider_mutation_invalidates_coverage=PASS
history_dataset_revision_bound_coverage=PASS
history_same_generation_dataset_mutation_fenced=PASS
history_provider_destructive_mutation_fails_closed=PASS
history_worker_no_direct_provider_mutation=PASS
history_worker_cannot_administer_provider_triggers=PASS
history_provider_truncate_fails_closed=PASS
history_visibility_shift_conflict_rejected=PASS
history_visibility_shift_cannot_mint_coverage=PASS
late_history_reconciliation=PASS
```

## Physical PITR authority and restored-instance single-winner recovery

A separate surviving control PostgreSQL, excluded from source backup/restore, owns recovery authority and issues structured authenticated grant only after `F`. A local restored receipt is insufficient. Grant fields use deterministic self-delimiting canonical representation before HMAC.

The earlier authenticated-principal binding was insufficient because two restored instances can reuse one role/credential and therefore share `session_user`. The final evidence starts two physical restores from the same committed R backup. Each creates after R a random local `instance_id` plus a 256-bit `instance_secret` that was absent from the backup. The normal claim/verify path reads that secret inside the restored database through local `SECURITY DEFINER` code; the shell does not use the secret to perform the primary/clone claim.

Surviving authority validates grant integrity and atomically binds the grant to:

```text
authenticated session_user
restored instance_id
fingerprint(instance_secret)
```

The primary restore and its physical clone deliberately use the **same recovery role/password**. Retry by the same restore returns true. The clone, despite identical external credentials, has a different post-R capability and returns false. A separate independent-principal race still proves exactly one winner. Recovery principals cannot directly read the grant table; tampered grant cannot be claimed.

Exact #145:

```text
physical_pitr_recovery_instance_capability_generated_post_R=PASS
physical_pitr_recovery_clone_capability_distinct=PASS
physical_pitr_recovery_claim_api_grant_plus_instance_proof=PASS
physical_pitr_recovery_claim_identity_from_authenticated_session=PASS
physical_pitr_recovery_principal_no_direct_grant_read=PASS
physical_pitr_recovery_principal_spoof_rejected=PASS
physical_pitr_tampered_grant_cannot_claim=PASS
physical_pitr_tamper_leaves_grant_unclaimed=PASS
physical_pitr_recovery_claim_single_winner_race=PASS
physical_pitr_recovery_grant_same_instance_retry=PASS
physical_pitr_recovery_same_principal_clone_rejected=PASS
physical_pitr_recovery_other_principal_rejected=PASS
physical_pitr_recovery_grant_authenticated_principal_binding=PASS
physical_pitr_recovery_grant_instance_id_binding=PASS
physical_pitr_recovery_instance_fingerprint_binding=PASS
physical_pitr_duplicate_restored_authority_not_admitted=PASS
physical_pitr_recovery_single_winner_instance_capability=PASS
physical_pitr_post_reconcile_admission=PASS authority=surviving_external_authenticated_single_winner_instance_capability
```

The concrete PostgreSQL LOGIN/password, local random secret and `dblink` path are evidence-only. Production may use TPM/TEE/KMS-backed non-exportable material, workload identity or another mechanism only if it preserves the same non-shareable restored-instance authority property.

## Timescale mediated profile

On TimescaleDB 2.29.2 / PostgreSQL 17.11, direct pooled `RLS + columnstore` and `RLS + continuous aggregate` are ineligible (`0A000`). Surviving profile uses fixed-search-path `SECURITY DEFINER` mediation, NOLOGIN `ts_owner`, and LOGIN `ts_automation_owner` only as explicit cross-tenant privileged infrastructure. `PASSWORD NULL` is not NOLOGIN or production admission proof.

Fresh-cluster restore reconstructs minimum role topology and re-runs tenant-isolation/escalation attacks after restore and restored background-job execution.

## Tier 1 ↔ Tier 2 relocation

Tier 1 locks source placement before deriving `F`; in-flight authoritative acceptance resolves first and is included. `max(target)=F` is never completeness. Target state is measured and sealed by target authority; any target row `>F` before activation prevents seal, and `sealed` rejects all DML until authorized activation.

### Canonical typed values before cryptography

Finite `timestamptz` serializes in UTC with microseconds and explicit AD/BC; non-finite values use exact `-infinity`/`infinity`. Unconstrained `numeric` uses normalized finite representation and exact `NaN`/`Infinity`/`-Infinity`. Both authoritative and target digests are statically verified to call total typed canonicalizers before self-delimiting field framing.

### Target signing-key provenance and verifier separation

Effective HMAC key is generated inside Tier 2 target authority. Cross-database controller does not provision/retain it. Tier 1 has no target signing-key relation; projection writer and verifier principals cannot read it. Verifier connection credentials live in restricted owner-controlled capability tables and are absent from SQL function source. Raw bounded transport is owner-only. `connect_timeout` bounds setup; asynchronous polling enforces caller-local post-connect response deadlines. Failure/uncertainty returns false before local authority locks.

### Durable activation grant and atomic rollback

Tier 1 verifies exact target checkpoint, then commits successor placement plus durable activation grant in one local transaction. Target remains sealed until independently verifying exact committed grant. Deliberately conflicting grant after placement-update path forces unique violation and proves entire Tier 1 transaction rolls back.

## Material finding classes closed by D2

The evidence program has repaired **37 material classes**, with panoramic review after each repair:

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
26. established `dblink` verification lacking caller-local response deadline;
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
37. duplicate physical restore being accepted as same-principal retry when external recovery credential is copied/reused.

## What acceptance would and would not mean

If exact-final-HEAD package is reviewed clean and Track B explicitly accepted, `OPEN-REL-030` may be selected/conformed for accepted mechanism/profile. Wave 4 implementation remains separately unauthorized.

Acceptance would not freeze production PostgreSQL/Timescale versions, KMS/HSM topology, database authentication/network/RPC topology, non-shareable recovery-instance mechanism, verifier secret-store mechanism, production timeout numerics, capacity numerics, or exact evidence encoding/`dblink` mechanism.

## Review disposition

```text
Evidence completeness        COMPLETE
Executable empirical anchor  ce6f04c1192aae68f305d0b9f5fcaefd4964f8fb / #2155 / #145
Exact-final documentation CI REQUIRED AFTER THIS DOC MUTATION
Fresh Codex exact-head        REQUIRED
Native Assurance exact-head   REQUIRED AGAIN
Track B acceptance            NOT GRANTED
Wave 4 implementation         NOT AUTHORIZED
Production authority          NONE
Merge                         NOT AUTHORIZED
```
