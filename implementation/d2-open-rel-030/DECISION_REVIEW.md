# D2 / OPEN-REL-030 — Decision Review Record

**Decision:** `OPEN-REL-030` — customer-monitoring durable acceptance/projection mechanism  
**Class:** C2 bounded evidence-generating implementation decision  
**Canonical spike base:** `main@5f031ae4bacc0c441eeee16f9c67d272e39d6b0b`  
**Current disposition:** evidence complete; recommendation ready for exact-HEAD review; not yet accepted  
**Production authority:** none  
**Track B acceptance authorization:** not granted  
**Wave 4 implementation authorization:** not granted

## Recommendation

Subject to exact-final-HEAD review and explicit Track B acceptance:

1. select the ADR-008 PostgreSQL transactional acceptance pattern as Tier 1 only with immutable canonical observation content, owner-controlled active source/poll authority, durable live poll claims and current-state CAS by platform ordering authority;
2. require late-history finality/currentness from durable provider-owner authority, never worker/caller timestamps;
3. bind every late-history coverage run to the exact owner `authority_generation`, exact current `provider_dataset_revision` and owner-required snapshot currentness;
4. invalidate prior materialized reconciliation coverage whenever owner authority generation advances, even if snapshot/finality timestamps remain equal;
5. atomically increment `provider_dataset_revision` and invalidate coverage for owner-visible provider INSERT/UPDATE, including same-generation corrections whose timestamps do not advance;
6. prohibit stable provider identity rewrite and require destructive provider-history DELETE/TRUNCATE to fail closed unless a separate explicit governed gap/authority path is selected;
7. keep the reconciliation worker out of direct provider-history INSERT/UPDATE/DELETE/TRUNCATE and provider-owner/trigger-administration authority;
8. require every ordered history hardening module matching `00[4-9]_history_*.sql` to be wired into the extended conformance runner, with CI failing if an existing reviewer-critical module is omitted;
9. reject conflicting provider-visible canonical content under an already accepted `(stream_id, observation_id)` before recording any reconciliation coverage;
10. perform stable-identity conflict validation before provider-time window selection whenever either the accepted or owner-current timestamp intersects the requested window, so a correction that moves across a window boundary cannot mint false coverage;
11. require physical PITR recovery admission from authenticated surviving `(R,F]` evidence external to the restored authority;
12. require surviving recovery-grant consumption to be atomic single-winner authority derived from an authenticated surviving-authority session principal, never a caller-supplied target/principal identifier;
13. require recovery claim/verification interfaces to resolve grant facts internally and expose no direct grant-table read privilege to recovery principals;
14. require deterministic versioned self-delimiting structured bytes before hash/MAC/signature;
15. require canonical typed values themselves to be total and injective over the full accepted domain: PostgreSQL `timestamptz` must preserve finite UTC time, microseconds and explicit AD/BC era plus distinct exact `infinity`/`-infinity`; unconstrained PostgreSQL `numeric` must normalize finite values and preserve distinct exact `NaN`, `Infinity` and `-Infinity` values before field framing;
16. select TimescaleDB as Tier 2 historical projection only under the mediated shared-history profile proven by this spike;
17. classify `ts_automation_owner` as LOGIN cross-tenant privileged infrastructure and require production admission controls to exclude tenant/application use;
18. reject direct pooled RLS assumptions for Timescale columnstore/CAGG on the evaluated profile;
19. require genuine fresh-cluster reconstruction of database-global role topology;
20. require source relocation placement authority to be locked before deriving `F`;
21. require target-owned authenticated sealed canonical-payload checkpoints before Tier 1 can authorize target placement;
22. require target checkpoint signing/mint authority exclusively on the target side;
23. require the effective checkpoint signing key to be generated inside target authority, not provisioned or retained by an external orchestrator acting across both databases;
24. require Tier 1 verification capability to exclude the target signing key or any equivalent mint capability;
25. require cross-authority verifier connection secrets to remain restricted authority-owned state rather than embedded in function source;
26. require Tier 1 successor placement and the exact durable activation grant to commit atomically, bound to tenant, `F`, checkpoint id/generation, target attestation and successor placement version;
27. require target `sealed → activated` to verify that exact committed Tier 1 grant; the target automation principal must not self-promote;
28. require cross-authority verification to be bounded/fail-closed both at connection establishment and after a peer has connected; established-call response deadlines must be locally enforced by the caller and verification must remain outside local authority-lock windows;
29. reject any target data above `F` before activation unless excluded by the target lifecycle;
30. preserve `OPEN-REL-020` as owner of production capacity/SLO/retention/cardinality/cost numerics;
31. treat database versions, image digests, evidence crypto, recovery/verifier LOGIN mechanisms, verifier transport, capability-store layout, local evidence deadlines and concrete canonical encoding as reproducibility dependencies rather than immutable production selections.

## Exact empirical anchor before reviewer-document mutation

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

This anchor proves the executable mechanism after generation/revision-bound owner-current history repair, cross-window stable-identity hardening, provider dataset mutation fencing, destructive DELETE/TRUNCATE fail-closed behavior, history-runner completeness guarding, authenticated-principal single-winner recovery, total/injective AD/BC/non-finite `timestamptz` canonicalization, total/injective finite-and-special-value `numeric` canonicalization, target-owned relocation authority and caller-local post-connect verifier deadline repair. It becomes provenance after reviewer-document mutation; the exact final package HEAD must independently rerun both gates.

## Tier 1 acceptance and owner-current history authority

The PostgreSQL harness establishes independent-session atomic create-or-observe, immutable canonical identity/content, owner source generation and poll epoch, durable live poll claims, current-state CAS independent from provider event time, historical obligation/outbox atomicity, crash rollback and post-COMMIT ambiguity convergence.

Durable `provider_authority` owns `authority_generation`, `provider_dataset_revision`, `current_snapshot_at`, `finality_floor` and `required_reconciliation_snapshot_at`. Coverage is valid only for the exact current generation + exact current provider dataset revision + owner-required snapshot currentness. `advance_provider_authority(...)` clears materialized coverage; owner-visible provider INSERT/UPDATE increments dataset revision and invalidates coverage in the same transaction. `sweep(...)` and provider mutation serialize on the same `provider_authority` row.

Stable provider identity cannot be rewritten. DELETE is rejected and statement-level TRUNCATE has an independent fail-closed guard. The reconciliation worker has no direct provider INSERT/UPDATE/DELETE/TRUNCATE privilege, no provider-owner membership and no trigger-administration path. Production owner/superuser governance remains an explicit deployment trust boundary.

Accepted history is immutable under stable reconciliation identity. Conflict validation occurs before provider-time-only selection: when either accepted or owner-current `observed_at` intersects the requested window, immutable timestamp/value content is compared. Any mismatch rejects before a `reconciliation_run` can be minted.

The structural CI guard enumerates every existing `00[4-9]_history_*.sql` file and fails if it is not referenced by `run_conformance_extended.sh`. Exact #138 reports `history_modules=4` and executes `004 → 005 → 006 → 007`.

Representative #138 markers:

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

## Physical PITR authority and authenticated-principal single-winner recovery

A separate surviving control PostgreSQL, excluded from source backup/restore, owns recovery authority and issues a structured authenticated grant only after `F`. A local restored receipt is insufficient. Grant fields use deterministic self-delimiting canonical representation before HMAC.

The bounded claim interface is `claim_grant(grant_id)` / `verify_claimed_grant(grant_id)`. Recovery principals have EXECUTE but no direct read privilege on `recovery_grant`. The surviving authority loads and verifies the grant internally, derives the claimant from `session_user`, locks the grant and atomically binds it to the first authenticated principal. Same-principal retry converges; another authenticated principal returns false. Caller-supplied target/principal identity and caller-supplied signed grant facts are not authority inputs.

Representative #138 markers include:

```text
physical_pitr_recovery_claim_api_id_only=PASS
physical_pitr_recovery_claim_identity_from_authenticated_session=PASS
physical_pitr_recovery_principal_no_direct_grant_read=PASS
physical_pitr_recovery_principal_spoof_rejected=PASS
physical_pitr_tampered_grant_cannot_claim=PASS
physical_pitr_recovery_claim_single_winner_race=PASS
physical_pitr_recovery_grant_same_principal_retry=PASS
physical_pitr_recovery_grant_other_principal_rejected=PASS
physical_pitr_recovery_grant_authenticated_principal_binding=PASS
physical_pitr_duplicate_restored_authority_not_admitted=PASS
physical_pitr_recovery_single_winner_authenticated_principal=PASS
physical_pitr_post_reconcile_admission=PASS authority=surviving_external_authenticated_single_winner_principal
```

The concrete PostgreSQL LOGIN/password path is evidence-only; production identity/authentication remains separately selected.

## Timescale mediated profile

On TimescaleDB 2.29.2 / PostgreSQL 17.11, direct pooled `RLS + columnstore` and `RLS + continuous aggregate` are ineligible (`0A000`). The surviving profile uses fixed-search-path `SECURITY DEFINER` mediation, NOLOGIN `ts_owner`, and least-privilege LOGIN `ts_automation_owner` only as explicit cross-tenant privileged infrastructure. `PASSWORD NULL` is not treated as NOLOGIN or as production admission proof.

Fresh-cluster restore reconstructs the minimum role topology and re-runs tenant-isolation/escalation attacks after restore and after restored background-job execution.

## Tier 1 ↔ Tier 2 relocation

Tier 1 locks source placement before deriving `F`; an in-flight authoritative acceptance must resolve first and be included. `max(target)=F` is never completeness. Target state is measured and sealed by target authority; any target row `>F` before activation prevents seal, and `sealed` rejects all DML until authorized activation.

### Canonical typed values before cryptography

Target and verifier construct deterministic self-delimiting messages. Equal bytes are required across stores but do not imply equal signing authority.

#### `timestamptz`

Finite values serialize in UTC with microseconds and explicit `AD`/`BC`. PostgreSQL non-finite values use reserved exact `-infinity` / `infinity` literals. Both `authoritative_digest(...)` and `target_digest(...)` are statically verified to call `canonical_timestamp(...)` before field framing.

```text
relocation_timestamp_era_injective=PASS
relocation_timestamp_era_cross_store=PASS
relocation_timestamp_negative_infinity_canonical=PASS value=-infinity
relocation_timestamp_positive_infinity_canonical=PASS value=infinity
relocation_timestamp_nonfinite_cross_store=PASS
relocation_timestamp_nonfinite_digest_injective=PASS
relocation_digest_uses_total_timestamp_canonicalizer=PASS
```

#### `numeric`

The relocation evidence column is unconstrained PostgreSQL `numeric`. `canonical_numeric(...)` maps finite values through `trim_scale(...)::text` and maps `NaN`, `Infinity` and `-Infinity` to exact reserved literals before self-delimiting field framing. Both stores must produce the same canonical representation and distinct special-value digest material; the effective digest functions are statically verified to call the numeric canonicalizer.

```text
relocation_numeric_nan_canonical=PASS value=NaN
relocation_numeric_positive_infinity_canonical=PASS value=Infinity
relocation_numeric_negative_infinity_canonical=PASS value=-Infinity
relocation_numeric_finite_scale_canonical=PASS value=1.23
relocation_numeric_special_values_cross_store=PASS
relocation_numeric_special_value_digest_injective=PASS
relocation_digest_uses_total_numeric_canonicalizer=PASS
```

### Target signing-key provenance and verifier separation

The effective HMAC key is generated inside Tier 2 target authority using target-side randomness. The cross-database test controller may administer the disposable laboratory but does not provision or retain the protocol key. Tier 1 has no target signing-key relation; projection writer and verifier principals cannot read it.

Verifier connection credentials live in restricted owner-controlled capability tables and are absent from SQL function source. Raw bounded transport is owner-only. `connect_timeout` bounds setup; asynchronous `dblink_send_query` + `dblink_is_busy` polling enforces a caller-local post-connect response deadline. Failure or uncertainty returns false before local authority locks are acquired.

### Durable activation grant and atomic rollback

Tier 1 verifies the exact target checkpoint, then commits successor placement plus a durable activation grant bound to tenant, `F`, checkpoint id/generation, target attestation and successor placement version in one local transaction. Target remains sealed until it independently verifies that exact committed grant. A deliberately conflicting grant after the placement-update path forces a unique violation and proves the whole Tier 1 transaction rolls back.

Representative evidence:

```text
relocation_tier1_has_no_target_signing_key=PASS
relocation_controller_does_not_retain_target_signing_key=PASS
relocation_target_authority_generated_signing_key=PASS
relocation_target_verifier_stalled_peer_fails_closed=PASS
relocation_tier1_verifier_stalled_peer_fails_closed=PASS
relocation_tier1_cannot_mint_target_attestation=PASS
relocation_target_cannot_self_activate_before_tier1_grant=PASS
relocation_activation_commit_conflict_rolls_back=PASS
relocation_activation_conflict_preserves_fenced_placement=PASS
relocation_activation_grant_placement_atomicity=PASS
relocation_tier1_activation_grant_committed=PASS
tenant_relocation_tier1_tier2_continuity=PASS
```

## Material finding classes closed by D2

The evidence program has repaired the following classes, with panoramic review after each repair:

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
18. Tier 1 holding the target checkpoint HMAC key and inheriting mint capability;
19. target automation leaving `sealed` before Tier 1 grant;
20. placement/grant needing explicit all-or-nothing failure evidence;
21. signing key being generated/provisioned by the cross-database controller instead of target authority;
22. verifier connection secrets being embedded in SQL function source rather than restricted authority capability state;
23. reconciliation coverage reusable across authority-generation changes when timestamps remained equal;
24. owner-current provider history conflicting with persisted accepted content being silently treated as a duplicate;
25. surviving recovery grant behaving as a reusable bearer across multiple restored authorities instead of a single-winner claim;
26. established cross-authority `dblink` calls lacking a caller-local response deadline after TCP connection succeeded;
27. recovery single-winner binding relying on a caller-copyable target identifier instead of authenticated surviving-authority session identity;
28. recovery principals needing direct grant-table reads or caller-supplied signed grant facts to consume authority;
29. stable reconciled identity corrections escaping validation when owner-current timestamp crosses the requested sweep-window boundary;
30. relocation timestamp canonicalization being non-injective across PostgreSQL BC/AD eras;
31. provider-visible dataset mutation being able to leave completed coverage reusable without an owner dataset-revision change;
32. a reviewer-critical history hardening module being present in the branch but omitted from the extended runner, producing false-green assurance for an unexecuted fix;
33. PostgreSQL non-finite `timestamptz` values becoming NULL/omitted under `to_char(...)`, allowing `infinity` / `-infinity` timestamp facts to disappear from the digest;
34. statement-level `TRUNCATE` bypassing row-level provider dataset revision/destructive-mutation triggers;
35. unconstrained PostgreSQL `numeric` special values (`NaN`, `Infinity`, `-Infinity`) lacking explicit total/injective cross-store canonicalization before relocation hashing.

## What acceptance would and would not mean

If the exact-final-HEAD package is reviewed clean and Track B is explicitly accepted, `OPEN-REL-030` may be selected/conformed for the accepted mechanism/profile. Wave 4 implementation remains separately unauthorized.

Acceptance would not freeze production PostgreSQL/Timescale versions, KMS/HSM topology, database authentication/network/RPC topology, recovery identity mechanism, verifier secret-store mechanism, production timeout numerics, capacity numerics, or the exact evidence encoding/`dblink` mechanism.

## Review disposition

```text
Evidence completeness        COMPLETE
Executable empirical anchor  4c6e3a051d76b257df8058bf2b4503e2b6d84013 / #2141 / #138
Material finding classes     35 closed by current mechanism
Final documentation HEAD     REQUIRES FRESH EXACT-HEAD CI AFTER THIS MUTATION
Codex final review           REQUIRED ON FINAL EXACT HEAD
Native Assurance             REQUIRED ON FINAL EXACT HEAD
OPEN-REL-030 canonical state NOT YET ACCEPTED
Track B acceptance           EXPLICIT AUTHORIZATION REQUIRED
Wave 4 implementation        SEPARATE AUTHORIZATION REQUIRED
Merge                        NOT AUTHORIZED BY THIS RECORD
```
