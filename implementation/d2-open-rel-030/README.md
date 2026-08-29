# D2 — OPEN-REL-030 Monitoring Conformance Evidence

**Status:** evidence complete — ready for exact-HEAD decision review; no production authority  
**Canonical base:** `main@5f031ae4bacc0c441eeee16f9c67d272e39d6b0b`  
**Branch:** `evidence/open-rel-030-monitoring-conformance`  
**Decision under test:** `docs/11-reliability-resilience/OPEN-REL-030-decision-record.md`  
**Track B acceptance:** not granted  
**Wave 4 implementation authorization:** not granted

## Purpose

This package is a bounded reproducible falsification laboratory for `OPEN-REL-030`. It does not implement the Monitoring product vertical and grants no production authority.

It evaluates:

1. **Tier 1 PostgreSQL:** transactional acceptance/idempotency, owner source/poll authority, current-state CAS, ambiguity recovery, owner-current late-history reconciliation, physical PITR and relocation authority.
2. **Tier 2 TimescaleDB:** tenant isolation, feature compatibility, privileged jobs, genuine fresh-cluster restore, target-owned checkpoint/freeze authority and bounded mechanism fitness.

## Non-negotiable boundaries

- Provider event time is metadata, never current-state authority.
- Worker/caller assertions never substitute for source, poll, provider-finality, recovery or target-checkpoint authority.
- History coverage is contiguous and bound to exact owner generation + dataset revision + required snapshot currentness.
- Owner-visible provider mutation invalidates prior coverage atomically; stable identity rewrite, DELETE and TRUNCATE fail closed.
- Stable accepted identities are validated against owner-current canonical content independently of current `became_visible_at`.
- Every current history-hardening module must be executed by the extended runner and protected by anti-orphan structural CI.
- Structured cryptographic evidence uses deterministic self-delimiting representation; typed canonical values are total/injective across their accepted domains.
- Recovery authorization is not a reusable bearer grant and a reusable external credential is not a restored-instance identity.
- **One active recovery event has one winner even when multiple equivalent valid grant IDs represent it.** `grant_id` is not authority.
- **A valid grant signature does not create a new recovery event.** Before winner-key derivation, the surviving singleton active-authority tuple must be locked; any grant with drifted domain/R/F/successor epoch/placement/receipt fails closed even if its signature is valid.
- **Recovery admission must authenticate what survived `(R,F]`, not merely who may recover.** Every grant is bound to an authenticated surviving effect digest, and local reconciliation is derived from applying verified recovery material.
- Recovery material must be fetched from one consistent authority snapshot: revalidate active authority, lock grant, boundary claim and effect, hold signing state, then revalidate authority→claim→grant→effect before returning material.
- Claim alone cannot mark reconciliation complete and a locally recreated continuity receipt cannot admit recovery.
- Local reconciled state must remain fenced to the exact active successor epoch and placement.
- **The effective hardened recovery path must itself complete a legitimate positive admission.** After active-authority hardening is installed, a reset-to-R winner must succeed through `claim → verify → fetch/apply → verify`.
- Independent restores and post-enrollment PGDATA copies must not duplicate the effective restored-instance authority.
- A fail-closed clone negative is accepted as evidence only after the same clone proves its capability/helper/credential/transport path operational through a positive-control grant.
- Recovery and post-enrollment clone RPC require caller-local established-response deadlines; `connect_timeout` only bounds connection setup.
- A cooperative server delay is insufficient deadline evidence by itself: an established authenticated TCP blackhole must also fail closed locally without synchronous remote cancel/cleanup extending the deadline path.
- Target signing material originates/remains in target authority; verification does not imply mint capability.
- Cross-authority activation requires explicit durable authority from both sides and target cannot self-promote.
- **The effective final relocation verifier must not synchronously cancel/disconnect on deadline expiry.** Real response blackholes in both verification directions must fail closed under the caller-local deadline with bounded cleanup or equivalent session retirement.
- A single cross-tenant leak rejects the candidate profile.
- `OPEN-REL-020` retains production telemetry capacity/numeric ownership.
- Evidence database versions, HMAC/SHA, `dblink`, LOGIN roles, capability mounts/stores, one-shot session retirement and deadlines are reproducibility dependencies, not production selections.
- `READY_FOR_MERGE != AUTHORIZED_TO_MERGE`.

## Tier 1 history authority

`provider_authority` owns generation, dataset revision, current snapshot, finality floor and required reconciliation snapshot. A reconciliation run contributes to coverage only when those owner-controlled dimensions still match. Provider mutation and `sweep(...)` serialize on the same authority row.

Stable identity validation happens before coverage publication. For an already accepted `(stream_id, observation_id)`, current provider visibility timing cannot suppress immutable-content comparison.

The runner executes:

```text
004_history_reconciliation.sql
005_history_identity_window_hardening.sql
006_history_dataset_revision_hardening.sql
007_history_dataset_revision_edge_hardening.sql
008_history_visibility_correction_hardening.sql
```

The workflow independently enumerates matching `00[4-9]_history_*.sql` files and fails if any current module is absent from the runner.

## Physical PITR recovery model

### 1. Exact R and surviving post-R effect

The harness physically restores PostgreSQL to committed `R` and proves the restored state contains neither the later business change nor the continuity receipt. The live source then reaches committed `F` after the real post-R change.

After `F`, the separate surviving control authority records canonical `recovery_effect` evidence derived from the **actual source state** and authenticates it. Recovery grants include the exact effect digest and cannot validate against absent/tampered/mismatched effect evidence.

### 2. Active authority and one winner per recovery event

The surviving singleton is the authority for the currently recoverable event:

```text
(expected_domain, R, F, expected_successor_epoch, expected_placement_version, required_receipt)
```

`claim_grant(...)` locks this row before deriving the winner key. The boundary fingerprint is derived from this locked tuple. An otherwise-valid grant must match it exactly before it can participate in the single-winner CAS. `verify_claimed_grant(...)` and `fetch_claimed_recovery_material(...)` revalidate the same authority.

For equivalent grants that match the active tuple, `recovery_boundary_claim.boundary_fingerprint` remains the single-winner key. Sequential and concurrent cross-grant tests prove one claim row and same-winner convergence.

### 3. Effect-bound, consistent local reconciliation

A successful boundary claim does not mutate local business truth. Only after surviving authority verifies the winner may `fetch_claimed_recovery_material(...)` return recovery material. That fetch revalidates active authority, locks the exact grant, canonical boundary claim and referenced effect, holds signing-key state and revalidates the complete authority/effect binding before returning. The restored side independently recomputes the canonical effect digest and atomically applies the authenticated post-R business state, receipt and successor authority.

The in-flight substitution negative is empirical: a test-only hold wrapper keeps the fetch locks live while separate owner writes try to mutate grant, effect and boundary claim. Each mutation must block until `lock_timeout` rather than replacing the state being materialized.

### 4. Effective hardened positive replay — class #46

Class #45 originally installed the active-authority definitions only after the base vector's successful recovery. Exact #180 closes that gap by retaining surviving authority/effect/boundary state, resetting the legitimate winning restore to exact R and replaying the positive path through the effective hardened functions:

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

This proves the hardened positive `claim → fetch → apply` path itself, not only verification and invalid-grant rejection.

### 5. Bounded recovery and post-enrollment clone transport — classes #44/#47

Base physical-recovery claim, verify and material-fetch use local asynchronous send/poll with a caller-local deadline. Timeout/uncertainty returns fail-closed without synchronous remote cleanup; the one-shot SQL backend/session is retired. A real established TCP response blackhole is exercised.

The separate post-enrollment clone path now has the same property. Exact #180 proves:

```text
physical_pitr_post_enrollment_helpers_use_bounded_transport=PASS
physical_pitr_post_enrollment_deadline_path_has_no_synchronous_cleanup=PASS
physical_pitr_post_enrollment_stalled_peer_fails_closed=PASS
physical_pitr_post_enrollment_local_deadline=PASS elapsed_ms=564
physical_pitr_post_enrollment_real_blackhole_fails_closed=PASS
physical_pitr_post_enrollment_real_blackhole_local_deadline=PASS elapsed_ms=518
physical_pitr_post_enrollment_timeout_backend_retirement=PASS one_shot_sql_session=true
```

The same bounded path then successfully executes the clone positive-control claim/verify and the primary-grant clone claim/verify negatives. Therefore a fail-closed negative is not accepted merely because the RPC path is broken or unbounded.

### 6. Restored-instance / post-enrollment clone authority

The baseline physical restore vector uses distinct post-R instance capabilities and deliberately demonstrates that reusable authentication credentials do not define unique restore identity.

The post-enrollment clone vector covers the stronger copy case: PGDATA is physically copied after database identity enrollment. The effective C2 proof remains outside PGDATA, so the copy retains database-visible identity but cannot duplicate authority.

These file/mount and LOGIN mechanisms are C2 evidence machinery only. Production must preserve the semantic property with separately reviewed non-shareable workload/TPM/TEE/KMS-backed or equivalent authority.

## Timescale mediated profile

Direct pooled `RLS + columnstore` and `RLS + continuous aggregate` remain ineligible on the evaluated profile. The surviving candidate uses fixed-search-path mediation, no direct tenant privilege on shared raw/CAGG/internal materialization, NOLOGIN mediation owner and a separately isolated LOGIN automation owner classified as cross-tenant privileged infrastructure.

Fresh-cluster restore reconstructs database-global roles before data restore, validates object/job ownership and reruns tenant isolation/escalation attacks after restore and background jobs.

## Canonical representation and relocation

Canonical field framing is self-delimiting. Relocation `timestamptz` covers finite UTC+microseconds+explicit AD/BC and exact `±infinity`; unconstrained `numeric` covers normalized finite values plus exact `NaN` and `±Infinity`.

Relocation locks source placement before `F`, requires exact canonical source↔target completeness, seals target state under target-owned authority, keeps target signing/mint capability out of Tier 1, atomically commits Tier 1 placement + activation grant and keeps the target sealed until it independently verifies that exact grant.

### Effective verifier timeout cleanup — class #48

The final ordered relocation hardening layer replaces the effective Tier1/Tier2 verifier transport before subsequent authority operations. Successful calls may disconnect normally; timeout/send-error/uncertainty returns fail-closed without synchronous `dblink_cancel_query` or `dblink_disconnect`, and the one-shot SQL backend is retired.

Exact #180 proves both directions under a real established response blackhole:

```text
relocation_response_deadline_has_no_synchronous_timeout_cleanup=PASS
relocation_effective_verifier_transport_uses_session_retirement=PASS
relocation_target_verifier_real_blackhole_fails_closed=PASS value=false
relocation_target_verifier_real_blackhole_local_deadline=PASS elapsed_ms=506
relocation_tier1_verifier_real_blackhole_fails_closed=PASS value=false
relocation_tier1_verifier_real_blackhole_local_deadline=PASS elapsed_ms=520
relocation_timeout_backend_retirement=PASS one_shot_sql_session=true
```

All downstream checkpoint, seal, canonical completeness, atomic placement+grant rollback/commit, activation and post-cutover vectors remain PASS after the final transport replacement.

## Exact empirical anchor before governance documentation

```text
HEAD
f2a7f0c4cc1dedf02c64ed1129117f327d11931a

JLMIRROR Deterministic Assurance #2225
run id 33279609441
SUCCESS

JLMIRROR OPEN-REL-030 Conformance #180
run id 33279609464
SUCCESS
```

The anchor includes all prior history, recovery #38–#45, clone positive-control, Timescale, canonicalization and relocation vectors plus classes #46–#48. It becomes provenance after the governance mutation; the exact final documentation HEAD must rerun both workflows.

## Governance state

Material finding classes closed by the evidence program: **48**.

Latest recovery/transport classes:

- **#40:** one winner per canonical recovery boundary across multiple equivalent grant IDs;
- **#41:** authenticated surviving `(R,F]` effect evidence and local reconciliation derived from its verified application;
- **#42:** caller-local bounded established-response semantics for physical-recovery claim/verify/material-fetch;
- **#43:** consistent locked recovery-material fetch with complete authority→claim→grant→effect revalidation against in-flight substitution;
- **#44:** real established TCP-blackhole proof plus timeout-path session retirement without synchronous remote cleanup;
- **#45:** locked active surviving-authority binding before winner-key derivation; validly signed epoch/placement drift cannot create or verify a second authority;
- **#46:** successful reset-to-R `claim → verify → fetch/apply → verify` replay after #45 hardening is installed;
- **#47:** bounded async post-enrollment clone claim/verify with real-blackhole falsification and one-shot session retirement before positive-control/negative interpretation;
- **#48:** effective relocation verifier timeout path has no synchronous remote cleanup and real blackholes fail closed in both cross-authority directions before downstream activation operations.

Evidence completion does not accept `OPEN-REL-030`, authorize Wave 4, select production deployment/authentication/identity/RPC topology, select production capacity numerics, or authorize merge. Exact-final-HEAD CI, fresh adversarial Codex review, exact-head Native Assurance and explicit Track B acceptance remain separate gates.
