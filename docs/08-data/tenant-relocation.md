# Tenant Relocation Between Cells

**Status:** proposed baseline  
**Primary ADRs:** ADR-004, ADR-019  
**Threat focus:** TM-012

## Goal

Move a tenant between cells without changing logical tenant/resource identities, without split authoritative writes and without trusting stale routing from requests/jobs.

## Preconditions

- source and target cells are healthy enough for migration;
- target schema/runtime contracts are compatible;
- target has capacity and satisfies isolation/residency policy;
- relocation operation has durable Control Plane state;
- tenant-specific data classes/artifacts/telemetry are inventoried in a migration manifest;
- pending async/process state is inventoried;
- rollback boundary is declared before execution.

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
- ensure source remains authoritative;
- mark placement `migrating` with current `placement_version`.

## COPYING

Copy tenant-scoped transactional rows by domain, required telemetry and artifact references/objects according to manifest. Source continues normal service.

Copy mechanisms may use snapshot/export/CDC/native tooling, but every row is selected by immutable tenant identity and target writes remain non-authoritative.

Published historical outbox entries do not need to be re-published simply because data is copied. Pending/unpublished effect state, inbox/deduplication state, idempotency records and long-running process state are handled explicitly by the migration manifest.

## CATCHING_UP

Apply deltas after the base snapshot until lag is below cutover threshold. Validate domain counts/checksums/invariants appropriate to each data class.

Track a durable synchronization watermark for transactional change propagation and, where applicable, telemetry transfer.

## QUIESCING / write fence

1. ingress/control policy stops admitting new tenant mutations to source;
2. source cell local tenant admission enters fenced/read-only migration state;
3. in-flight mutations drain;
4. tenant schedulers stop acquiring new work;
5. effectful workers either finish before the fence boundary or are safely cancelled/replayed under stable `operation_id` semantics;
6. source outbox dispatcher stops publishing new tenant events after the declared fence/watermark;
7. final transactional delta is synchronized;
8. pending/unpublished outbox, inbox/deduplication, idempotency and owner-process state required for continuation is synchronized exactly according to manifest;
9. final telemetry/artifact delta required for cutover is synchronized or explicitly marked for post-cutover historical completion;
10. stale source writers are rejected even if they hold cached old placement.

The local write fence is critical: Control Plane cache invalidation alone is not sufficient protection.

## Async ownership at cutover

No effectful unit of work may be concurrently owned by source and target.

At cutover every pending unit is in one of these states:

- completed and durably recorded on source before final delta;
- explicitly drained/cancelled and re-created on target using the same logical operation identity;
- transferred as pending durable process/job state according to contract;
- quarantined for operator reconciliation.

Inbox/deduplication and idempotency state required to recognize pre-cutover message/operation IDs is available at target before target starts effectful processing.

## CUTOVER

- activate target tenant admission for new placement generation;
- atomically update Control Plane placement to target `cell_id` and increment `placement_version`;
- invalidate/propagate placement change;
- route new units of work to target;
- target schedulers/workers acquire tenant work only after target admission is authoritative;
- source remains permanently write-fenced for that generation.

Jobs/messages created before cutover re-resolve logical placement. Work that is safe to continue is re-enqueued/redirected according to job policy; stale physical routing is rejected.

## VERIFYING

Validate:

- target authorization/tenant isolation;
- transactional domain counts/invariants;
- outbox publication watermark and no duplicate unpublished transfer;
- inbox/idempotency continuity;
- long-running process/job ownership;
- current monitoring state and telemetry accessibility;
- artifact accessibility;
- provider integrations/secrets references;
- scheduled work ownership;
- no accepted writes/effectful worker ownership at source after fence;
- representative API/worker/realtime flows.

## Cleanup

Source tenant data is retained for a defined recovery window in a non-authoritative, write-fenced state, then deleted according to policy after completion evidence and recovery obligations are satisfied.

## Rollback rule

Before authoritative cutover, aborting to source is allowed when consistency is validated and the source fence is safely released. After target accepts authoritative writes, rollback is not a pointer flip; use controlled forward recovery/reverse relocation to avoid diverging histories.
