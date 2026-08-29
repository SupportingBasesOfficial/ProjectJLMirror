# D2 — OPEN-REL-030 Monitoring Conformance Evidence

**Status:** evidence complete — ready for exact-HEAD decision review; no production authority  
**Canonical base:** `main@5f031ae4bacc0c441eeee16f9c67d272e39d6b0b`  
**Branch:** `evidence/open-rel-030-monitoring-conformance`  
**Decision under test:** `docs/11-reliability-resilience/OPEN-REL-030-decision-record.md`  
**Track B acceptance:** not granted  
**Wave 4 implementation authorization:** not granted

## Purpose

This package is a bounded, reproducible falsification laboratory for `OPEN-REL-030`. It does not implement the Monitoring product vertical and has no production authority.

It evaluates:

1. **Tier 1 PostgreSQL:** transactional acceptance/idempotency, source/poll authority, current-state CAS, ambiguity, owner-current late-history reconciliation, physical PITR and relocation activation authority.
2. **Tier 2 TimescaleDB:** tenant isolation, feature compatibility, privileged background jobs, fresh-cluster restore, target-owned checkpoint/freeze authority and bounded mechanism capacity.

## Non-negotiable boundaries

- Provider event time is metadata, never current-state authority.
- Worker/caller assertions never substitute for source, poll, provider-finality, recovery or target-checkpoint authority.
- Reconciliation completeness is bound to exact owner `authority_generation`, exact current `provider_dataset_revision` and owner-required snapshot currentness.
- Owner-visible provider INSERT/UPDATE atomically increments dataset revision and invalidates prior coverage; stable identity rewrite is rejected and destructive DELETE/TRUNCATE fail closed.
- Reconciliation worker has no direct provider-history INSERT/UPDATE/DELETE/TRUNCATE privilege, provider-owner membership or trigger-administration path.
- Stable accepted identities are validated against owner-current canonical content independently of current `became_visible_at`; visibility filtering may control admission of new rows but cannot hide a conflict for an already accepted identity.
- Every ordered history hardening module matching `00[4-9]_history_*.sql` must be referenced by the extended runner; structural CI fails if a reviewer-critical module exists but is not executed.
- Structured crypto messages require deterministic, versioned, unambiguous/self-delimiting representation before cryptography.
- Typed canonical values must be total/injective across their full supported domain. Relocation `timestamptz` covers finite UTC+microseconds+AD/BC and exact `infinity`/`-infinity`; relocation `numeric` covers normalized finite values plus exact `NaN`, `Infinity` and `-Infinity`.
- A verifier must not inherit issuer/mint capability merely because it can validate an attestation.
- Target signing material must originate and remain inside target authority; the test controller must not provision or retain it.
- Recovery grants are not reusable bearer authorization and **a reusable external credential is not a restored-instance identity**.
- Surviving recovery authority binds admission to authenticated principal plus a post-R instance capability generated independently by each physical restore.
- Recovery principals have no direct grant-table read privilege and cannot submit principal/target identity or signed grant facts as authority.
- Cross-authority verifier credentials stay out of function source and inside restricted authority-owned capability state.
- Cross-authority calls require a caller-local post-connect deadline; a connected but stalled peer must fail closed.
- Cross-authority activation requires explicit durable authority from both sides; target cannot self-promote.
- A single cross-tenant leak rejects the candidate profile.
- `OPEN-REL-020` retains production telemetry capacity/numeric ownership.
- PostgreSQL/Timescale versions and image digests are evidence dependencies, not immutable production selections.
- Evidence HMAC/SHA, canonical encoding, `dblink`, recovery/verifier LOGIN roles, instance-secret mechanism and capability-store layout do not select production KMS/HSM, workload identity, TPM/TEE, authentication, network or RPC topology.
- `READY_FOR_MERGE != AUTHORIZED_TO_MERGE`.

## Tier 1 authority coverage

The executable package proves atomic create-or-observe across independent connections; immutable canonical observation content; owner-controlled source/poll authority; exact durable `live` poll claims; current-state CAS by platform authority; stale/predecessor rejection; crash rollback; post-COMMIT ambiguity convergence; durable Tier2-down backlog responsibility; generation/revision-bound owner-current late-history finality/currentness; cross-window and visibility-shift conflicting-content rejection; provider dataset mutation invalidation; destructive mutation fail-closed behavior; worker privilege separation; and PITR recovery admission only from surviving authenticated `(R,F]` authority with single-winner restored-instance binding.

### Owner-current late-history reconciliation

`provider_authority` durably owns `authority_generation`, `provider_dataset_revision`, `current_snapshot_at`, `finality_floor` and `required_reconciliation_snapshot_at`. Workers supply only a window and expected owner authority.

A reconciliation run contributes to contiguous coverage only when authority generation, provider dataset revision and provider snapshot currentness still match locked owner authority. Every authority-generation advance invalidates prior materialized coverage. Owner-visible INSERT/UPDATE increments `provider_dataset_revision` and invalidates coverage in the same transaction. Provider mutation and `sweep(...)` serialize on the same owner row.

Stable identity validation precedes coverage publication. An already accepted `(stream_id, observation_id)` is compared with owner-current provider content whenever either accepted or provider `observed_at` intersects the requested window. This comparison deliberately does **not** require `became_visible_at <= current_snapshot_at`; otherwise a correction could move visibility into the future and hide a conflict. Visibility filtering remains on the insertion path for previously unaccepted rows.

Stable provider identity rewrites reject. DELETE and statement-level TRUNCATE fail closed. The reconciliation worker has no direct provider DML/TRUNCATE privilege and cannot administer protecting triggers.

The extended runner executes:

```text
004_history_reconciliation.sql
005_history_identity_window_hardening.sql
006_history_dataset_revision_hardening.sql
007_history_dataset_revision_edge_hardening.sql
008_history_visibility_correction_hardening.sql
```

The workflow independently enumerates existing `00[4-9]_history_*.sql` files and fails if any is absent from the runner. Exact #145 reports `history_modules=5` and proves/preserves:

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
history_visibility_shift_conflict_rejected=PASS
history_visibility_shift_cannot_mint_coverage=PASS
late_history_reconciliation=PASS
```

### Physical PITR single-winner restored-instance authority

A surviving external control PostgreSQL is excluded from source backup/restore and owns the recovery signing key. It issues a structured authenticated grant only after `F`; a local recreated receipt remains insufficient.

Grant integrity is resolved internally by the surviving authority and recovery principals cannot directly read the grant relation. Authentication principal is one authority dimension, but it is not sufficient for idempotent retry because an external role/password can be copied.

The physical vector therefore starts **two PostgreSQL restores from the same committed R backup**. Each independently creates after R:

```text
instance_id     random UUID
instance_secret random 256-bit local secret
```

The normal claim path keeps the secret inside the restored database and uses a local `SECURITY DEFINER` helper to prove possession to the surviving authority. The surviving grant is atomically bound to:

```text
session_user
instance_id
fingerprint(instance_secret)
```

The winning restore and its physical clone intentionally use the **same external recovery role/password**. Same-instance retry succeeds; the clone's different post-R capability is rejected despite identical external credentials. A separate two-principal/two-capability race still requires exactly one winner.

Exact #145 proves:

```text
physical_pitr_recovery_instance_capability_generated_post_R=PASS
physical_pitr_recovery_clone_capability_distinct=PASS
physical_pitr_recovery_claim_api_grant_plus_instance_proof=PASS
physical_pitr_recovery_claim_identity_from_authenticated_session=PASS
physical_pitr_recovery_principal_no_direct_grant_read=PASS
physical_pitr_recovery_principal_spoof_rejected=PASS
physical_pitr_tampered_grant_cannot_claim=PASS
physical_pitr_tamper_leaves_grant_unclaimed=PASS
physical_pitr_recovery_claim_single_winner_race=PASS
physical_pitr_recovery_grant_same_instance_retry=PASS
physical_pitr_recovery_same_principal_clone_rejected=PASS
physical_pitr_recovery_other_principal_rejected=PASS
physical_pitr_recovery_grant_authenticated_principal_binding=PASS
physical_pitr_recovery_grant_instance_id_binding=PASS
physical_pitr_recovery_instance_fingerprint_binding=PASS
physical_pitr_duplicate_restored_authority_not_admitted=PASS
physical_pitr_recovery_single_winner_instance_capability=PASS
physical_pitr_post_reconcile_admission=PASS authority=surviving_external_authenticated_single_winner_instance_capability
```

This PostgreSQL LOGIN + post-R local secret + `dblink` path is evidence-only. Production may use a different non-shareable workload/instance authority such as TPM/TEE/KMS-backed or platform workload identity, but it must preserve the proven property: copied reusable credentials alone cannot impersonate the admitted restored instance.

## Timescale mediated profile

Direct pooled `RLS + columnstore` and `RLS + continuous aggregate` are ineligible on the evaluated TimescaleDB 2.29.2 / PostgreSQL 17.11 profile (`0A000`). The surviving candidate uses no direct tenant-facing privilege on shared raw history/CAGG/internal materialization, fixed-search-path `SECURITY DEFINER` mediation, NOLOGIN `ts_owner`, and LOGIN `ts_automation_owner` only as cross-tenant privileged infrastructure. `PASSWORD NULL` is not production admission proof.

Fresh-cluster restore reconstructs minimum role topology, restores historical projection and background jobs, validates ownership and re-runs isolation/escalation attacks.

## Canonical representation before cryptography

The bounded field representation is:

```text
<UTF-8 byte length in decimal>:<lowercase UTF-8 hex>
```

Field framing is applied only after each typed value has a total/injective canonical text form.

### Timestamp

Finite PostgreSQL `timestamptz` values serialize as UTC + microseconds + explicit `AD`/`BC`. Non-finite `-infinity` and `infinity` use exact reserved literals. Exact #145 preserves era injectivity, cross-store equality, non-finite distinction and mandatory digest use of `canonical_timestamp(...)`.

### Numeric

The accepted relocation value column is unconstrained PostgreSQL `numeric`. Both Tier 1 and Tier 2 use `canonical_numeric(...)`: finite values normalize through `trim_scale`, while `NaN`, `Infinity` and `-Infinity` map to explicit exact literals. Exact #145 preserves special-value cross-store equality/injectivity and mandatory digest use of the numeric canonicalizer.

## Relocation authority model

Tier 1 locks source placement before deriving `F`. `max(target)=F` is not completeness. Target measures and seals its own canonical state.

```text
open
  staging allowed
  seal rejects any row > F

sealed
  all target-history DML rejected
  target cannot self-activate

Tier 1 cutover authority
  verifies exact target checkpoint through target-owned verifier
  remote verification occurs before local authority locks
  commits placement + exact activation_grant atomically

activated
  only after target verifies exact committed Tier 1 grant
  existing history immutable
  INSERT <= F rejected
  new append > F allowed
```

The effective target checkpoint key is generated inside Tier 2. Tier 1 contains no target signing-key relation; the controller does not retain the key; projection writer/verifier cannot read it. Verifier connection credentials are restricted capability state and absent from function source. Raw asynchronous transport is owner-only; `connect_timeout` bounds connection setup and asynchronous polling enforces caller-local established-response deadlines.

Exact #145 preserves target-key provenance, verifier-secret isolation, stalled-peer fail-closed behavior, target seal/DML serialization, forged-attestation rejection, placement+grant rollback injection, target self-activation rejection, exact activation-grant verification and final Tier1↔Tier2 continuity.

## Exact empirical anchor before reviewer documentation

```text
HEAD
ce6f04c1192aae68f305d0b9f5fcaefd4964f8fb

JLMIRROR Deterministic Assurance #2155
run id 33255911094
SUCCESS

JLMIRROR OPEN-REL-030 Conformance #145
run id 33255911080
SUCCESS
```

The #145 extended run executes all five history-hardening modules (`004–008`), closes the visibility-shift conflict class, proves recovery single-winner authority against a second physical restore reusing the exact same external credential, and preserves all prior Tier1/Timescale/relocation/canonicalization vectors. This anchor becomes provenance after reviewer-document mutation; exact final documentation HEAD must rerun both workflows.

## Governance state

Evidence completion does not accept `OPEN-REL-030`, authorize Wave 4, select production deployment/authentication/instance-identity topology or authorize merge. Exact-final-HEAD CI, fresh Codex review, Native Assurance and explicit Track B acceptance remain separate gates.
