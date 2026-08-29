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
- Independent restores and post-enrollment PGDATA copies must not duplicate the effective restored-instance authority.
- A fail-closed clone negative is accepted as evidence only after the same clone proves its capability/helper/credential/transport path operational through a positive-control grant.
- Recovery claim, verify and material-fetch calls require caller-local established-response deadlines; `connect_timeout` only bounds connection setup.
- A cooperative server delay is insufficient deadline evidence by itself: an established authenticated TCP blackhole must also fail closed locally without synchronous remote cancel/cleanup extending the deadline path.
- Target signing material originates/remains in target authority; verification does not imply mint capability.
- Cross-authority activation requires explicit durable authority from both sides and target cannot self-promote.
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

After `F`, the separate surviving control authority records a canonical `recovery_effect` derived from the **actual source state** and authenticates it. Recovery grants include the exact effect digest and cannot validate against absent/tampered/mismatched effect evidence.

### 2. Active authority and one winner per recovery event

The surviving singleton is the authority for the currently recoverable event:

```text
(expected_domain, R, F, expected_successor_epoch, expected_placement_version, required_receipt)
```

`claim_grant(...)` locks this row before deriving the winner key. The boundary fingerprint is derived from this locked tuple. An otherwise-valid grant must match it exactly before it can participate in the single-winner CAS. `verify_claimed_grant(...)` and `fetch_claimed_recovery_material(...)` revalidate the same authority.

The class #45 vector creates two **validly signed** grants reusing the real main R/F/effect but drifting one dimension each:

```text
grant-F-alt-epoch      successor_epoch 6 -> 7
grant-F-alt-placement  placement_version 8 -> 9
```

Exact #178 proves:

```text
physical_pitr_alt_epoch_grant_signature_valid=PASS value=true
physical_pitr_alt_placement_grant_signature_valid=PASS value=true
physical_pitr_active_authority_singleton=PASS value=open-rel-030-recovery-v1|R|F|6|8|effect|after-r
physical_pitr_alt_epoch_grant_rejected_by_active_authority=PASS value=false
physical_pitr_alt_placement_grant_rejected_by_active_authority=PASS value=false
physical_pitr_alt_epoch_verify_rejected=PASS value=false
physical_pitr_alt_placement_apply_rejected=PASS value=false
physical_pitr_alt_grants_leave_claim_count_unchanged=PASS value=1
physical_pitr_alt_grants_remain_unclaimed=PASS value=2
physical_pitr_local_successor_authority_fence=PASS
physical_pitr_main_grant_still_verifies_after_authority_hardening=PASS value=true
physical_pitr_duplicate_grant_same_winner_retry_after_authority_hardening=PASS value=true
physical_pitr_clone_still_rejected_after_authority_hardening=PASS value=false
physical_pitr_claim_locks_active_authority_before_winner_key=PASS
physical_pitr_verify_fetch_revalidate_active_authority=PASS
physical_pitr_active_authority_binding=PASS
```

For equivalent grants that match the active tuple, `recovery_boundary_claim.boundary_fingerprint` remains the single-winner key. Sequential and concurrent cross-grant tests prove one claim row and same-winner convergence.

### 3. Effect-bound, consistent local reconciliation

A successful boundary claim does not mutate local business truth. Only after the surviving authority verifies the winner may `fetch_claimed_recovery_material(...)` return recovery material. That fetch revalidates the active authority, locks the exact grant, canonical boundary claim and referenced effect, holds signing-key state and revalidates the complete authority/effect binding before returning. The restored side independently recomputes the canonical effect digest and atomically applies the authenticated post-R business state, receipt and successor authority.

The in-flight substitution negative is empirical: a test-only hold wrapper keeps the fetch locks live while separate owner writes try to mutate the grant, effect and boundary claim. Each mutation must block until `lock_timeout` rather than replacing the state being materialized.

### 4. Bounded recovery verifier transport and real blackhole

Claim, verify and material-fetch all use the same local bounded asynchronous transport. `dblink_send_query` starts the established-session query; caller-side `dblink_is_busy` polling enforces a local deadline.

On timeout/uncertainty the C2 helper returns fail-closed without synchronous `dblink_cancel_query` or synchronous remote disconnect on that deadline path. The evidence call is executed from a one-shot SQL backend/session, so that local session is retired and closes its abandoned connection. This mechanism is deliberately evidence-only; production transport must provide independently bounded cancellation/cleanup or equivalent session retirement.

Exact #178 preserved the cooperative five-second delay negative at ~562 ms and the real established-session TCP response blackhole at ~514 ms.

### 5. Restored-instance / post-enrollment clone authority

The baseline physical restore vector uses distinct post-R instance capabilities and deliberately demonstrates that reusable authentication credentials do not define unique restore identity.

The post-enrollment clone vector covers the stronger copy case: PGDATA is physically copied after database identity enrollment. The effective C2 proof remains outside PGDATA, so the copy retains database-visible identity but cannot duplicate authority.

Because fail-closed helpers can otherwise create false-negative evidence, the same clone must first successfully claim+verify a separate probe grant through the exact path used by the negative, and the surviving-authority fingerprint must equal the clone-local capability fingerprint. Only then is its rejection on the primary-winning grant accepted as meaningful capability-binding evidence.

These file/mount and LOGIN mechanisms are C2 evidence machinery only. Production must preserve the semantic property with separately reviewed non-shareable workload/TPM/TEE/KMS-backed or equivalent authority.

## Timescale mediated profile

Direct pooled `RLS + columnstore` and `RLS + continuous aggregate` remain ineligible on the evaluated profile. The surviving candidate uses fixed-search-path mediation, no direct tenant privilege on shared raw/CAGG/internal materialization, NOLOGIN mediation owner and a separately isolated LOGIN automation owner classified as cross-tenant privileged infrastructure.

Fresh-cluster restore reconstructs database-global roles before data restore, validates object/job ownership and reruns tenant isolation/escalation attacks after restore and background jobs.

## Canonical representation and relocation

Canonical field framing is self-delimiting. Relocation `timestamptz` covers finite UTC+microseconds+explicit AD/BC and exact `±infinity`; unconstrained `numeric` covers normalized finite values plus exact `NaN` and `±Infinity`.

Relocation locks source placement before `F`, requires exact canonical source↔target completeness, seals target state under target-owned authority, keeps target signing/mint capability out of Tier 1, bounds verifier response locally, atomically commits Tier 1 placement + activation grant and keeps the target sealed until it independently verifies that exact grant.

## Exact empirical anchor before governance documentation

```text
HEAD
4fae89bc49a0cf589ad6d20f360bf29f2bb4f604

JLMIRROR Deterministic Assurance #2221
run id 33277420151
SUCCESS

JLMIRROR OPEN-REL-030 Conformance #178
run id 33277420178
SUCCESS
```

The anchor includes all prior history, clone positive-control, Timescale, canonicalization and relocation vectors plus recovery classes #40–#45. It becomes provenance after the governance mutation; the exact final documentation HEAD must rerun both workflows.

## Governance state

Material finding classes closed by the evidence program: **45**.

Latest recovery classes:

- **#40:** one winner per canonical recovery boundary across multiple equivalent grant IDs;
- **#41:** authenticated surviving `(R,F]` effect evidence and local reconciliation derived from its verified application;
- **#42:** caller-local bounded established-response semantics for physical-recovery claim/verify/material-fetch;
- **#43:** consistent locked recovery-material fetch with complete claim→grant→effect revalidation against in-flight substitution;
- **#44:** real established TCP-blackhole proof plus timeout-path session retirement without synchronous remote cleanup;
- **#45:** locked active surviving-authority binding before winner-key derivation; validly signed epoch/placement drift cannot create or verify a second authority, and local reconciled state is fenced to the active successor.

Evidence completion does not accept `OPEN-REL-030`, authorize Wave 4, select production deployment/authentication/identity/RPC topology, select production capacity numerics, or authorize merge. Exact-final-HEAD CI, fresh adversarial Codex review, exact-head Native Assurance and explicit Track B acceptance remain separate gates.
