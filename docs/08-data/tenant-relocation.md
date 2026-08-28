# Tenant Relocation Between Cells

**Status:** accepted  
**Primary ADRs:** ADR-004, ADR-018, ADR-019  
**Threat focus:** TM-012

## Goal

Move a tenant between cells without changing logical tenant/resource identities, without split authoritative writes, without trusting stale routing from requests/jobs and without leaving long-lived realtime subscriptions attached to a retired source placement generation. When the relocation mechanism is used for point-in-time recovery, it also preserves reconciled safety/accountability/security-authority/governance continuity across the recovery interval.

## Preconditions

- source and target cells are healthy enough for migration;
- target schema/runtime contracts are compatible;
- target has capacity and satisfies isolation/residency policy;
- relocation operation has durable Control Plane state;
- tenant-specific data classes/artifacts/telemetry are inventoried in a migration manifest;
- where duplicate-sensitive inbox/dedup evidence uses keyed/authenticated (e.g. HMAC) comparison, the migration manifest additionally inventories the historical key/verifier-generation reference required to interpret that evidence at the target, not only the fingerprint bytes themselves;
- pending async/process state is inventoried;
- active realtime subscription retirement/resubscription behavior for the tenant is defined;
- rollback boundary is declared before execution;
- for recovery-driven relocation, recovery point `R`, current-source write fence `F` strategy and reconciliation classes are declared.

## State machine

```text
REQUESTED
   -> PREPARING
   -> COPYING
   -> CATCHING_UP
   -> QUIESCING
   -> CUTOVER
   -> VERIFYING
   -> COMPLETED

Any pre-cutover stage -> ABORTED/FAILED with source remaining authority when safe.
Post-cutover failure -> FORWARD_RECOVERY or controlled reverse relocation; never silent dual authority.
```

## PREPARING

- create target tenant admission in non-active state;
- validate target schema/capacity;
- establish migration manifest/checkpoints;
- establish async/outbox/job migration policy and watermarks;
- establish realtime placement-generation retirement/resubscription policy;
- ensure source remains authoritative;
- mark placement `migrating` with current `placement_version`.

For recovery-driven relocation, the manifest separately classifies rollback-subject business state and safety/accountability/security-authority/governance continuity state from the post-recovery-point interval. Governance continuity includes applicable governed deletion/erasure or anonymization decisions and tombstones, legal-retention/legal-hold state, and approved cryptographic-erasure/key-destruction decisions whose loss could re-expose data or enable a destructive lifecycle action under stale policy.

## COPYING

Copy tenant-scoped transactional rows by domain, required telemetry and artifact references/objects according to manifest. Source continues normal service.

Copy mechanisms may use snapshot/export/CDC/native tooling, but every row is selected by immutable tenant identity and target writes remain non-authoritative.

Published historical outbox entries do not need to be re-published simply because data is copied. Pending/unpublished effect state, inbox/deduplication state, idempotency records and long-running process state are handled explicitly by the migration manifest.

## CATCHING_UP

Apply deltas after the base snapshot until lag is below cutover threshold. Validate domain counts/checksums/invariants appropriate to each data class.

Track a durable synchronization watermark for transactional change propagation and, where applicable, telemetry transfer.

A normal relocation catches forward all required authoritative state. A recovery-driven relocation does **not** blindly replay all business mutations after recovery point `R`; it reconciles the `(R, F]` interval according to ADR-018 and the recovery manifest.

## QUIESCING / write fence

1. ingress/control policy stops admitting new tenant mutations to source;
2. source cell local tenant admission enters fenced/read-only migration state;
3. in-flight mutations drain;
4. tenant schedulers stop acquiring new work;
5. effectful workers either finish before the fence boundary or are safely cancelled/replayed under stable `operation_id` semantics;
6. source outbox dispatcher stops publishing new tenant events after the declared fence/watermark;
7. final transactional delta or recovery reconciliation inventory is established;
8. pending/unpublished outbox, inbox/deduplication, idempotency and owner-process state required for continuation is synchronized exactly according to manifest;
9. for recovery-driven relocation, required security-authority continuity through `F` is synchronized/reconciled, including later session/credential revocations where applicable, membership disablement/revocation, permission/scope removals, tenant suspension/access-denial state and authorization/revocation generations or equivalent freshness markers;
10. for recovery-driven relocation, required governance continuity through `F` is synchronized/reconciled, including applicable governed deletion/erasure or anonymization decisions and durable tombstones, current legal-retention/legal-hold state including relevant hold placement/release decisions, and approved cryptographic-erasure/key-destruction decisions/evidence whose loss could revive an older usable key path;
11. source realtime admission for the tenant's current placement generation enters draining/retiring state: no new protected tenant subscription may be admitted on a generation that will be retired by cutover;
12. final telemetry/artifact delta required for cutover is synchronized or explicitly marked for post-cutover historical completion;
13. stale source writers are rejected even if they hold cached old placement.

The local write fence is critical: Control Plane cache invalidation alone is not sufficient protection. The same principle applies to realtime: a placement-cache invalidation signal alone is not enough if the source gateway can continue treating an old-generation subscription as current.

## Async ownership at cutover

No effectful unit of work may be concurrently owned by source and target.

At cutover every pending unit is in one of these states:

- completed and durably recorded on source before final delta;
- explicitly drained/cancelled and re-created on target using the same logical operation identity;
- transferred as pending durable process/job state according to contract;
- quarantined for operator reconciliation.

Inbox/deduplication and idempotency state required to recognize pre-cutover message/operation IDs is available at target before target starts effectful processing. Where that state's comparison evidence is keyed/authenticated, "available" includes the target holding, or having narrowly-scoped read access to, the source cell's historical key/verifier generation for the in-flight dedup horizon — per `08-cryptographic-authority-and-secret-recovery.md`'s "historical verification" concept, a verifier made available this way does not become current cryptographic authority for unrelated work. Its absence at cutover is a `recovery_continuity_blocked` condition for the affected identities, not a license to trust the fingerprint bytes alone.

For recovery-driven relocation, this rule extends through `(R, F]`: completed irreversible effects after `R` retain the receipts/operation identities needed to prevent replay even if corresponding business state is intentionally restored to `R`. Ambiguous external outcomes are reconciled or quarantined before target effectful processing begins.

## CUTOVER

For a normal relocation, cutover proceeds only after the standard migration preconditions are complete.

For a **recovery-driven relocation**, the target SHALL remain non-active/non-authoritative until **all** applicable pre-cutover continuity gates have passed. Before activating target tenant admission or routing protected/effectful traffic, the platform SHALL validate:

- post-`R` deduplication/idempotency/process outcomes and external-operation reconciliation needed to prevent repeated irreversible effects;
- required immutable audit/accountability evidence;
- post-`R` session/credential revocations where applicable, membership disablement/revocation, permission/scope removal, tenant suspension/access-denial state and current authorization/revocation generation or equivalent freshness state;
- applicable post-`R` governed deletion/erasure and anonymization decisions plus durable tombstones/evidence needed to prevent restored protected data from becoming authoritative or visible again;
- current legal-retention/legal-hold state, including relevant post-`R` hold placement/release decisions, before any destructive lifecycle behavior can resume;
- applicable approved cryptographic-erasure/key-destruction decisions/evidence, proving recovery does not revive an older usable key path that defeats current governed erasure;
- current authoritative security **and governance** state at reintroduction time, so a stale restored grant, stale retention policy or older pre-erasure state cannot override a later authoritative decision;
- unresolved ambiguous operations are quarantined and cannot execute;
- protected data with unresolved erasure/anonymization status remains unavailable, and destructive deletion with unresolved legal-retention status remains blocked;
- placement/admission generation is ready for the target and source remains fenced.

If any required security-authority, governance, reliability/accountability or external-effect continuity evidence is incomplete, protected/effectful cutover fails closed. `VERIFYING` does not substitute for this pre-cutover gate.

After those gates pass:

- activate target tenant admission for the new placement generation;
- atomically update Control Plane placement to target `cell_id` and increment `placement_version`;
- retire the old source placement/admission generation for protected realtime subscriptions as part of the cutover authority change;
- invalidate/propagate placement change;
- route new units of work and new protected tenant subscriptions to target;
- target schedulers/workers/realtime subscriptions acquire tenant work/scope only after target admission is authoritative;
- source remains permanently write-fenced for that generation;
- source gateway removes the affected tenant subscriptions bound to the retired generation or terminates their connection; a multi-tenant connection may remain only if the relocated tenant's stale subscriptions are removed.

Jobs/messages created before cutover re-resolve logical placement. Work that is safe to continue is re-enqueued/redirected according to job policy; stale physical routing is rejected.

## Realtime subscriptions at cutover

A protected tenant realtime subscription is bound to the tenant's current trusted placement/admission generation when the subscription is authorized. That binding is revalidated during the long-lived subscription lifecycle; a source-cell subscription does not retain authority merely because its WebSocket transport remains open.

When relocation increments `placement_version` or retires the source admission generation, every affected old-generation source subscription becomes stale. The source gateway SHALL stop protected delivery for that tenant and remove the affected subscription or close the connection within the accepted bounded relocation-invalidation interval. A missed invalidation signal is caught by bounded placement/admission-generation revalidation; an old source socket MUST NOT remain apparently healthy and tenant-current indefinitely after the source generation is retired.

The default handoff is **retire and resubscribe**, not transparent socket transfer:

```text
source subscription bound to generation N
        -> generation N retired / placement moves
        -> source subscription removed or connection closed
        -> client re-resolves through logical BFF/realtime path
        -> fresh authorization + current placement generation N+1
        -> subscribe on target
        -> snapshot/resynchronize authoritative state
```

A safe best-effort relocation/resubscribe hint MAY accelerate reconnection, but correctness does not depend on the hint being delivered. Any future transparent transfer mechanism must re-establish current authorization, trusted target placement/admission generation and replay/resynchronization semantics; copying socket/subscription memory across cells is not authority.

## VERIFYING

Post-cutover verification is defense in depth. Validate:

- target authorization/tenant isolation still matches current authoritative security state;
- no reconciled revocation/deny state regressed after admission;
- governed deletion/erasure or anonymization decisions remain enforced and no governed-out protected data became authoritative/visible again;
- current legal-retention/legal-hold state remains enforced and no destructive lifecycle action ran under stale or unresolved retention state;
- approved cryptographic erasure remains effective and recovery did not restore an older usable key path that defeats it;
- transactional domain counts/invariants;
- outbox publication watermark and no duplicate unpublished transfer;
- inbox/idempotency continuity, including historical key/verifier-generation availability at target where dedup evidence is keyed/authenticated;
- long-running process/job ownership;
- current monitoring state and telemetry accessibility;
- artifact accessibility;
- provider integrations/secrets references;
- scheduled work ownership;
- no accepted writes/effectful worker ownership at source after fence;
- no protected tenant realtime subscription remains authorized on the retired source placement generation beyond the accepted invalidation/revalidation bound;
- a reconnect/resubscribe resolves the target generation and snapshot/resync exposes current target-backed authoritative state;
- for recovery, no completed `(R, F]` irreversible effect became retry-eligible and required later audit/governance evidence remains available;
- representative API/worker/realtime flows.

## Cleanup

Source tenant data is retained for a defined recovery window in a non-authoritative, write-fenced state, then deleted according to policy after completion evidence and recovery obligations are satisfied.

For recovery-driven relocation, source cleanup cannot destroy the only remaining post-`R` immutable audit/reliability/security-authority/governance evidence. Required continuity evidence must first exist in its governed durable destination. Source cleanup also SHALL NOT delete data whose current legal-retention/hold state requires continued preservation, nor preserve/re-expose content that current governed erasure requires to remain unavailable.

## Rollback rule

Before authoritative cutover, aborting to source is allowed when consistency is validated and the source fence is safely released. After target accepts authoritative writes, rollback is not a pointer flip; use controlled forward recovery/reverse relocation to avoid diverging histories.
