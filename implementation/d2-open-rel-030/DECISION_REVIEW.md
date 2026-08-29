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
3. bind every late-history coverage run to the exact owner `authority_generation` as well as owner-required snapshot currentness;
4. invalidate prior materialized reconciliation coverage whenever owner authority generation advances, even if snapshot/finality timestamps remain equal;
5. reject conflicting provider-visible canonical content under an already accepted `(stream_id, observation_id)` before recording any reconciliation coverage;
6. require physical PITR recovery admission from authenticated surviving `(R,F]` evidence external to the restored authority;
7. require surviving recovery-grant consumption to be atomic single-winner authority derived from an authenticated surviving-authority session principal, never a caller-supplied target/principal identifier;
8. require recovery claim/verification interfaces to resolve grant facts internally and expose no direct grant-table read privilege to recovery principals;
9. require deterministic versioned self-delimiting structured bytes before hash/MAC/signature;
10. select TimescaleDB as Tier 2 historical projection only under the mediated shared-history profile proven by this spike;
11. classify `ts_automation_owner` as LOGIN cross-tenant privileged infrastructure and require production admission controls to exclude tenant/application use;
12. reject direct pooled RLS assumptions for Timescale columnstore/CAGG on the evaluated profile;
13. require genuine fresh-cluster reconstruction of database-global role topology;
14. require source relocation placement authority to be locked before deriving `F`;
15. require target-owned authenticated sealed canonical-payload checkpoints before Tier 1 can authorize target placement;
16. require target checkpoint signing/mint authority exclusively on the target side;
17. require the effective checkpoint signing key to be generated inside target authority, not provisioned or retained by an external orchestrator acting across both databases;
18. require Tier 1 verification capability to exclude the target signing key or any equivalent mint capability;
19. require cross-authority verifier connection secrets to remain restricted authority-owned state rather than embedded in function source;
20. require Tier 1 successor placement and the exact durable activation grant to commit atomically, bound to tenant, `F`, checkpoint id/generation, target attestation and successor placement version;
21. require target `sealed → activated` to verify that exact committed Tier 1 grant; the target automation principal must not self-promote;
22. require cross-authority verification to be bounded/fail-closed both at connection establishment and after a peer has connected; established-call response deadlines must be locally enforced by the caller and verification must remain outside local authority-lock windows;
23. reject any target data above `F` before activation unless excluded by the target lifecycle;
24. preserve `OPEN-REL-020` as owner of production capacity/SLO/retention/cardinality/cost numerics;
25. treat database versions, image digests, evidence crypto, recovery/verifier LOGIN mechanisms, verifier transport, capability-store layout, local evidence deadlines and concrete canonical encoding as reproducibility dependencies rather than immutable production selections.

## Exact empirical anchor before this review-document mutation

```text
HEAD
176018388292c3842619292de2eba8947642bc1a

JLMIRROR Deterministic Assurance
run #2092
run id 33228913654
SUCCESS

JLMIRROR OPEN-REL-030 Conformance
run #114
run id 33228913650
SUCCESS
```

This SHA proves the executable mechanism after the generation-bound owner-current history repair, authenticated-principal single-winner recovery hardening and caller-local post-connect verifier deadline repair. It becomes provenance after this document mutation; the exact final package HEAD must rerun both gates.

## Tier 1 acceptance and owner-current history authority

The PostgreSQL harness establishes independent-session atomic create-or-observe, immutable canonical identity/content, owner source generation and poll epoch, durable live poll claims, current-state CAS independent from provider event time, historical obligation/outbox atomicity, crash rollback and post-COMMIT ambiguity convergence.

Late-history workers cannot self-assert provider authority, finality or currentness. Durable `provider_authority` owns `authority_generation`, `current_snapshot_at`, `finality_floor` and `required_reconciliation_snapshot_at`.

Coverage is valid only for the **exact current generation**. `contiguous_covered_through(...)` filters by current `authority_generation` and owner-required snapshot. `advance_provider_authority(...)` clears materialized coverage and transitions every non-gap stream to `reconciliation_required`, including a generation advance that keeps all timestamps unchanged. Therefore a provider correction/revision cannot recycle previous-generation coverage simply by retaining the same snapshot timestamp.

Accepted history is also immutable under stable reconciliation identity. `sweep(...)` compares owner-visible `observed_at` and `numeric_value` against an existing accepted row before any insert/run record; mismatch raises `reconciled observation identity content mismatch`. The rejected sweep cannot change accepted canonical content or create a `reconciliation_run`.

Exact #114 proves:

```text
history_conflicting_observation_rejected=PASS
history_generation_bound_coverage=PASS
history_owner_currentness_authority=PASS
late_history_reconciliation=PASS
```

## Physical PITR authority and authenticated-principal single-winner recovery

A separate surviving control PostgreSQL, excluded from source backup/restore, owns recovery authority and issues a structured authenticated grant only after `F`. The restored database cannot self-mint admission. Delimiter framing is explicitly falsified; the grant is authenticated over deterministic self-delimiting structured fields.

A valid signature is necessary but not sufficient. The bounded claim interface is intentionally reduced to `claim_grant(grant_id)` and `verify_claimed_grant(grant_id)`. Recovery principals have EXECUTE but no direct read privilege on `recovery_grant`. The surviving authority loads the grant internally, reconstructs and verifies its canonical HMAC, derives the claimant from `session_user`, locks the grant and atomically binds it to the first authenticated principal. The same principal may retry after ambiguity; a different authenticated principal receives false. The claim function accepts no caller-supplied target ID or principal identity and no caller-supplied signed grant fields. A rival credential used with the winner role name must fail authentication.

The harness also issues a dedicated grant and races two independently authenticated principals. Exactly one must win, the winner retry must succeed, the loser retry must fail, and the persisted binding must equal the authenticated winner principal.

Exact #114 proves:

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

The concrete PostgreSQL LOGIN/password path is evidence-only. Production may use another identity/authentication mechanism only if retries/admission remain bound to the same authenticated authority and caller-copyable identifiers cannot substitute for that authority.

## Timescale mediated profile

On TimescaleDB 2.29.2 / PostgreSQL 17.11, direct pooled `RLS + columnstore` and `RLS + continuous aggregate` are ineligible (`0A000`). The surviving profile uses fixed-search-path `SECURITY DEFINER` mediation, NOLOGIN `ts_owner`, and separate least-privilege LOGIN `ts_automation_owner` only for evaluated job-bearing objects. Production connection/admission controls remain an explicit requirement.

## Tier 1 ↔ Tier 2 relocation

### Source fence and target lifecycle

Source placement is locked before deriving `F`; an in-flight authoritative acceptance must resolve first and is included. `max(target)=F` is not completeness.

```text
open
  staging allowed
  seal rejects any row > F

sealed
  all target-history DML rejected
  target cannot self-activate

Tier 1 committed activation authority
  exact target checkpoint verified
  placement + exact activation grant committed atomically

activated
  only after target verifies exact Tier 1 grant
  existing history immutable
  new append only > F
```

### Canonical checkpoint message

Target and verifier construct the same deterministic self-delimiting checkpoint message before HMAC. Cross-store equality is required, but equal bytes do not imply equal signing authority.

### Target signing-key provenance

The effective HMAC key is generated inside Tier 2 target authority using target-side randomness. The trusted disposable-lab controller may administer both databases for setup and fault injection, but it does not provision or retain the protocol key. Tier 1 contains no target signing-key relation. Projection writer and verifier principals cannot read the generated key.

Exact #114 preserves:

```text
relocation_tier1_has_no_target_signing_key=PASS
relocation_controller_does_not_retain_target_signing_key=PASS
relocation_target_authority_generated_signing_key=PASS
relocation_projection_writer_still_cannot_read_generated_signing_key=PASS
relocation_target_verifier_still_cannot_read_generated_signing_key=PASS
relocation_tier1_cannot_mint_target_attestation=PASS
relocation_fabricated_target_attestation_rejected=PASS
```

### Verifier capability-secret isolation and bounded established calls

The evidence harness uses random verifier LOGIN credentials plus `dblink` solely to exercise independent database authorities. Credentials live in restricted owner-controlled capability tables; owner `SECURITY DEFINER` helpers use fixed search paths. Verifier/automation principals cannot read the tables, and the secrets are not embedded in `pg_proc` function source.

The raw asynchronous transport helper is not executable by verifier/projection principals. Connection establishment uses `connect_timeout=1`. After connection, `dblink_send_query` + `dblink_is_busy` are polled against a caller-local deadline; timeout/uncertainty disconnects and returns false. A five-second remote delay probe is tested against a 500 ms local probe deadline and must return well below 1.8 seconds.

Exact #114 proves:

```text
relocation_tier1_verifier_cannot_call_raw_bounded_transport=PASS
relocation_target_principals_cannot_call_raw_bounded_transport=PASS
relocation_target_verifier_stalled_peer_fails_closed=PASS
relocation_target_verifier_local_deadline=PASS
relocation_tier1_verifier_stalled_peer_fails_closed=PASS
relocation_tier1_verifier_local_deadline=PASS
```

Observed evidence durations were approximately 579 ms and 581 ms. These values are laboratory evidence, not production timeout selections.

### Durable activation grant and atomic rollback

After target checkpoint verification, Tier 1 re-establishes local authority under lock and commits placement plus the exact activation grant in one PostgreSQL transaction. The target remains sealed until it independently verifies that grant.

The fault injection preoccupies the grant identity after the placement-UPDATE path begins, forcing a unique violation and proving full rollback:

```text
relocation_target_cannot_self_activate_before_tier1_grant=PASS
relocation_premature_mark_keeps_future_insert_blocked=PASS
relocation_activation_commit_conflict_rolls_back=PASS
relocation_activation_conflict_preserves_fenced_placement=PASS
relocation_activation_conflict_did_not_replace_grant=PASS
relocation_conflicting_grant_cannot_activate_target=PASS
relocation_activation_conflict_keeps_target_sealed=PASS
relocation_activation_grant_placement_atomicity=PASS
relocation_tier1_activation_grant_committed=PASS
```

Neither authority can unilaterally create the full cutover state.

## Cross-authority call ordering

Remote verification occurs before local authority locks. Connection establishment and established-response time are independently bounded by the caller; after successful verification, each side performs only short local transactional/CAS work. Verification failure, disconnect, deadline expiry or uncertainty fails closed. Production may use a service/API, asymmetric verifier, KMS-backed verification or another mechanism only if it preserves issuer/verifier separation, target-only mint authority, bounded verification, exact grant binding and the same failure semantics.

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
28. recovery principals needing direct grant-table reads or caller-supplied signed grant facts to consume authority.

## What acceptance would and would not mean

If the exact-final-HEAD package is reviewed clean and Track B is explicitly accepted, `OPEN-REL-030` may be selected/conformed for the accepted mechanism/profile. Wave 4 implementation remains separately unauthorized.

Acceptance would not freeze production PostgreSQL/Timescale versions, KMS/HSM topology, database authentication/network/RPC topology, recovery identity mechanism, verifier secret-store mechanism, production timeout numerics, capacity numerics, or the exact evidence encoding/`dblink` mechanism.

## Review disposition

```text
Evidence completeness        COMPLETE
Executable empirical anchor  176018388292c3842619292de2eba8947642bc1a / #2092 / #114
Final documentation HEAD     REQUIRES FRESH EXACT-HEAD CI
Codex final review           REQUIRED
Native Assurance             REQUIRED
OPEN-REL-030 canonical state NOT YET ACCEPTED
Track B acceptance           EXPLICIT AUTHORIZATION REQUIRED
Wave 4 implementation        SEPARATE AUTHORIZATION REQUIRED
Merge                        NOT AUTHORIZED BY THIS RECORD
```
