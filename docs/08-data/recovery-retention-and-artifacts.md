# Recovery, Retention and Artifacts

**Status:** proposed baseline  
**Primary ADR:** ADR-018

## Recovery scopes

JLMIRROR distinguishes:

- Control Plane recovery;
- whole-cell transactional recovery;
- tenant-level logical recovery within a pooled cell;
- telemetry recovery/reconstruction;
- artifact/object recovery;
- configuration/secret-reference recovery;
- cryptographic authority/key-hierarchy recovery required to decrypt retained data.

A backup is not a recovery capability until restoration **and required decryption** are rehearsed.

## Control Plane recovery

Placement/lifecycle metadata is high criticality. Recovery must restore a consistent tenant-to-cell authority and prevent routing to ambiguous/stale placement. Restore procedures include validation of cell/placement versions before normal topology changes resume.

## Cell physical recovery

Cell transactional PostgreSQL uses encrypted backup and point-in-time recovery capabilities selected by platform design. Cell recovery occurs to a controlled target, validates schema/invariants and only then resumes admitted traffic.

## Cryptographic recovery dependency

Persisted ciphertext, encrypted database backups and protected objects are only recoverable if the required KMS/secret-manager key hierarchy remains available through an approved DR path.

Recovery inventory therefore tracks, by protected data class:

```text
ciphertext / backup class
key or key-alias/reference
key version / cryptographic metadata as required
recovery authority/provider scope
retention/deletion dependency
approved recovery mechanism
```

The selected platform must define provider-appropriate recovery for root/master/key-encryption-key authority, such as protected multi-region replication, recoverable provider-managed key authority, or controlled backup/escrow for customer-managed keys where technically supported and security-approved.

Plaintext master/root keys are never copied into application databases, ordinary backup sets, source code or general runbooks. Recovery authority uses separate least-privilege access and stronger operational controls where appropriate.

Keys needed by still-retained recoverable ciphertext/backups cannot be irreversibly destroyed unless the governed intent is cryptographic erasure of those retained copies.

Reissuable third-party credentials normally use controlled reprovisioning/rotation rather than plaintext backup; recovery still restores the references/configuration and procedure needed to re-establish them.

## Tenant-level recovery in pooled cells

Physical PITR restores an entire database, not one logical tenant. Tenant recovery therefore begins in an isolated recovery environment:

```text
restore cell snapshot/PITR to quarantine
   -> recover/validate required cryptographic authority
   -> select tenant rows by tenant_id across owned schemas
   -> validate relationships/invariants/audit/outbox/process state
   -> build a tenant recovery set
   -> materialize/validate in an isolated recovery target
   -> fence the currently authoritative tenant if replacement is required
   -> perform controlled cutover/reconciliation
```

### Preferred replacement model

When the requirement is to restore the tenant to an earlier coherent point, the preferred model is **restore as a new isolated target followed by controlled authority cutover using relocation-grade fencing semantics**. The currently active tenant is never overwritten piecemeal while it continues accepting writes.

This produces one authoritative history at a time and reuses placement/write-fence controls already required for relocation.

### In-place reconciliation

Selective domain reconciliation into the existing authoritative tenant is allowed only when the owning domain defines merge semantics. It requires tenant write coordination/fencing appropriate to the mutated aggregates, idempotency/audit, and proof that unrelated current changes are not silently overwritten.

A generic row-level "merge everything from backup" into a live tenant is prohibited.

## Recovery point/time objectives

Numeric RPO/RTO values remain OPEN until commercial/SLO work. Targets are defined separately for Control Plane, cell transactional data, telemetry, artifacts and cryptographic authority because their business criticality/recovery paths differ.

## Retention policy

Retention is driven by data class, tenant plan/policy, security/compliance/legal requirement and storage tier.

Canonical lifecycle:

```text
hot/current -> warm/rolled-up -> archive -> governed deletion
```

Not every data class uses every stage.

Retention policy must account for key lifecycle: deleting a key version may make otherwise retained encrypted data permanently unrecoverable.

## Deletion/anonymization

Data-rights workflows distinguish physical deletion, anonymization, pseudonymization and legal retention. Auditability does not justify retaining unnecessary personal data forever.

## Object/artifact storage

Large generated/exported binary content lives outside transactional PostgreSQL. Metadata includes:

```text
artifact_id
tenant_id
artifact_type
storage_reference
content_type
size
checksum
created_at
expires_at/retention policy
classification
status
```

Object namespaces use immutable tenant identity, not mutable slug. Access is mediated by application authorization or short-lived scoped download capability; storage paths are not authorization.

## Artifact authorization

For delayed exports/reports, authorization is checked when requested and, where policy requires, again before artifact release/download. Revoked users do not retain indefinite access through stale permanent links.

## Restore rehearsal

Scheduled recovery tests prove:

- backup readability;
- recovery-path availability of required KMS/secret-manager authority and key versions;
- successful decryption of representative restored application ciphertext without exposing root/master plaintext to ordinary operators;
- restore procedure correctness;
- RLS/tenant isolation after restore;
- application/schema compatibility;
- tenant recovery set completeness across bounded contexts;
- write-fence/cutover safety for tenant-level replacement;
- retained-backup decryptability across key rotation/version changes;
- measured recovery duration and data-loss window.

A database/object restore that completes structurally but cannot decrypt required protected data is a failed rehearsal.

Results are operational evidence used to set/revise RPO/RTO.
