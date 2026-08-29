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
- reconciliation coverage bound to the exact current `authority_generation`, exact current `provider_dataset_revision` and owner-required snapshot currentness;
- every authority-generation transition invalidates prior materialized coverage until a fresh sweep under the new generation re-establishes it;
- every owner-visible provider dataset INSERT/UPDATE atomically increments the dataset revision and invalidates prior coverage, including corrections that keep the authority generation and timestamps unchanged;
- stable provider observation identity cannot be rewritten; DELETE and TRUNCATE of owner-visible provider history fail closed and require an explicit governed gap/authority path rather than silently reusing coverage;
- the reconciliation worker has no direct INSERT/UPDATE/DELETE/TRUNCATE privilege on owner-visible provider history, is not a member of the provider owner role and cannot administer the dataset-revision/truncate triggers;
- conflicting canonical content under an existing reconciled observation identity rejects the sweep before a new coverage run can be recorded;
- stable-identity conflict validation occurs **before provider-time windowing** whenever either the already accepted timestamp or owner-current provider timestamp intersects the requested sweep window, so a correction cannot escape validation by moving across the window boundary;
- all ordered history hardening modules matching `00[4-9]_history_*.sql` are executable conformance inputs; CI fails if any existing module is not wired into the extended runner;
- stale reconciliation worker generations rejected;
- physical PITR to committed `R` remaining fail-closed until surviving external authenticated `(R,F]` recovery authority is established;
- recovery grant facts stored structurally and authenticated over a deterministic self-delimiting canonical representation;
- recovery claim API accepts only `grant_id`; grant facts and winner identity are resolved inside the surviving authority;
- recovery admission is single-winner by authenticated surviving-authority session principal: the first authenticated principal claims the grant atomically, same-principal retries converge, and another authenticated principal is rejected;
- recovery principals have no direct read privilege on grant state and caller-supplied target/principal identity is not an authority input;
- a locally recreated receipt after restore is insufficient for re-admission;
- source relocation authority locked before deriving `F`;
- source↔target payload comparison and checkpoint attestation using deterministic self-delimiting canonical serialization;
- timestamp serialization is total and injective over the supported PostgreSQL `timestamptz` evidence domain: finite values use UTC + microseconds + explicit AD/BC era, while non-finite values use reserved exact `infinity` / `-infinity` literals before entering the relocation digest;
- target checkpoint authenticity verified through a target-owned verification boundary while Tier 1 has no target signing key and no mint capability;
- verifier transport credentials held in authority-owned restricted capability stores rather than embedded in function source;
- cross-authority verification has both bounded connection setup and a caller-local post-connect response deadline; stalled peers fail closed before local authority locks;
- the exact relocation activation grant and the Tier 1 placement transition committed atomically, so neither can survive without the other.

### Tier 2 — Timescale mediated shared history

Recommend C2 acceptance only under the conformed mediated profile:

- no direct tenant-facing privilege on shared raw history, CAGG or internal materialization;
- fixed-search-path `SECURITY DEFINER` mediation with tenant binding outside caller-writable SQL state;
- `ts_owner` NOLOGIN mediation/checkpoint authority;
- `ts_automation_owner` LOGIN only as explicit cross-tenant privileged infrastructure, never as an application/tenant principal;
- `PASSWORD NULL` is not treated as `NOLOGIN` or production admission proof;
- fresh-cluster role reconstruction + attack matrix after restore/jobs;
- target-owned authenticated sealed relocation checkpoint over the actual target canonical payload;
- the effective checkpoint signing key is generated inside Tier 2 target authority and is not provisioned or retained by the test controller;
- verifier and projection-writer principals cannot read that signing key;
- target/Tier1 verifier connection capabilities are restricted authority-owned state and are not readable by verifier/automation principals;
- verifier secrets are not embedded in `pg_proc` function source;
- raw verifier transport helpers are not executable by tenant/projection verifier principals;
- established cross-authority calls use asynchronous polling with a local deadline and fail closed on a stalled authenticated peer;
- no target row `>F` may survive or enter before activation;
- `sealed` rejects all target-history DML;
- `sealed → activated` requires successful verification of the exact durable Tier 1 activation grant bound to tenant, `F`, checkpoint id/generation, target attestation and successor placement version;
- after `activated`, existing history is immutable and only append `>F` is eligible.

## Exact empirical anchor before this reviewer-document mutation

```text
HEAD
723022253af332b0fa08ff7be3fbcad326dd8712

JLMIRROR Deterministic Assurance
run #2131
run id 33233145281
SUCCESS

JLMIRROR OPEN-REL-030 Conformance
run #133
run id 33233145277
SUCCESS
```

That SHA is provenance only after this documentation update. The exact final documentation HEAD must rerun both gates.

## Owner-currentness history gate

The history worker does not provide authority, finality or currentness facts. Durable `provider_authority` owns `authority_generation`, `provider_dataset_revision`, `current_snapshot_at`, `finality_floor` and `required_reconciliation_snapshot_at`. `sweep(...)` accepts only the requested window plus expected owner authority; `try_finalize(...)` accepts no caller authority/finality/currentness timestamp.

Coverage is a function of the exact owner generation, exact owner dataset revision and required owner snapshot. `reconciliation_run` records the revision it observed and `contiguous_covered_through(...)` accepts only runs whose generation/revision/currentness still match the locked owner authority. Authority-generation transition clears materialized coverage. Owner-visible provider INSERT/UPDATE increments `provider_dataset_revision` in the same transaction and invalidates materialized coverage; rollback of the provider mutation also rolls back the revision change. `sweep(...)` and provider mutation serialize on the same `provider_authority` row, so a same-generation correction cannot remain hidden behind a just-published coverage watermark.

Stable provider identity is immutable. Identity rewrite is rejected. Destructive DELETE and statement-level TRUNCATE fail closed rather than silently mutating the owner-current history set. `history_reconcile_worker` has no direct provider-table mutation privilege, no owner membership and no trigger-administration path. Production owner/superuser governance remains a deployment trust boundary rather than an authority granted to the reconciliation worker.

An existing `(stream_id, observation_id)` is immutable canonical history. Conflict validation happens before new rows are selected solely by provider `observed_at`: if either the accepted timestamp or owner-current provider timestamp intersects the requested window, the stable identity is compared. Therefore a correction from, for example, accepted `11:58` to provider-current `12:01` cannot escape an `11:55..12:00` sweep and mint false coverage. Any `observed_at` or `numeric_value` mismatch raises `reconciled observation identity content mismatch`; the failed sweep records no new run and leaves accepted canonical content unchanged.

The extended-runner structural guard enumerates existing `00[4-9]_history_*.sql` modules and fails if one is not referenced by `run_conformance_extended.sh`. Exact #133 reported `history_modules=4` and executed `004 → 005 → 006 → 007`.

Exact #133 proves:

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

The same run preserves continuous coverage from the supported floor and durable `gap` on unrecoverable retention loss.

## PITR recovery admission gate

The restored PostgreSQL cannot self-authorize from a local receipt. A separate surviving control database, excluded from the source backup/restore, owns the recovery signing key and issues a grant after `F`. The structured grant facts are individually self-delimiting before HMAC-SHA-256.

Grant validation alone is not admission. Recovery principals are provisioned only after restore reaches `R`; the bounded evidence implementation uses independently authenticated PostgreSQL LOGIN sessions solely as a C2 identity mechanism. The claim API is `claim_grant(grant_id)`: it accepts neither target ID nor principal nor signed grant facts from the caller. The surviving authority loads the grant internally, reconstructs and verifies the canonical HMAC, derives the claimant from `session_user`, locks the grant and atomically binds it to the first authenticated principal. Retry from that same principal converges; any different authenticated principal is rejected. Restore principals cannot directly read `recovery_grant`, and presenting a rival credential under the winner role name fails authentication.

Exact #133 preserves:

```text
physical_pitr_recovery_claim_api_id_only=PASS
physical_pitr_recovery_claim_identity_from_authenticated_session=PASS
physical_pitr_recovery_principal_no_direct_grant_read=PASS
physical_pitr_recovery_principal_spoof_rejected=PASS
physical_pitr_tampered_grant_cannot_claim=PASS
physical_pitr_tamper_leaves_grant_unclaimed=PASS
physical_pitr_recovery_claim_winner_retry=PASS
physical_pitr_recovery_claim_loser_rejected=PASS
physical_pitr_recovery_claim_single_winner_race=PASS
physical_pitr_recovery_grant_same_principal_retry=PASS
physical_pitr_recovery_grant_other_principal_rejected=PASS
physical_pitr_recovery_grant_authenticated_principal_binding=PASS
physical_pitr_duplicate_restored_authority_not_admitted=PASS
physical_pitr_recovery_single_winner_authenticated_principal=PASS
physical_pitr_post_reconcile_admission=PASS authority=surviving_external_authenticated_single_winner_principal
```

The concrete LOGIN/password exchange is evidence machinery, not a production authentication topology selection. The accepted invariant is that a retry/admission must be bound to the same authenticated recovery authority, not to a caller-copyable identifier.

## Canonical structured-message gate

Every structured cryptographic evidence message must use deterministic, versioned, injective or equivalently unambiguous serialization before hash/MAC/signature. The bounded evidence representation is `<UTF-8 byte length in decimal>:<lowercase UTF-8 hex>`, used for observation payloads, target-checkpoint facts and PITR recovery-grant facts. Typed values must themselves have injective canonical text over the entire accepted domain before field framing.

For relocation `timestamptz`, finite values are normalized to UTC with microseconds **and explicit `AD`/`BC` era**. PostgreSQL non-finite sentinels are mapped to reserved exact literals `-infinity` and `infinity`; they are never allowed to become SQL NULL/empty fields in a digest. Both stores must produce identical self-delimiting bytes and distinct SHA-256 values for the two sentinels. An accepted implementation may use another canonical representation only with equivalent independently reviewed evidence.

Exact #133 proves:

```text
relocation_timestamp_era_injective=PASS
relocation_timestamp_era_cross_store=PASS
relocation_timestamp_negative_infinity_canonical=PASS value=-infinity
relocation_timestamp_positive_infinity_canonical=PASS value=infinity
relocation_timestamp_nonfinite_cross_store=PASS
relocation_timestamp_nonfinite_digest_injective=PASS
relocation_digest_uses_total_timestamp_canonicalizer=PASS
```

## Relocation target and issuer/verifier gate

The target checkpoint is bound to target-owned measurement of actual current state, count/max/SHA-256 over canonical immutable payload, and domain-separated HMAC over the canonical checkpoint message. The effective signing key is generated inside target authority using target-side randomness. The trusted disposable-lab controller can administer both databases for setup/fault injection, but it neither provisions nor retains the protocol signing key.

Exact #133 continues to prove:

```text
relocation_tier1_has_no_target_signing_key=PASS
relocation_controller_does_not_retain_target_signing_key=PASS
relocation_target_authority_generated_signing_key=PASS
relocation_projection_writer_still_cannot_read_generated_signing_key=PASS
relocation_target_verifier_still_cannot_read_generated_signing_key=PASS
relocation_tier1_verifier_cannot_read_target_connection_capability=PASS
relocation_projection_writer_cannot_read_tier1_connection_capability=PASS
relocation_target_verifier_cannot_read_tier1_connection_capability=PASS
relocation_target_verifier_secret_not_in_function_source=PASS
relocation_tier1_verifier_secret_not_in_function_source=PASS
relocation_tier1_verifier_cannot_call_raw_bounded_transport=PASS
relocation_target_principals_cannot_call_raw_bounded_transport=PASS
relocation_tier1_cannot_mint_target_attestation=PASS
relocation_fabricated_target_attestation_rejected=PASS
```

Thus the evidence separates issuer from verifier at the database-authority and key-provenance levels, not merely by table naming.

## Cross-authority activation gate

The target checkpoint verifier and Tier 1 activation verifier are capability-restricted yes/no interfaces. The evidence uses short-lived random verifier credentials plus PostgreSQL `dblink` only to exercise independent authorities. Those credentials live in restricted authority-owned capability tables and are not embedded in verifier function source. This concrete transport/auth mechanism remains C2 laboratory machinery and does not select production database-authentication, network, secret-distribution or RPC topology.

`connect_timeout=1` bounds connection establishment. After connection, the owner-only helper uses `dblink_send_query` + `dblink_is_busy` polling with a caller-local deadline; a 5-second remote delay probe returns false well before an unrelated outer timeout. The raw bounded transport helper is not executable by verifier/projection principals.

```text
relocation_target_verifier_stalled_peer_fails_closed=PASS
relocation_target_verifier_local_deadline=PASS
relocation_tier1_verifier_stalled_peer_fails_closed=PASS
relocation_tier1_verifier_local_deadline=PASS
```

Remote verification remains outside local authority-lock windows. Tier 1 then atomically commits successor placement plus a durable activation grant. Target remains `sealed` until it verifies the exact committed grant.

Exact #133 also preserves:

```text
relocation_target_cannot_self_activate_before_tier1_grant=PASS
relocation_premature_mark_keeps_future_insert_blocked=PASS
relocation_activation_commit_conflict_rolls_back=PASS
relocation_activation_conflict_preserves_fenced_placement=PASS
relocation_conflicting_grant_cannot_activate_target=PASS
relocation_activation_conflict_keeps_target_sealed=PASS
relocation_activation_grant_placement_atomicity=PASS
relocation_tier1_activation_grant_committed=PASS
open_rel_030_extended_conformance=PASS
```

## Tier 2 trust boundary

`ts_automation_owner` remains a LOGIN cross-tenant privileged infrastructure principal because the evaluated Timescale background-job profile requires it. Production must prevent tenant/application principals from authenticating as or assuming this owner through `pg_hba`, local socket/peer/trust behavior, network exposure, role membership or credential provisioning. Widening that boundary invalidates the conformed profile until fresh review/evidence.

## Acceptance boundary

Evidence completion does not accept `OPEN-REL-030`.

```text
Evidence package             COMPLETE
Exact-final-HEAD CI          REQUIRED AGAIN AFTER DOC MUTATION
Codex exact-final-HEAD       REQUIRED
Native Assurance             REQUIRED
Track B acceptance           EXPLICIT AUTHORIZATION REQUIRED
Wave 4 implementation        SEPARATE EXPLICIT AUTHORIZATION REQUIRED
Merge                        NOT AUTHORIZED
```

Only after exact-final-HEAD CI + adversarial review + Native Assurance are clean may Track B be presented for explicit acceptance. Acceptance still does not authorize Wave 4 implementation or production deployment.
