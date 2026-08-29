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
- stable-identity conflict validation occurs before provider-time windowing whenever accepted or owner-current timestamp intersects the requested window;
- every existing `00[4-9]_history_*.sql` hardening module is wired into the extended runner and structurally guarded against orphaning;
- physical PITR to committed `R` remains fail-closed until surviving external authenticated `(R,F]` recovery authority is established;
- recovery claim API is ID-only and single-winner by authenticated surviving-authority `session_user`;
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
4c6e3a051d76b257df8058bf2b4503e2b6d84013

JLMIRROR Deterministic Assurance
run #2141
run id 33233751143
SUCCESS

JLMIRROR OPEN-REL-030 Conformance
run #138
run id 33233751124
SUCCESS
```

That SHA is provenance only after reviewer-document mutation. The exact final documentation HEAD must rerun both gates.

## Owner-current history gate

Durable `provider_authority` owns `authority_generation`, `provider_dataset_revision`, `current_snapshot_at`, `finality_floor` and `required_reconciliation_snapshot_at`. Coverage is valid only when run generation, dataset revision and snapshot currentness still match the locked owner authority. Generation transition clears materialized coverage. Owner-visible provider INSERT/UPDATE increments `provider_dataset_revision` and invalidates coverage in the same transaction. Provider mutation and `sweep(...)` serialize on the same owner row.

Stable provider identity is immutable. Identity rewrite rejects. DELETE and statement-level TRUNCATE fail closed. `history_reconcile_worker` has no direct provider DML/TRUNCATE privilege, owner membership or trigger-admin path. Conflict validation occurs before provider-time-only selection, so a correction crossing the requested time-window boundary cannot evade validation and mint false coverage.

The structural guard enumerates existing `00[4-9]_history_*.sql` modules and fails if one is absent from `run_conformance_extended.sh`. Exact #138 reports `history_modules=4` and executes `004 → 005 → 006 → 007`.

Exact #138 preserves:

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
late_history_reconciliation=PASS
```

## PITR recovery admission gate

The restored PostgreSQL cannot self-authorize from a local receipt. A separate surviving control database owns the post-`F` recovery signing key and grant authority. The claim surface is `claim_grant(grant_id)` / `verify_claimed_grant(grant_id)`; restore principals cannot directly read grant state or submit target/principal identity as authority. The surviving authority loads/verifies grant facts internally, derives the claimant from `session_user`, and atomically binds the grant to the first authenticated principal. Same-principal retry converges; another authenticated principal is rejected.

Exact #138 preserves the full authenticated-principal single-winner PITR suite, including claim API ID-only, spoof rejection, no direct grant read, tampered-grant rejection, exactly-one-winner concurrency, same-principal retry, rival rejection and duplicate restored-authority denial.

## Canonical typed-value gate

Every structured cryptographic evidence message uses deterministic versioned self-delimiting field representation. Typed values must first have a total/injective canonical representation over the full accepted evidence domain.

### `timestamptz`

Finite values use UTC + microseconds + explicit `AD`/`BC`; PostgreSQL non-finite sentinels map to exact `-infinity` / `infinity` literals. Exact #138 proves cross-store equality, distinct non-finite digest material and mandatory digest use of `canonical_timestamp(...)`.

```text
relocation_timestamp_era_injective=PASS
relocation_timestamp_era_cross_store=PASS
relocation_timestamp_negative_infinity_canonical=PASS value=-infinity
relocation_timestamp_positive_infinity_canonical=PASS value=infinity
relocation_timestamp_nonfinite_cross_store=PASS
relocation_timestamp_nonfinite_digest_injective=PASS
relocation_digest_uses_total_timestamp_canonicalizer=PASS
```

### `numeric`

The evidence `numeric_value` column is unconstrained. Both authorities therefore use `canonical_numeric(...)`: finite values are normalized through `trim_scale`; `NaN`, `Infinity` and `-Infinity` map to explicit exact literals before field framing.

```text
relocation_numeric_nan_canonical=PASS value=NaN
relocation_numeric_positive_infinity_canonical=PASS value=Infinity
relocation_numeric_negative_infinity_canonical=PASS value=-Infinity
relocation_numeric_finite_scale_canonical=PASS value=1.23
relocation_numeric_special_values_cross_store=PASS
relocation_numeric_special_value_digest_injective=PASS
relocation_digest_uses_total_numeric_canonicalizer=PASS
```

## Relocation target / verifier / activation gate

The target checkpoint is bound to target-owned measurement of actual target state and SHA-256 over canonical immutable payload. Effective signing key is generated inside target authority; Tier 1 has no target signing-key relation and cannot mint. Connection capabilities are restricted authority-owned state; verifier secrets are absent from function source. The raw asynchronous transport helper is not executable by verifier/projection principals. Connection setup and established-response time are independently bounded.

Tier 1 atomically commits successor placement plus a durable activation grant. Target remains `sealed` until it verifies that exact committed grant. Exact #138 preserves target key provenance, verifier-secret isolation, stalled-peer fail-closed vectors, seal-vs-DML serialization, forged-attestation rejection, grant-conflict rollback, target self-activation rejection, activation-grant atomicity and Tier1↔Tier2 continuity.

## Tier 2 trust boundary

`ts_automation_owner` remains a LOGIN cross-tenant privileged infrastructure principal. Production must prevent tenant/application principals from authenticating as or assuming this owner through `pg_hba`, local socket/peer/trust behavior, network exposure, role membership or credential provisioning. Widening that boundary invalidates the conformed profile until fresh review/evidence.

## Acceptance boundary

Evidence completion does not accept `OPEN-REL-030`.

```text
Evidence package             COMPLETE
Executable empirical anchor  4c6e3a051d76b257df8058bf2b4503e2b6d84013 / #2141 / #138
Exact-final-HEAD CI          REQUIRED AGAIN AFTER DOC MUTATION
Codex exact-final-HEAD       REQUIRED
Native Assurance             REQUIRED
Track B acceptance           EXPLICIT AUTHORIZATION REQUIRED
Wave 4 implementation        SEPARATE EXPLICIT AUTHORIZATION REQUIRED
Merge                        NOT AUTHORIZED
```

Only after exact-final-HEAD CI + fresh adversarial Codex review + Native Assurance are clean may Track B be presented for explicit acceptance. Acceptance still does not authorize Wave 4 implementation or production deployment.
