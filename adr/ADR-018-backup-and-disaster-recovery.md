# ADR-018 — Backup, Restore and Disaster-Recovery Model

**Status:** proposed  
**Date:** 2026-08-17  
**Reversibility:** costly

## Context

`INV-RECOVERY-001` requires tested restoration. Cells reduce blast radius but create multiple recovery units. Tenant-level operator error must not require destructive restore of every tenant. RPO/RTO are not yet numerically committed.

Encrypted database/object backups are insufficient if the independent cryptographic authority required to decrypt restored ciphertext is lost. Because ADR-015 keeps production secret/KMS root authority outside ordinary databases, DR must recover both protected data and the key hierarchy/configuration necessary to make that data usable.

Point-in-time recovery has an additional correctness risk at any authoritative scope: restoring state to time `R` must not erase later knowledge required to prevent duplicate irreversible effects, preserve accountability or keep security revocations effective. Tenant-level and whole-cell PITR therefore require an explicit reconciliation boundary before the recovered authority can resume protected or effectful traffic.

Drivers: `QA-REC-001`, `INV-RECOVERY-001`, `INV-SECRET-001`, `INV-ASYNC-001`, `FR-OPS-003`, `SEC-SEC-*`, `SEC-AUD-*`, `SEC-AUTHZ-*`, `SEC-BROWSER-*`, `AP-11`.

## Decision

Recovery is designed at multiple scopes:

1. **control plane:** encrypted backups/PITR as supported by selected store, with tested restoration of tenant/placement/catalog metadata and continuity of authoritative security/lifecycle denies where applicable;
2. **cell transactional store:** automated backups plus point-in-time recovery capability with whole-cell reconciliation before normal authority resumes;
3. **tenant logical recovery:** tooling to restore/export a tenant into an isolated verification namespace/environment before controlled reintroduction;
4. **object artifacts:** versioning/retention according to data policy where needed;
5. **telemetry:** backup/retention strategy based on business value, cost and re-ingest possibility, separate from transactional assumptions;
6. **cryptographic authority:** recoverable/reconstructable KMS/secret-manager configuration, key aliases/versions/policies and root/master key availability required to decrypt persisted ciphertext and encrypted backups.

### Scope-wide PITR continuity invariant

Any recovery scope that can roll back authorization/revocation state, deduplication/idempotency state, process outcomes, audit evidence or knowledge of external irreversible effects SHALL define:

- recovery point `R`;
- a later authoritative reconciliation boundary `F` representing the final trusted activity/evidence boundary that must be accounted for before restored authority resumes;
- rollback-subject state that intentionally returns to `R`;
- safety/accountability/security-authority continuity state from `(R, F]` that must survive, be reconstructed or be reconciled forward.

If the previous authority is still reachable, `F` is established through an explicit write/admission fence and final synchronization/reconciliation boundary. If the previous authority is lost, `F` is derived from the best surviving durable authorities and watermarks available for that scope, such as replicated transactional/WAL evidence, protected audit sinks, idempotency/process records, security/revocation authorities and external-provider acknowledgements. Uncertainty is not treated as proof of absence.

If the platform cannot establish enough continuity evidence to prove safe protected/effectful resumption, the recovered scope remains quarantined/non-authoritative for those operations and fails closed until reconciliation or an explicitly governed recovery decision resolves the uncertainty.

### Whole-cell point-in-time recovery continuity

A whole-cell PITR restores cell-owned state for many tenants at once, including organization/access state, outbox/inbox/idempotency/process records, tenant domain state and potentially audit intents. It therefore SHALL NOT resume normal admitted traffic merely because PostgreSQL starts and schema/invariant checks pass.

The restored cell remains in a **recovery quarantine/non-authoritative admission state** while the platform:

1. establishes recovery point `R` and reconciliation boundary `F` for the failed/replaced cell;
2. inventories affected tenants and continuity-bearing records/effects in `(R, F]`;
3. reconciles inbox/deduplication, idempotency outcomes, process/execution state, outbox publication/effect state and completed/ambiguous external operations;
4. restores or references required immutable audit/accountability evidence;
5. reconciles session/credential revocations where cell-owned or relevant, membership disablement/revocation, permission/scope removals, tenant suspension/access-denial state, authorization/session generations, revocation tombstones or equivalent freshness state;
6. validates placement/admission state and current external/security authorities;
7. proves that stale authority and already-completed irreversible effects cannot become eligible solely because the cell was restored to `R`.

Only after those pre-admission gates pass may the cell resume protected tenant traffic and effectful workers/schedulers. Post-admission verification remains defense in depth; it is not the first authorization/reliability check.

If the cell outage destroyed the only copy of continuity evidence for some operation, affected effectful work is quarantined or reconciled with its external authority before retry. Protected access whose current deny/revocation state cannot be established fails closed.

### Tenant point-in-time recovery continuity

For a tenant recovery from selected recovery point `R`, the system SHALL establish a later write fence `F` on the currently authoritative tenant before replacement cutover. The interval `(R, F]` is a **recovery reconciliation interval**.

The recovery plan SHALL classify state into at least:

- **rollback subject state:** business/domain state intentionally restored to `R`;
- **safety/accountability/security-authority continuity state:** records that must survive or be reconciled forward even though they occurred after `R`, including immutable audit evidence, inbox/deduplication receipts, idempotency outcomes, completed/attempted irreversible external operations, provider/payment operation identities, long-running process/execution outcomes, security/compliance evidence, session/credential revocations, membership disablement/revocation, permission/scope removal, tenant suspension/access denial, authorization/session generations or revocation tombstones, and other records required to prevent duplicate effects, loss of accountability or resurrection of stale authority.

Before the restored target becomes authoritative, the reconciliation interval SHALL be examined and continuity state SHALL be merged/reconstructed/referenced into the recovery target or another durable authority under owning-domain rules. The procedure MUST NOT blindly replay all post-`R` business mutations, because the recovery intent may deliberately be to undo those mutations.

Every irreversible/external operation in `(R, F]` is classified into one of: already-completed/preserve dedup evidence, externally reconcile current truth, compensate under explicit domain policy, or quarantine for operator decision. A target SHALL NOT accept effectful retries until the identifiers/outcomes required to suppress duplicate irreversible effects are present and validated.

### Authorization revocation continuity

Ordinary business/domain PITR MUST NOT implicitly reverse a security denial that became effective after `R`.

Session/credential revocation, membership disablement/revocation, permission/scope removal, tenant suspension/access denial and equivalent deny state from `(R, F]` SHALL be reconciled forward by default before protected traffic resumes.

Where authorization/session generation or revocation-marker semantics are used, the recovered authority SHALL preserve a trustworthy current generation/freshness state that does not move backwards merely because the business database was restored. A capability, session or token minted against an older generation remains stale after recovery.

Before reintroduction, the recovered target SHALL reconcile security deny/revocation state through `F` and then validate against the current authoritative security state. If completeness or freshness cannot be established safely, protected admission fails closed.

Reversing a post-`R` revocation is a distinct security-recovery operation requiring current authorization, applicable step-up/approval and immutable audit evidence. It is not an incidental effect of PITR.

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
- post-recovery-point authorization revocations remain effective unless explicitly reversed through a separate security operation;
- whole-cell restoration cannot bypass the same continuity guarantees required of tenant-level restoration;
- evidence-based RPO/RTO becomes possible.

### Negative / cost
- logical tenant restore tooling is non-trivial for pooled data;
- whole-cell PITR requires all-tenant continuity inventory/reconciliation before normal admission;
- point-in-time tenant recovery requires interval reconciliation rather than a simple pointer cutover;
- security-revocation continuity adds another recovery dependency that must be inventoried and tested;
- cryptographic authority introduces a separate critical recovery dependency;
- restore rehearsals, external reconciliation and key-recovery controls consume operational capacity.

## Validation

Scheduled restore tests SHALL cover control plane, a representative cell and tenant-scoped recovery. Integrity, authorization, placement, deduplication/process continuity and audit consistency are validated before reintroduction.

A whole-cell PITR rehearsal SHALL restore a cell to `R` after creating representative later membership/permission revocations, idempotency receipts, immutable audit evidence and completed/ambiguous external effects. The recovered cell must remain non-authoritative until `(R, F]` continuity is reconciled and must prove that revoked access stays denied and already-completed effects are not repeated when admission resumes.

A tenant PITR rehearsal SHALL create representative post-recovery-point irreversible effects and audit/idempotency records, then restore to the earlier point and prove the recovered target cannot repeat those effects and does not lose the post-point accountability evidence after cutover/source cleanup.

A security recovery rehearsal SHALL establish a session/capability or membership/permission grant before `R`, revoke or suspend it in `(R, F]`, restore business state to `R`, reconcile the interval and prove the recovered target still rejects the stale authority before protected traffic resumes. Authorization/session generation or equivalent revocation freshness MUST NOT regress across recovery.

At least one DR rehearsal SHALL simulate loss/unavailability of the normal secret/KMS environment and prove that representative restored encrypted application data can be decrypted through the approved recovery path without exposing plaintext root/master keys to ordinary application operators. Key-version rotation and retained-backup decryptability are also tested.

## Exit / revisit conditions

Storage-specific backup technology and KMS/secret-provider mechanisms may change; multi-scope tested recovery, cryptographic recoverability, post-recovery-point safety/accountability reconciliation and revocation continuity remain mandatory.
