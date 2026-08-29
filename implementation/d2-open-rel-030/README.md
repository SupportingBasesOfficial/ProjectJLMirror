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
- Independent restores from R must not converge on one recovery authority merely because they reuse credentials.
- A physical copy of PostgreSQL `PGDATA` taken after restored-instance enrollment must not copy the effective restored-instance authority.
- Recovery principals have no direct grant-table read privilege and cannot submit principal/target identity or signed grant facts as authority.
- Cross-authority verifier credentials stay out of function source and inside restricted authority-owned capability state.
- Cross-authority calls require a caller-local post-connect deadline; a connected but stalled peer must fail closed.
- Cross-authority activation requires explicit durable authority from both sides; target cannot self-promote.
- A single cross-tenant leak rejects the candidate profile.
- `OPEN-REL-020` retains production telemetry capacity/numeric ownership.
- PostgreSQL/Timescale versions and image digests are evidence dependencies, not immutable production selections.
- Evidence HMAC/SHA, canonical encoding, `dblink`, recovery/verifier LOGIN roles, external-to-PGDATA capability mount and capability-store layout do not select production KMS/HSM, workload identity, TPM/TEE, authentication, network or RPC topology.
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

The workflow independently enumerates existing `00[4-9]_history_*.sql` files and fails if any is absent from the runner. Pre-documentation exact #158 reports `history_modules=5` and preserves all prior owner-current history vectors.

### Physical PITR single-winner restored-instance authority

A surviving external control PostgreSQL is excluded from source backup/restore and owns the recovery signing key. It issues a structured authenticated grant only after `F`; a local recreated receipt remains insufficient.

The baseline PITR vector proves that authentication principal alone is insufficient: two independent physical restores from the same committed R backup intentionally reuse one external role/password but generate distinct post-R capabilities. The surviving grant binds the winner to authenticated session principal plus instance identity/fingerprint, same-instance retry succeeds, and the independently restored rival is rejected.

#### Post-enrollment clone hardening

Native Assurance then found material class #38: if the effective secret lives inside PostgreSQL, a physical snapshot made **after** capability creation inherits `instance_id + instance_secret` and can look exactly like the winning retry.

The final C2 package therefore wires `physical_pitr_post_enrollment_clone.sh` into the extended runner and guards that wiring in CI. The vector:

1. enrolls the restored database identity;
2. keeps the effective instance proof outside `PGDATA` in an evidence-only per-instance mount;
3. stops PostgreSQL and physically copies PGDATA after enrollment;
4. proves primary and clone expose the exact same copied database `instance_id`;
5. gives both copies the exact same surviving-authority external role/password;
6. gives the clone a distinct external-to-PGDATA proof;
7. proves primary claim/retry/verify succeeds while clone claim/verify fails.

Pre-documentation exact #158 passed:

```text
physical_pitr_post_enrollment_capability_outside_pgdata=PASS
physical_pitr_post_enrollment_pgdata_identity_copied=PASS
physical_pitr_post_enrollment_external_capability_distinct=PASS
physical_pitr_post_enrollment_primary_claimed=PASS
physical_pitr_post_enrollment_same_instance_retry=PASS
physical_pitr_post_enrollment_pgdata_clone_claim_rejected=PASS
physical_pitr_post_enrollment_primary_verify=PASS
physical_pitr_post_enrollment_pgdata_clone_verify_rejected=PASS
physical_pitr_post_enrollment_authenticated_principal_binding=PASS
physical_pitr_post_enrollment_copied_database_id_binding=PASS
physical_pitr_post_enrollment_pgdata_clone_cannot_duplicate_authority=PASS
physical_pitr_post_enrollment_single_winner_external_capability=PASS
```

The file/mount mechanism is C2 evidence machinery only. It proves the precise clone-domain property: **copying PostgreSQL data state alone does not duplicate recovery authority**. Production must strengthen this into genuinely non-shareable per-instance authority using an appropriate workload identity, TPM/TEE/KMS-backed non-exportable capability or another separately reviewed mechanism.

## Timescale mediated profile

Direct pooled `RLS + columnstore` and `RLS + continuous aggregate` are ineligible on the evaluated TimescaleDB 2.29.2 / PostgreSQL 17.11 profile (`0A000`). The surviving candidate uses no direct tenant-facing privilege on shared raw history/CAGG/internal materialization, fixed-search-path `SECURITY DEFINER` mediation, NOLOGIN `ts_owner`, and LOGIN `ts_automation_owner` only as cross-tenant privileged infrastructure. `PASSWORD NULL` is not production admission proof.

Fresh-cluster restore reconstructs minimum role topology, restores historical projection and background jobs, validates ownership and re-runs isolation/escalation attacks.

## Canonical representation before cryptography

The bounded field representation is:

```text
<UTF-8 byte length in decimal>:<lowercase UTF-8 hex>
```

Field framing is applied only after each typed value has a total/injective canonical text form. Finite `timestamptz` values serialize as UTC + microseconds + explicit AD/BC; non-finite values use exact sentinels. Unconstrained `numeric` uses normalized finite values plus exact `NaN`, `Infinity` and `-Infinity` sentinels. Pre-documentation #158 preserves all canonicalization vectors.

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

## Exact empirical anchor before reviewer documentation

```text
HEAD
c9207f8bbd3c42ec0428987a2580b7f1bfb7e06d

JLMIRROR Deterministic Assurance #2181
run id 33272308047
SUCCESS

JLMIRROR OPEN-REL-030 Conformance #158
run id 33272308006
SUCCESS
```

This anchor includes the post-enrollment physical-clone hardening and all prior Tier1/Timescale/relocation/canonicalization vectors. It becomes provenance after reviewer-document mutation; exact final documentation HEAD must rerun both workflows.

## Governance state

Material finding classes closed by the evidence program: **38**.

Evidence completion does not accept `OPEN-REL-030`, authorize Wave 4, select production deployment/authentication/instance-identity topology or authorize merge. Exact-final-HEAD CI, fresh Codex review, Native Assurance and explicit Track B acceptance remain separate gates.
