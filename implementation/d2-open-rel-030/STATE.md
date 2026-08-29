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
- recovery admission is single-winner over **authenticated principal + restored-instance capability**, not principal name/credential alone;
- independent restores from `R` must not converge merely because they reuse one external credential;
- copying PostgreSQL `PGDATA` after instance enrollment must not copy the effective restored-instance authority: the conformed C2 hardening keeps the effective proof outside the physical database clone domain and proves a post-enrollment PGDATA copy with the same database identity and same external credential is rejected;
- same-instance retry succeeds only for the authority that still presents the winning external-to-PGDATA capability;
- the laboratory file/mount capability is evidence-only; production must preserve the stronger non-shareable per-instance property through an appropriate workload/TPM/TEE/KMS-backed or equivalent authority mechanism;
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
c9207f8bbd3c42ec0428987a2580b7f1bfb7e06d

JLMIRROR Deterministic Assurance
run #2181
run id 33272308047
SUCCESS

JLMIRROR OPEN-REL-030 Conformance
run #158
run id 33272308006
SUCCESS
```

This anchor includes the P1 post-enrollment physical-clone hardening. It becomes provenance after this documentation mutation; the exact final documentation HEAD must independently rerun both gates.

## Owner-current history gate

Durable `provider_authority` owns `authority_generation`, `provider_dataset_revision`, `current_snapshot_at`, `finality_floor` and `required_reconciliation_snapshot_at`. Coverage is valid only when run generation, dataset revision and snapshot currentness still match locked owner authority. Generation transitions clear materialized coverage. Owner-visible provider INSERT/UPDATE increments `provider_dataset_revision` and invalidates coverage in the same transaction. Provider mutation and `sweep(...)` serialize on the same owner row.

Stable provider identity is immutable. Identity rewrite rejects. DELETE and statement-level TRUNCATE fail closed. `history_reconcile_worker` has no direct provider DML/TRUNCATE privilege, owner membership or trigger-admin path.

The final `sweep(...)` hardening validates already accepted stable identities independently of `became_visible_at`. If either accepted or owner-current `observed_at` intersects the requested window, immutable timestamp/value content is compared before provider visibility/window insertion filtering. Therefore a correction that simultaneously moves `observed_at` out of the window and `became_visible_at` beyond the current provider snapshot cannot disappear behind a fresh current-revision sweep.

The structural guard enumerates existing `00[4-9]_history_*.sql` modules and fails if one is absent from `run_conformance_extended.sh`. Exact #158 preserves `history_modules=5` and executes `004 → 005 → 006 → 007 → 008`.

## PITR recovery admission gate

The restored PostgreSQL cannot self-authorize from a local receipt. A separate surviving control database owns the post-`F` recovery signing key and grant authority. Grant facts are loaded/authenticated internally and recovery principals cannot directly read `recovery_grant`.

Authentication identity alone is insufficient for retry authority. The original physical vector starts two independent physical restores from the same committed `R` backup. Each generates a distinct post-R capability and both deliberately reuse the same external recovery role/password; the surviving authority binds the winning grant to authenticated `session_user + instance_id + fingerprint(instance_secret)`, so the independently restored rival is rejected.

### P1 post-enrollment clone hardening

Panoramic Native Assurance identified a stronger clone class: if the effective secret is persisted inside the restored database, a physical snapshot taken **after** capability creation copies both `instance_id` and `instance_secret` and can be misclassified as the same-instance retry. That invalidated the earlier CLEAN result and became material finding class #38.

The final C2 hardening adds `physical_pitr_post_enrollment_clone.sh`, wired into `run_conformance_extended.sh` and structurally checked by CI. It:

1. enrolls a restored database identity;
2. keeps the effective proof outside `PGDATA` in an evidence-only per-instance mount;
3. physically copies `PGDATA` after enrollment, so primary and clone have the exact same database-visible `instance_id` and helper code;
4. gives both copies the exact same surviving-authority external role/password;
5. gives the clone a distinct external-to-PGDATA capability;
6. proves primary claim + same-instance retry + verification succeed while clone claim and verification fail.

Exact pre-documentation #158 passed the new vector, including:

```text
physical_pitr_post_enrollment_capability_outside_pgdata=PASS
physical_pitr_post_enrollment_pgdata_identity_copied=PASS
physical_pitr_post_enrollment_external_capability_distinct=PASS
physical_pitr_post_enrollment_primary_claimed=PASS
physical_pitr_post_enrollment_same_instance_retry=PASS
physical_pitr_post_enrollment_pgdata_clone_claim_rejected=PASS
physical_pitr_post_enrollment_primary_verify=PASS
physical_pitr_post_enrollment_pgdata_clone_verify_rejected=PASS
physical_pitr_post_enrollment_authenticated_principal_binding=PASS
physical_pitr_post_enrollment_copied_database_id_binding=PASS
physical_pitr_post_enrollment_pgdata_clone_cannot_duplicate_authority=PASS
physical_pitr_post_enrollment_single_winner_external_capability=PASS
```

The mount/file mechanism is **not** a production secret-store or workload-identity selection. The proven C2 property is narrower and explicit: **copying PostgreSQL database state alone cannot duplicate restored-instance authority**. Production must strengthen this to genuinely non-shareable per-instance authority beyond reusable credentials and copyable recovered state.

## Canonical typed-value gate

Every structured cryptographic evidence message uses deterministic versioned self-delimiting field representation. Typed values must first have a total/injective canonical representation over the full accepted evidence domain.

### `timestamptz`

Finite values use UTC + microseconds + explicit `AD`/`BC`; PostgreSQL non-finite sentinels map to exact `-infinity` / `infinity` literals. Exact #158 preserves cross-store equality, distinct non-finite digest material and mandatory digest use of `canonical_timestamp(...)`.

### `numeric`

The evidence `numeric_value` column is unconstrained. Both authorities use `canonical_numeric(...)`: finite values normalize through `trim_scale`; `NaN`, `Infinity` and `-Infinity` map to explicit exact literals before field framing. Exact #158 preserves all cross-store/special-value vectors.

## Relocation target / verifier / activation gate

The target checkpoint is bound to target-owned measurement of actual target state and SHA-256 over canonical immutable payload. Effective signing key is generated inside target authority; Tier 1 has no target signing-key relation and cannot mint. Connection capabilities are restricted authority-owned state; verifier secrets are absent from function source. Raw asynchronous transport is owner-only. Connection setup and established-response time are independently bounded.

Tier 1 atomically commits successor placement plus a durable activation grant. Target remains `sealed` until it verifies that exact committed grant. Exact #158 preserves target key provenance, verifier-secret isolation, stalled-peer fail-closed vectors, seal-vs-DML serialization, forged-attestation rejection, grant-conflict rollback, target self-activation rejection, activation-grant atomicity and Tier1↔Tier2 continuity.

## Tier 2 trust boundary

`ts_automation_owner` remains a LOGIN cross-tenant privileged infrastructure principal. Production must prevent tenant/application principals from authenticating as or assuming this owner through `pg_hba`, local socket/peer/trust behavior, network exposure, role membership or credential provisioning. Widening that boundary invalidates the conformed profile until fresh review/evidence.

## Acceptance boundary

Evidence completion does not accept `OPEN-REL-030`.

```text
Evidence package             COMPLETE
Executable empirical anchor  c9207f8bbd3c42ec0428987a2580b7f1bfb7e06d / #2181 / #158
Material finding classes     38
Exact-final-HEAD CI          REQUIRED AGAIN AFTER DOC MUTATION
Codex exact-final-HEAD       REQUIRED
Native Assurance             REQUIRED AGAIN ON FINAL HEAD
Track B acceptance           EXPLICIT AUTHORIZATION REQUIRED
Wave 4 implementation        SEPARATE EXPLICIT AUTHORIZATION REQUIRED
Merge                        NOT AUTHORIZED
```

Only after exact-final-HEAD CI + fresh adversarial Codex review + Native Assurance are clean may Track B be presented for explicit acceptance. Acceptance still does not authorize Wave 4 implementation or production deployment.
