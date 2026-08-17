# Tenant Isolation and PostgreSQL RLS

**Status:** proposed baseline  
**Primary ADR:** ADR-003

## Defense in depth

Pooled tenant isolation combines:

1. authenticated principal;
2. validated logical tenant membership/context;
3. server-side authorization;
4. trusted cell placement/admission;
5. transaction-local tenant database context;
6. PostgreSQL row-level security/data policy;
7. tenant-safe composite relationships/indexes;
8. audit and automated isolation tests.

No single layer is considered sufficient.

## Mandatory tenant column

Every pooled protected tenant table carries non-null immutable `tenant_id`.

Tables that are deliberately global/public/system-wide are explicitly classified and do not accidentally omit tenant policy.

## Transaction-local context

Database tenant context is established inside the transaction, never as process-global mutable state and never trusted from a caller-provided schema.

Canonical PostgreSQL pattern:

```sql
BEGIN;
SELECT set_config('jlmirror.tenant_id', :tenant_id::text, true);
-- use case queries
COMMIT;
```

The third argument `true` makes the value transaction-local. Connection pooling therefore cannot legitimately preserve one tenant's context for a later transaction.

## Policy pattern

Representative tenant table policy:

```sql
ALTER TABLE monitoring.devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE monitoring.devices FORCE ROW LEVEL SECURITY;

CREATE POLICY devices_tenant_policy
ON monitoring.devices
USING (
  tenant_id = NULLIF(
    current_setting('jlmirror.tenant_id', true),
    ''
  )::uuid
)
WITH CHECK (
  tenant_id = NULLIF(
    current_setting('jlmirror.tenant_id', true),
    ''
  )::uuid
);
```

The exact setting name may be standardized in implementation, but semantics are normative: missing tenant context does not produce broad access.

## Database roles

Normal runtime roles MUST NOT be PostgreSQL superuser, table owner with unrestricted bypass semantics, or hold `BYPASSRLS`.

Logical privilege classes include:

- migration/DDL owner;
- normal application read/write runtime;
- worker runtime where separate privilege is justified;
- reporting/read runtime where separate privilege is justified;
- privileged operator/data-administration role with explicitly narrower workflow;
- observability/backup roles as required.

Exact role names are implementation details; least privilege and separation are not.

## Cross-tenant privileged operations

A global/platform administrator does not use the normal tenant runtime role with `tenant_id=*`.

Cross-tenant operations use a distinct privileged application path with explicit target tenant(s), authorization, reason/purpose where required and audit. Direct database bypass is reserved for controlled operational/recovery procedures with separate credentials and audit, not normal product behavior.

## RLS and children

Tenant identity is repeated on child tables, and composite foreign keys prevent cross-tenant parent linkage. RLS is still applied to the child table even when parent tenancy is derivable.

## Indexing

High-frequency tenant queries generally place `tenant_id` in composite indexes with the actual query dimensions, for example:

```text
(tenant_id, status, created_at)
(tenant_id, resource_id)
(tenant_id, external_provider, external_id)
```

Index order follows measured query patterns, not a blanket rule.

## Isolation test suite

CI/integration tests MUST include known Tenant B identifiers executed under Tenant A context for:

- direct repository reads/writes;
- parent/child inserts;
- API use cases;
- reporting projections;
- realtime subscription source queries;
- export/data-admin paths;
- worker processing;
- caches where protected values are stored.

A single leaked row is a release blocker.
