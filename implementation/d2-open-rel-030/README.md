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
- Reconciliation completeness is bound to exact owner `authority_generation`, exact current `provider_dataset_revision` and owner-required snapshot currentness.
- Owner-visible provider INSERT/UPDATE atomically increments dataset revision and invalidates prior coverage; stable identity rewrite is rejected and destructive DELETE/TRUNCATE fail closed.
- The reconciliation worker has no direct provider-history INSERT/UPDATE/DELETE/TRUNCATE privilege, no provider-owner membership and no trigger-administration path.
- Stable-identity conflict validation precedes provider-time windowing whenever either accepted or owner-current timestamp intersects the sweep window.
- Every existing ordered history hardening module matching `00[4-9]_history_*.sql` must be referenced by the extended runner; structural CI fails if a reviewer-critical history module exists but is not executed.
- Structured crypto messages require deterministic, versioned, unambiguous/self-delimiting representation before cryptography.
- Typed canonical values must be total/injective across their full supported domain. Relocation `timestamptz` covers finite UTC+microseconds+AD/BC and exact `infinity`/`-infinity`; relocation `numeric` covers normalized finite values plus exact `NaN`, `Infinity` and `-Infinity`.
- A verifier must not inherit issuer/mint capability merely because it can validate an attestation.
- Target signing material must originate and remain inside target authority; the test controller must not provision or retain it.
- Recovery grants are not reusable bearer authorization: surviving authority atomically binds each grant to one authenticated recovery principal derived from session authority.
- Recovery claim/verification APIs are ID-only; restore principals have no direct grant-table read privilege.
- Cross-authority verifier credentials stay out of function source and inside restricted authority-owned capability state.
- Cross-authority calls require a caller-local post-connect deadline; a connected but stalled peer must fail closed.
- Cross-authority activation requires explicit durable authority from both sides; target cannot self-promote.
- A single cross-tenant leak rejects the candidate profile.
- `OPEN-REL-020` retains production telemetry capacity/numeric ownership.
- PostgreSQL/Timescale versions and image digests are evidence dependencies, not immutable production selections.
- Evidence HMAC/SHA, canonical encoding, `dblink`, recovery/verifier LOGIN roles and capability-store layout do not select production KMS/HSM, authentication, network or RPC topology.
- `READY_FOR_MERGE != AUTHORIZED_TO_MERGE`.

## Tier 1 authority coverage

The executable package proves atomic create-or-observe across independent connections; immutable canonical observation content; owner-controlled source/poll authority; exact durable `live` poll claims; current-state CAS by platform authority; stale/predecessor rejection; crash rollback; post-COMMIT ambiguity convergence; durable Tier2-down backlog responsibility; generation/revision-bound owner-current late-history finality/currentness; cross-window conflicting-content rejection; provider dataset mutation invalidation; destructive mutation fail-closed behavior; worker privilege separation; and PITR recovery admission only from surviving authenticated `(R,F]` authority with single-winner authenticated-principal binding.

### Owner-current late-history reconciliation

`provider_authority` durably owns `authority_generation`, `provider_dataset_revision`, `current_snapshot_at`, `finality_floor` and `required_reconciliation_snapshot_at`. Workers supply only a window and expected owner authority.

A reconciliation run contributes to contiguous coverage only when its authority generation, provider dataset revision and provider snapshot currentness still match the locked owner authority. Every `advance_provider_authority(...)` invalidates prior materialized coverage. Owner-visible INSERT/UPDATE increments `provider_dataset_revision` and invalidates coverage in the same transaction. Provider mutation and `sweep(...)` serialize on the same owner row.

Stable identity validation occurs before provider-time window selection. Any immutable `observed_at` or `numeric_value` mismatch rejects the sweep before a coverage run can be minted. Stable provider identity rewrites reject. DELETE and statement-level TRUNCATE fail closed. The reconciliation worker has no direct provider DML/TRUNCATE privilege and cannot administer the protecting triggers.

The extended runner explicitly executes:

```text
004_history_reconciliation.sql
005_history_identity_window_hardening.sql
006_history_dataset_revision_hardening.sql
007_history_dataset_revision_edge_hardening.sql
```

The workflow independently enumerates existing `00[4-9]_history_*.sql` files and fails if any one is absent from the runner. Exact #138 reports `history_modules=4` and preserves:

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

The bounded claim surface is `claim_grant(grant_id)` / `verify_claimed_grant(grant_id)`. Restore principals cannot directly read `recovery_grant` and cannot supply target/principal identity or signed grant facts. The surviving authority loads and verifies the grant internally, derives the claimant from `session_user`, and atomically binds the grant to the first authenticated principal. Same-principal retry converges; another authenticated principal loses. A dedicated race requires exactly one winner, and rival credentials cannot authenticate as the winner.

Exact #138 preserves the full PITR suite, including:

```text
physical_pitr_recovery_claim_api_id_only=PASS
physical_pitr_recovery_claim_identity_from_authenticated_session=PASS
physical_pitr_recovery_principal_no_direct_grant_read=PASS
physical_pitr_recovery_principal_spoof_rejected=PASS
physical_pitr_recovery_claim_single_winner_race=PASS
physical_pitr_recovery_grant_same_principal_retry=PASS
physical_pitr_recovery_grant_other_principal_rejected=PASS
physical_pitr_duplicate_restored_authority_not_admitted=PASS
physical_pitr_recovery_single_winner_authenticated_principal=PASS
physical_pitr_post_reconcile_admission=PASS authority=surviving_external_authenticated_single_winner_principal
```

The PostgreSQL LOGIN/password mechanism is evidence-only. The invariant is binding to the same authenticated recovery authority rather than to a caller-copyable identifier.

## Timescale mediated profile

Direct pooled `RLS + columnstore` and direct pooled `RLS + continuous aggregate` are ineligible on the evaluated TimescaleDB 2.29.2 / PostgreSQL 17.11 profile (`0A000`). The surviving candidate uses no direct tenant-facing privilege on shared raw history/CAGG/internal materialization, fixed-search-path `SECURITY DEFINER` mediation, NOLOGIN `ts_owner`, and LOGIN `ts_automation_owner` only as cross-tenant privileged infrastructure. `PASSWORD NULL` is not production admission proof.

Fresh-cluster restore reconstructs the minimum role topology, restores the historical projection and background jobs, validates ownership and re-runs isolation/escalation attacks.

## Canonical representation before cryptography

The bounded field representation is:

```text
<UTF-8 byte length in decimal>:<lowercase UTF-8 hex>
```

Field framing is applied only after each typed value has a total/injective canonical text form.

### Timestamp

Finite PostgreSQL `timestamptz` values serialize as UTC + microseconds + explicit `AD`/`BC`. Non-finite `-infinity` and `infinity` use those exact reserved literals, so they cannot become SQL NULL and disappear from `string_agg`.

Exact #138 proves:

```text
relocation_timestamp_era_injective=PASS
relocation_timestamp_era_cross_store=PASS
relocation_timestamp_negative_infinity_canonical=PASS value=-infinity
relocation_timestamp_positive_infinity_canonical=PASS value=infinity
relocation_timestamp_nonfinite_cross_store=PASS
relocation_timestamp_nonfinite_digest_injective=PASS
relocation_digest_uses_total_timestamp_canonicalizer=PASS
```

### Numeric

The accepted relocation value column is unconstrained PostgreSQL `numeric`, whose evaluated domain includes finite values plus `NaN`, `Infinity` and `-Infinity`. Both Tier 1 and Tier 2 now use `canonical_numeric(...)`: finite values are normalized through `trim_scale`, while special values map to explicit exact literals before self-delimiting framing.

Exact #138 proves:

```text
relocation_numeric_nan_canonical=PASS value=NaN
relocation_numeric_positive_infinity_canonical=PASS value=Infinity
relocation_numeric_negative_infinity_canonical=PASS value=-Infinity
relocation_numeric_finite_scale_canonical=PASS value=1.23
relocation_numeric_special_values_cross_store=PASS
relocation_numeric_special_value_digest_injective=PASS
relocation_digest_uses_total_numeric_canonicalizer=PASS
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

The effective target checkpoint key is generated inside Tier 2. Tier 1 contains no target signing-key relation; the controller does not retain the key; projection writer/verifier cannot read it. Verifier connection credentials are restricted capability state and absent from function source. The raw asynchronous transport helper is owner-only, `connect_timeout` bounds connection setup, and `dblink_send_query` + `dblink_is_busy` enforce a caller-local established-response deadline.

Exact #138 preserves target-key provenance, verifier-secret isolation, stalled-peer fail-closed behavior, target seal/DML serialization, forged-attestation rejection, placement+grant rollback injection, target self-activation rejection, exact activation-grant verification and final Tier1↔Tier2 continuity.

## Exact empirical anchor before reviewer documentation

```text
HEAD
4c6e3a051d76b257df8058bf2b4503e2b6d84013

JLMIRROR Deterministic Assurance #2141
run id 33233751143
SUCCESS

JLMIRROR OPEN-REL-030 Conformance #138
run id 33233751124
SUCCESS
```

The #138 extended run executes all four history-hardening modules (`004–007`), preserves all prior authority/isolation/recovery/relocation vectors, and additionally proves total full-domain canonicalization for both PostgreSQL `timestamptz` and unconstrained `numeric` special values. This anchor becomes provenance after reviewer-document mutation; the exact final documentation HEAD must rerun both workflows.

## Governance state

Evidence completion does not accept `OPEN-REL-030`, authorize Wave 4, select production deployment/authentication topology or authorize merge. Exact-final-HEAD CI, fresh Codex review, Native Assurance and explicit Track B acceptance remain separate gates.
