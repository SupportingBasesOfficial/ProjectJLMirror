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

1. **Tier 1 PostgreSQL:** transactional acceptance/idempotency, source/poll authority, current-state CAS, ambiguity, owner-current late-history reconciliation, PITR and relocation activation authority.
2. **Tier 2 TimescaleDB:** tenant isolation, feature compatibility, privileged background jobs, fresh-cluster restore, target-owned checkpoint/freeze authority and bounded mechanism capacity.

## Non-negotiable boundaries

- Provider event time is metadata, never current-state authority.
- Worker/caller assertions never substitute for source, poll, provider-finality, recovery or target-checkpoint authority.
- Reconciliation completeness is bound to exact owner `authority_generation`, exact current `provider_dataset_revision` and owner-required snapshot currentness; timestamp equality alone never carries coverage across an authority or dataset revision.
- Owner-visible provider INSERT/UPDATE atomically increments dataset revision and invalidates prior coverage; stable identity rewrite is rejected and destructive DELETE/TRUNCATE fail closed instead of silently changing the reconciled universe.
- The reconciliation worker has no direct provider-history INSERT/UPDATE/DELETE/TRUNCATE privilege, no provider-owner membership and no trigger-administration path.
- Existing reconciled observation identity implies immutable canonical accepted content; owner-visible conflicting content rejects/quarantines rather than becoming a duplicate.
- Stable-identity conflict validation precedes provider-time windowing whenever either accepted or owner-current timestamp intersects the sweep window; a correction cannot evade validation by moving across a window boundary.
- Every existing ordered history hardening module matching `00[4-9]_history_*.sql` must be referenced by the extended runner; structural CI fails if a reviewer-critical history module exists but is not executed.
- Structured crypto messages require deterministic versioned unambiguous/self-delimiting representation before cryptography.
- Typed canonical values must be injective across their full supported domain; finite relocation timestamps use UTC + microseconds + explicit AD/BC era, while PostgreSQL non-finite sentinels use exact reserved `infinity` / `-infinity` literals before hashing.
- A verifier must not inherit issuer/mint capability merely because it can validate an attestation.
- Target signing material must originate and remain inside target authority; the test controller must not provision or retain it.
- Recovery grants are not reusable bearer authorization: surviving authority atomically binds each grant to one **authenticated recovery principal** derived from session authority, not caller-supplied target/principal data.
- Recovery claim/verification APIs are ID-only; restore principals have no direct grant-table read privilege.
- Cross-authority verifier credentials must not be embedded in function source and must be held in restricted authority-owned capability state.
- Cross-authority calls require a caller-local post-connect deadline; a connected but stalled peer must fail closed.
- Cross-authority activation requires explicit durable authority from both sides; target cannot self-promote.
- A single cross-tenant leak rejects the candidate profile.
- `OPEN-REL-020` retains production telemetry capacity/numeric ownership.
- PostgreSQL/Timescale versions and image digests are evidence dependencies, not immutable production selections.
- Evidence HMAC/SHA, canonical encoding, `dblink`, recovery/verifier LOGIN roles and capability-store layout do not select production KMS/HSM, authentication, network or RPC topology.
- `READY_FOR_MERGE != AUTHORIZED_TO_MERGE`.

## Tier 1 authority coverage

The executable package proves atomic create-or-observe across independent connections; immutable canonical observation content; owner-controlled source/poll authority; exact durable `live` poll claims; current-state CAS by platform authority; stale/predecessor rejection; crash rollback; post-COMMIT ambiguity convergence; durable Tier2-down backlog responsibility; generation/revision-bound owner-current late-history finality/currentness; conflicting reconciled-content rejection including corrections crossing requested window boundaries; provider dataset mutation invalidation; destructive mutation fail-closed behavior; worker privilege separation; and PITR recovery admission only from surviving authenticated `(R,F]` authority with single-winner authenticated-principal binding.

### Owner-current late-history reconciliation

`provider_authority` durably owns `authority_generation`, `provider_dataset_revision`, `current_snapshot_at`, `finality_floor` and `required_reconciliation_snapshot_at`. Workers supply only a window and expected owner authority.

A reconciliation run contributes to contiguous coverage only when all are true:

1. its `authority_generation` equals the currently locked owner generation;
2. its `provider_dataset_revision` equals the currently locked owner dataset revision;
3. its provider snapshot satisfies the owner-required snapshot floor.

Every `advance_provider_authority(...)` invalidates the stream's materialized reconciliation coverage and moves a non-gap stream to `reconciliation_required`, even if the new generation uses exactly the same timestamps. Owner-visible INSERT/UPDATE also increments `provider_dataset_revision` and invalidates materialized coverage in the same transaction. The provider mutation path and `sweep(...)` serialize on the same owner authority row, preventing a same-generation correction from hiding behind stale completed coverage.

Stable identity validation happens before provider-time window selection. If either the accepted timestamp or the owner-current provider timestamp intersects the requested window, an existing `(stream_id, observation_id)` is compared against owner-current content. A correction from an accepted row inside the window to a provider timestamp outside the window therefore cannot be omitted and followed by a false coverage run. Any immutable `observed_at` or `numeric_value` mismatch raises `reconciled observation identity content mismatch`; the failed transaction cannot alter accepted canonical history or mint a coverage run.

Stable provider identity rewrites are rejected. DELETE and statement-level TRUNCATE of owner-visible provider history fail closed; the evidence does not infer absence from destructive mutation. The reconciliation worker has no direct provider DML/TRUNCATE privilege and cannot administer the protecting triggers.

The extended runner explicitly executes:

```text
004_history_reconciliation.sql
005_history_identity_window_hardening.sql
006_history_dataset_revision_hardening.sql
007_history_dataset_revision_edge_hardening.sql
```

The workflow independently enumerates existing `00[4-9]_history_*.sql` files and fails if any one is absent from the runner. Exact #133 reports `history_modules=4`.

Exact empirical evidence includes:

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

### Physical PITR single-winner authenticated recovery authority

A surviving external control PostgreSQL is excluded from the source backup/restore and owns the recovery signing key. It issues a structured authenticated grant only after `F`.

Verification does not itself authorize every restore. The bounded claim surface is deliberately reduced to `claim_grant(grant_id)` and `verify_claimed_grant(grant_id)`. Restore principals cannot directly read `recovery_grant` and cannot supply a target ID, principal identity or signed grant facts to the claim function. The surviving authority loads and verifies the grant internally, derives the claimant from `session_user`, and atomically binds the grant to the first authenticated principal. Retry by that same principal converges; a different authenticated principal loses. A dedicated race between two independently authenticated principals requires exactly one winner. A rival credential presented under the winner role name must fail authentication.

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

The PostgreSQL LOGIN/password mechanism is evidence-only. The accepted invariant is binding to the same authenticated recovery authority rather than to a caller-copyable identifier.

## Timescale mediated profile

Direct pooled `RLS + columnstore` and direct pooled `RLS + continuous aggregate` are ineligible on the evaluated TimescaleDB 2.29.2 / PostgreSQL 17.11 profile (`0A000`). The surviving candidate uses no direct tenant-facing privilege on shared raw history/CAGG/internal materialization, fixed-search-path `SECURITY DEFINER` mediation, NOLOGIN `ts_owner`, and LOGIN `ts_automation_owner` only as cross-tenant privileged infrastructure. `PASSWORD NULL` is not production admission proof.

Fresh-cluster restore reconstructs the minimum role topology, restores the historical projection and background jobs, validates ownership and re-runs isolation/escalation attacks.

## Canonical representation before cryptography

The bounded field representation is:

```text
<UTF-8 byte length in decimal>:<lowercase UTF-8 hex>
```

It is applied to immutable observation fields, target-checkpoint facts and PITR recovery-grant facts. The evidence explicitly falsifies delimiter-based framing and proves cross-store equality of the canonical checkpoint payload.

Field framing alone is not enough if the typed value is already ambiguous. Both Tier 1 and Tier 2 use a total relocation timestamp canonicalizer. Finite PostgreSQL `timestamptz` values are serialized as UTC + microseconds + explicit `AD`/`BC`; non-finite `-infinity` and `infinity` are mapped to those exact reserved literals. The two sentinels must be nonempty, distinct, cross-store equal and generate distinct self-delimiting SHA-256 inputs/digests rather than disappearing as NULL inside `string_agg`.

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

## Relocation authority model

Tier 1 locks source placement before deriving `F`. `max(target)=F` is not completeness. The target measures and seals its own canonical state.

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

### Target signing-key provenance

The effective target checkpoint key is generated **inside Tier 2** using target-side randomness. The disposable-lab controller may administer both databases for setup/fault injection, but it does not provision or retain the protocol signing key. Tier 1 contains no target signing-key relation. Projection writer and verifier principals cannot read the key.

Exact executable evidence proves:

```text
relocation_tier1_has_no_target_signing_key=PASS
relocation_controller_does_not_retain_target_signing_key=PASS
relocation_target_authority_generated_signing_key=PASS
relocation_projection_writer_still_cannot_read_generated_signing_key=PASS
relocation_target_verifier_still_cannot_read_generated_signing_key=PASS
relocation_tier1_cannot_mint_target_attestation=PASS
relocation_fabricated_target_attestation_rejected=PASS
```

### Verifier capability-secret isolation and local deadline

The C2 harness uses random LOGIN credentials plus PostgreSQL `dblink` only to exercise separate authorities. Credentials are stored in restricted authority-owned capability tables and read only through owner `SECURITY DEFINER` helpers with fixed search paths. They are not interpolated into function definitions.

The raw asynchronous transport helper is owner-only. Verifier/projection principals cannot call it directly. Connection setup is bounded with `connect_timeout=1`; established queries use `dblink_send_query` + `dblink_is_busy` polling with a caller-local deadline. A remote five-second delay probe is required to fail closed near the 500 ms probe deadline and well below 1.8 seconds.

The matrix proves:

```text
relocation_tier1_verifier_cannot_read_target_connection_capability=PASS
relocation_projection_writer_cannot_read_tier1_connection_capability=PASS
relocation_target_verifier_cannot_read_tier1_connection_capability=PASS
relocation_target_verifier_secret_not_in_function_source=PASS
relocation_tier1_verifier_secret_not_in_function_source=PASS
relocation_tier1_verifier_cannot_call_raw_bounded_transport=PASS
relocation_target_principals_cannot_call_raw_bounded_transport=PASS
relocation_target_verifier_stalled_peer_fails_closed=PASS
relocation_target_verifier_local_deadline=PASS
relocation_tier1_verifier_stalled_peer_fails_closed=PASS
relocation_tier1_verifier_local_deadline=PASS
```

This is evidence machinery, not a production RPC/timeout selection.

### Activation atomicity

Tier 1 grant is bound to tenant, `F`, checkpoint id/generation, target attestation, successor placement version and committed state. A fault injection preoccupies the grant identity after the placement-UPDATE path begins; PostgreSQL must roll back the full transaction.

```text
relocation_target_cannot_self_activate_before_tier1_grant=PASS
relocation_premature_mark_keeps_future_insert_blocked=PASS
relocation_activation_commit_conflict_rolls_back=PASS
relocation_activation_conflict_preserves_fenced_placement=PASS
relocation_conflicting_grant_cannot_activate_target=PASS
relocation_activation_conflict_keeps_target_sealed=PASS
relocation_activation_grant_placement_atomicity=PASS
relocation_tier1_activation_grant_committed=PASS
```

## Exact empirical anchor before reviewer documentation

```text
HEAD
723022253af332b0fa08ff7be3fbcad326dd8712

JLMIRROR Deterministic Assurance #2131
run id 33233145281
SUCCESS

JLMIRROR OPEN-REL-030 Conformance #133
run id 33233145277
SUCCESS
```

The #133 extended run executes all four current history-hardening modules (`004–007`), proves generation + dataset-revision + snapshot-bound history coverage, same-generation mutation fencing, destructive DELETE/TRUNCATE fail-closed behavior, worker privilege separation, authenticated-principal single-winner physical recovery with ID-only authority API, total era/non-finite timestamp canonicalization, target key provenance, capability-secret isolation, bounded stalled-peer verification, verifier/mint separation, durable activation grant, premature-activation negatives, grant/placement rollback injection, structured serialization and all prior authority/isolation/recovery/relocation vectors. This anchor becomes provenance after documentation mutation and the final documentation HEAD must rerun both workflows.

## Governance state

Evidence completion does not accept `OPEN-REL-030`, authorize Wave 4, select production deployment/authentication topology or authorize merge. Exact-final-HEAD CI, fresh Codex review, Native Assurance and explicit Track B acceptance remain separate gates.
