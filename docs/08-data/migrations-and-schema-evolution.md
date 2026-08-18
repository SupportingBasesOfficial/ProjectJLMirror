# Migrations and Schema Evolution

**Status:** proposed baseline  
**Primary ADRs:** ADR-002, ADR-006, ADR-016, ADR-019

## Migration tracks

JLMIRROR maintains distinct migration tracks for:

1. Control Plane transactional schema;
2. Cell transactional schema;
3. Telemetry store/schema when separately specialized;
4. analytics/read projections where applicable.

Cells share one canonical cell schema contract regardless of pooled or dedicated isolation class.

## Source of truth

Versioned migrations are the schema source of truth. Runtime code does not auto-create or mutate production schemas outside the controlled migration system.

## Cell version metadata

Control Plane cell metadata records current/target schema compatibility information sufficient for placement and rollout safety.

A tenant MUST NOT be placed/cut over to a cell whose schema/runtime version cannot serve the required contracts.

## Expand / migrate / contract

Breaking changes follow:

```text
EXPAND
  add backward-compatible structure
    |
DEPLOY compatible readers/writers
    |
MIGRATE/BACKFILL data asynchronously if large
    |
SWITCH canonical read/write path
    |
OBSERVE/VERIFY
    |
CONTRACT old structure in a later safe release
```

Large backfills do not hold schema migrations/transactions open for the entire data rewrite.

## Tenant-isolation migration gate

A new pooled tenant table is incomplete until the migration defines/tests:

- non-null `tenant_id` where tenant-scoped;
- RLS/data policy;
- runtime role privileges;
- tenant-safe unique/index constraints;
- tenant-safe parent/child foreign-key semantics where relevant;
- isolation tests.

## Rollout order

Cell changes are deployed progressively:

1. test environment;
2. staging/reference cell;
3. production canary cell(s);
4. bounded production wave;
5. remaining cells.

Rollout pauses automatically/manual when migration/application health violates gates.

## Mixed-version compatibility

Rolling deployments define supported old/new application and schema combinations. A migration that makes old active application instances unsafe is not rolled out before those instances are drained/upgraded.

## Migration locking

Migration execution uses one controlled owner per target database/cell with a database-safe lock/lease so multiple deploy replicas cannot race DDL.

## Destructive operations

Dropping data/columns/tables requires:

- accepted migration plan;
- proof no supported runtime reads/writes it;
- retention/recovery consideration;
- rollback/forward-recovery plan;
- observation period where risk warrants.

## Observability

Every migration/backfill exposes version, target, start/end, progress where measurable, error class, retry/resume state and correlation with deployment.
