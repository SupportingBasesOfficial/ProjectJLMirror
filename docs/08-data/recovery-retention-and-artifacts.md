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

A backup is not a recovery capability until restoration, required decryption **and safety/accountability/security-authority reconciliation** are rehearsed for the applicable scope.

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
restore cell snapshot/PITR to quarantine at recovery point R
   -> recover/validate required cryptographic authority
   -> select tenant rows by tenant_id across owned schemas
   -> validate relationships/invariants/audit/outbox/process state at R
   -> build a tenant recovery set
   -> materialize/validate in an isolated recovery target
   -> establish/fence current authoritative tenant at F
   -> reconcile safety/accountability/security-authority interval (R, F]
   -> verify no duplicate irreversible effect or revoked authority becomes eligible
   -> controlled authority cutover
```

### Preferred replacement model

When the requirement is to restore tenant business/domain state to an earlier coherent point, the preferred model is **restore as a new isolated target followed by reconciliation and controlled authority cutover using relocation-grade fencing semantics**. The currently active tenant is never overwritten piecemeal while it continues accepting writes.

This produces one authoritative business-state history at a time without pretending that all safety, accountability or security-authority evidence should travel backwards with it.

### Recovery reconciliation interval

Let `R` be the selected recovery point and `F` the final write fence on the currently authoritative tenant. All relevant records/effects in `(R, F]` are inventoried before cutover.

The recovery manifest distinguishes:

**Rollback subject state** — domain/business state intentionally restored to `R`.

**Safety/accountability/security-authority continuity state** — state that cannot be forgotten merely because business state is being rolled back, including:

- immutable audit records/intents;
- inbox/deduplication receipts and idempotency outcomes;
- external provider/payment/automation operation identities and acknowledgements;
- long-running process/execution outcomes;
- committed/pending outbox state needed to determine whether an effect was already published/accepted;
- security/compliance evidence;
- session/credential revocations and logout invalidation state;
- membership disablement/revocation, permission/scope removal and tenant suspension/access-denial state;
- authorization/session generations, revocation generations, tombstones or equivalent freshness state whose loss could reactivate stale authority;
- compensation and reconciliation state.

For each irreversible/external operation after `R`, the owning domain must determine whether it was completed, externally accepted, compensatable, still pending, or ambiguous. The restored target does not become authoritative for effectful processing until required deduplication identities/outcomes are present and ambiguous operations are reconciled or quarantined.

### Authorization revocation continuity

Point-in-time business recovery MUST NOT implicitly re-grant access by restoring an older positive authorization state over a later revoke/deny/suspend event.

A session revocation, credential revocation, membership disablement/revocation, permission/scope removal, tenant suspension or equivalent security denial that became effective in `(R, F]` is continuity state by default and SHALL be preserved or reconciled forward before the recovered target resumes protected traffic.

Where authorization/session generation or revocation-marker semantics are used, recovery SHALL preserve a trustworthy generation/freshness value that is at least as restrictive as the reconciled security state. A capability/session/token minted against an older generation MUST remain stale after recovery and MUST NOT become valid merely because the underlying database was restored to `R`.

Before protected traffic resumes, the recovered target SHALL reconcile revocation/deny state through `F` and then validate against the current authoritative security state at reintroduction time. If completeness or freshness of that authority cannot be established safely, protected admission fails closed.

If the business intent is specifically to reverse a post-`R` security revocation, that is a separate security-recovery operation. It requires current authorization, any applicable step-up/approval policy, explicit scope and immutable audit evidence; it is never an accidental side effect of ordinary PITR.

A point-in-time restore MUST NOT blindly copy all post-`R` domain mutations forward, because doing so can defeat the recovery objective. Conversely it MUST NOT blindly discard all post-`R` reliability, audit or authorization-revocation history, because doing so can recreate duplicate side effects, erase accountability or resurrect access.

If immutable audit evidence for `(R, F]` resides in a protected external sink or retained source, that evidence remains authoritative and is linked/reintroduced as required before the old source is destroyed. Recovery-induced cleanup never serves as a mechanism to erase valid later audit history.

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

Retention for idempotency/deduplication/audit/reliability/revocation evidence must cover the recovery and replay windows in which losing that evidence could make an irreversible effect repeatable, accountability incomplete or stale authority valid again.

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

For a user-requested delayed/asynchronous export or report:

1. authorization is checked when the request/process is created;
2. authorization is checked again before the delayed job begins or performs the protected export action;
3. authorization is checked again before the completed artifact is released or a download capability is minted.

These rechecks are **mandatory**, not policy-optional, when the operation is delayed/asynchronous under `SEC-EXEC-003`. If membership/scope/permission was revoked, the job/release fails closed and records a safe audited outcome.

A downloadable capability is short-lived and scoped to one artifact/tenant. If a policy requires revocation after capability issuance, delivery uses an application-mediated or otherwise revocable mechanism instead of an irrevocable permanent link.

Scheduled/system-generated exports use an explicitly authorized service principal/process policy rather than inheriting stale authority from a human who once configured the schedule.

## Restore rehearsal

Scheduled recovery tests prove:

- backup readability;
- recovery-path availability of required KMS/secret-manager authority and key versions;
- successful decryption of representative restored application ciphertext without exposing root/master plaintext to ordinary operators;
- restore procedure correctness;
- RLS/tenant isolation after restore;
- application/schema compatibility;
- tenant recovery set completeness across bounded contexts;
- explicit inventory and reconciliation of `(R, F]` reliability/audit/external-effect/security-revocation state;
- already-completed irreversible effects are not repeated after cutover;
- post-`R` immutable audit evidence remains available after source cleanup;
- a session/capability or membership grant valid at `R` but revoked in `(R, F]` remains rejected after restore and cutover;
- authorization/session generation or equivalent revocation freshness does not move backwards during recovery;
- write-fence/cutover safety for tenant-level replacement;
- retained-backup decryptability across key rotation/version changes;
- measured recovery duration and data-loss window.

A database/object restore that completes structurally but cannot decrypt required protected data, suppress duplicate irreversible effects, preserve required accountability evidence or preserve effective revocation/deny state is a failed rehearsal.

Results are operational evidence used to set/revise RPO/RTO.
