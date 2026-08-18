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

A backup is not a recovery capability until restoration, required decryption **and safety/accountability/security-authority/governance continuity reconciliation** are rehearsed for the applicable scope.

## Scope-wide PITR continuity

A point-in-time restore is allowed to move rollback-subject state to an earlier time; it is not allowed to erase later evidence or governed decisions that the platform still needs for security, idempotency, accountability, external-effect correctness, privacy/data-rights enforcement or legal retention.

For any recovered authoritative scope that can roll back such state, recovery defines:

```text
R = selected recovery point
F = later authoritative reconciliation boundary
(R,F] = continuity interval that must be accounted for
```

When the old authority remains available, `F` is established with an explicit write/admission fence and final reconciliation watermark. When it is unavailable, `F` is reconstructed from surviving durable authorities/watermarks and any unresolved uncertainty is treated as unsafe rather than as proof that nothing happened.

Until applicable continuity state has been reconciled, the recovered scope remains quarantined/non-authoritative for protected and effectful traffic. Restricted diagnostic/read-only access, if ever allowed, is a separate explicit operational policy and does not imply normal authority. Protected data whose post-`R` erasure/anonymization state is unresolved MUST NOT be re-exposed merely because it exists in the restored image, and data whose legal-retention state is unresolved MUST NOT be destructively removed merely because an older snapshot lacks the hold.

## Control Plane recovery

Placement/lifecycle metadata is high criticality. Recovery must restore a consistent tenant-to-cell authority and prevent routing to ambiguous/stale placement. Restore procedures include validation of cell/placement versions before normal topology changes resume.

If Control Plane PITR can roll back tenant suspension, global/session revocation, placement lifecycle, governed erasure/retention control state or another deny/fence authority, the later authoritative state is continuity state and is reconciled before topology-changing or protected admission decisions resume. A restored older positive state does not automatically override a later authoritative deny or governance decision.

## Cell physical recovery

Cell transactional PostgreSQL uses encrypted backup and point-in-time recovery capabilities selected by platform design. A restored cell first comes up in a controlled **recovery quarantine/non-authoritative state**; database/schema/invariant health is necessary but not sufficient to resume admitted traffic.

### Whole-cell PITR reconciliation

Whole-cell PITR can roll back cell-owned membership/access state, tenant domain state, outbox/inbox/idempotency records, long-running process outcomes, required audit evidence and governed deletion/anonymization/retention state for many tenants at once. The restored cell therefore executes this recovery lifecycle before normal admission:

```text
restore cell to recovery point R in quarantine
   -> recover/validate required cryptographic authority
   -> establish reconciliation boundary F
   -> inventory affected tenants and (R,F] continuity state
   -> reconcile dedup/idempotency/process/outbox/external-effect outcomes
   -> restore/reference required immutable audit evidence
   -> reconcile membership/permission/tenant-deny and authorization freshness state
   -> reconcile erasure/anonymization tombstones and current legal-retention state
   -> reconcile artifact metadata/object lifecycle where the transactional snapshot can roll back artifact authority
   -> validate placement/admission and current security/governance authorities
   -> prove stale authority, erased data and completed effects are not admission/retry eligible
   -> enable protected/effectful admission
   -> post-admission verification as defense in depth
```

If the prior cell is still available, `F` is a final write/admission fence/watermark. If the prior cell was lost, `F` and continuity are reconstructed from surviving replication/WAL/journal evidence, external audit/security/governance authorities, provider acknowledgements and other durable records. Missing evidence creates an unresolved recovery condition; it does not authorize retry, access or re-exposure of data whose governed erasure/anonymization status cannot be established.

A restored cell SHALL NOT resume protected tenant traffic, schedulers or effectful workers until the applicable all-tenant safety/accountability/security-authority/governance reconciliation is complete. If current authorization/deny state cannot be established, protected access fails closed. If an external effect outcome cannot be established, that operation is reconciled or quarantined before retry. If erasure/anonymization status is unresolved, the affected protected data remains unavailable; if legal-retention status is unresolved, destructive deletion remains blocked.

Post-recovery authorization, governance and tenant-isolation checks continue after admission, but they are defense in depth and do not replace the pre-admission reconciliation gate.

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

Keys needed by still-retained recoverable ciphertext/backups cannot be irreversibly destroyed unless the governed intent is cryptographic erasure of those retained copies. Conversely, when cryptographic erasure is the approved governed decision, recovery MUST NOT silently restore an older usable key path that defeats that erasure; the erasure decision/evidence is continuity state even when the destroyed key material itself is not recoverable.

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
   -> reconcile safety/accountability/security-authority/governance interval (R, F]
   -> verify no duplicate irreversible effect, revoked authority or erased data becomes eligible
   -> controlled authority cutover
```

### Preferred replacement model

When the requirement is to restore tenant business/domain state to an earlier coherent point, the preferred model is **restore as a new isolated target followed by reconciliation and controlled authority cutover using relocation-grade fencing semantics**. The currently active tenant is never overwritten piecemeal while it continues accepting writes.

This produces one authoritative business-state history at a time without pretending that all safety, accountability, security-authority or governance evidence should travel backwards with it.

### Recovery reconciliation interval

Let `R` be the selected recovery point and `F` the final write fence on the currently authoritative tenant. All relevant records/effects/decisions in `(R, F]` are inventoried before cutover.

The recovery manifest distinguishes:

**Rollback subject state** — domain/business state intentionally restored to `R`.

**Safety/accountability/security-authority/governance continuity state** — state that cannot be forgotten merely because business state is being rolled back, including:

- immutable audit records/intents;
- inbox/deduplication receipts and idempotency outcomes;
- external provider/payment/automation operation identities and acknowledgements;
- long-running process/execution outcomes;
- committed/pending outbox state needed to determine whether an effect was already published/accepted;
- security/compliance evidence;
- session/credential revocations and logout invalidation state;
- membership disablement/revocation, permission/scope removal and tenant suspension/access-denial state;
- authorization/session generations, revocation generations, tombstones or equivalent freshness state whose loss could reactivate stale authority;
- governed deletion/erasure decisions, anonymization/pseudonymization state and durable tombstones/evidence needed to prevent removed or de-identified protected data from becoming authoritative again;
- current legal-retention/legal-hold decisions and effective state, including applicable hold placement/release decisions that constrain deletion or disclosure behavior;
- governed cryptographic-erasure/key-destruction decisions/evidence where restoring an older usable key path would defeat the accepted erasure;
- artifact lifecycle metadata/object reconciliation evidence needed to prevent protected object bytes from becoming untracked, indefinitely retained, falsely available or silently resurrected;
- compensation and reconciliation state.

For each irreversible/external operation after `R`, the owning domain must determine whether it was completed, externally accepted, compensatable, still pending, or ambiguous. The restored target does not become authoritative for effectful processing until required deduplication identities/outcomes are present and ambiguous operations are reconciled or quarantined.

### Authorization revocation continuity

Point-in-time business recovery MUST NOT implicitly re-grant access by restoring an older positive authorization state over a later revoke/deny/suspend event.

A session revocation, credential revocation, membership disablement/revocation, permission/scope removal, tenant suspension or equivalent security denial that became effective in `(R, F]` is continuity state by default and SHALL be preserved or reconciled forward before the recovered target resumes protected traffic.

Where authorization/session generation or revocation-marker semantics are used, recovery SHALL preserve a trustworthy generation/freshness value that is at least as restrictive as the reconciled security state. A capability/session/token minted against an older generation MUST remain stale after recovery and MUST NOT become valid merely because the underlying database was restored to `R`.

Before protected traffic resumes, the recovered target SHALL reconcile revocation/deny state through `F` and then validate against the current authoritative security state at reintroduction time. If completeness or freshness of that authority cannot be established safely, protected admission fails closed.

If the business intent is specifically to reverse a post-`R` security revocation, that is a separate security-recovery operation. It requires current authorization, any applicable step-up/approval policy, explicit scope and immutable audit evidence; it is never an accidental side effect of ordinary PITR.

A point-in-time restore MUST NOT blindly copy all post-`R` domain mutations forward, because doing so can defeat the recovery objective. Conversely it MUST NOT blindly discard all post-`R` reliability, audit, authorization-revocation or governance history, because doing so can recreate duplicate side effects, erase accountability, resurrect access or re-expose data that was governed out of active use.

If immutable audit evidence for `(R, F]` resides in a protected external sink or retained source, that evidence remains authoritative and is linked/reintroduced as required before the old source is destroyed. Recovery-induced cleanup never serves as a mechanism to erase valid later audit history.

### Governed erasure, anonymization and retention continuity

Business/domain PITR MUST NOT implicitly reverse a governed deletion/erasure, anonymization or cryptographic-erasure decision that became effective after `R`.

Before a recovered tenant/cell/control-plane authority can expose protected data restored from `R`, it SHALL reconcile the current governance state through `F` and re-apply or preserve all effective erasure/anonymization decisions and the durable tombstones/evidence needed to prove that those decisions remain enforced. The recovery process may reconstruct metadata required to enforce the decision, but MUST NOT reconstitute intentionally erased personal content merely to make the restored image look complete.

Legal-retention/legal-hold state is also continuity state when it constrains whether data may be deleted, transformed, released or retained. Recovery SHALL reconcile the current authoritative hold/retention state, including applicable post-`R` hold placement or release decisions, before destructive lifecycle actions resume.

Where privacy erasure and legal retention obligations interact, the restored system follows the currently authoritative governance policy rather than the stale policy at `R`. If the current decision cannot be established safely, the platform takes the conservative split posture: affected protected data is not re-exposed while erasure/anonymization status is unresolved, and destructive deletion is blocked while legal-retention status is unresolved.

A deliberate reversal of an anonymization/erasure or retention decision, where legally and technically possible, is a distinct currently authorized and audited governance operation. It is never an incidental consequence of PITR.

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

Retention for idempotency/deduplication/audit/reliability/revocation/governance evidence must cover the recovery and replay windows in which losing that evidence could make an irreversible effect repeatable, accountability incomplete, stale authority valid again, erased data reappear or an active legal hold be forgotten.

## Deletion/anonymization

Data-rights workflows distinguish physical deletion, anonymization, pseudonymization, cryptographic erasure and legal retention. Auditability does not justify retaining unnecessary personal data forever.

A governed deletion/anonymization/erasure decision has recovery semantics: durable tombstone/decision metadata sufficient to prevent accidental resurrection is retained separately from the content that the decision removes or renders irrecoverable, subject to the applicable legal/compliance policy. Recovery of an older backup does not by itself reverse the later decision.

Legal-retention/hold metadata likewise survives or is reconstructed across PITR when needed to prevent an older snapshot from incorrectly deleting data that the current policy requires to retain. Any eventual hold release is also reconciled from current authoritative policy rather than inferred from the snapshot at `R`.

## Object/artifact storage

Large generated/exported binary content lives outside transactional PostgreSQL. Metadata includes:

```text
artifact_id
lifecycle_generation / upload_generation
stable object identity / storage reference
current object version/reference when applicable
tenant_id
artifact_type
content_type
size
checksum
created_at
expires_at/retention policy
classification
status
last reconciliation state/time when needed
```

Object namespaces use immutable tenant identity and stable `artifact_id`, not mutable slug. Access is mediated by application authorization or short-lived scoped download capability; storage paths are not authorization.

### Crash-consistent artifact creation

Artifact metadata and object bytes are separate persistence authorities, so the platform SHALL use an explicit staged lifecycle rather than pretending their creation is one atomic transaction.

Every upload attempt is bound to the artifact's current **lifecycle/upload generation** and to a stable immutable attempt/object-version identity. The object-storage protocol MUST prevent a stale worker from publishing bytes as the current artifact after that generation has been fenced. A version-specific immutable staging key plus transactional compare-and-set finalization is the default conceptual model; a provider-native conditional-write/lease/fencing mechanism is acceptable only if it provides equivalent single-current-generation semantics.

Representative lifecycle:

```text
transactional metadata authority
  create artifact_id + tenant/governance/retention metadata
  lifecycle_generation = N
  status = STAGING/PENDING_OBJECT
  persist stable generation-bound object attempt identity/reference
  persist durable outbox/job/process intent
COMMIT
        |
        v
object worker uploads bytes to non-public immutable staged identity for generation N
        |
        v
verify object identity/version + checksum + size
        |
        v
transactionally finalize with CAS
  require status still STAGING/PENDING_OBJECT
  require lifecycle_generation still N
  object reference/version/checksum/size
  status = READY/AVAILABLE
COMMIT
```

The binary upload MUST NOT be the first durable step for a protected artifact unless the selected storage protocol provides an equivalent discoverable staging manifest. In the normal contract, an artifact lifecycle record exists before object bytes are uploaded, so a crash after object upload cannot create tenant data with no durable artifact identity.

Only a terminal `READY/AVAILABLE` artifact whose expected object version/identity and integrity metadata have been verified **and whose generation is still current** may be released/downloaded as complete. `STAGING`, `DELETING`, `RECONCILIATION_REQUIRED`, failed or otherwise non-terminal records are not treated as completed artifacts.

A stale upload attempt MAY finish transferring bytes after its generation has been fenced, but it MUST NOT be able to finalize/publish those bytes as the current artifact. Such bytes remain generation-identifiable staging/orphan state subject to reconciliation and governed cleanup.

A crash after metadata creation but before upload leaves a discoverable staged record that may be safely retried or expired. A crash after upload but before metadata finalization leaves a discoverable staged record/object pair that reconciliation can verify and finalize idempotently only if its generation is still current; otherwise it is stale and cannot become ready.

### Artifact reconciliation and garbage collection

The platform SHALL run or provide an equivalent deterministic reconciliation path over non-terminal artifact records and the controlled staging/object namespace.

Reconciliation classifies at least:

- metadata exists, object absent -> retry upload or fail/expire according to process policy;
- metadata exists, object exists and matches stable identity/checksum **and current generation** -> idempotently finalize when policy permits;
- metadata/object belongs to a stale fenced generation -> never finalize as current; quarantine or governed-clean it;
- metadata exists, object exists but integrity/version mismatches -> quarantine/reconciliation, never mark ready;
- controlled staging/object bytes exist with no corresponding live metadata because of restore/operator/storage anomaly -> quarantine and governed cleanup using stable artifact/tenant/generation identity rather than indefinite retention;
- metadata says ready but object is absent/corrupt -> artifact is unavailable/reconciliation-required; a completed-looking metadata row MUST NOT cause release of nonexistent/wrong bytes.

Staging objects and orphan candidates have a bounded lifecycle/scan policy sufficient to prevent inaccessible protected data from remaining indefinitely outside governance. Garbage collection is **governed**, not blind TTL deletion: current legal hold/retention/erasure policy is consulted before destructive removal, and required audit/evidence is preserved according to policy.

### Crash-consistent artifact deletion/erasure

Deletion/erasure also spans authorities and uses an explicit **writer-fenced lifecycle**. Cancellation of workers is useful operationally but is not itself a correctness fence.

The metadata authority first makes the artifact non-releasable and advances or terminally fences its lifecycle/upload generation before object deletion begins. After that transition, every upload/finalize attempt created under an older generation is stale and MUST be unable to publish/finalize as current even if its object I/O later completes.

Representative lifecycle:

```text
transactional metadata authority
  record governed delete/erasure intent or tombstone
  mark artifact non-releasable / DELETING
  advance/fence lifecycle_generation from N to N+1 (or terminal erasure generation)
  prevent any generation <= N from finalizing/publishing
COMMIT
        |
        v
stop/cancel known upload workers when possible
        |
        v
idempotently delete/crypto-erase all object versions/attempt identities
from generations fenced by the delete intent, under current retention/hold policy
        |
        v
reconcile storage inventory and publisher state
        |
        v
record confirmed deletion/erasure outcome ONLY when
  no prior generation can still publish/finalize
  no relevant live object/version remains releasable
  required governance evidence is durable
retain only metadata/evidence allowed and required by governance
```

A mutable stable object key that an old worker can recreate after deletion is not sufficient unless the storage protocol provides an equivalent conditional generation fence that prevents stale publication. Prefer immutable/version-specific attempt keys with metadata-controlled publication because stale attempts then remain discoverable without becoming current.

A deletion/erasure outcome MUST NOT be marked confirmed merely because one delete request returned success. Confirmation proves that all upload attempts from fenced generations have lost publication authority and that the relevant object/version inventory has been reconciled. If in-flight/stale-writer state or object inventory is materially uncertain, the artifact remains `DELETING` or `RECONCILIATION_REQUIRED`; it does not become confirmed-erased optimistically.

A metadata row is not simply deleted first while object bytes remain undiscoverable. Conversely, successful object deletion followed by a crash before metadata finalization is safe to reconcile because the stable artifact identity, generation fence and delete intent remain durable. Legal hold can block destructive object cleanup; privacy erasure can block re-exposure even when older backups still contain bytes.

Artifact/object PITR and restore procedures reconcile metadata authority with object inventory/version/generation state before artifacts are made available. Restoring an older metadata snapshot cannot silently re-release an object governed out of use, restore an older unfenced upload generation, or permit a stale writer to republish bytes after erasure; restoring object bytes without current metadata/governance authority does not make them downloadable.

## Delayed export/report/import authorization

For a user-requested delayed/asynchronous **export or report**:

1. authorization is checked when the request/process is created;
2. authorization is checked again before the delayed job begins or performs the protected export action;
3. authorization is checked again before the completed artifact is released or a download capability is minted.

For a user-requested delayed/asynchronous **import**:

1. authorization is checked when the import request/process is created;
2. the worker re-establishes current tenant context and checks current membership/permission/scope immediately before the delayed import begins any protected mutation;
3. a resumed/multi-stage import rechecks current authorization before a later mutation stage whenever the prior authorization decision may no longer be fresh; persisted job metadata or the request-time decision is never treated as continuing human authority.

These execution-time rechecks are **mandatory**, not policy-optional, under `SEC-EXEC-003`. If membership/scope/permission or tenant access was revoked before delayed import execution, the import fails closed before mutating tenant data and records a safe audited outcome. Validation/parsing that is deliberately allowed before authorization MUST remain bounded/untrusted and MUST NOT mutate protected tenant state or reveal protected resource existence.

A downloadable capability is short-lived and scoped to one artifact/tenant. It is minted/released only after the artifact lifecycle is terminal-ready and fresh authorization succeeds. If a policy requires revocation after capability issuance, delivery uses an application-mediated or otherwise revocable mechanism instead of an irrevocable permanent link.

Scheduled/system-generated exports or imports use an explicitly authorized service principal/process policy rather than inheriting stale authority from a human who once configured the schedule.

## Restore rehearsal

Scheduled recovery tests prove:

- backup readability;
- recovery-path availability of required KMS/secret-manager authority and key versions;
- successful decryption of representative restored application ciphertext without exposing root/master plaintext to ordinary operators;
- restore procedure correctness;
- RLS/tenant isolation after restore;
- application/schema compatibility;
- whole-cell recovery remains quarantined until all affected tenant continuity classes required for protected/effectful admission are reconciled;
- whole-cell restore does not reactivate later-revoked membership/permission/tenant access, re-expose later-erased/anonymized protected data or repeat already-completed external effects;
- tenant recovery set completeness across bounded contexts;
- explicit inventory and reconciliation of `(R, F]` reliability/audit/external-effect/security-revocation/governance state;
- already-completed irreversible effects are not repeated after cutover;
- post-`R` immutable audit evidence remains available after source cleanup;
- a session/capability or membership grant valid at `R` but revoked in `(R, F]` remains rejected after restore and cutover;
- authorization/session generation or equivalent revocation freshness does not move backwards during recovery;
- governed erasure/anonymization decisions effective in `(R,F]` remain enforced after restore, with removed protected content not becoming authoritative again;
- current legal-retention/legal-hold state survives or is reconstructed so PITR neither destroys protected retained data nor relies on stale hold state;
- governed cryptographic-erasure intent is not defeated by restoring an older usable key path;
- artifact crash points before upload, after upload/before finalize, after finalize/before response and during delete/erasure are reconciled without falsely available artifacts, untracked protected bytes or indefinite orphan retention;
- artifact erasure races an already-started upload/finalization attempt: deletion fences the old generation before object cleanup, stale completion cannot publish/finalize, and confirmed erasure is withheld until prior-generation publisher/object state is reconciled;
- artifact/object inventory after PITR reconciles stable artifact identity, metadata status, object version/checksum/generation and current governance before release or destructive cleanup;
- write-fence/cutover safety for tenant-level replacement;
- retained-backup decryptability across key rotation/version changes;
- measured recovery duration and data-loss window.

Authorization tests for delayed work additionally revoke membership/import permission after a delayed import is queued but before execution and prove the worker performs zero protected tenant mutation.

A database/object restore that completes structurally but cannot decrypt required protected data, suppress duplicate irreversible effects, preserve required accountability evidence, preserve effective revocation/deny state, preserve current governed erasure/retention decisions or reconcile artifact metadata/object lifecycle safely is a failed rehearsal.

Results are operational evidence used to set/revise RPO/RTO.
