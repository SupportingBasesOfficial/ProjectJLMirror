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
3. require physical PITR recovery admission from authenticated surviving `(R,F]` evidence external to the restored authority;
4. require deterministic versioned self-delimiting structured bytes before hash/MAC/signature;
5. select TimescaleDB as Tier 2 historical projection only under the mediated shared-history profile proven by this spike;
6. classify `ts_automation_owner` as LOGIN cross-tenant privileged infrastructure and require production admission controls to exclude tenant/application use;
7. reject direct pooled RLS assumptions for Timescale columnstore/CAGG on the evaluated profile;
8. require genuine fresh-cluster reconstruction of database-global role topology;
9. require source relocation placement authority to be locked before deriving `F`;
10. require target-owned authenticated sealed canonical-payload checkpoints before Tier 1 can authorize target placement;
11. require target checkpoint signing/mint authority exclusively on the target side;
12. require the effective checkpoint signing key to be generated inside target authority, not provisioned or retained by an external orchestrator acting across both databases;
13. require Tier 1 verification capability to exclude the target signing key or any equivalent mint capability;
14. require cross-authority verifier connection secrets to remain restricted authority-owned state rather than embedded in function source;
15. require Tier 1 successor placement and the exact durable activation grant to commit atomically, bound to tenant, `F`, checkpoint id/generation, target attestation and successor placement version;
16. require target `sealed → activated` to verify that exact committed Tier 1 grant; the target automation principal must not self-promote;
17. require cross-authority verification to be bounded/fail-closed and performed outside local authority-lock windows;
18. reject any target data above `F` before activation unless excluded by the target lifecycle;
19. preserve `OPEN-REL-020` as owner of production capacity/SLO/retention/cardinality/cost numerics;
20. treat database versions, image digests, evidence crypto, verifier transport, capability-store layout and concrete canonical encoding as reproducibility dependencies rather than immutable production selections.

## Exact empirical anchor before this review-document mutation

```text
HEAD
a0f9b03199d3881a48a18c52c826b9a36b65ac84

JLMIRROR Deterministic Assurance
run #2054
run id 33226307343
SUCCESS

JLMIRROR OPEN-REL-030 Conformance
run #95
run id 33226307321
SUCCESS
```

This SHA proves the executable mechanism after the authority-level key-provenance and verifier-secret panorama. It becomes provenance after this document mutation; the exact final package HEAD must rerun both gates.

## Tier 1 acceptance and history authority

The PostgreSQL harness establishes independent-session atomic create-or-observe, immutable canonical identity/content, owner source generation and poll epoch, durable live poll claims, current-state CAS independent from provider event time, historical obligation/outbox atomicity, crash rollback and post-COMMIT ambiguity convergence. Late-history workers cannot self-assert provider finality/currentness; durable owner state controls finalization and contiguous coverage.

## Physical PITR authority

A separate surviving control PostgreSQL, excluded from source backup/restore, owns recovery authority and issues a structured authenticated grant only after `F`. The restored database cannot self-mint admission. Delimiter framing is explicitly falsified; the grant is authenticated over deterministic self-delimiting structured fields. Recovery succeeds only after fresh verification of surviving authority.

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

Exact #95 evidence:

```text
relocation_tier1_has_no_target_signing_key=PASS
relocation_controller_does_not_retain_target_signing_key=PASS
relocation_target_authority_generated_signing_key=PASS
relocation_projection_writer_still_cannot_read_generated_signing_key=PASS
relocation_target_verifier_still_cannot_read_generated_signing_key=PASS
relocation_tier1_cannot_mint_target_attestation=PASS
relocation_fabricated_target_attestation_rejected=PASS
```

This closes the distinction between database-local key storage and actual authority-level key provenance.

### Verifier capability-secret isolation

The evidence harness uses random verifier LOGIN credentials plus `dblink` solely to exercise independent database authorities. Credentials live in restricted owner-controlled capability tables; owner `SECURITY DEFINER` helpers use fixed search paths. Verifier/automation principals cannot read the tables, and the secrets are not embedded in `pg_proc` function source.

Exact #95 evidence:

```text
relocation_tier1_verifier_cannot_read_target_connection_capability=PASS
relocation_projection_writer_cannot_read_tier1_connection_capability=PASS
relocation_target_verifier_cannot_read_tier1_connection_capability=PASS
relocation_target_verifier_secret_not_in_function_source=PASS
relocation_tier1_verifier_secret_not_in_function_source=PASS
```

This is evidence-only secret plumbing; it does not select production database authentication, network, service RPC or secret-distribution topology.

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

Remote verification occurs before local authority locks. After verification, each side performs only short local transactional/CAS work. Verification failure or uncertainty fails closed. Production may use a service/API, asymmetric verifier, KMS-backed verification or another mechanism only if it preserves issuer/verifier separation, target-only mint authority, bounded verification, exact grant binding and the same failure semantics.

## Material finding classes closed by D2

The evidence program has repaired the following classes, with panoramic review after each repair:

1. conflicting observation content under stable identity;
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
22. verifier connection secrets being embedded in SQL function source rather than restricted authority capability state.

## What acceptance would and would not mean

If the exact-final-HEAD package is reviewed clean and Track B is explicitly accepted, `OPEN-REL-030` may be selected/conformed for the accepted mechanism/profile. Wave 4 implementation remains separately unauthorized.

Acceptance would not freeze production PostgreSQL/Timescale versions, KMS/HSM topology, database authentication/network/RPC topology, verifier secret-store mechanism, capacity numerics, or the exact evidence encoding/`dblink` mechanism.

## Review disposition

```text
Evidence completeness        COMPLETE
Executable empirical anchor  a0f9b03199d3881a48a18c52c826b9a36b65ac84 / #2054 / #95
Final documentation HEAD     REQUIRES FRESH EXACT-HEAD CI
Codex final review           REQUIRED
Native Assurance             REQUIRED
OPEN-REL-030 canonical state NOT YET ACCEPTED
Track B acceptance           EXPLICIT AUTHORIZATION REQUIRED
Wave 4 implementation        SEPARATE AUTHORIZATION REQUIRED
Merge                        NOT AUTHORIZED BY THIS RECORD
```
