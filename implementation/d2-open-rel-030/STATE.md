# D2 / OPEN-REL-030 Evidence State

**State:** EVIDENCE COMPLETE — READY FOR EXACT-HEAD DECISION REVIEW  
**Production authority:** none  
**Track B acceptance authorization:** not granted  
**Wave 4 implementation authorization:** not granted  
**Production versions/numerics:** not selected; capacity envelopes remain `OPEN-REL-020` C3

## Current recommendation

Recommend C2 acceptance only if the complete invariant set below remains preserved together.

### Tier 1 — transactional and history authority

- canonical observation identity/content is immutable;
- active source generation, poll epoch and durable `live` poll claim come from owner-controlled state inside the acceptance transaction;
- current-state CAS is based on platform authority, never provider event time;
- late-history coverage is contiguous from `supported_history_floor` and bound to exact owner `authority_generation`, `provider_dataset_revision` and required snapshot currentness;
- owner-visible provider mutation invalidates prior coverage atomically; stable identity rewrite, DELETE and TRUNCATE fail closed;
- accepted stable identities are compared with owner-current canonical content before coverage publication whenever either side intersects the requested window, independently of current `became_visible_at`;
- every current `00[4-9]_history_*.sql` hardening module is executed by the extended runner and structurally guarded against orphaning.

### Physical PITR recovery authority

Recovery admission is not a bearer-grant check and not a local-receipt check. It is a surviving, authenticated, effect-bound, active-authority-bound, boundary-single-winner authority:

1. the source reaches committed `R`;
2. a real `(R,F]` business effect occurs and committed `F` is established;
3. surviving authority, outside the restored database, stores canonical authenticated effect evidence derived from the actual post-R source state;
4. each recovery grant is cryptographically bound to that exact effect digest;
5. the surviving singleton owns the active recovery tuple `(domain,R,F,successor_epoch,placement_version,required_receipt)` and is locked before winner-key derivation;
6. a valid signature is insufficient if any active-authority dimension differs: epoch-drift and placement-drift grants are rejected without creating another claim;
7. all equivalent grant IDs matching the active tuple map to one canonical `boundary_fingerprint` and one atomic `recovery_boundary_claim`;
8. the winner is bound to authenticated `session_user + restored-instance id + instance-proof fingerprint`;
9. same-instance retry converges, while another physical restore/clone cannot become a second winner by reusing credentials or switching equivalent grant IDs;
10. claim alone leaves the restored database at `R`; only verified recovery material can atomically apply the authenticated post-R effect and exact active successor authority;
11. material fetch locks/revalidates the active authority, exact grant, boundary claim and effect, holds signing state, then revalidates the complete authority→claim→grant→effect binding before returning recovery material;
12. verify and material-fetch fail closed if the grant no longer matches the active surviving-authority tuple;
13. local reconciled state is fenced to the expected successor epoch and placement version as defense in depth;
14. the effective hardened positive path itself is exercised after hardening is installed: reset the legitimate winner to exact `R`, then `claim → verify → fetch/apply → verify`, while preserving one boundary claim and clone rejection;
15. claim, verify and recovery-material fetch use caller-local bounded asynchronous transport; `connect_timeout` covers setup only, timeout/uncertainty returns fail-closed without synchronous remote cancellation/cleanup, and the C2 one-shot SQL session is retired;
16. an established authenticated TCP blackhole is exercised directly and must fail closed under the caller-local response deadline;
17. a locally recreated continuity receipt remains non-authoritative.

Post-enrollment clone hardening remains separately required:

- effective restored-instance proof is outside the `PGDATA` clone domain in the C2 evidence mechanism;
- a physical PGDATA copy after enrollment retains the same database-visible identity but does not inherit effective authority;
- clone claim/verify use caller-local asynchronous response deadlines, not synchronous established-session `dblink` response semantics;
- the clone vector includes both cooperative-stall and real established TCP-blackhole falsification before authority interpretation;
- timeout/uncertainty performs no synchronous remote cleanup; the one-shot SQL backend is retired;
- the clone-rejection negative is valid only after a same-path positive control proves the clone capability/helper/credential/transport path operational and binds the surviving-authority fingerprint to the clone-local capability fingerprint.

The evidence-only file/mount capability, LOGIN roles, `dblink` transport and one-shot session-retirement mechanism are **not** production identity/RPC/secret-store selections. Production must preserve the stronger non-shareable per-instance, locked active-authority, surviving-effect, effective-positive-path, consistent-fetch and independently bounded failure/cleanup properties through separately governed mechanisms.

### Tier 2 / relocation

- Timescale shared history remains acceptable only under the mediated profile: no direct tenant access to shared raw history/CAGG/internal materialization; fixed-search-path mediation; privileged automation owner explicitly isolated from tenant/application principals;
- typed canonicalization is total/injective across evaluated `timestamptz` and `numeric` domains;
- target checkpoint measurement/signing authority originates inside Tier 2; Tier 1 verifies but cannot mint;
- cross-authority verifier credentials remain restricted and absent from function source;
- the **effective final verifier transport**, not merely an earlier bootstrap definition, uses asynchronous caller-local response deadlines;
- timeout/send-error/uncertainty does not synchronously cancel or disconnect the remote peer; one-shot SQL session retirement closes abandoned connections;
- real established response blackholes are exercised in both Tier1→Tier2 and Tier2→Tier1 directions and must fail closed locally;
- source placement is locked before `F`; target completeness is canonical-set completeness, never max-only;
- Tier 1 placement transition + exact activation grant commit atomically;
- target remains `sealed` until it verifies that committed Tier 1 grant; after activation existing history remains immutable and only new append `>F` is eligible.

## Exact empirical anchor before this governance mutation

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

This anchor closes classes #46–#48 while preserving the complete prior Tier1/history, recovery #38–#45, Timescale, canonicalization and relocation package. It is provenance only after this governance mutation; the exact final documentation HEAD must independently rerun both gates.

Representative #180 additions:

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
physical_pitr_post_enrollment_helpers_use_bounded_transport=PASS
physical_pitr_post_enrollment_deadline_path_has_no_synchronous_cleanup=PASS
physical_pitr_post_enrollment_stalled_peer_fails_closed=PASS
physical_pitr_post_enrollment_local_deadline=PASS elapsed_ms=564
physical_pitr_post_enrollment_real_blackhole_fails_closed=PASS
physical_pitr_post_enrollment_real_blackhole_local_deadline=PASS elapsed_ms=518
physical_pitr_post_enrollment_timeout_backend_retirement=PASS one_shot_sql_session=true
relocation_response_deadline_has_no_synchronous_timeout_cleanup=PASS
relocation_effective_verifier_transport_uses_session_retirement=PASS
relocation_target_verifier_real_blackhole_fails_closed=PASS value=false
relocation_target_verifier_real_blackhole_local_deadline=PASS elapsed_ms=506
relocation_tier1_verifier_real_blackhole_fails_closed=PASS value=false
relocation_tier1_verifier_real_blackhole_local_deadline=PASS elapsed_ms=520
relocation_timeout_backend_retirement=PASS one_shot_sql_session=true
open_rel_030_extended_conformance=PASS
```

The same run preserves active-authority drift rejection, one boundary winner, authenticated effect application, locked recovery-material fetch, base PITR real-blackhole retirement, post-enrollment positive-control/clone negatives, all five history hardening modules (`004–008`), fresh-cluster Timescale restore/jobs, total typed canonicalization and complete Tier1↔Tier2 relocation activation/rollback vectors.

## Material classes #38–#48

- **#38 — post-enrollment PGDATA clone authority:** database-resident instance proof was copyable with PGDATA. Closed by keeping the effective C2 proof outside the physical database clone domain.
- **#39 — false-negative clone evidence:** fail-closed helper/transport failure could masquerade as capability rejection. Closed by a same-path positive control before the governed negative.
- **#40 — grant-id scoped single winner:** different grant IDs for one recovery event could create multiple winners. Closed by a canonical recovery-boundary fingerprint and atomic one-row boundary claim across equivalent grant IDs, including a real cross-grant race.
- **#41 — unauthenticated post-R reconciliation:** a restored database could recreate a receipt and mark reconciliation without applying the committed post-R effect. Closed by authenticated surviving effect evidence, grant→effect-digest binding and local mutation only from verified recovery material.
- **#42 — unbounded physical-recovery established response:** synchronous `dblink` response semantics could hang after connection establishment. Closed by asynchronous send/poll and a caller-local response deadline for claim/verify/material-fetch.
- **#43 — recovery-material fetch TOCTOU:** verify-then-unlocked-reread allowed an in-flight re-signed grant/effect substitution. Closed by a consistent locked authority→grant→claim→effect/signing-state snapshot and complete binding revalidation.
- **#44 — cooperative-delay false confidence:** `pg_sleep` did not prove a real established network blackhole, and synchronous cancel/disconnect could exceed the nominal deadline. Closed by removing synchronous timeout cleanup, retiring the one-shot SQL session and exercising a real TCP response blackhole.
- **#45 — validly signed drifted successor authority:** a grant reusing R/F/effect could alter successor epoch/placement and become independent authority. Closed by locking/validating the surviving active-authority tuple before winner derivation and revalidating it in verify/fetch/local successor fencing.
- **#46 — hardened positive-path gap:** the #45 definitions were installed only after the original successful recovery. Closed by resetting the legitimate winner to exact R after hardening and replaying successful hardened `claim → verify → fetch/apply → verify`, with one boundary claim and clone rejection preserved.
- **#47 — post-enrollment clone unbounded response:** clone claim/verify still used synchronous established-session `dblink`. Closed by bounded async local deadlines, real TCP-blackhole falsification and timeout-path one-shot backend retirement, while preserving same-path positive control and clone rejection.
- **#48 — relocation timeout cleanup outside deadline:** effective verifier timeout entered synchronous `dblink_disconnect`, which could hang under a real blackhole. Closed by an ordered final transport override with no synchronous timeout cleanup, one-shot session retirement and real response blackholes in both verification directions before downstream relocation authority operations.

## Acceptance boundary

```text
Evidence package             COMPLETE
Executable empirical anchor  f2a7f0c4cc1dedf02c64ed1129117f327d11931a / #2225 / #180
Material finding classes     48
Inline review threads        0 unresolved at anchor review
Exact-final-HEAD CI          REQUIRED AGAIN AFTER THIS GOVERNANCE MUTATION
Fresh Codex exact-head       REQUIRED
Native Assurance exact-head  REQUIRED AGAIN
Track B acceptance           EXPLICIT AUTHORIZATION REQUIRED
Wave 4 implementation        SEPARATE EXPLICIT AUTHORIZATION REQUIRED
Production authority         NONE
Merge                        NOT AUTHORIZED
```

Evidence completion, CI success, mergeability or reviewer cleanliness do not themselves accept `OPEN-REL-030`, authorize Wave 4, select production topology/numerics, or authorize merge. `READY_FOR_MERGE != AUTHORIZED_TO_MERGE`.
