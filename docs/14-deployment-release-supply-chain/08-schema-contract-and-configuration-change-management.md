# Phase 14 — Schema, Contract and Configuration Change Management

**Status:** proposed baseline

## Data migration inheritance

Phase 14 preserves the accepted Data sequence:

```text
EXPAND
 -> DEPLOY compatible readers/writers
 -> MIGRATE/BACKFILL
 -> SWITCH canonical path
 -> OBSERVE/VERIFY
 -> CONTRACT later
```

Large backfills are resumable/durable operations and do not hold one ordinary schema transaction for the full rewrite.

## Migration operation

`release.migration-operation@1` records target environment/cell/database scope, migration identity, expected current schema/config/runtime generations, owning principal, lock/fence identity, progress, terminal/reconciliation state and release relationship.

## Locking / single authority

Migration execution has one controlled authority per target scope with database-safe lock/lease/fence semantics. Multiple deploy replicas cannot race privileged DDL by convenience.

## Mixed-version matrix

Every release with relevant changes declares supported combinations among:

- old/new application runtime;
- schema version/state;
- API compatibility family;
- event/message contract versions;
- configuration generation/profile;
- worker specialization versions;
- artifact/runtime profile generations;
- applicable release-policy/verifier generation/profile.

Compatibility is semantic, not just schema shape.

## Cell compatibility metadata

Accepted Data authority requires Control Plane cell metadata to record current/target schema compatibility information sufficient for placement and rollout safety.

Phase 14 therefore treats cell compatibility metadata as an explicit release input/evidence surface. A cell-affecting release binds:

```text
cell_id
current admitted runtime/schema compatibility state
target runtime/schema compatibility state
release/artifact identity
target configuration generation/profile
migration step/state
compatibility metadata version/generation or equivalent
```

Rules:

- release tooling cannot infer compatibility only from deployment success;
- caller/tenant input cannot select target compatibility state;
- placement/cutover to a cell remains blocked when its admitted current/target metadata is incompatible with the required contract set;
- stale metadata cannot override a newer incompatible/deny state;
- rollback/forward recovery updates compatibility state through the owning authority rather than rewriting history informally.

## Validation reference cell

For cell/runtime/schema-affecting releases, the accepted Data rollout stage “staging/reference cell” is satisfied inside `environment.validation@1` as `validation.reference-cell@1`.

The same immutable artifact and the production-relevant schema/runtime/configuration semantic profile are validated there before production canary unless evidence-backed `NO_APPLICABLE_CASE` applies.

The validation reference-cell configuration may use environment-specific non-production values and secret references. Production may use a distinct exact configuration identity/generation only when release evidence accounts for every material semantic difference through compatibility/equivalence or target-specific validation.

The reference cell is non-production authority and cannot be reused as production placement or receive production secret material merely because its combination passed validation.

## API/event compatibility

A release cannot use deployment timing to weaken Phase 09/10 compatibility. Parser, idempotency, replay, callback, realtime, artifact, failure and recovery semantics remain part of compatibility even when wire schemas are unchanged.

## Contract step

Destructive `CONTRACT` occurs only after evidence proves supported old runtime/readers/writers are retired and retention/recovery/governance allow the removal. Rollback needing the removed structure is no longer eligible after contract unless an explicit forward migration/recovery path exists.

Before `CONTRACT`, the current cell compatibility metadata must no longer advertise any supported active runtime/schema combination that depends on the structure being removed.

## Backfill

Backfills are:

- resumable;
- idempotent/reconciliation-safe where repeated;
- bounded by tenant/cell/workload capacity;
- observable by progress/outcome;
- independently pausable;
- coordinated with the declared cell compatibility state when read/write semantics depend on migration progress;
- not allowed to infer missing data as safe absence after restore/ambiguity.

## Configuration changes

Semantic configuration follows the same compatibility rigor as code. A config-only change that alters trust, tenant isolation, egress, failure handling, SLI meaning, runtime authority, schema/API/event behavior, recovery or Product behavior is not operationally trivial.

Validation evidence records the exact configuration identity/profile used. Reuse of that evidence for a different target configuration requires explicit validation-to-target compatibility/equivalence evidence. A target-specific material difference triggers applicable revalidation and may change mixed-version/cell compatibility state.

`RLV-049` falsifies promotion of a materially different production configuration using unrelated validation evidence.

## Secret changes

Secret reference/credential rotation is separate from artifact/schema change unless the consuming protocol semantics require coordinated release. Rollback never resurrects retired credentials as current.

Secret values are not copied between validation and production to establish configuration equality; compatibility reasons about reference purpose/policy and consuming semantics without exposing material.

## Runtime admission

A cell/tenant is not admitted to a release combination that violates the declared matrix, target configuration evidence or current accepted cell compatibility metadata, even if individual components are independently healthy.