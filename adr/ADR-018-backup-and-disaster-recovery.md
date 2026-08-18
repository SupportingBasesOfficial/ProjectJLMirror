# ADR-018 — Backup, Restore and Disaster-Recovery Model

**Status:** proposed  
**Date:** 2026-08-17  
**Reversibility:** costly

## Context

`INV-RECOVERY-001` requires tested restoration. Cells reduce blast radius but create multiple recovery units. Tenant-level operator error must not require destructive restore of every tenant. RPO/RTO are not yet numerically committed.

Encrypted database/object backups are insufficient if the independent cryptographic authority required to decrypt restored ciphertext is lost. Because ADR-015 keeps production secret/KMS root authority outside ordinary databases, DR must recover both protected data and the key hierarchy/configuration necessary to make that data usable.

Point-in-time tenant recovery has an additional correctness risk: restoring business state to time `R` must not erase knowledge of irreversible external effects, deduplication receipts, process outcomes or immutable audit evidence that occurred between `R` and the final recovery write fence `F`. Otherwise a restored target can repeat an already-completed external action or lose accountability history.

Drivers: `QA-REC-001`, `INV-RECOVERY-001`, `INV-SECRET-001`, `INV-ASYNC-001`, `FR-OPS-003`, `SEC-SEC-*`, `SEC-AUD-*`, `AP-11`.

## Decision

Recovery is designed at multiple scopes:

1. **control plane:** encrypted backups/PITR as supported by selected store, with tested restoration of tenant/placement/catalog metadata;
2. **cell transactional store:** automated backups plus point-in-time recovery capability;
3. **tenant logical recovery:** tooling to restore/export a tenant into an isolated verification namespace/environment before controlled reintroduction;
4. **object artifacts:** versioning/retention according to data policy where needed;
5. **telemetry:** backup/retention strategy based on business value, cost and re-ingest possibility, separate from transactional assumptions;
6. **cryptographic authority:** recoverable/reconstructable KMS/secret-manager configuration, key aliases/versions/policies and root/master key availability required to decrypt persisted ciphertext and encrypted backups.

### Tenant point-in-time recovery continuity

For a tenant recovery from selected recovery point `R`, the system SHALL establish a later write fence `F` on the currently authoritative tenant before replacement cutover. The interval `(R, F]` is a **recovery reconciliation interval**.

The recovery plan SHALL classify state into at least:

- **rollback subject state:** business/domain state intentionally restored to `R`;
- **safety/accountability continuity state:** records that must survive or be reconciled forward even though they occurred after `R`, including immutable audit evidence, inbox/deduplication receipts, idempotency outcomes, completed/attempted irreversible external operations, provider/payment operation identities, long-running process/execution outcomes, security/compliance evidence and other records required to prevent duplicate effects or loss of accountability.

Before the restored target becomes authoritative, the reconciliation interval SHALL be examined and safety/accountability continuity state SHALL be merged/reconstructed/referenced into the recovery target or another durable authority under owning-domain rules. The procedure MUST NOT blindly replay all post-`R` business mutations, because the recovery intent may deliberately be to undo those mutations.

Every irreversible/external operation in `(R, F]` is classified into one of: already-completed/preserve dedup evidence, externally reconcile current truth, compensate under explicit domain policy, or quarantine for operator decision. A target SHALL NOT accept effectful retries until the identifiers/outcomes required to suppress duplicate irreversible effects are present and validated.

Immutable audit evidence from `(R, F]` is not destroyed merely because domain state is rolled back to `R`; if the audit store itself is restored from an older snapshot, the missing evidence interval must be recovered from the protected source/replica/sink before old source cleanup can remove it.

### Cryptographic recovery requirements

The DR design SHALL maintain an inventory that maps protected data classes to the cryptographic authority/key versions required for recovery. A successful database restore that cannot decrypt required application ciphertext is a failed recovery.

The selected KMS/secret-management design MUST provide a provider-appropriate recovery strategy for root/master/key-encryption-key material. Depending on platform capability this may use protected multi-region/key replication, recoverable provider-managed keys, controlled backup/escrow of customer-managed key material, or another explicitly accepted mechanism.

The recovery mechanism MUST NOT copy plaintext master keys into application databases, ordinary backups, source repositories or runbooks. Recovery credentials/key material use separate least-privilege controls and, where appropriate, dual-control/break-glass procedures.

Key deletion/crypto-shredding policies MUST account for backup retention. A key version required by retained recoverable ciphertext cannot be irreversibly destroyed unless making that ciphertext unrecoverable is the explicit governed intent.

Secret values that can be reissued (for example external-provider credentials) SHOULD generally be rotated/re-provisioned rather than backed up as plaintext. Recovery still preserves the metadata/reference and operational process required to re-establish them.

Restore procedures SHALL be rehearsed. Backup existence without a successful restore-and-decrypt-and-reconcile test is not accepted recovery capability.

RPO/RTO numerical objectives remain OPEN until SLO/business-tier work. Production commitments cannot be made before those objectives and corresponding restore measurements are accepted.

## Consequences

### Positive
- recovery matches cell and tenant blast radius;
- tenant operator error does not automatically imply fleet rollback;
- encrypted restores remain actually usable after infrastructure/account/region loss scenarios;
- point-in-time recovery does not silently recreate eligibility for already-completed irreversible effects;
- audit/accountability history survives logical business-state rollback;
- evidence-based RPO/RTO becomes possible.

### Negative / cost
- logical tenant restore tooling is non-trivial for pooled data;
- point-in-time tenant recovery requires interval reconciliation rather than a simple pointer cutover;
- cryptographic authority introduces a separate critical recovery dependency;
- restore rehearsals, external reconciliation and key-recovery controls consume operational capacity.

## Validation

Scheduled restore tests SHALL cover control plane, a representative cell and tenant-scoped recovery. Integrity, authorization, placement, deduplication/process continuity and audit consistency are validated before reintroduction.

A tenant PITR rehearsal SHALL create representative post-recovery-point irreversible effects and audit/idempotency records, then restore to the earlier point and prove the recovered target cannot repeat those effects and does not lose the post-point accountability evidence after cutover/source cleanup.

At least one DR rehearsal SHALL simulate loss/unavailability of the normal secret/KMS environment and prove that representative restored encrypted application data can be decrypted through the approved recovery path without exposing plaintext root/master keys to ordinary application operators. Key-version rotation and retained-backup decryptability are also tested.

## Exit / revisit conditions

Storage-specific backup technology and KMS/secret-provider mechanisms may change; multi-scope tested recovery, cryptographic recoverability and post-recovery-point safety/accountability reconciliation remain mandatory.
