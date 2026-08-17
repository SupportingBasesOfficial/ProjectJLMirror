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
- ensure source remains authoritative;
- mark placement `migrating` with current `placement_version`.

## COPYING

Copy tenant-scoped transactional rows by domain, required telemetry and artifact references/objects according to manifest. Source continues normal service.

Copy mechanisms may use snapshot/export/CDC/native tooling, but every row is selected by immutable tenant identity and target writes remain non-authoritative.

## CATCHING_UP

Apply deltas after the base snapshot until lag is below cutover threshold. Validate domain counts/checksums/invariants appropriate to each data class.

## QUIESCING / write fence

1. ingress/control policy stops admitting new tenant mutations to source;
2. source cell local tenant admission enters fenced/read-only migration state;
3. in-flight mutations drain;
4. workers/schedulers stop or fence side effects for the tenant;
5. final deltas/outbox/process state are synchronized;
6. stale source writers are rejected even if they hold cached old placement.

The local write fence is critical: Control Plane cache invalidation alone is not sufficient protection.

## CUTOVER

- activate target tenant admission for new placement generation;
- atomically update Control Plane placement to target `cell_id` and increment `placement_version`;
- invalidate/propagate placement change;
- route new units of work to target;
- source remains permanently write-fenced for that generation.

Jobs/messages created before cutover re-resolve logical placement. Work that is safe to continue is re-enqueued/redirected according to job policy; stale physical routing is rejected.

## VERIFYING

Validate:

- target authorization/tenant isolation;
- transactional domain counts/invariants;
- outbox/inbox/idempotency/process state;
- current monitoring state and telemetry accessibility;
- artifact accessibility;
- provider integrations/secrets references;
- scheduled work ownership;
- no accepted writes at source after fence;
- representative API/worker/realtime flows.

## Cleanup

Source tenant data is retained for a defined recovery window in a non-authoritative state, then deleted according to policy after completion evidence and recovery obligations are satisfied.

## Rollback rule

Before authoritative cutover, aborting to source is allowed when consistency is validated. After target accepts authoritative writes, rollback is not a pointer flip; use controlled forward recovery/reverse relocation to avoid diverging histories.
