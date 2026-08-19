# Tenant Isolation and PostgreSQL RLS

**Status:** accepted  
**Primary ADR:** ADR-003

## Defense in depth

Pooled tenant isolation combines:

1. authenticated principal;
2. validated logical tenant membership/context;
3. server-side authorization;
4. trusted cell placement/admission;
5. tenant binding appropriate to the query trust class;
6. PostgreSQL row-level security/data policy;
7. tenant-safe composite relationships/indexes;
8. database-role/function hardening;
9. audit and automated isolation tests.

No single layer is considered sufficient.

## Mandatory tenant column

Every pooled protected tenant table carries non-null immutable `tenant_id`.

Tables that are deliberately global/public/system-wide are explicitly classified and do not accidentally omit tenant policy.

## Trusted application transaction context

For platform-owned application/worker SQL, database tenant context may be established inside the transaction after the server has resolved trusted logical tenant placement/authorization. It is never process-global state and never trusted from caller-provided physical routing.

Canonical application pattern:

```sql
BEGIN;
SELECT set_config('jlmirror.tenant_id', :trusted_server_tenant_id::text, true);
-- platform-owned use case queries
COMMIT;
```

The third argument `true` makes the value transaction-local. Connection pooling therefore cannot legitimately preserve one tenant's context for a later transaction.

A transaction that cannot establish a valid tenant context must not execute protected tenant queries.

**This GUC pattern is not an accepted tenant-binding mechanism for caller-authored arbitrary SQL.** A SQL principal can normally issue `SET`/`set_config` for custom settings, so a direct SQL surface must not use a caller-writable setting as the policy authority.

## Policy pattern for trusted application runtime

Representative application-runtime tenant table policy:

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

The exact setting name may be standardized in implementation, but semantics are normative: missing trusted application tenant context does not produce broad access.

## Interactive/direct SQL tenant binding

Caller-authored SQL is a different trust class from platform-owned repository SQL.

An interactive SQL path against pooled protected data SHALL use one of these accepted classes:

1. a **tenant-bound database principal/session identity** whose tenant mapping is stored/controlled outside the caller's writable SQL state and used by the policy through a narrowly reviewed mechanism;
2. a **mediated query surface/read model** that does not grant the caller direct access to pooled protected base tables and enforces tenant scope outside caller-authored SQL;
3. a **physically tenant-isolated query target** for a dedicated isolation class.

The caller MUST NOT be able to change the tenant authority by `SET`, `set_config`, `SET ROLE`, `SET SESSION AUTHORIZATION`, search-path manipulation or user-controlled helper functions. A dedicated console role has no role memberships/privileges that allow assumption of a broader tenant/bypass principal.

If none of these bindings can be proven for an implementation, arbitrary SQL access to pooled protected base tables is prohibited.

## Database roles

Normal runtime roles MUST NOT be PostgreSQL superuser, table owner with unrestricted bypass semantics, or hold `BYPASSRLS`.

Logical privilege classes include:

- migration/DDL owner;
- normal application read/write runtime;
- worker runtime where separate privilege is justified;
- reporting/read runtime where separate privilege is justified;
- privileged operator/data-administration role with explicitly narrower workflow;
- tenant-bound interactive-query principal/class where offered;
- observability/backup roles as required.

Exact role names are implementation details; least privilege and separation are not.

Normal runtime and interactive-query roles MUST NOT have permission to `SET ROLE`/assume migration-owner, backup, superuser or other RLS-bypass privileges.

## Privileged database functions

Database functions are part of the tenant trust boundary.

A `SECURITY DEFINER` function is prohibited by default for ordinary domain access. When one is genuinely required it MUST:

- have a narrowly scoped owner/privilege set;
- use a fixed safe `search_path` rather than caller-controlled lookup;
- validate tenant/operation authorization explicitly where tenant data is touched;
- avoid dynamic SQL from untrusted identifiers unless safely constrained;
- be executable only by intended roles;
- be covered by cross-tenant isolation tests and security review.

No helper function may become an undocumented RLS escape hatch.

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
- caches where protected values are stored;
- privileged database functions and runtime role escalation attempts;
- interactive SQL attempts to mutate tenant/session authority (`SET`, `set_config`, role/session authorization, search-path/helper abuse).

A single leaked row is a release blocker.
