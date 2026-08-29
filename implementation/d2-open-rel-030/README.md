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
- **One recovery event has one winner even when multiple valid grant IDs represent it.** Winner scope is the canonical governed recovery boundary, not `grant_id`.
- **Recovery admission must authenticate what survived `(R,F]`, not merely who may recover.** Every grant is bound to an authenticated surviving effect digest, and local reconciliation is derived from applying verified recovery material.
- Claim alone cannot mark reconciliation complete and a locally recreated continuity receipt cannot admit recovery.
- Independent restores and post-enrollment PGDATA copies must not duplicate the effective restored-instance authority.
- A fail-closed clone negative is accepted as evidence only after the same clone proves its capability/helper/credential/transport path operational through a positive-control grant.
- Recovery claim, verify and material-fetch calls require caller-local established-response deadlines; `connect_timeout` only bounds connection setup.
- Target signing material originates/remains in target authority; verification does not imply mint capability.
- Cross-authority activation requires explicit durable authority from both sides and target cannot self-promote.
- A single cross-tenant leak rejects the candidate profile.
- `OPEN-REL-020` retains production telemetry capacity/numeric ownership.
- Evidence database versions, HMAC/SHA, `dblink`, LOGIN roles, capability mounts/stores and deadlines are reproducibility dependencies, not production selections.
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

After `F`, the separate surviving control authority records a canonical `recovery_effect` derived from the **actual source state**:

- recovery domain;
- `R` and `F` boundary identities;
- post-R business state;
- source poll generation;
- required continuity receipt.

It hashes the canonical effect and authenticates it with the surviving-authority key. Recovery grants include the exact effect digest and cannot validate against absent/tampered/mismatched effect evidence.

### 2. One winner per governed recovery boundary

`grant_id` is transport/evidence identity, not recovery-event authority. A canonical `boundary_fingerprint` is derived from:

```text
(domain, R, F, successor_epoch, placement_version, required_receipt)
```

`recovery_boundary_claim.boundary_fingerprint` is the single-winner key. The first valid authenticated principal + restored-instance capability wins that recovery event. Multiple valid grants for the same boundary converge to that same row.

The harness proves both sequential and concurrent cross-grant behavior:

```text
physical_pitr_duplicate_grants_same_boundary=PASS
physical_pitr_recovery_cross_grant_boundary_single_winner_race=PASS
physical_pitr_recovery_boundary_claim_rows_after_cross_grant_race=PASS value=1
physical_pitr_recovery_duplicate_grant_same_winner_retry=PASS value=true
physical_pitr_recovery_duplicate_grant_clone_rejected=PASS value=false
physical_pitr_recovery_main_boundary_single_claim=PASS value=1
physical_pitr_recovery_single_winner_per_boundary_across_grant_ids=PASS
```

### 3. Effect-bound local reconciliation

A successful boundary claim does not mutate local business truth. Exact evidence first proves:

```text
physical_pitr_claim_without_effect_application_stays_at_R=PASS value=state_at_R|false|0
```

Only after the surviving authority verifies the boundary winner may `fetch_claimed_recovery_material(...)` return recovery material. The restored side independently recomputes the canonical effect digest and then atomically applies the authenticated post-R business state, receipt and successor authority.

```text
physical_pitr_surviving_effect_source_state=PASS
physical_pitr_surviving_effect_evidence_published=PASS
physical_pitr_recovery_effect_digest_binding=PASS
physical_pitr_authenticated_effect_application=PASS value=true
physical_pitr_reconciled_from_authenticated_surviving_effect=PASS
physical_pitr_local_reconciled_state=PASS value=true
```

### 4. Bounded recovery verifier transport

Claim, verify and material-fetch all use the same local bounded asynchronous transport. `dblink_send_query` starts the established-session query; caller-side `dblink_is_busy` polling enforces a local deadline; expiry cancels/disconnects and returns uncertainty as fail-closed.

An authenticated five-second remote delay is terminated locally around 578 ms in the anchor run:

```text
physical_pitr_recovery_helpers_use_bounded_transport=PASS
physical_pitr_recovery_stalled_peer_fails_closed=PASS
physical_pitr_recovery_local_deadline=PASS elapsed_ms=578
```

### 5. Restored-instance / post-enrollment clone authority

The baseline physical restore vector uses distinct post-R instance capabilities and deliberately demonstrates that reusable authentication credentials do not define unique restore identity.

The post-enrollment clone vector covers the stronger copy case: PGDATA is physically copied after database identity enrollment. The effective C2 proof remains outside PGDATA, so the copy retains database-visible identity but cannot duplicate authority.

Because fail-closed helpers can otherwise create false-negative evidence, the same clone must first successfully claim+verify a separate probe grant through the exact path used by the negative, and the surviving-authority fingerprint must equal the clone-local capability fingerprint. Only then is its rejection on the primary-winning grant accepted as a meaningful capability-binding negative.

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
6f46c6700855207ad85fc206e258da00ce896c8b

JLMIRROR Deterministic Assurance #2207
run id 33274303103
SUCCESS

JLMIRROR OPEN-REL-030 Conformance #171
run id 33274303155
SUCCESS
```

The anchor includes all prior history, clone positive-control, Timescale, canonicalization and relocation vectors plus recovery classes #40–#42. It becomes provenance after the governance mutation; the exact final documentation HEAD must rerun both workflows.

## Governance state

Material finding classes closed by the evidence program: **42**.

Latest recovery classes:

- **#40:** one winner per canonical recovery boundary across multiple grant IDs;
- **#41:** authenticated surviving `(R,F]` effect evidence and local reconciliation derived from its verified application;
- **#42:** caller-local bounded response semantics for physical-recovery claim/verify/material-fetch.

Evidence completion does not accept `OPEN-REL-030`, authorize Wave 4, select production deployment/authentication/identity/RPC topology, select production capacity numerics, or authorize merge. Exact-final-HEAD CI, fresh adversarial Codex review, exact-head Native Assurance and explicit Track B acceptance remain separate gates.
