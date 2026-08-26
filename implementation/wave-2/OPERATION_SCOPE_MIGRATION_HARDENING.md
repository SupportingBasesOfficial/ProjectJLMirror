# Wave 2 — Operation Scope Migration Hardening

**Status:** implementation conformance boundary  
**Authority base:** `main@ff932cec10e3b7dcc13b050bb09d4a7efd634598`  
**Applies to:** `sql/wave2/006_operation_scope_binding_hardening.sql`

## Purpose

The permanent inbox operation-scope trigger protects future `INSERT` and `UPDATE` statements, but publication of that trigger is not allowed to silently grandfather inconsistent rows that may already exist when the migration runs.

The migration therefore proves both historical and future conformance:

```text
PREEXISTING ROW != TRUSTED JUST BECAUSE THE NEW TRIGGER DID NOT CREATE IT
FOREIGN KEY HIT != TENANT/OWNER AUTHORITY MATCH
TRIGGER INSTALLED != PREEXISTING DATA CONFORMANT
```

## Migration-time authority fence

Before preflight, the migration acquires locks that block concurrent inbox binding/state DML and operation-scope mutation for the duration of the transaction:

```text
async_consumer_inbox             -> SHARE ROW EXCLUSIVE
async_cross_authority_operation  -> SHARE
```

The preflight then checks every operation-bound inbox row against the complete immutable tuple:

```text
operation_id exists
+ operation.tenant_id IS NOT DISTINCT FROM inbox.tenant_id
+ operation.owner_contract IS NOT DISTINCT FROM inbox.consumer_contract
```

Any orphan, tenant mismatch or owner mismatch raises and aborts the migration before the permanent trigger is created.

## Publication order

```text
lock relevant durable authorities
 -> inspect every preexisting operation-bound receipt
 -> fail closed on any mismatch
 -> create SECURITY INVOKER scope guard
 -> publish BEFORE INSERT OR UPDATE trigger
 -> commit
```

The migration never repairs, rewrites or guesses an inconsistent authority binding. Remediation requires separate owned reconciliation/migration authority.

## Recovery and upgrade rule

A restored database, validation environment or upgrade target cannot become conformant merely because migration 006 can be applied. Existing rows must first satisfy the same operation/tenant/owner invariant required of future writes.

Missing operation state, restored stale tenant/owner binding or unknown continuity is not converted into current authority by trigger installation.

## Required falsification

`tests/wave2/test_operation_scope_migration_preflight.py` proves statically that:

- both migration locks exist;
- preflight inspects operation-bound rows before trigger publication;
- orphan operation references are rejected;
- tenant mismatch is rejected;
- owner-contract mismatch is rejected;
- the preflight failure path occurs before the permanent trigger is created.

This is migration/conformance evidence only. It selects no database HA/pooler/runtime product and grants no runtime database role.
