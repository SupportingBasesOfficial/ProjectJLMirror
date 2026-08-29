# D2 / OPEN-REL-030 Evidence State

**State:** EVIDENCE COMPLETE — READY FOR DECISION REVIEW  
**Production authority:** none  
**Wave 4 implementation authorization:** not granted  
**Track B acceptance authorization:** not granted  
**Production versions/numerics:** not selected; capacity envelopes remain `OPEN-REL-020` C3

## Current recommendation

### Tier 1 — PostgreSQL transactional authority

Recommend C2 acceptance only with all of the following preserved together:

- immutable canonical observation identity/content;
- active source generation and poll epoch resolved from owner-controlled state inside the acceptance transaction;
- exact durable `live` poll claim for current candidacy;
- current-state CAS by platform source/poll authority, never provider event time;
- contiguous late-history reconciliation anchored at `supported_history_floor`;
- provider snapshot/finality/currentness derived from durable owner authority, not worker-supplied timestamps;
- reconciliation coverage bound to exact current `authority_generation`, exact current `provider_dataset_revision` and owner-required snapshot currentness;
- owner-visible provider INSERT/UPDATE atomically increments dataset revision and invalidates prior coverage;
- stable provider identity rewrite, DELETE and TRUNCATE fail closed unless a separate governed gap/authority path exists;
- reconciliation worker has no direct provider INSERT/UPDATE/DELETE/TRUNCATE privilege, provider-owner membership or trigger-administration authority;
- stable accepted identities are validated against owner-current canonical content before coverage publication whenever either accepted or provider `observed_at` intersects the requested window, **independently of current `became_visible_at`**;
- visibility/current-snapshot filtering is allowed only when admitting previously unaccepted provider rows; it cannot hide a conflict for an already accepted stable identity;
- every existing `00[4-9]_history_*.sql` hardening module is wired into the extended runner and structurally guarded against orphaning;
- physical PITR to committed `R` remains fail-closed until surviving external authenticated `(R,F]` recovery authority is established;
- recovery grant integrity is resolved by the surviving authority and grant state remains unreadable to recovery principals;
- recovery admission is single-winner over **authenticated principal + post-R restored-instance capability**, not principal name/credential alone;
- each physical restore generates its own `instance_id + instance_secret` after reaching `R`; the surviving authority stores only the winning instance identity/fingerprint binding;
- retry succeeds only for the same authenticated principal presenting the same restored-instance capability; a second physical restore using the exact same external role/password but a different post-R capability is rejected;
- source relocation authority is locked before deriving `F`;
- source↔target payload comparison and checkpoint attestation use deterministic self-delimiting canonical serialization;
- typed canonicalization is total/injective over the evaluated accepted domains: `timestamptz` covers finite UTC+microseconds+AD/BC and exact `±infinity`; unconstrained `numeric` covers normalized finite values plus exact `NaN` and `±Infinity`;
- target checkpoint authenticity is verified through target-owned authority while Tier 1 has no target signing/mint capability;
- cross-authority verification is bounded/fail-closed before local authority locks;
- relocation activation grant and Tier 1 placement transition commit atomically.

### Tier 2 — Timescale mediated shared history

Recommend C2 acceptance only under the conformed mediated profile:

- no direct tenant-facing privilege on shared raw history, CAGG or internal materialization;
- fixed-search-path `SECURITY DEFINER` mediation;
- `ts_owner` NOLOGIN mediation/checkpoint authority;
- `ts_automation_owner` LOGIN only as explicit cross-tenant privileged infrastructure, never as application/tenant principal;
- `PASSWORD NULL` is not treated as `NOLOGIN` or production admission proof;
- fresh-cluster role reconstruction + attack matrix after restore/jobs;
- target-owned authenticated sealed relocation checkpoint over actual canonical target payload;
- effective checkpoint signing key generated inside Tier 2 and unreadable by verifier/projection writer;
- verifier connection capabilities restricted and secrets absent from `pg_proc` source;
- established cross-authority calls use caller-local deadlines and fail closed;
- no target row `>F` before activation; `sealed` rejects all target-history DML;
- `sealed → activated` requires exact committed Tier 1 grant verification;
- after activation, existing history is immutable and only append `>F` is eligible.

## Exact empirical anchor before this reviewer-document mutation

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

That SHA is provenance only after this documentation update. The exact final documentation HEAD must rerun both gates.

## Owner-current history gate

Durable `provider_authority` owns `authority_generation`, `provider_dataset_revision`, `current_snapshot_at`, `finality_floor` and `required_reconciliation_snapshot_at`. Coverage is valid only when run generation, dataset revision and snapshot currentness still match locked owner authority. Generation transitions clear materialized coverage. Owner-visible provider INSERT/UPDATE increments `provider_dataset_revision` and invalidates coverage in the same transaction. Provider mutation and `sweep(...)` serialize on the same owner row.

Stable provider identity is immutable. Identity rewrite rejects. DELETE and statement-level TRUNCATE fail closed. `history_reconcile_worker` has no direct provider DML/TRUNCATE privilege, owner membership or trigger-admin path.

The final `sweep(...)` hardening validates already accepted stable identities independently of `became_visible_at`. If either accepted or owner-current `observed_at` intersects the requested window, immutable timestamp/value content is compared before provider visibility/window insertion filtering. Therefore a correction that simultaneously moves `observed_at` out of the window and `became_visible_at` beyond the current provider snapshot cannot disappear behind a fresh current-revision sweep.

The structural guard enumerates existing `00[4-9]_history_*.sql` modules and fails if one is absent from `run_conformance_extended.sh`. Exact #145 reports `history_modules=5` and executes `004 → 005 → 006 → 007 → 008`.

Exact #145 proves/preserves:

```text
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

## PITR recovery admission gate

The restored PostgreSQL cannot self-authorize from a local receipt. A separate surviving control database owns the post-`F` recovery signing key and grant authority. Grant facts are loaded/authenticated internally and recovery principals cannot directly read `recovery_grant`.

Authentication identity alone is also insufficient for retry authority. Two physical restores from the same committed `R` backup are started in the evidence vector. Each creates a fresh local `instance_id` and random `instance_secret` only after reaching `R`. The actual winning restore and its physical clone deliberately use the **same** external recovery role/password. The surviving authority atomically binds a valid grant to `session_user + instance_id + fingerprint(instance_secret)`. Same-instance retry converges; the second physical restore with the same credential but a different post-R capability is rejected.

The local secret remains protected local state and the normal claim/verify path uses a local `SECURITY DEFINER` helper to present proof. The concrete PostgreSQL LOGIN/password + local-secret + `dblink` mechanism is C2 falsification machinery, not a production workload-identity, TPM/TEE/KMS or secret-distribution selection.

Exact #145 proves:

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

## Canonical typed-value gate

Every structured cryptographic evidence message uses deterministic versioned self-delimiting field representation. Typed values must first have a total/injective canonical representation over the full accepted evidence domain.

### `timestamptz`

Finite values use UTC + microseconds + explicit `AD`/`BC`; PostgreSQL non-finite sentinels map to exact `-infinity` / `infinity` literals. Exact #145 preserves cross-store equality, distinct non-finite digest material and mandatory digest use of `canonical_timestamp(...)`.

### `numeric`

The evidence `numeric_value` column is unconstrained. Both authorities use `canonical_numeric(...)`: finite values normalize through `trim_scale`; `NaN`, `Infinity` and `-Infinity` map to explicit exact literals before field framing. Exact #145 preserves all cross-store/special-value vectors.

## Relocation target / verifier / activation gate

The target checkpoint is bound to target-owned measurement of actual target state and SHA-256 over canonical immutable payload. Effective signing key is generated inside target authority; Tier 1 has no target signing-key relation and cannot mint. Connection capabilities are restricted authority-owned state; verifier secrets are absent from function source. Raw asynchronous transport is owner-only. Connection setup and established-response time are independently bounded.

Tier 1 atomically commits successor placement plus a durable activation grant. Target remains `sealed` until it verifies that exact committed grant. Exact #145 preserves target key provenance, verifier-secret isolation, stalled-peer fail-closed vectors, seal-vs-DML serialization, forged-attestation rejection, grant-conflict rollback, target self-activation rejection, activation-grant atomicity and Tier1↔Tier2 continuity.

## Tier 2 trust boundary

`ts_automation_owner` remains a LOGIN cross-tenant privileged infrastructure principal. Production must prevent tenant/application principals from authenticating as or assuming this owner through `pg_hba`, local socket/peer/trust behavior, network exposure, role membership or credential provisioning. Widening that boundary invalidates the conformed profile until fresh review/evidence.

## Acceptance boundary

Evidence completion does not accept `OPEN-REL-030`.

```text
Evidence package             COMPLETE
Executable empirical anchor  ce6f04c1192aae68f305d0b9f5fcaefd4964f8fb / #2155 / #145
Exact-final-HEAD CI          REQUIRED AGAIN AFTER DOC MUTATION
Codex exact-final-HEAD       REQUIRED
Native Assurance             REQUIRED AGAIN ON FINAL HEAD
Track B acceptance           EXPLICIT AUTHORIZATION REQUIRED
Wave 4 implementation        SEPARATE EXPLICIT AUTHORIZATION REQUIRED
Merge                        NOT AUTHORIZED
```

Only after exact-final-HEAD CI + fresh adversarial Codex review + Native Assurance are clean may Track B be presented for explicit acceptance. Acceptance still does not authorize Wave 4 implementation or production deployment.
