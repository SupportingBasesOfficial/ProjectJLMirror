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
- Reconciliation completeness is bound to exact owner `authority_generation` plus owner-required snapshot currentness; timestamp equality alone never carries coverage across generations.
- Existing reconciled observation identity implies immutable canonical accepted content; owner-visible conflicting content rejects/quarantines rather than becoming a duplicate.
- Structured crypto messages require deterministic versioned unambiguous/self-delimiting representation before cryptography.
- A verifier must not inherit issuer/mint capability merely because it can validate an attestation.
- Target signing material must originate and remain inside target authority; the test controller must not provision or retain it.
- Recovery grants are not reusable bearer authorization: surviving authority binds each grant to one restore target with atomic single-winner claim semantics.
- Cross-authority verifier credentials must not be embedded in function source and must be held in restricted authority-owned capability state.
- Cross-authority calls require a caller-local post-connect deadline; a connected but stalled peer must fail closed.
- Cross-authority activation requires explicit durable authority from both sides; target cannot self-promote.
- A single cross-tenant leak rejects the candidate profile.
- `OPEN-REL-020` retains production telemetry capacity/numeric ownership.
- PostgreSQL/Timescale versions and image digests are evidence dependencies, not immutable production selections.
- Evidence HMAC/SHA, canonical encoding, `dblink`, verifier LOGIN roles and capability-store layout do not select production KMS/HSM, authentication, network or RPC topology.
- `READY_FOR_MERGE != AUTHORIZED_TO_MERGE`.

## Tier 1 authority coverage

The executable package proves atomic create-or-observe across independent connections; immutable canonical observation content; owner-controlled source/poll authority; exact durable `live` poll claims; current-state CAS by platform authority; stale/predecessor rejection; crash rollback; post-COMMIT ambiguity convergence; durable Tier2-down backlog responsibility; generation-bound owner-current late-history finality/currentness; conflicting reconciled-content rejection; and PITR recovery admission only from surviving authenticated `(R,F]` authority with single-winner restore-target binding.

### Owner-current late-history reconciliation

`provider_authority` durably owns `authority_generation`, `current_snapshot_at`, `finality_floor` and `required_reconciliation_snapshot_at`. Workers supply only a window and an expected generation.

A reconciliation run contributes to contiguous coverage only when both are true:

1. its `authority_generation` equals the currently locked owner generation;
2. its provider snapshot satisfies the owner-required snapshot floor.

Every `advance_provider_authority(...)` invalidates the stream's materialized reconciliation coverage and moves a non-gap stream to `reconciliation_required`, even if the new generation uses exactly the same timestamps. A fresh sweep under that generation must re-establish coverage.

Before a sweep inserts or records any run, it compares any already-accepted observation identity against the currently visible provider content. A mismatch in immutable `observed_at` or `numeric_value` raises `reconciled observation identity content mismatch`; the failed transaction cannot alter accepted canonical history or mint a coverage run.

Exact empirical evidence includes:

```text
history_conflicting_observation_rejected=PASS
history_generation_bound_coverage=PASS
history_owner_currentness_authority=PASS
late_history_reconciliation=PASS
```

### Physical PITR single-winner recovery authority

A surviving external control PostgreSQL is excluded from the source backup/restore and owns the recovery signing key. It issues a structured authenticated grant only after `F`.

Verification does not itself authorize every restore. The grant must be atomically claimed against a unique restore `target_id`. Same-target retries converge after ambiguity; a different target loses. A dedicated race between two distinct target IDs requires exactly one winner. The restored database then applies successor epoch/placement only after the surviving authority confirms that exact target owns the grant.

Exact #108 proves:

```text
physical_pitr_recovery_claim_winner_retry=PASS
physical_pitr_recovery_claim_loser_rejected=PASS
physical_pitr_recovery_claim_single_winner_race=PASS
physical_pitr_recovery_grant_claimed=PASS
physical_pitr_recovery_grant_same_target_retry=PASS
physical_pitr_recovery_grant_other_target_rejected=PASS
physical_pitr_duplicate_restored_authority_not_admitted=PASS
physical_pitr_recovery_single_winner=PASS
physical_pitr_post_reconcile_admission=PASS authority=surviving_external_authenticated_single_winner_grant
```

## Timescale mediated profile

Direct pooled `RLS + columnstore` and direct pooled `RLS + continuous aggregate` are ineligible on the evaluated TimescaleDB 2.29.2 / PostgreSQL 17.11 profile (`0A000`). The surviving candidate uses no direct tenant-facing privilege on shared raw history/CAGG/internal materialization, fixed-search-path `SECURITY DEFINER` mediation, NOLOGIN `ts_owner`, and LOGIN `ts_automation_owner` only as cross-tenant privileged infrastructure. `PASSWORD NULL` is not production admission proof.

Fresh-cluster restore reconstructs the minimum role topology, restores the historical projection and background jobs, validates ownership and re-runs isolation/escalation attacks.

## Canonical representation before cryptography

The bounded evidence representation is:

```text
<UTF-8 byte length in decimal>:<lowercase UTF-8 hex>
```

It is applied to immutable observation fields, target-checkpoint facts and PITR recovery-grant facts. The evidence explicitly falsifies delimiter-based framing and proves cross-store equality of the canonical checkpoint payload.

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

Exact #108 measured approximately 574 ms and 580 ms for the two stalled-peer directions. This is evidence machinery, not a production RPC/timeout selection.

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
1e58646d903f09954e85cca605c2c840f5099ee4

JLMIRROR Deterministic Assurance #2080
run id 33227438465
SUCCESS

JLMIRROR OPEN-REL-030 Conformance #108
run id 33227438503
SUCCESS
```

The #108 extended run includes generation-bound late-history coverage, conflicting reconciled-content rejection, target key provenance, capability-secret isolation, bounded stalled-peer verification, verifier/mint separation, single-winner physical recovery grant claiming, durable activation grant, premature-activation negatives, grant/placement rollback injection, structured serialization and all prior authority/isolation/recovery/relocation vectors. This anchor becomes provenance after documentation mutation and the final documentation HEAD must rerun both workflows.

## Governance state

Evidence completion does not accept `OPEN-REL-030`, authorize Wave 4, select production deployment/authentication topology or authorize merge. Exact-final-HEAD CI, fresh Codex review, Native Assurance and explicit Track B acceptance remain separate gates.
