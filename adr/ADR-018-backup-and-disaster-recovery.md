# ADR-018 — Backup, Restore and Disaster-Recovery Model

**Status:** proposed  
**Date:** 2026-08-17  
**Reversibility:** costly

## Context

`INV-RECOVERY-001` requires tested restoration. Cells reduce blast radius but create multiple recovery units. Tenant-level operator error must not require destructive restore of every tenant. RPO/RTO are not yet numerically committed.

Encrypted database/object backups are insufficient if the independent cryptographic authority required to decrypt restored ciphertext is lost. Because ADR-015 keeps production secret/KMS root authority outside ordinary databases, DR must recover both protected data and the key hierarchy/configuration necessary to make that data usable.

Drivers: `QA-REC-001`, `INV-RECOVERY-001`, `INV-SECRET-001`, `FR-OPS-003`, `SEC-SEC-*`, `AP-11`.

## Decision

Recovery is designed at multiple scopes:

1. **control plane:** encrypted backups/PITR as supported by selected store, with tested restoration of tenant/placement/catalog metadata;
2. **cell transactional store:** automated backups plus point-in-time recovery capability;
3. **tenant logical recovery:** tooling to restore/export a tenant into an isolated verification namespace/environment before controlled reintroduction;
4. **object artifacts:** versioning/retention according to data policy where needed;
5. **telemetry:** backup/retention strategy based on business value, cost and re-ingest possibility, separate from transactional assumptions;
6. **cryptographic authority:** recoverable/reconstructable KMS/secret-manager configuration, key aliases/versions/policies and root/master key availability required to decrypt persisted ciphertext and encrypted backups.

### Cryptographic recovery requirements

The DR design SHALL maintain an inventory that maps protected data classes to the cryptographic authority/key versions required for recovery. A successful database restore that cannot decrypt required application ciphertext is a failed recovery.

The selected KMS/secret-management design MUST provide a provider-appropriate recovery strategy for root/master/key-encryption-key material. Depending on platform capability this may use protected multi-region/key replication, recoverable provider-managed keys, controlled backup/escrow of customer-managed key material, or another explicitly accepted mechanism.

The recovery mechanism MUST NOT copy plaintext master keys into application databases, ordinary backups, source repositories or runbooks. Recovery credentials/key material use separate least-privilege controls and, where appropriate, dual-control/break-glass procedures.

Key deletion/crypto-shredding policies MUST account for backup retention. A key version required by retained recoverable ciphertext cannot be irreversibly destroyed unless making that ciphertext unrecoverable is the explicit governed intent.

Secret values that can be reissued (for example external-provider credentials) SHOULD generally be rotated/re-provisioned rather than backed up as plaintext. Recovery still preserves the metadata/reference and operational process required to re-establish them.

Restore procedures SHALL be rehearsed. Backup existence without a successful restore-and-decrypt test is not accepted recovery capability.

RPO/RTO numerical objectives remain OPEN until SLO/business-tier work. Production commitments cannot be made before those objectives and corresponding restore measurements are accepted.

## Consequences

### Positive
- recovery matches cell and tenant blast radius;
- tenant operator error does not automatically imply fleet rollback;
- encrypted restores remain actually usable after infrastructure/account/region loss scenarios;
- evidence-based RPO/RTO becomes possible.

### Negative / cost
- logical tenant restore tooling is non-trivial for pooled data;
- cryptographic authority introduces a separate critical recovery dependency;
- restore rehearsals and key-recovery controls consume operational capacity.

## Validation

Scheduled restore tests SHALL cover control plane, a representative cell and tenant-scoped recovery. Integrity, authorization, placement and audit consistency are validated before reintroduction.

At least one DR rehearsal SHALL simulate loss/unavailability of the normal secret/KMS environment and prove that representative restored encrypted application data can be decrypted through the approved recovery path without exposing plaintext root/master keys to ordinary application operators. Key-version rotation and retained-backup decryptability are also tested.

## Exit / revisit conditions

Storage-specific backup technology and KMS/secret-provider mechanisms may change; multi-scope tested recovery, including required cryptographic authority, remains mandatory.
